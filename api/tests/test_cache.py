"""The cache: write rule, scope and index_id isolation, Redis commands, degrade-to-miss (AC-2..9)."""

from __future__ import annotations

import pathlib
import struct
from typing import Any

import pytest
import redis

from app.config import Settings
from app.schemas import AskResponse, Citation, RetrievedRef
from app.services.cache import (
    INDEX_PREFIX,
    CacheError,
    MemoryCache,
    SemanticCache,
    cacheable,
    get_cache,
)
from app.services.scope import scope

V = [1.0, 0.0, 0.0]
NEAR = [0.99, 0.14, 0.0]     # cosine about 0.99 with V
FAR = [0.0, 1.0, 0.0]


def resp(*, yes: bool = True, cite: bool = True, rid: str = "r1") -> AskResponse:
    return AskResponse(
        request_id=rid, answer="80%", answered_from_context=yes, confidence="high", provider="p",
        citations=[Citation(source="a.pdf", section="1.1", page=1)] if cite else [],
        retrieved=[RetrievedRef(chunk_id="c1", source="a.pdf", section="1.1", page=1, score=0.9)])


# -- the write rule (AC-3) -------------------------------------------------------------------

def test_cacheable_accepts_a_validated_answer() -> None:
    assert cacheable(resp(), "answered", follow_up=False)


@pytest.mark.parametrize("outcome", ["abstained", "fallback", "cached"])
def test_cacheable_rejects_other_outcomes(outcome: str) -> None:
    assert not cacheable(resp(), outcome, follow_up=False)


def test_cacheable_rejects_follow_up_and_not_from_context_and_no_citation() -> None:
    assert not cacheable(resp(), "answered", follow_up=True)
    assert not cacheable(resp(yes=False), "answered", follow_up=False)
    assert not cacheable(resp(cite=False), "answered", follow_up=False)


def test_cacheable_rejects_a_citation_that_was_not_retrieved() -> None:
    r = resp()
    r.citations = [Citation(source="other.pdf", section="9", page=1)]
    assert not cacheable(r, "answered", follow_up=False)


# -- scope and index_id isolation (AC-2, AC-4) ----------------------------------------------

def test_scope_tag_separates_entries() -> None:
    versions = ["2023-08", "2026-06"]
    t23 = scope("What is the withdrawal deadline in 2023?", versions).tag
    t26 = scope("What is the withdrawal deadline in 2026?", versions).tag
    cur = scope("What is the withdrawal deadline?", versions).tag
    assert len({t23, t26, cur}) == 3
    c = MemoryCache(0.9)
    c.maintain("i1", 3)
    c.store("i1", V, t26, "q", resp())
    assert c.lookup("i1", V, t26) is not None
    assert c.lookup("i1", V, t23) is None          # identical vector, other scope: no hit
    assert c.lookup("i1", V, cur) is None


def test_memory_threshold_and_index_id() -> None:
    c = MemoryCache(0.95)
    c.maintain("i1", 3)
    c.store("i1", V, "t", "q", resp())
    assert c.lookup("i1", NEAR, "t") is not None   # about 0.99
    assert c.lookup("i1", FAR, "t") is None
    assert c.lookup("i1", [1.0, 0.0], "t") is None  # wrong length
    c.maintain("i2", 3)                             # re-index: the old entries are gone
    assert c.lookup("i1", V, "t") is None and c.lookup("i2", V, "t") is None


# -- SemanticCache against a recording fake ---------------------------------------------------

class FakePipe:
    def __init__(self, r: FakeRedis) -> None:
        self.r = r
        self.ops: list[tuple] = []

    def hset(self, key: str, mapping: dict[str, Any]) -> None:
        self.ops.append(("hset", key, mapping))

    def expire(self, key: str, ttl: int) -> None:
        self.ops.append(("expire", key, ttl))

    def execute(self) -> None:
        if self.r.error:
            raise self.r.error
        self.r.writes += self.ops


class FakeRedis:
    def __init__(self) -> None:
        self.cmds: list[tuple] = []
        self.writes: list[tuple] = []
        self.indexes: list[str] = []
        self.error: Exception | None = None
        self.search_reply: Any = [0]
        self.search_error: Exception | None = None

    def execute_command(self, *a: Any) -> Any:
        self.cmds.append(a)
        if self.error:
            raise self.error
        if a[0] == "FT.CREATE":
            if a[1] in self.indexes:
                raise redis.ResponseError("Index already exists")
            self.indexes.append(a[1])
        elif a[0] == "FT._LIST":
            return [n.encode() for n in self.indexes]
        elif a[0] == "FT.DROPINDEX":
            if a[1] not in self.indexes:
                raise redis.ResponseError("Unknown Index name")
            self.indexes.remove(a[1])
        elif a[0] == "FT.SEARCH":
            if self.search_error:
                raise self.search_error
            return self.search_reply
        return None

    def ping(self) -> bool:
        if self.error:
            raise self.error
        return True

    def pipeline(self, transaction: bool = False) -> FakePipe:
        return FakePipe(self)


class Clock:
    t = 0.0

    def __call__(self) -> float:
        return self.t


def make(**kw: Any) -> tuple[SemanticCache, FakeRedis, Clock]:
    r, clock = FakeRedis(), Clock()
    return SemanticCache(r, 0.92, 100, clock=clock, **kw), r, clock


def hit_reply(dist: float, response: str | None = None) -> list[Any]:
    return [1, b"cache:i1:x", [b"response", (response or resp().model_dump_json()).encode(),
                               b"dist", str(dist).encode()]]


def test_maintain_creates_the_index_and_drops_the_others() -> None:
    c, r, _ = make()
    r.indexes = ["idx:cache:old1", "idx:cache:old2", "idx:other"]
    assert c.maintain("new", 768)
    assert r.indexes == ["idx:other", "idx:cache:new"]       # foreign indexes are left alone
    create = next(x for x in r.cmds if x[0] == "FT.CREATE")
    assert create[1] == "idx:cache:new" and "cache:new:" in create and "768" in create
    assert ("FT.DROPINDEX", "idx:cache:old1", "DD") in r.cmds
    n = len(r.cmds)
    assert c.maintain("new", 768) and len(r.cmds) == n        # no-op while unchanged


def test_maintain_is_idempotent_across_pods() -> None:
    a, r, _ = make()
    b = SemanticCache(r, 0.92, 100)
    assert a.maintain("i1", 3) and b.maintain("i1", 3)        # "already exists" is fine
    assert r.indexes == ["idx:cache:i1"]


def test_maintain_refuses_an_empty_index_id() -> None:
    c, r, _ = make()
    assert not c.maintain("", 768) and r.cmds == []


def test_lookup_command_and_threshold() -> None:
    c, r, _ = make()
    c.maintain("i1", 3)
    r.search_reply = hit_reply(0.05)                           # similarity 0.95
    got = c.lookup("i1", V, "abc123")
    assert got is not None and got.answer == "80%"
    search = next(x for x in r.cmds if x[0] == "FT.SEARCH")
    assert search[1] == "idx:cache:i1"
    assert search[2] == "(@scope:{abc123})=>[KNN 1 @embedding $vec AS dist]"
    assert "DIALECT" in search and search[search.index("vec") + 1] == struct.pack("<3f", *V)
    r.search_reply = hit_reply(0.09)                           # 0.91 < 0.92
    assert c.lookup("i1", V, "abc123") is None
    r.search_reply = hit_reply(0.08)                           # exactly 0.92 is a hit
    assert c.lookup("i1", V, "abc123") is not None


def test_lookup_skips_when_not_maintained_or_wrong_vector_length() -> None:
    c, r, _ = make()
    assert c.lookup("i1", V, "t") is None                      # never maintained
    c.maintain("i1", 3)
    assert c.lookup("i2", V, "t") is None                      # other index_id
    assert c.lookup("i1", [1.0], "t") is None
    assert not any(x[0] == "FT.SEARCH" for x in r.cmds)


def test_corrupt_entry_is_a_miss() -> None:
    c, r, _ = make()
    c.maintain("i1", 3)
    r.search_reply = hit_reply(0.0, "{not json")
    assert c.lookup("i1", V, "t") is None


def test_store_writes_a_hash_with_a_ttl() -> None:
    c, r, _ = make()
    c.maintain("i1", 3)
    c.store("i1", V, "tag1", "the question", resp())
    (hset, expire) = r.writes
    assert hset[1].startswith("cache:i1:") and expire == ("expire", hset[1], 100)
    m = hset[2]
    assert m["scope"] == "tag1" and m["question"] == "the question"
    assert m["embedding"] == struct.pack("<3f", *V) and AskResponse.model_validate_json(m["response"])


def test_store_is_skipped_for_an_unmaintained_index() -> None:
    c, r, _ = make()
    c.store("i1", V, "t", "q", resp())
    assert r.writes == []


# -- Redis down is a miss, never an exception (AC-5) -------------------------------------------

def test_redis_error_is_a_miss_and_never_raises(caplog) -> None:
    c, r, _ = make()
    assert c.maintain("i1", 3)
    r.search_error = redis.ConnectionError("refused")
    with caplog.at_level("WARNING"):
        assert c.lookup("i1", V, "t") is None
    assert any("cache unavailable" in x.message for x in caplog.records)
    r.error = redis.TimeoutError("slow")
    c.store("i1", V, "t", "q", resp())                         # does not raise


def test_backoff_skips_redis_then_retries() -> None:
    c, r, clock = make(backoff_seconds=5.0)
    r.error = redis.ConnectionError("refused")
    assert not c.maintain("i1", 3)
    n = len(r.cmds)
    clock.t = 4.0
    assert not c.maintain("i1", 3) and len(r.cmds) == n        # inside the window: no Redis call
    clock.t = 6.0
    r.error = None
    assert c.maintain("i1", 3) and len(r.cmds) > n             # window over, Redis back


def test_dropped_index_heals() -> None:
    c, r, _ = make()
    c.maintain("i1", 3)
    r.search_error = redis.ResponseError("idx:cache:i1: no such index")
    assert c.lookup("i1", V, "t") is None
    r.search_error, r.indexes = None, []                       # index really gone
    c._down_until = 0.0
    assert c.maintain("i1", 3) and r.indexes == ["idx:cache:i1"]


def test_check_ok_and_failures() -> None:
    c, r, _ = make()
    c.check("i1", 3)                                           # creates the index, then it is listed
    assert "idx:cache:i1" in r.indexes
    r.error = redis.ConnectionError("refused")
    with pytest.raises(CacheError):
        c.check("i1", 3)


def test_check_recreates_a_missing_index() -> None:
    c, r, _ = make()
    c.check("i1", 3)
    r.indexes = []
    c.check("i1", 3)
    assert r.indexes == ["idx:cache:i1"]


# -- configuration and the lane rule (AC-8, AC-9) ----------------------------------------------

def test_get_cache_reads_settings_and_does_not_connect() -> None:
    c = get_cache(Settings(redis_host="no-such-host.invalid", redis_port=1234,
                           cache_threshold=0.9, cache_ttl_seconds=7))
    assert (c._threshold, c._ttl) == (0.9, 7)
    kw = c._r.connection_pool.connection_kwargs
    assert kw["host"] == "no-such-host.invalid" and kw["port"] == 1234
    assert kw["socket_timeout"] == 1.0 and kw["socket_connect_timeout"] == 1.0


def test_indexer_has_no_redis() -> None:
    root = pathlib.Path(__file__).resolve().parents[2] / "indexer"
    hits = [str(p) for p in root.rglob("*.py")
            if "tests" not in p.parts and ".venv" not in p.parts
            and ("redis" in p.read_text().lower())]
    assert hits == []
    assert not any("redis" in x.lower() for x in (root / "requirements.txt").read_text().splitlines())


def test_index_prefix_is_the_documented_one() -> None:
    assert INDEX_PREFIX == "idx:cache:"
