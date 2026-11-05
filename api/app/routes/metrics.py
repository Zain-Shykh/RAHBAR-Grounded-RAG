"""Prometheus metrics at /metrics (architecture 4.14). The names are fixed (AD-24).

`rahbar_request_seconds` is the kit's name for the request latency histogram; 4.14 lists it as
`rahbar_request_duration_seconds`. Both are exposed with the same observations (D-66).
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

router = APIRouter()

_REQ_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120)
_FAST = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10)

REQUESTS = Counter("rahbar_requests_total", "HTTP requests", ["path", "status"])
LATENCY = Histogram("rahbar_request_seconds", "HTTP request latency (kit name)", ["path"],
                    buckets=_REQ_BUCKETS)
DURATION = Histogram("rahbar_request_duration_seconds", "HTTP request latency", ["path"],
                     buckets=_REQ_BUCKETS)
EMBED_SECONDS = Histogram("rahbar_embed_seconds", "Question embedding time", buckets=_FAST)
RETRIEVAL_SECONDS = Histogram("rahbar_retrieval_seconds", "Vector search time", buckets=_FAST)
GENERATION_SECONDS = Histogram("rahbar_generation_seconds", "Model generation time, all attempts",
                               ["provider"], buckets=_REQ_BUCKETS)
CACHE_LOOKUPS = Counter("rahbar_cache_lookups_total", "Semantic cache lookups", ["result"])
CACHE_HIT_RATIO = Gauge("rahbar_cache_hit_ratio", "Cache hits over lookups, per process lifetime")
ABSTENTIONS = Counter("rahbar_abstentions_total", "Abstentions", ["reason"])
FALLBACKS = Counter("rahbar_fallbacks_total", "Canned fallbacks", ["reason"])
TOKENS = Histogram("rahbar_tokens", "Model tokens per request", ["direction"],
                   buckets=(16, 64, 128, 256, 512, 1024, 2048, 4096, 8192))
TOP_SCORE = Histogram("rahbar_top_score", "Best retrieved similarity per request",
                      buckets=(0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0))
INDEX_INFO = Gauge("rahbar_index_info", "The index this pod believes is live (=1)",
                   ["embed_model", "index_id", "chunks"])

_live_index: tuple[str, str, str] | None = None
_lookups = [0, 0]   # hits, lookups: this process only


def record_lookup(hit: bool) -> None:
    """One semantic cache lookup: the counter and the per-process hit ratio gauge (4.14)."""
    CACHE_LOOKUPS.labels(result="hit" if hit else "miss").inc()
    _lookups[0] += hit
    _lookups[1] += 1
    CACHE_HIT_RATIO.set(_lookups[0] / _lookups[1])


def set_index_info(embed_model: str, index_id: str, chunks: int) -> None:
    """Keep exactly one label set at 1: the index the pod currently serves."""
    global _live_index
    labels = (embed_model, index_id, str(chunks))
    if labels == _live_index:
        return
    if _live_index is not None:
        INDEX_INFO.remove(*_live_index)
    INDEX_INFO.labels(*labels).set(1)
    _live_index = labels


@router.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
