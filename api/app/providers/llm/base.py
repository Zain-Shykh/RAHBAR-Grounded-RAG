"""The LLM provider interface (section 3.5). Swapping providers is one file.

A provider has no policy: retry, fallback and validation belong to the service layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...schemas import Answer, Passage


@dataclass
class GenerationResult:
    answer: Answer
    tokens_in: int
    tokens_out: int


class InvalidModelOutput(Exception):
    """The model reply is not JSON, not the schema, or cites something not retrieved.

    `str(exc)` is the reason, which the retry hint quotes back to the model.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ProviderError(Exception):
    """Timeout, connection failure or HTTP error from the model backend."""


class LLMProvider(Protocol):
    name: str

    def generate(
        self, question: str, passages: list[Passage], *, hint: str | None = None
    ) -> GenerationResult:
        """Answer the question from the passages. `hint` is set on the single retry."""
        ...
