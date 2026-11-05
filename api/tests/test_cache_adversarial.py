"""Tester round 1: adversarial unit cases for the cache (fakes only, no network)."""

from __future__ import annotations

import threading
from typing import Any

import redis

from app.logjson import request_id_var
from app.services.cache import MemoryCache, SemanticCache
from tests.test_answer import Scripted, ans
from tests.test_cache import FakeRedis, hit_reply, make, resp
from tests.test_cache_answer import State, ask, ret


def test_empty_index_id_never_stores_or_hits_and_still_answers() -> None:
    cache, prov = MemoryCache(0.9), Scripted(ans(1), ans(1))
    r = ret(state=State(""))
    assert ask(r, prov, cache).outcome == "answered"
    assert ask(r, prov, cache).cache != "HIT" and len(prov.calls) == 2


def test_very_long_question_still_answers_and_hits() -> None:
    cache, prov, r = MemoryCache(0.9), Scripted(ans(1)), ret()
    q = "attendance " * 20_000
    assert ask(r, prov, cache, q).cache == "MISS"
    assert ask(r, prov, cache, q).cache == "HIT"


def test_hit_never_returns_the_stored_request_id() -> None:
    cache, r, prov = MemoryCache(0.9), ret(), Scripted(ans(1))
    token = request_id_var.set("stored-id")
    ask(r, prov, cache)
    request_id_var.set("new-id")
    hit = ask(r, prov, cache)
    request_id_var.reset(token)
    assert hit.response.request_id == "new-id"


def test_corrupt_entry_in_the_pipeline_falls_through_to_a_normal_answer() -> None:
    fake = FakeRedis()
    fake.search_reply = hit_reply(0.0, "{broken")
    cache = SemanticCache(fake, 0.92, 60)
    res = ask(ret(), Scripted(ans(1)), cache)
    assert res.outcome == "answered" and res.cache == "MISS"


def test_search_error_other_than_missing_index_is_a_miss_and_backs_off() -> None:
    c, fake, clock = make()
    assert c.maintain("i1", 3)
    fake.search_error = redis.ResponseError("Syntax error")
    assert c.lookup("i1", [1.0, 0.0, 0.0], "t") is None
    assert not c.maintain("i1", 3)              # inside the backoff window
    clock.t += 10
    assert c.maintain("i1", 3)                  # window over: recreated


def test_hit_at_exactly_the_threshold_and_just_below() -> None:
    c, fake, _ = make()
    c.maintain("i1", 3)
    fake.search_reply = hit_reply(1 - 0.92 + 1e-6)
    assert c.lookup("i1", [1.0, 0.0, 0.0], "t") is None
    fake.search_reply = hit_reply(1 - 0.93)
    assert c.lookup("i1", [1.0, 0.0, 0.0], "t") is not None


def test_malformed_search_replies_are_misses() -> None:
    c, fake, _ = make()
    c.maintain("i1", 3)
    for reply in ([1], [1, b"k"], None, [], [1, b"k", [b"dist", b"x", b"response", b"{}"]],
                  [1, b"k", [b"response", b"{}"]]):
        fake.search_reply = reply
        assert c.lookup("i1", [1.0, 0.0, 0.0], "t") is None


def test_threads_on_semantic_cache_fake_never_raise() -> None:
    c, fake, _ = make()
    errors: list[BaseException] = []

    def work(n: int) -> None:
        try:
            for i in range(50):
                c.maintain(f"i{i % 3}", 3)
                c.store(f"i{i % 3}", [1.0, 0.0, 0.0], f"t{n}", "q", resp())
                c.lookup(f"i{i % 3}", [1.0, 0.0, 0.0], f"t{n}")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    ts: list[Any] = [threading.Thread(target=work, args=(n,)) for n in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not errors
