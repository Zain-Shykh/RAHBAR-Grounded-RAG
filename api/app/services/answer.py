"""The query pipeline (architecture 5.5). One call per step, in this order:

scope, embed, cache lookup, retrieve, floor, prompt + generate, validate, one retry, fallback,
response, headers, log line, metrics, cache store (only for a validated, answered response).
A model failure never becomes a 500 (I-16); an unusable index is the one infrastructure error
and surfaces as `IndexUnavailable` (the route maps it to 503).
"""

from __future__ import annotations

import logging
import re
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
from .cache import Cache, cacheable
from .guardrails import scan_passages
from .prompt import build_messages
from .scope import scope as make_scope
from .trace import Trace, prompt_hash
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
    question: str, shown: list[Passage], provider: LLMProvider, attempts_out: list[int] | None = None
) -> tuple[Answer | None, str, int, int]:
    """Up to two attempts. Returns (answer or None, fallback reason, tokens in, tokens out)."""
    tin = tout = 0
    hint: str | None = None
    reason = "provider_error"
    for attempt in range(_ATTEMPTS):
        if attempts_out is not None:
            attempts_out[0] = attempt + 1
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


def _cached(hit: AskResponse, scope_key: str, ms_embed: float) -> AskResult:
    """A cache hit: the stored response under a fresh request_id; no retrieval, no model call."""
    response = hit.model_copy(update={"request_id": request_id_var.get()})
    log.info("answered", extra={
        "provider": response.provider, "scope": scope_key, "cache": "hit", "outcome": "cached",
        "chunk_ids": [r.chunk_id for r in response.retrieved],
        "answered_from_context": response.answered_from_context,
        "tokens_in": 0, "tokens_out": 0, "ms_embed": ms_embed, "ms_retrieve": 0.0, "ms_generate": 0.0})
    return AskResult(response, "cached", "HIT")


def answer_question(
    question: str, retriever: Retriever, provider: LLMProvider, settings: Settings,
    *, follow_up: bool = False, cache: Cache | None = None, bypass: bool = False,
) -> AskResult:
    tr = Trace(request_id_var.get(), question, settings)
    result = _answer(question, retriever, provider, settings, follow_up, cache, bypass, tr)
    tr.finish(result.response, result.outcome, "bypassed" if bypass else
              {"HIT": "hit", "MISS": "miss", "SKIP": "skipped"}[result.cache])
    tr.emit()
    return result


def _ranked(passages: list[Passage]) -> list[dict]:
    return [{"rank": i + 1, "chunk_id": p.chunk_id, "doc_id": p.source, "section": p.section, "page": p.page,
             "doc_version": p.doc_version, "superseded": p.superseded, "score": round(p.score, 4)}
            for i, p in enumerate(passages)]


def _answer(
    question: str, retriever: Retriever, provider: LLMProvider, settings: Settings,
    follow_up: bool, cache: Cache | None, bypass: bool, tr: Trace,
) -> AskResult:
    t_scope = time.perf_counter()
    state = getattr(retriever, "state", None)         # IndexState; the stub retriever has none
    embedder = getattr(retriever, "embedder", None)   # None for the stub, or an unknown EMBED_MODEL

    # 2. Scope. Needs the live doc_versions; IndexUnavailable here becomes the 503.
    versions: list[str] = []
    snap = None
    if state is not None:
        snap = state.get()
        state.require_pin(snap)                       # never embed with the wrong model
        versions = snap.doc_versions
        m.set_index_info(snap.embed_model, snap.index_id, snap.chunk_count)
    sc = make_scope(question, versions)
    tr.lat("scope", _ms(t_scope))
    tr.r["scope"] = {"where": sc.where, "key": sc.key, "tag": sc.tag}
    if snap is not None:
        tr.index(snap)

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
        tr.lat("embed", ms_embed)
        m.EMBED_SECONDS.observe(ms_embed / 1000)

    # 4. Cache lookup (5.9.2). Skipped for a follow-up, without a vector or without an index id.
    # A Redis failure is a miss (I-16). `usable` also gates the store at step 10.
    cache_header: CacheHeader = "SKIP"
    usable = False
    if cache is not None and snap is not None and vector is not None and not follow_up:
        cache_header = "MISS"
        t_cache = time.perf_counter()
        usable = cache.maintain(snap.index_id, snap.dimension)
        hit = cache.lookup(snap.index_id, vector, sc.tag) if usable else None
        tr.lat("cache", _ms(t_cache))
        m.record_lookup(hit is not None)
        if hit is not None:
            tr.r["retrieved"] = [{"rank": i + 1, "chunk_id": r.chunk_id, "doc_id": r.source, "section": r.section,
                                  "page": r.page, "score": round(r.score, 4)} for i, r in enumerate(hit.retrieved)]
            return _cached(hit, sc.key, ms_embed)

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
        tr.lat("retrieve", ms_retrieve)
        tr.r["retrieved"] = _ranked(passages)
        m.RETRIEVAL_SECONDS.observe(ms_retrieve / 1000)
        best = max((p.score for p in passages), default=None)
        if best is not None:
            m.TOP_SCORE.observe(max(0.0, min(1.0, best)))

        tr.r["floor"] = {"value": settings.relevance_floor, "best_score": None if best is None else round(best, 4),
                         "passed": bool(best is not None and best >= settings.relevance_floor)}
        if best is None or not (best >= settings.relevance_floor):  # also true for NaN (T12-D1)
            # 6. Floor: abstain with no model call (AD-12).
            answer, outcome, abstain_reason = abstention(reason="floor"), "abstained", "below_floor"
            tr.guard({"rail": "relevance_floor", "action": "abstain", "detail": {"best": tr.r["floor"]["best_score"]}})
        else:
            # 7-9. Augment, generate, validate, retry. Only passages at or above the floor are shown.
            shown = [p for p in passages if p.score >= settings.relevance_floor]
            t = time.perf_counter()
            shown, actions = scan_passages(shown) if settings.injection_rail else (shown, [])   # AD-40
            tr.lat("guardrails", _ms(t))
            for a in actions:
                tr.guard(a)
                m.INJECTION_FLAGS.labels(rail=a["rail"]).inc()
            runs = sum(len(re.findall(r"[<>]{2,}", x)) for x in [question, *(p.text for p in shown)])
            if runs:
                tr.guard({"rail": "delimiter_strip", "action": "stripped", "detail": {"runs": runs}})
            tr.r["reranked_order"] = [p.chunk_id for p in shown]
            if not shown:
                answer, outcome, abstain_reason = abstention(reason="guardrail"), "abstained", "guardrail"
            else:
                messages = build_messages(question, shown)
                tr.r["prompt"], tr.r["prompt_sha256"] = (messages if settings.trace_prompt else None), prompt_hash(messages)
                attempts = [0]
                t = time.perf_counter()
                got, reason, tin, tout = _generate(question, shown, provider, attempts)
                ms_generate = _ms(t)
                tr.lat("generate", ms_generate)
                tr.r["model"] = {"provider": provider.name, "name": settings.llm_model, "attempts": attempts[0],
                                 "params": {"temperature": settings.temperature, "num_ctx": settings.llm_num_ctx,
                                            "num_predict": settings.llm_max_tokens, "seed": settings.llm_seed,
                                            "format": "json-schema"}}
                tr.guard({"rail": "citation_check", "action": "pass" if got is not None else "rejected",
                          "detail": {"attempts": attempts[0]} if got is not None else {"reason": reason}})
                m.GENERATION_SECONDS.labels(provider=provider.name).observe(ms_generate / 1000)
                m.TOKENS.labels(direction="in").observe(tin)
                m.TOKENS.labels(direction="out").observe(tout)
                if got is None:
                    answer, outcome, fallback_reason = fallback(), "fallback", reason
                elif got.answered_from_context:
                    answer, outcome = got, "answered"
                else:
                    answer, outcome, abstain_reason = got, "abstained", "model"

    tr.r["tokens"] = {"in": tin, "out": tout}
    tr.r["abstain_reason"], tr.r["fallback_reason"] = abstain_reason, fallback_reason
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
            "scope": sc.key, "cache": {"SKIP": "skipped"}.get(cache_header, cache_header.lower()),
            "outcome": outcome,
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
    # 10. Store (5.9.2): only a validated, answered, from-context, non-follow-up response.
    if usable and cache is not None and snap is not None and vector is not None \
            and cacheable(response, outcome, follow_up):
        cache.store(snap.index_id, vector, sc.tag, question, response)
    return AskResult(response, outcome, cache_header)
