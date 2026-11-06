"""The semantic cache on Redis Stack (architecture 5.9, AD-03, AD-04, AD-05).

Only the API touches Redis. Every search index and every entry is named by the `index_id` it was
built under, so a re-index makes old entries unreachable and `maintain` drops them. A cache
failure is never a request failure: every Redis call degrades to a miss (I-16).
"""

from __future__ import annotations

import logging
import math
import struct
import threading
import time
import uuid
from collections.abc import Callable, Sequence
from typing import Any

import redis
from pydantic import ValidationError

from ..config import Settings
from ..schemas import AskResponse

log = logging.getLogger("rahbar.cache")

INDEX_PREFIX = "idx:cache:"
_ERRORS = (redis.RedisError, OSError, ValueError)


class CacheError(RuntimeError):
    """Redis or the cache index is not usable (for /readyz)."""


def cacheable(response: AskResponse, outcome: str, follow_up: bool) -> bool:
    """The write rule (5.9.2): only a validated, answered, from-context, non-follow-up response.

    This is the never-cache rule: abstentions, fallbacks, validation failures and follow-ups
    are never stored. Only outcome "answered" passes.
    The citation check is repeated so a bad entry can never be served many times.
    """
    if follow_up or outcome != "answered" or not response.answered_from_context:
        return False
    if not response.citations:
        return False
    got = {(r.source, r.section) for r in response.retrieved}
    return all((c.source, c.section) in got for c in response.citations)


def _revive(raw: bytes | str, where: str) -> AskResponse | None:
    try:
        return AskResponse.model_validate_json(raw)
    except ValidationError as exc:   # a corrupt entry is a miss, not a 500
        log.warning("cache entry unreadable", extra={"where": where, "error": str(exc)[:200]})
        return None


class SemanticCache:
    name = "redis"

    def __init__(self, client: Any, threshold: float, ttl_seconds: int, *,
                 clock: Callable[[], float] = time.monotonic, backoff_seconds: float = 5.0) -> None:
        self._r = client
        self._threshold = threshold
        self._ttl = ttl_seconds
        self._clock = clock
        self._backoff = backoff_seconds
        self._lock = threading.Lock()
        self._maintained: tuple[str, int] | None = None
        self._down_until = 0.0

    # -- failure handling ------------------------------------------------------------------

    def _fail(self, op: str, exc: Exception) -> None:
        self._maintained = None          # re-create the index when Redis comes back
        self._down_until = self._clock() + self._backoff
        log.warning("cache unavailable", extra={"operation": op, "error": repr(exc)[:200]})

    def _down(self) -> bool:
        return self._clock() < self._down_until

    # -- index lifecycle -------------------------------------------------------------------

    def _maintain(self, index_id: str, dimension: int) -> None:
        """Create idx:cache:{index_id}, then drop every other cache index with its entries (5.9.4)."""
        name = INDEX_PREFIX + index_id
        try:
            self._r.execute_command(
                "FT.CREATE", name, "ON", "HASH", "PREFIX", "1", f"cache:{index_id}:", "SCHEMA",
                "scope", "TAG", "embedding", "VECTOR", "HNSW", "6", "TYPE", "FLOAT32",
                "DIM", str(dimension), "DISTANCE_METRIC", "COSINE")
        except redis.ResponseError as exc:
            if "already exists" not in str(exc).lower():
                raise
        for old in self._r.execute_command("FT._LIST"):
            old = old.decode() if isinstance(old, bytes) else str(old)
            if old.startswith(INDEX_PREFIX) and old != name:
                try:
                    self._r.execute_command("FT.DROPINDEX", old, "DD")
                except redis.ResponseError as exc:   # another pod dropped it first
                    if "unknown" not in str(exc).lower():
                        raise

    def maintain(self, index_id: str, dimension: int) -> bool:
        """True when the cache is usable for this index. Cheap when nothing changed."""
        if not index_id or dimension <= 0:
            return False
        if self._maintained == (index_id, dimension):
            return True
        if self._down():
            return False
        with self._lock:
            if self._maintained == (index_id, dimension):
                return True
            try:
                self._maintain(index_id, dimension)
            except _ERRORS as exc:
                self._fail("maintain", exc)
                return False
            self._maintained = (index_id, dimension)
            return True

    def check(self, index_id: str, dimension: int) -> None:
        """/readyz: Redis answers PING and the current cache index exists."""
        try:
            self._r.ping()
            self._down_until = 0.0       # an explicit probe may close the backoff early
            self._maintained = None      # re-run the idempotent create, so a dropped index is healed
            if not self.maintain(index_id, dimension):
                raise CacheError("cache index could not be created")
            names = [n.decode() if isinstance(n, bytes) else str(n)
                     for n in self._r.execute_command("FT._LIST")]
        except CacheError:
            raise
        except _ERRORS as exc:
            self._fail("check", exc)
            raise CacheError(repr(exc)) from exc
        if INDEX_PREFIX + index_id not in names:
            self._maintained = None
            raise CacheError(f"{INDEX_PREFIX}{index_id} is missing")

    # -- lookup and store ------------------------------------------------------------------

    def lookup(self, index_id: str, vector: Sequence[float], tag: str) -> AskResponse | None:
        m = self._maintained
        if m is None or m[0] != index_id or len(vector) != m[1]:
            return None
        try:
            res = self._r.execute_command(
                "FT.SEARCH", INDEX_PREFIX + index_id,
                f"(@scope:{{{tag}}})=>[KNN 1 @embedding $vec AS dist]",
                "PARAMS", "2", "vec", struct.pack(f"<{len(vector)}f", *vector),
                "RETURN", "2", "response", "dist", "SORTBY", "dist", "DIALECT", "2")
        except redis.ResponseError as exc:
            if "no such index" in str(exc).lower() or "unknown" in str(exc).lower():
                self._maintained = None          # dropped behind our back: recreate on next request
            self._fail("lookup", exc)
            return None
        except _ERRORS as exc:
            self._fail("lookup", exc)
            return None
        if not res or res[0] < 1 or len(res) < 3:
            return None
        fields = dict(zip(res[2][::2], res[2][1::2], strict=False))
        try:
            similarity = 1.0 - float(fields[b"dist"])
            raw = fields[b"response"]
        except (KeyError, ValueError, TypeError):
            return None
        if similarity < self._threshold:
            return None
        return _revive(raw, "lookup")

    def store(self, index_id: str, vector: Sequence[float], tag: str, question: str,
              response: AskResponse) -> None:
        m = self._maintained
        if m is None or m[0] != index_id or len(vector) != m[1]:
            return
        key = f"cache:{index_id}:{uuid.uuid4().hex}"
        try:
            pipe = self._r.pipeline(transaction=False)
            pipe.hset(key, mapping={
                "question": question, "scope": tag,
                "embedding": struct.pack(f"<{len(vector)}f", *vector),
                "response": response.model_dump_json(), "created": int(time.time())})
            pipe.expire(key, self._ttl)
            pipe.execute()
        except _ERRORS as exc:
            self._fail("store", exc)


class MemoryCache:
    """Same interface in process memory, for unit tests and for reasoning about the rules."""

    name = "memory"

    def __init__(self, threshold: float = 0.96) -> None:
        self._threshold = threshold
        self._entries: dict[str, list[tuple[str, list[float], str]]] = {}
        self._dim: dict[str, int] = {}

    def maintain(self, index_id: str, dimension: int) -> bool:
        if not index_id:
            return False
        for old in [i for i in self._entries if i != index_id]:
            del self._entries[old]
            self._dim.pop(old, None)
        self._entries.setdefault(index_id, [])
        self._dim[index_id] = dimension
        return True

    def check(self, index_id: str, dimension: int) -> None:
        self.maintain(index_id, dimension)

    def lookup(self, index_id: str, vector: Sequence[float], tag: str) -> AskResponse | None:
        if self._dim.get(index_id) != len(vector):
            return None
        best, raw = -1.0, None
        for t, vec, stored in self._entries.get(index_id, []):
            if t != tag:
                continue
            sim = _cosine(vec, vector)
            if sim > best:
                best, raw = sim, stored
        if raw is None or best < self._threshold:
            return None
        return _revive(raw, "lookup")

    def store(self, index_id: str, vector: Sequence[float], tag: str, question: str,
              response: AskResponse) -> None:
        if self._dim.get(index_id) != len(vector):
            return
        self._entries[index_id].append((tag, list(vector), response.model_dump_json()))


Cache = SemanticCache | MemoryCache


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb) if na and nb else 0.0


def get_cache(settings: Settings) -> SemanticCache:
    """No connection is made here: redis-py connects on first use, so start-up never needs Redis."""
    client = redis.Redis(host=settings.redis_host, port=settings.redis_port,
                         socket_timeout=1.0, socket_connect_timeout=1.0)
    return SemanticCache(client, settings.cache_threshold, settings.cache_ttl_seconds)
