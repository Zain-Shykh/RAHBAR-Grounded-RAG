"""Rule-based provider for CI mode (AD-07, architecture 5.15). No model, no network.

It quotes the best-matching sentence(s) of one retrieved passage and cites only that
passage, so it cannot invent a citation. Deterministic: same input, same output.
"""

from __future__ import annotations

import re

from ...config import Settings
from ...schemas import Answer, Citation, Passage
from .base import GenerationResult

_STOP = frozenset(
    "the and for are was were what which who whom whose when where why how does did "
    "can could should would will shall may might must has have had its their there this "
    "that these those with from into about than then but not any all per out our your "
    "his her she they them you".split()
)
# Split after . ! ? (not after a digit) when whitespace follows, or at a newline.
# "1.1 A student" is not split: the dot there is followed by a digit, not whitespace.
_SPLIT = re.compile(r"(?<![0-9])(?<=[.!?])\s+|\n+")


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) >= 3 and w not in _STOP}


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SPLIT.split(text) if s.strip()]


class ExtractiveProvider:
    name = "extractive"

    def __init__(self, settings: Settings) -> None:
        self.floor = settings.relevance_floor

    def generate(
        self, question: str, passages: list[Passage], *, hint: str | None = None
    ) -> GenerationResult:
        q = _words(question)
        best_key: tuple[int, float, int] | None = None
        best: tuple[Passage, list[str], int] | None = None
        for rank, p in enumerate(passages):
            sents = _sentences(p.text)
            for i, s in enumerate(sents):
                overlap = len(q & _words(s))
                if overlap == 0:
                    continue
                key = (overlap, p.score, -rank)   # most overlap, then score, then earlier rank
                if best_key is None or key > best_key:
                    best_key, best = key, (p, sents, i)
        if best is None:
            ans = Answer(
                reasoning="extractive",
                answer="The retrieved passages do not contain an answer to this question.",
                citations=[],
                answered_from_context=False,
                confidence="low",
            )
            return GenerationResult(ans, len(question.split()), 0)

        p, sents, i = best
        chosen = [sents[i]]
        if i + 1 < len(sents) and q & _words(sents[i + 1]):
            chosen.append(sents[i + 1])
        text = " ".join(chosen)
        ans = Answer(
            reasoning="extractive",
            answer=text,
            citations=[Citation(source=p.source, section=p.section, page=p.page)],
            answered_from_context=True,
            confidence="high" if p.score >= self.floor + 0.15 else "medium",
        )
        tokens_in = len(question.split()) + sum(len(x.text.split()) for x in passages)
        return GenerationResult(ans, tokens_in, len(text.split()))
