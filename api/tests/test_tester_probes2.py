"""Tester round 2: more hostile model output must only ever raise InvalidModelOutput."""

from __future__ import annotations

import json

import pytest

from app.providers.llm.base import InvalidModelOutput
from app.schemas import Passage
from app.services.validate import validate

PS = [Passage(chunk_id="c", text="t", source="d.pdf", section="1.1", page=1, score=0.8)]


@pytest.mark.parametrize("raw", [
    "[" * 5000 + "]" * 5000,
    '{"a":' * 5000 + "1" + "}" * 5000,
    "1" * 50000,
    json.dumps({"reasoning": "r", "answer": "a", "answered_from_context": True,
                "confidence": "high", "citations": [[[[[[1]]]]]]}),
    json.dumps({"reasoning": "r", "answer": "a", "answered_from_context": "yes",
                "confidence": "high", "citations": []}),
    '{"answer": "a", "answer": "b"}',
    "\x00",
    "﻿{}",
])
def test_probe2_hostile_json_only_raises_invalid_model_output(raw) -> None:
    with pytest.raises(InvalidModelOutput):
        validate(raw, PS)


def test_probe2_duplicate_keys_last_wins_still_checked() -> None:
    raw = ('{"reasoning":"r","answer":"x","answered_from_context":true,"confidence":"high",'
           '"citations":[{"source":"d.pdf","section":"1.1"}],'
           '"citations":[{"source":"ghost","section":"1.1"}]}')
    with pytest.raises(InvalidModelOutput, match="bad_citation"):
        validate(raw, PS)
