"""One trace record per query (architecture-a3 7.1, AD-39, R3-D1-1).

Built by `answer_question` as each stage completes and emitted once: a JSON line on stdout (logger
`rahbar.trace`, readable with `kubectl logs`) and, when TRACE_DIR is set, a line in one file per pod
(`traces-<UTC date>-<pod>.jsonl`, a single writer per file). Writing never fails a request (I-22) and a record
never holds a secret (I-23): the prompt is stored; headers, environment variables and URLs are not.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any

import httpx

from ..config import Settings
from ..routes import metrics as m

TRACE_LOG = logging.getLogger("rahbar.trace")
log = logging.getLogger("rahbar.api")


_VERSIONS: dict[tuple[str, str], str] = {}


def embed_version(model: str, url: str) -> str:
    """`<model>@<digest12>` from Ollama /api/tags, `hashing-bow-768@1` for the CI embedder, else `<model>@unknown`.
    Cached per (model, url) except `@unknown`: a failed first lookup is retried on the next request (R9, R3-F3-4)."""
    if (model, url) in _VERSIONS:
        return _VERSIONS[(model, url)]
    v = f"{model}@unknown"
    if model.startswith("hashing-bow"):
        v = f"{model}@1"
    else:
        try:
            tags = httpx.get(f"{url.rstrip('/')}/api/tags", timeout=3.0).json()["models"]
            for t in tags:
                if t["name"].split(":")[0] == model.split(":")[0]:
                    v = f"{model}@{str(t['digest'])[:12]}"
        except Exception:
            pass
    if not v.endswith("@unknown"):
        _VERSIONS[(model, url)] = v
    return v


embed_version.cache_clear = _VERSIONS.clear  # type: ignore[attr-defined]


def prompt_hash(messages: list[dict[str, str]]) -> str:
    return hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class Trace:
    def __init__(self, trace_id: str, query: str, settings: Settings) -> None:
        self.s = settings
        self.t0 = time.perf_counter()
        self.r: dict[str, Any] = {
            "type": "trace", "trace_id": trace_id, "request_id": trace_id,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z", "query": query, "rewritten_query": None,
            "embedding": {"model": settings.embed_model, "version": None, "dimension": None},
            "collection": {"name": settings.collection, "index_id": None, "chunk_count": None},
            "scope": None, "retrieved": [], "reranked_order": [], "floor": None, "prompt": None, "prompt_sha256": None,
            "model": None, "response": None, "guardrails": [], "cache": "skipped",
            "latency_ms": {"scope": 0.0, "embed": 0.0, "cache": 0.0, "retrieve": 0.0, "guardrails": 0.0,
                           "generate": 0.0, "total": 0.0},
            "tokens": {"in": 0, "out": 0}, "fallback_reason": None, "abstain_reason": None}

    def index(self, snap: Any, dim: int | None = None) -> None:
        self.r["collection"].update(index_id=snap.index_id, chunk_count=snap.chunk_count, embed_model=snap.embed_model)
        self.r["embedding"].update(version=embed_version(self.s.embed_model, self.s.ollama_url),
                                   dimension=dim or snap.dimension)

    def guard(self, action: dict[str, Any]) -> None:
        self.r["guardrails"].append(action)

    def lat(self, stage: str, ms: float) -> None:
        self.r["latency_ms"][stage] = ms

    def finish(self, response: Any, outcome: str, cache: str) -> None:
        self.r["response"] = {"answer": response.answer, "citations": [c.model_dump() for c in response.citations],
                              "confidence": response.confidence,
                              "answered_from_context": response.answered_from_context, "outcome": outcome}
        self.r["cache"] = cache
        self.r["latency_ms"]["total"] = round((time.perf_counter() - self.t0) * 1000, 1)

    def emit(self) -> None:
        try:
            line = json.dumps(self.r, ensure_ascii=False, default=str)
            TRACE_LOG.info(line)
            d = self.s.trace_dir
            if d:
                os.makedirs(d, exist_ok=True)
                name = f"traces-{time.strftime('%Y%m%d', time.gmtime())}-{os.environ.get('HOSTNAME', 'local')}.jsonl"
                with open(os.path.join(d, name), "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception:   # a trace must never fail the request (I-22)
            m.TRACE_WRITE_ERRORS.inc()
            log.warning("trace write failed", exc_info=True)
