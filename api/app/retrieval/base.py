"""The retriever interface. The rest of the API only ever sees this."""

from __future__ import annotations

from typing import Any, Protocol

from ..schemas import Passage


class Retriever(Protocol):
    name: str

    def retrieve(self, question: str, k: int, *, vector: list[float] | None = None,
                 where: dict[str, Any] | None = None) -> list[Passage]:
        """Return up to k passages, best first.

        `vector` is the already-embedded question (the retriever embeds it when None);
        `where` is the Chroma filter from services.scope. The stub ignores both.
        """
        ...
