"""POST /api/ask. The Ingress sends /api/* here unchanged, so the prefix stays."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from ..schemas import AskRequest, AskResponse
from ..services.answer import answer_question

router = APIRouter(prefix="/api")


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, request: Request, response: Response) -> AskResponse:
    state = request.app.state
    # The request has only `question` (AD-16), so follow_up is always False.
    result = answer_question(body.question, state.retriever, state.provider, state.settings,
                             follow_up=False, cache=state.cache)
    response.headers["X-Outcome"] = result.outcome
    response.headers["X-Cache"] = result.cache
    return result.response
