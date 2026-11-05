# ruff: noqa: F811, F401
"""Tester round 1: adversarial cases for SemanticCache on a real Redis Stack. Needs REDIS_URL."""

from __future__ import annotations

import os
import struct
import threading
import time

import pytest

from tests.test_cache_redis import DIM, cache, r, resp, vec  # noqa: F401  (r is a fixture)

pytestmark = pytest.mark.skipif(not os.environ.get("REDIS_URL"), reason="REDIS_URL not set")


def test_corrupt_stored_response_is_a_miss_not_an_error(r) -> None:
    c = cache(r)
    c.maintain("t-1", DIM)
    c.store("t-1", vec(1), "s", "q", resp())
    (key,) = r.keys("cache:t-1:*")
    r.hset(key, "response", b"{not json")
    assert c.lookup("t-1", vec(1), "s") is None


def test_stored_json_of_the_wrong_shape_is_a_miss(r) -> None:
    c = cache(r)
    c.maintain("t-1", DIM)
    c.store("t-1", vec(1), "s", "q", resp())
    (key,) = r.keys("cache:t-1:*")
    r.hset(key, "response", b'{"answer": 5}')
    assert c.lookup("t-1", vec(1), "s") is None


def test_entry_expires_after_its_ttl(r) -> None:
    c = cache(r, ttl=1)
    c.maintain("t-1", DIM)
    c.store("t-1", vec(1), "s", "q", resp())
    assert c.lookup("t-1", vec(1), "s") is not None
    time.sleep(2.2)
    assert c.lookup("t-1", vec(1), "s") is None


def test_entry_under_an_old_index_id_is_never_served(r) -> None:
    c = cache(r)
    c.maintain("t-old", DIM)
    c.maintain("t-new", DIM)
    # a straggler request holding the old snapshot writes under the old prefix after the swap
    r.hset("cache:t-old:straggler", mapping={
        "scope": "s", "embedding": struct.pack(f"<{DIM}f", *vec(1)),
        "response": resp("stale").model_dump_json()})
    assert c.lookup("t-new", vec(1), "s") is None
    assert c.lookup("t-old", vec(1), "s") is None


def test_zero_nan_and_inf_vectors_never_raise(r) -> None:
    c = cache(r)
    c.maintain("t-1", DIM)
    c.store("t-1", vec(1), "s", "q", resp())
    for bad in ([0.0] * DIM, [float("nan")] * DIM, [float("inf")] * DIM):
        c.lookup("t-1", bad, "s")
        c.store("t-1", bad, "s", "q", resp())


def test_tag_with_odd_characters_does_not_raise(r) -> None:
    c = cache(r)
    c.maintain("t-1", DIM)
    for tag in ("a-b", "x y", "a|b", "{}", "", "é"):
        assert c.lookup("t-1", vec(1), tag) is None


def test_very_long_question_is_stored_and_hit(r) -> None:
    c = cache(r)
    c.maintain("t-1", DIM)
    c.store("t-1", vec(1), "s", "x" * 200_000, resp("long"))
    got = c.lookup("t-1", vec(1), "s")
    assert got is not None and got.answer == "long"


def test_threads_calling_maintain_lookup_store_never_raise(r) -> None:
    c = cache(r)
    errors: list[BaseException] = []

    def work(n: int) -> None:
        try:
            for i in range(30):
                c.maintain("t-1", DIM)
                c.store("t-1", vec(1, i % 5), f"s{n}", "q", resp())
                c.lookup("t-1", vec(1, i % 5), f"s{n}")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    ts = [threading.Thread(target=work, args=(n,)) for n in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not errors
    assert c.lookup("t-1", vec(1, 1), "s0") is not None


def test_two_pods_with_different_snapshots_leave_one_cache_index(r) -> None:
    a, b = cache(r), cache(r)
    a.maintain("t-1", DIM)
    b.maintain("t-2", DIM)
    names = {n.decode() for n in r.execute_command("FT._LIST") if n.decode().startswith("idx:cache:t-")}
    assert names == {"idx:cache:t-2"}
