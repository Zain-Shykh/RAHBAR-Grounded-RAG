"""Liveness and readiness (architecture 4.8). They answer different questions."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..services.index_state import IndexUnavailable
from . import metrics

router = APIRouter()

CHECK_TIMEOUT = 2.0   # seconds per check (4.8)
_REASON_NAME = {"dimension": "embed_dimension"}   # IndexState reason -> /readyz check name
_ORDER = ["chroma", "collection", "embed_pin", "redis", "embed_dimension"]


@router.get("/healthz")
def healthz(request: Request) -> dict[str, str]:
    """Is the process alive? Never touches Chroma, Redis or the LLM."""
    return {"status": "alive", "version": request.app.state.settings.app_version}


def _within(seconds: float, fn: Callable[[], Any]) -> tuple[bool, Any]:
    """Run fn in a daemon thread. (finished, result or exception). A hung call is abandoned."""
    box: list[Any] = []

    def run() -> None:
        try:
            box.append(fn())
        except Exception as exc:
            box.append(exc)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(seconds)
    return (not t.is_alive()), (box[0] if box else None)


@router.get("/readyz")
def readyz(request: Request) -> JSONResponse:
    state = request.app.state.index_state
    if state is None:   # RETRIEVER=stub: nothing to check
        return JSONResponse({"status": "ready", "checks": {"retriever": "stub"}})

    failed: str | None = None
    done, result = _within(CHECK_TIMEOUT, lambda: state.get(force=True))
    if not done:
        failed = "chroma"
    elif isinstance(result, IndexUnavailable):
        failed = _REASON_NAME.get(result.reason, result.reason)
    elif isinstance(result, Exception):
        failed = "chroma"
    else:
        metrics.set_index_info(result.embed_model, result.index_id, result.chunk_count)
        problem = state.problem()      # embed_pin or dimension, set by the snapshot and queries
        if problem:
            failed = _REASON_NAME.get(problem, problem)

    # Redis joins in phase 11 (D-67). Until then it is reported, not checked.
    checks = {name: "ok" for name in _ORDER}
    checks["redis"] = "skipped"
    if failed is None:
        return JSONResponse({"status": "ready", "checks": checks})
    # Checks after the failing one were not decided by it; mark only the failure.
    for name in _ORDER[_ORDER.index(failed) + 1:]:
        checks[name] = "not_checked"
    checks[failed] = "failed"
    return JSONResponse({"status": "not_ready", "failed": [failed], "checks": checks}, status_code=503)
