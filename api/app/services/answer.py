"""The query pipeline (architecture 5.5). One call per step, in this order:

scope, embed, cache seam, retrieve, floor, prompt + generate, validate, one retry, fallback,
response, headers, log line, metrics. The cache is built in phase 11; its seam is marked below.
A model failure never becomes a 500 (I-16); an unusable index is the one infrastructure error
and surfaces as `IndexUnavailable` (the route maps it to 503).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Literal

from ..config import Settings
from ..embedding import EmbedError
from ..logjson import request_id_var
from ..providers.llm.base import InvalidModelOutput, LLMProvider, ProviderError
from ..retrieval.base import Retriever
from ..routes import metrics as m
from ..schemas import Answer, AskResponse, Passage, RetrievedRef
from .scope import scope as make_scope
from .validate import abstention, fallback, retry_hint, validate

log = logging.getLogger("rahbar.answer")

Outcome = Literal["answered", "abstained", "fallback", "cached"]
CacheHeader = Literal["HIT", "MISS", "SKIP"]
_ATTEMPTS = 2   # one call and one retry (5.7.3, 5.7.4)


@dataclass
class AskResult:
    response: AskResponse
    outcome: Outcome
    cache: CacheHeader


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)


def _generate(
    question: str, shown: list[Passage], provider: LLMProvider
) -> tuple[Answer | None, str, int, int]:
    """Up to two attempts. Returns (answer or None, fallback reason, tokens in, tokens out)."""
    tin = tout = 0
    hint: str | None = None
    reason = "provider_error"
    for attempt in range(_ATTEMPTS):
        try:
            res = provider.generate(question, shown, hint=hint)
            tin, tout = tin + res.tokens_in, tout + res.tokens_out
            return validate(res.answer, shown), "", tin, tout
        except InvalidModelOutput as exc:
            hint = retry_hint(exc)
            reason = "bad_citation" if exc.reason.startswith("bad_citation") else "invalid_output"
            log.warning("model output rejected", extra={
                "reason": exc.reason, "attempt": attempt + 1,
                "will retry": attempt + 1 < _ATTEMPTS})
        except ProviderError as exc:
            reason = "provider_error"
            log.warning("provider error", extra={"error": str(exc), "transient": exc.transient,
                                                 "attempt": attempt + 1})
            if not exc.transient:
                break
            hint = None
        except Exception:   # a provider bug must still not be a 500 (I-16)
            log.exception("provider failed unexpectedly")
            reason = "provider_error"
            break
    return None, reason, tin, tout


def answer_question(
    question: str, retriever: Retriever, provider: LLMProvider, settings: Settings,
    *, follow_up: bool = False,
) -> AskResult:
    state = getattr(retriever, "state", None)         # IndexState; the stub retriever has none
    embedder = getattr(retriever, "embedder", None)   # None for the stub, or an unknown EMBED_MODEL

    # 2. Scope. Needs the live doc_versions; IndexUnavailable here becomes the 503.
    versions: list[str] = []
    if state is not None:
        snap = state.get()
        state.require_pin(snap)                       # never embed with the wrong model
        versions = snap.doc_versions
        m.set_index_info(snap.embed_model, snap.index_id, snap.chunk_count)
    sc = make_scope(question, versions)

    # 3. Embed once; the vector is reused for retrieval (5.5.1 note).
    vector: list[float] | None = None
    ms_embed = ms_retrieve = ms_generate = 0.0
    embed_failed = False
    if embedder is not None:
        t = time.perf_counter()
        try:
            vector = embedder.embed_query(question)
        except EmbedError as exc:
            embed_failed = True
            log.warning("query embedding failed", extra={"error": str(exc)})
        ms_embed = _ms(t)
        m.EMBED_SECONDS.observe(ms_embed / 1000)

    # 4. Cache seam (phase 11): lookup(vector, sc.tag) goes here, skipped when follow_up is true.
    cache: CacheHeader = "SKIP"

    passages: list[Passage] = []
    answer: Answer
    outcome: Outcome
    abstain_reason: str | None = None
    fallback_reason: str | None = None
    tin = tout = 0

    if embed_failed:
        answer, outcome, fallback_reason = fallback(), "fallback", "provider_error"
    else:
        # 5. Retrieve. IndexUnavailable propagates (503).
        t = time.perf_counter()
        passages = retriever.retrieve(question, k=settings.top_k, vector=vector, where=sc.where)
        ms_retrieve = _ms(t)
        m.RETRIEVAL_SECONDS.observe(ms_retrieve / 1000)
        best = max((p.score for p in passages), default=None)
        if best is not None:
            m.TOP_SCORE.observe(max(0.0, min(1.0, best)))

        if best is None or best < settings.relevance_floor:
            # 6. Floor: abstain with no model call (AD-12).
            answer, outcome, abstain_reason = abstention(reason="floor"), "abstained", "below_floor"
        else:
            # 7-9. Augment, generate, validate, retry. Only passages at or above the floor are shown.
            shown = [p for p in passages if p.score >= settings.relevance_floor]
            t = time.perf_counter()
            got, reason, tin, tout = _generate(question, shown, provider)
            ms_generate = _ms(t)
            m.GENERATION_SECONDS.labels(provider=provider.name).observe(ms_generate / 1000)
            m.TOKENS.labels(direction="in").observe(tin)
            m.TOKENS.labels(direction="out").observe(tout)
            if got is None:
                answer, outcome, fallback_reason = fallback(), "fallback", reason
            elif got.answered_from_context:
                answer, outcome = got, "answered"
            else:
                answer, outcome, abstain_reason = got, "abstained", "model"

    if abstain_reason:
        m.ABSTENTIONS.labels(reason=abstain_reason).inc()
    if fallback_reason:
        m.FALLBACKS.labels(reason=fallback_reason).inc()

    log.info(
        "answered",
        extra={
            "retriever": retriever.name, "provider": provider.name, "top_k": settings.top_k,
            "chunk_ids": [p.chunk_id for p in passages],
            "scores": [round(p.score, 4) for p in passages],
            "scope": sc.key, "cache": "skipped", "outcome": outcome,
            "abstain_reason": abstain_reason, "fallback_reason": fallback_reason,
            "answered_from_context": answer.answered_from_context,
            "tokens_in": tin, "tokens_out": tout,
            "ms_embed": ms_embed, "ms_retrieve": ms_retrieve, "ms_generate": ms_generate,
        },
    )
    response = AskResponse(
        request_id=request_id_var.get(),
        answer=answer.answer,
        citations=answer.citations,
        answered_from_context=answer.answered_from_context,
        confidence=answer.confidence,
        retrieved=[RetrievedRef(chunk_id=p.chunk_id, source=p.source, section=p.section,
                                page=p.page, score=p.score) for p in passages],
        provider=provider.name,
    )
    return AskResult(response, outcome, cache)
