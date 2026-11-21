"""POST /api/ask. The Ingress sends /api/* here unchanged, so the prefix stays."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from ..schemas import AskRequest, AskResponse
from ..services.answer import answer_question
from ..services.scope import scope as make_scope

router = APIRouter(prefix="/api")


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, request: Request, response: Response) -> AskResponse:
    state = request.app.state
    # The request has only `question` (AD-16), so follow_up is always False.
    # X-Cache-Bypass: 1 skips the semantic cache for this request (evaluation runs, AD-38).
    bypass = request.headers.get("X-Cache-Bypass") == "1"
    result = answer_question(body.question, state.retriever, state.provider, state.settings,
                             follow_up=False, cache=None if bypass else state.cache, bypass=bypass)
    response.headers["X-Outcome"] = result.outcome
    response.headers["X-Cache"] = result.cache
    return result.response


class RetrieveRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    k: int = Field(default=5, ge=1, le=20)


@router.post("/retrieve")
def retrieve(body: RetrieveRequest, request: Request) -> dict:
    """Retrieval only, no model call: the component under test at the second level (paper Table 1).

    Same scope rules and the same retriever as /api/ask. Read-only (I-1). Used by eval/suite.
    """
    state = request.app.state
    retriever = state.retriever
    idx = getattr(retriever, "state", None)
    versions: list[str] = []
    snap = None
    if idx is not None:
        snap = idx.get()
        idx.require_pin(snap)
        versions = snap.doc_versions
    sc = make_scope(body.question, versions)
    started = time.perf_counter()
    passages = retriever.retrieve(body.question, k=body.k, where=sc.where)
    ms = round((time.perf_counter() - started) * 1000, 1)
    return {
        "scope": sc.key, "ms_retrieve": ms,
        "index_id": snap.index_id if snap else None, "embed_model": snap.embed_model if snap else None,
        "retrieved": [{"rank": i + 1, "chunk_id": p.chunk_id, "source": p.source, "section": p.section,
                       "page": p.page, "score": p.score, "doc_version": p.doc_version,
                       "superseded": p.superseded, "text": p.text} for i, p in enumerate(passages)],
    }
