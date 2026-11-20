"""Module level: the embedding model on its own (R3-B-3, paper Table 1 row 1).

Measures paraphrase versus unrelated cosine, embedding time per chunk, memory per embedding, and determinism.
Calls Ollama directly with the pinned model (OLLAMA_URL, EMBED_MODEL); the API and the Chroma index are not involved.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

from .metrics import mean, percentile

HERE = Path(__file__).resolve().parents[1]


def cos(a: list[float], b: list[float]) -> float:
    na, nb = sum(x * x for x in a) ** 0.5, sum(x * x for x in b) ** 0.5
    return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb)


class Embedder:
    def __init__(self, url: str | None = None, model: str | None = None) -> None:
        self.url = (url or os.environ.get("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.environ.get("EMBED_MODEL", "nomic-embed-text")
        self.c = httpx.Client(timeout=120.0)

    def embed(self, texts: list[str]) -> list[list[float]]:
        r = self.c.post(f"{self.url}/api/embed", json={"model": self.model, "input": texts})
        r.raise_for_status()
        return r.json()["embeddings"]

    def version(self) -> str:
        try:
            tags = self.c.get(f"{self.url}/api/tags").json()["models"]
            for m in tags:
                if m["name"].split(":")[0] == self.model.split(":")[0]:
                    return f"{self.model}@{m['digest'][:12]}"
        except Exception:
            pass
        return f"{self.model}@unknown"


def run(pairs_path: Path = HERE / "embedding_pairs.jsonl", chunk_texts: list[str] | None = None,
        embedder: Embedder | None = None) -> dict:
    e = embedder or Embedder()
    pairs = [json.loads(ln) for ln in pairs_path.read_text().splitlines() if ln.strip()]
    sims: dict[str, list[float]] = {"paraphrase": [], "unrelated": []}
    for p in pairs:
        va, vb = e.embed(["search_query: " + p["a"], "search_query: " + p["b"]])
        sims[p["kind"]].append(cos(va, vb))
    out: dict = {
        "model": e.version(), "pairs_paraphrase": len(sims["paraphrase"]), "pairs_unrelated": len(sims["unrelated"]),
        "paraphrase_mean": mean(sims["paraphrase"]), "unrelated_mean": mean(sims["unrelated"]),
        "paraphrase_min": min(sims["paraphrase"]), "unrelated_max": max(sims["unrelated"]),
    }
    out["gap"] = out["paraphrase_mean"] - out["unrelated_mean"]
    texts = (chunk_texts or [p["a"] for p in pairs])[:100]
    per_chunk = []
    for t in texts:
        s = time.perf_counter()
        e.embed(["search_document: " + t])
        per_chunk.append((time.perf_counter() - s) * 1000)
    out.update(chunks_timed=len(texts), ms_per_chunk_median=percentile(per_chunk, 0.5),
               ms_per_chunk_p95=percentile(per_chunk, 0.95))
    sample = ["search_document: " + t for t in texts[:5]]
    v1, v2 = e.embed(sample), e.embed(sample)
    out["determinism_max_abs_diff"] = max(abs(a - b) for x, y in zip(v1, v2, strict=True) for a, b in zip(x, y, strict=True))
    out["dimension"] = len(v1[0])
    out["bytes_per_embedding_float32"] = len(v1[0]) * 4
    return out
