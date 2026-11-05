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
        # OPEN: D-63. The HTTP client lands in phase 10; fail at startup, not on a request.
        raise NotImplementedError(
            f"LLM_PROVIDER={name} is built in phase 10; use stub or extractive until then"
        )
    if name == "hosted":
        from .hosted import HostedProvider

        return HostedProvider(settings)
    raise ValueError(
        f"unknown LLM_PROVIDER {name!r}; expected stub, extractive, ollama-host, ollama-incluster or hosted"
    )
