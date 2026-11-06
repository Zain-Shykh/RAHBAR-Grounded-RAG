"""hashing-bow-768 (phase 7 spec AC-5). The golden below is the parity check with the api copy (AD-09)."""

from __future__ import annotations

import math

from pipeline.embedding.hashing import DIM, embed_hashing, embed_one

GOLDEN_TEXT = "The attendance rule requires 75% attendance"
# (bucket, value) of every non-zero entry: tokens attendance x2, rule, requires, 75; "the" is a stop word.
GOLDEN = [(517, -0.412859), (627, 0.412859), (647, -0.69903), (692, -0.412859)]


def _nonzero(v: list[float]) -> list[tuple[int, float]]:
    return [(i, round(x, 6)) for i, x in enumerate(v) if x]


def test_golden_vector() -> None:
    assert _nonzero(embed_one(GOLDEN_TEXT)) == GOLDEN


def test_dimension_unit_length_deterministic() -> None:
    a, b = embed_hashing([GOLDEN_TEXT, GOLDEN_TEXT])
    assert len(a) == DIM == 768 and a == b
    assert math.isclose(sum(x * x for x in a), 1.0, rel_tol=1e-9)


def test_document_prefix_is_ignored() -> None:
    assert embed_one("search_document: " + GOLDEN_TEXT) == embed_one(GOLDEN_TEXT)


def test_stop_words_and_case_and_punctuation() -> None:
    assert embed_one("THE Attendance, of the rule!") == embed_one("attendance rule")


def test_shared_words_raise_cosine() -> None:
    q, near, far = embed_hashing(["late fee payment", "fee payment is late", "library opening hours"])
    cos = lambda a, b: sum(x * y for x, y in zip(a, b, strict=True))  # noqa: E731
    assert cos(q, near) > 0.9 > cos(q, far)


def test_empty_text_is_zero_vector() -> None:
    assert embed_one("") == [0.0] * DIM
    assert embed_one("the of and") == [0.0] * DIM


def test_one_vector_per_text_in_order() -> None:
    out = embed_hashing(["alpha", "beta", "alpha"])
    assert len(out) == 3 and out[0] == out[2] and out[0] != out[1]
