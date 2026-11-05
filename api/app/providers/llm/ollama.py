"""Ollama provider: ollama-host or ollama-incluster (architecture 5.7.3, 5.12).

One file, no policy: the service layer owns retry, validation and fallback. A semaphore of
LLM_MAX_CONCURRENCY keeps a pod from flooding a laptop Ollama (AD-21).
"""

from __future__ import annotations

import threading

import httpx

from ...config import Settings
from ...schemas import Answer, Passage
from ...services.prompt import build_messages
from ...services.validate import parse_answer
from .base import GenerationResult, InvalidModelOutput, ProviderError

_TRANSIENT = (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError)


class OllamaProvider:
    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self.name = settings.llm_provider        # the configured name, in every outcome (D-69)
        self._url = settings.ollama_url.rstrip("/")
        self._sem = threading.BoundedSemaphore(max(1, settings.llm_max_concurrency))
        self._client = httpx.Client(timeout=settings.llm_timeout_seconds, transport=transport)

    def generate(
        self, question: str, passages: list[Passage], *, hint: str | None = None
    ) -> GenerationResult:
        s = self.settings
        body = {
            "model": s.llm_model,
            "messages": build_messages(question, passages, hint=hint),
            "stream": False,
            "format": Answer.model_json_schema(),
            "options": {"temperature": s.temperature, "num_ctx": s.llm_num_ctx,
                        "num_predict": s.llm_max_tokens},
        }
        if not self._sem.acquire(timeout=s.llm_timeout_seconds):
            raise ProviderError("busy: no free model slot before the timeout")   # not transient (D-70)
        try:
            r = self._client.post(f"{self._url}/api/chat", json=body)
            r.raise_for_status()
            data = r.json()
            content = data["message"]["content"]
        except _TRANSIENT as exc:
            raise ProviderError(f"ollama {type(exc).__name__}", transient=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"ollama {type(exc).__name__}: {exc}") from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError(f"ollama reply has no message content: {exc!r}") from exc
        finally:
            self._sem.release()
        if not isinstance(content, str):
            raise InvalidModelOutput("not_json")
        return GenerationResult(parse_answer(content), int(data.get("prompt_eval_count") or 0),
                                int(data.get("eval_count") or 0))
