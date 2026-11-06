"""The extractive provider (phase 9; AC-4)."""

from __future__ import annotations

from app.config import Settings
from app.providers.llm.extractive import ExtractiveProvider
from app.schemas import Passage
from app.services.validate import validate

FLOOR = 0.5
prov = ExtractiveProvider(Settings(relevance_floor=FLOOR))


def P(n: int, text: str, score: float = 0.7) -> Passage:
    return Passage(chunk_id=f"c{n}", text=text, source=f"d{n}.pdf", section=f"{n}.1 S", page=n,
                   score=score)


ATT = P(1, "1.1 A student must attend at least 80 percent of the lectures. "
           "The Head may condone absence for medical reasons. Unrelated closing sentence.")
FEE = P(2, "2.1 The tuition fee is due before the semester starts.", score=0.9)


def test_extractive_quotes_best_sentence_and_cites_only_that_passage() -> None:
    r = prov.generate("What attendance percent must a student have?", [FEE, ATT])
    a = r.answer
    assert a.answered_from_context and a.reasoning == "extractive"
    assert "80 percent" in a.answer and "Unrelated" not in a.answer
    assert [(c.source, c.section) for c in a.citations] == [("d1.pdf", "1.1 S")]
    assert validate(a, [FEE, ATT]).citations[0].page == 1   # passes the real validator
    assert r.tokens_out > 0 and r.tokens_in > r.tokens_out


def test_extractive_abstains_without_passages_or_overlap() -> None:
    for passages in ([], [FEE]):
        a = prov.generate("Where is the hostel mess located?", passages).answer
        assert not a.answered_from_context and a.citations == []


def test_extractive_confidence_rule_and_determinism() -> None:
    q = "attendance percent lectures"
    assert prov.generate(q, [P(1, ATT.text, FLOOR + 0.15)]).answer.confidence == "high"
    assert prov.generate(q, [P(1, ATT.text, FLOOR + 0.14)]).answer.confidence == "medium"
    assert prov.generate(q, [ATT, FEE]) == prov.generate(q, [ATT, FEE])


def test_extractive_ties_prefer_higher_score_then_rank() -> None:
    a, b = P(1, "Fee deadline is Friday.", 0.6), P(2, "Fee deadline is Friday.", 0.6)
    assert prov.generate("fee deadline", [a, b]).answer.citations[0].source == "d1.pdf"
    b2 = P(2, "Fee deadline is Friday.", 0.7)
    assert prov.generate("fee deadline", [a, b2]).answer.citations[0].source == "d2.pdf"
