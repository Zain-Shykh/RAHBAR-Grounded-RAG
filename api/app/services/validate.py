"""Output validation, the citation check (5.7.3, 5.8) and the canned responses (5.7.4, 5.10).

The model's reply is untrusted. Nothing here evaluates it; it is parsed as JSON and
checked against the schema and against the passages retrieved for this request.
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from ..providers.llm.base import InvalidModelOutput
from ..schemas import Answer, Citation, Passage

ABSTAIN_TEXT = "The documents in the corpus do not cover this question."
FALLBACK_TEXT = (
    "I could not produce a verified answer from the documents right now. "
    "Please try again, or rephrase the question."
)


def citation_matches(c: Citation, passages: list[Passage]) -> Passage | None:
    """The passage this citation names (exact source and section), or None."""
    for p in passages:
        if p.source == c.source and p.section == c.section:
            return p
    return None


def parse_answer(raw: str) -> Answer:
    """Model text to `Answer`, or `InvalidModelOutput("not_json" | "schema")`."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError, RecursionError) as e:   # deep nesting: RecursionError
        raise InvalidModelOutput("not_json") from e
    try:
        return Answer.model_validate(data)
    except ValidationError as e:
        raise InvalidModelOutput("schema") from e


def validate(raw: str | Answer, passages: list[Passage]) -> Answer:
    """Return a checked `Answer`, or raise `InvalidModelOutput(reason)`."""
    ans = raw if isinstance(raw, Answer) else parse_answer(raw)

    checked: list[Citation] = []
    for c in ans.citations:
        p = citation_matches(c, passages)
        if p is None:
            raise InvalidModelOutput(f"bad_citation: {c.source} / {c.section}")
        fixed = Citation(source=p.source, section=p.section, page=p.page)
        if fixed not in checked:
            checked.append(fixed)

    if ans.answered_from_context and not checked:
        raise InvalidModelOutput("no_citation")
    if not ans.answer.strip():
        raise InvalidModelOutput("empty_answer")
    return ans.model_copy(update={"citations": checked if ans.answered_from_context else []})


def abstention(*, reason: str = "floor") -> Answer:
    """No model call. `high` confidence only when the floor produced it. Never cached."""
    return Answer(
        reasoning=f"abstain: {reason}",
        answer=ABSTAIN_TEXT,
        citations=[],
        answered_from_context=False,
        confidence="high" if reason == "floor" else "low",
    )


def fallback() -> Answer:
    """Canned reply when the model cannot be trusted. Never an extractive answer. Never cached."""
    return Answer(
        reasoning="fallback",
        answer=FALLBACK_TEXT,
        citations=[],
        answered_from_context=False,
        confidence="low",
    )


def retry_hint(exc: InvalidModelOutput) -> str:
    return (
        f"Your previous reply was invalid because: {exc.reason}. "
        "Reply with valid JSON and cite only the evidence blocks."
    )
