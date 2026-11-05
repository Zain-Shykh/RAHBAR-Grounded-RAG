"""scope(): version intent rules (phase 8 AC-2)."""

from __future__ import annotations

from app.services.scope import scope

VERSIONS = ["2023-08", "2023-24", "2026", "2026-06", "2026-27", "2019-20"]


def test_year_selects_matching_versions() -> None:
    s = scope("What was the withdrawal deadline in 2023?", VERSIONS)
    assert s.where == {"doc_version": {"$in": ["2023-08", "2023-24"]}}
    assert s.key == "2023-08+2023-24"


def test_year_range_token_is_a_prefix_match() -> None:
    s = scope("Rules for 2026-27 please", VERSIONS)
    assert s.where == {"doc_version": {"$in": ["2026-27"]}}


def test_year_matching_superseded_and_current_keeps_both() -> None:
    # 2026 is a prefix of three versions; whatever their flags, the year decides, not `superseded`.
    s = scope("What changed in 2026?", VERSIONS)
    assert s.where == {"doc_version": {"$in": ["2026", "2026-06", "2026-27"]}}


def test_older_phrase_means_all_versions() -> None:
    for q in ("What was the previous withdrawal rule?", "What did the older rules say", "It used to be different?"):
        s = scope(q, VERSIONS)
        assert s.where is None and s.key == "all", q


def test_default_is_current_only() -> None:
    s = scope("What is the deadline to withdraw from a course?", VERSIONS)
    assert s.where == {"superseded": False} and s.key == "current"


def test_year_matching_nothing_falls_through() -> None:
    assert scope("Rules in 2030?", VERSIONS).key == "current"
    assert scope("Rules in 2030 versus the earlier ones?", VERSIONS).key == "all"


def test_year_wins_over_older_phrase() -> None:
    assert scope("What was the old rule in 2023?", VERSIONS).key == "2023-08+2023-24"


def test_word_boundaries() -> None:
    assert scope("Is the threshold 120300 credits? gold standard", VERSIONS).key == "current"


def test_tag_is_stable_short_and_scope_specific() -> None:
    a, b = scope("in 2023", VERSIONS), scope("plain question", VERSIONS)
    assert len(a.tag) == 12 and a.tag == scope("again in 2023", VERSIONS).tag != b.tag
