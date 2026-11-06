"""SemanticCache against a real Redis Stack. Skipped unless REDIS_URL is set (CI has none).

  make dev-services   # then:
  REDIS_URL=redis://localhost:6379 .venv/bin/pytest api/tests/test_cache_redis.py
"""

from __future__ import annotations

import math
import os

import pytest
import redis

from app.schemas import AskResponse, Citation, RetrievedRef
from app.services.cache import CacheError, SemanticCache

URL = os.environ.get("REDIS_URL")
pytestmark = pytest.mark.skipif(not URL, reason="REDIS_URL not set (integration test)")

DIM = 8


def vec(*head: float) -> list[float]:
    v = list(head) + [0.0] * (DIM - len(head))
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def resp(answer: str = "80%") -> AskResponse:
    return AskResponse(
        request_id="r", answer=answer, answered_from_context=True, confidence="high", provider="p",
        citations=[Citation(source="a.pdf", section="1.1", page=1)],
        retrieved=[RetrievedRef(chunk_id="c1", source="a.pdf", section="1.1", page=1, score=0.9)])


@pytest.fixture()
def r():
    client = redis.Redis.from_url(URL, socket_timeout=2)   # type: ignore[arg-type]
    for name in client.execute_command("FT._LIST"):
        if name.decode().startswith("idx:cache:t-"):
            client.execute_command("FT.DROPINDEX", name, "DD")
    yield client
    for name in client.execute_command("FT._LIST"):
        if name.decode().startswith("idx:cache:t-"):
            client.execute_command("FT.DROPINDEX", name, "DD")


def cache(r, threshold: float = 0.9, ttl: int = 60) -> SemanticCache:
    return SemanticCache(r, threshold, ttl)


def test_store_then_lookup_hits_and_returns_the_response(r) -> None:
    c = cache(r)
    assert c.maintain("t-1", DIM)
    c.store("t-1", vec(1, 0.1), "scopeA", "q", resp("first"))
    got = c.lookup("t-1", vec(1, 0.1), "scopeA")
    assert got is not None and got.answer == "first"
    assert c.lookup("t-1", vec(1, 0.12), "scopeA") is not None      # a close paraphrase
    assert c.lookup("t-1", vec(0, 1), "scopeA") is None             # an unrelated question


def test_scope_tag_isolates(r) -> None:
    c = cache(r)
    c.maintain("t-1", DIM)
    c.store("t-1", vec(1), "tag2026", "q", resp())
    assert c.lookup("t-1", vec(1), "tag2026") is not None
    assert c.lookup("t-1", vec(1), "tag2023") is None               # similarity 1.0, other scope


def test_entry_has_a_ttl(r) -> None:
    c = cache(r, ttl=60)
    c.maintain("t-1", DIM)
    c.store("t-1", vec(1), "s", "q", resp())
    (key,) = r.keys("cache:t-1:*")
    assert 0 < r.ttl(key) <= 60


def test_new_index_id_drops_the_old_index_and_its_entries(r) -> None:
    c = cache(r)
    c.maintain("t-old", DIM)
    c.store("t-old", vec(1), "s", "q", resp())
    assert r.keys("cache:t-old:*")
    other = cache(r)                                                 # a second pod, same Redis
    assert other.maintain("t-new", DIM)
    names = {n.decode() for n in r.execute_command("FT._LIST")}
    assert "idx:cache:t-new" in names and "idx:cache:t-old" not in names
    assert not r.keys("cache:t-old:*")                               # DD deleted the entries
    assert other.lookup("t-new", vec(1), "s") is None
    assert c.lookup("t-old", vec(1), "s") is None                    # the old pod misses, no error


def test_concurrent_maintain_is_safe(r) -> None:
    a, b = cache(r), cache(r)
    assert a.maintain("t-1", DIM) and b.maintain("t-1", DIM)
    assert a.maintain("t-2", DIM) and b.maintain("t-2", DIM)
    assert {n.decode() for n in r.execute_command("FT._LIST") if n.decode().startswith("idx:cache:t-")} \
        == {"idx:cache:t-2"}


def test_check_ok_and_heals_a_dropped_index(r) -> None:
    c = cache(r)
    c.check("t-1", DIM)
    r.execute_command("FT.DROPINDEX", "idx:cache:t-1")
    c.check("t-1", DIM)
    assert b"idx:cache:t-1" in r.execute_command("FT._LIST")


def test_check_fails_when_redis_is_unreachable() -> None:
    dead = redis.Redis(host="127.0.0.1", port=1, socket_timeout=0.2, socket_connect_timeout=0.2)
    with pytest.raises(CacheError):
        SemanticCache(dead, 0.9, 60).check("t-1", DIM)


def test_lookup_on_a_dead_redis_is_a_miss_not_an_error() -> None:
    dead = redis.Redis(host="127.0.0.1", port=1, socket_timeout=0.2, socket_connect_timeout=0.2)
    c = SemanticCache(dead, 0.9, 60)
    assert not c.maintain("t-1", DIM)
    assert c.lookup("t-1", vec(1), "s") is None
    c.store("t-1", vec(1), "s", "q", resp())


def test_dropped_index_is_a_miss_then_recreated(r) -> None:
    c = cache(r)
    c.maintain("t-1", DIM)
    r.execute_command("FT.DROPINDEX", "idx:cache:t-1", "DD")
    assert c.lookup("t-1", vec(1), "s") is None                      # error became a miss
    c._down_until = 0.0
    assert c.maintain("t-1", DIM)
    c.store("t-1", vec(1), "s", "q", resp())
    assert c.lookup("t-1", vec(1), "s") is not None


def test_wrong_dimension_vector_is_never_written_or_searched(r) -> None:
    c = cache(r)
    c.maintain("t-1", DIM)
    c.store("t-1", [1.0, 0.0], "s", "q", resp())
    assert not r.keys("cache:t-1:*")
    assert c.lookup("t-1", [1.0, 0.0], "s") is None
