from __future__ import annotations

from ...config import Settings
from .base import LLMProvider


def get_provider(settings: Settings) -> LLMProvider:
    name = settings.llm_provider
    if name == "stub":
        from .stub import StubProvider

        return StubProvider()
    if name == "extractive":
        from .extractive import ExtractiveProvider

        return ExtractiveProvider(settings)
    if name in ("ollama-host", "ollama-incluster"):
        from .ollama import OllamaProvider

        return OllamaProvider(settings)
    if name == "hosted":
        # Not built (ADR 0004, D-87): it would send question text and corpus passages off-site.
        raise ValueError(
            "LLM_PROVIDER 'hosted' is not implemented in this build; "
            "use ollama-host, ollama-incluster, extractive or stub (see docs/adr/0004)"
        )
    raise ValueError(
        f"unknown LLM_PROVIDER {name!r}; expected stub, extractive, ollama-host or ollama-incluster"
    )
