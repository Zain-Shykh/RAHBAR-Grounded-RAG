#!/usr/bin/env python3
"""Choose CACHE_THRESHOLD with data (R-CAC-3, architecture 5.9.3). Manual: needs Ollama and Redis Stack.

  python scripts/calibrate_cache.py [--redis-url redis://localhost:6379] [--thresholds 0.88 0.92 0.96]

Each pair is (question A, question B). A is stored in a throwaway cache index with the real
SemanticCache, B is looked up under the SAME scope tag on purpose: that measures the embedding
(real nomic-embed-text), not the scope guard. A paraphrase pair should hit; a near-miss pair must
not. A near-miss that hits is a false hit. The year pair is also run through the real scope()
to show the scope tag alone keeps 2023 and 2026 apart. Cleans up its index.
"""

from __future__ import annotations

import argparse
import math
import pathlib
import sys
import time

import redis

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.embedding.ollama import OllamaEmbedder  # noqa: E402
from app.schemas import AskResponse, Citation, RetrievedRef  # noqa: E402
from app.services.cache import SemanticCache  # noqa: E402
from app.services.scope import scope  # noqa: E402

PARAPHRASES = [
    ("What is the deadline to withdraw from a course?",
     "By when must a student withdraw from a course?"),
    ("What minimum attendance does the Prospectus 2026 require for graduate programs?",
     "What is the minimum attendance requirement for graduate students under the 2026 prospectus?"),
    ("Are mobile phones and smart watches allowed in the examination hall?",
     "Can students bring mobile phones or smart watches into the exam hall?"),
    ("What percentage of the tuition fee is refunded if a student withdraws up to the 20th day?",
     "How much of the tuition fee is refunded when a student withdraws by day 20 of classes?"),
    ("What is the normal course load per regular semester?",
     "How many courses does a student normally take in one regular semester?"),
    ("What does clause 1.21 of the academic rules require?",
     "What is required by clause 1.21 of the academic rules?"),
    ("What is the tuition fee per credit hour for BS programs for 2026-27?",
     "How much is the per credit hour tuition for BS students in 2026-27?"),
    ("What counts as unacceptable use of Generative AI tools?",
     "Which uses of Generative AI tools are not acceptable?"),
    ("What is the attendance requirement?", "what is the attendance requirement"),
]
NEAR_MISSES = [
    ("What is the deadline to withdraw from a course under the 2023 rules?",
     "What is the deadline to withdraw from a course under the 2026 rules?"),
    ("What does clause 1.21 of the academic rules require?",
     "What does clause 1.22 of the academic rules require?"),
    ("What is the tuition fee per credit hour for BS programs for 2026-27?",
     "What is the tuition fee per credit hour for MS programs for 2026-27?"),
    ("What is the tuition fee per credit hour for BS programs?",
     "What is the admission fee for BS programs?"),
    ("What percentage of the tuition fee is refunded if a student withdraws up to the 20th day?",
     "What percentage of the tuition fee is refunded if a student withdraws up to the 40th day?"),
    ("What minimum attendance does the Prospectus 2026 require for undergraduate programs?",
     "What minimum attendance does the Prospectus 2026 require for graduate programs?"),
    ("How many courses can a student take in a regular semester?",
     "How many courses can a student take in a summer semester?"),
    ("Are mobile phones allowed in the examination hall?",
     "Are calculators allowed in the examination hall?"),
    ("What is the minimum CGPA required to graduate from a BS program?",
     "What is the minimum CGPA required to graduate from an MS program?"),
]
YEAR_PAIR = NEAR_MISSES[0]
VERSIONS = ["2023-08", "2026-06"]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True)) / (
        math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def answer() -> AskResponse:
    return AskResponse(
        request_id="calib", answer="stored", answered_from_context=True, confidence="high",
        provider="calibration",
        citations=[Citation(source="x.pdf", section="1", page=1)],
        retrieved=[RetrievedRef(chunk_id="c", source="x.pdf", section="1", page=1, score=0.9)])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--redis-url", default="redis://localhost:6379")
    ap.add_argument("--ollama", default="http://localhost:11434")
    ap.add_argument("--thresholds", nargs="+", type=float, default=[0.88, 0.92, 0.96])
    args = ap.parse_args()

    emb = OllamaEmbedder("nomic-embed-text", args.ollama)
    vec = {q: emb.embed_query(q) for pair in PARAPHRASES + NEAR_MISSES for q in pair}
    dim = len(next(iter(vec.values())))
    r = redis.Redis.from_url(args.redis_url, socket_timeout=3)

    print(f"{'kind':<11}{'cosine':>8}  pair")
    rows = []
    for kind, pairs in (("paraphrase", PARAPHRASES), ("near-miss", NEAR_MISSES)):
        for a, b in pairs:
            s = cosine(vec[a], vec[b])
            rows.append((kind, s, a, b))
            print(f"{kind:<11}{s:8.4f}  {a!r} | {b!r}")

    # Run the real cache path per threshold, one throwaway index per pair so pairs cannot interact.
    print()
    print("threshold  paraphrase_hits  false_hits  false-hit pairs (cosine)")
    summary = {}
    for t in args.thresholds:
        ph = fh = 0
        bad = []
        for kind, pairs in (("paraphrase", PARAPHRASES), ("near-miss", NEAR_MISSES)):
            for a, b in pairs:
                index_id = f"calib-{time.time_ns()}"
                c = SemanticCache(r, t, 60)
                try:
                    assert c.maintain(index_id, dim)
                    c.store(index_id, vec[a], "same", a, answer())
                    hit = c.lookup(index_id, vec[b], "same") is not None
                finally:
                    r.execute_command("FT.DROPINDEX", f"idx:cache:{index_id}", "DD")
                if kind == "paraphrase":
                    ph += hit
                elif hit:
                    fh += 1
                    bad.append(f"{a!r} | {b!r} ({cosine(vec[a], vec[b]):.3f})")
        summary[t] = (ph, fh, bad)
        print(f"{t:<10} {ph:>2}/{len(PARAPHRASES):<14} {fh:>2}/{len(NEAR_MISSES):<9}  {bad[0] if bad else '-'}")
        for extra in bad[1:]:
            print(f"{'':<39}{extra}")

    a, b = YEAR_PAIR
    ta, tb = scope(a, VERSIONS).tag, scope(b, VERSIONS).tag
    print(f"\nyear pair scope tags: 2023={ta} 2026={tb} different={ta != tb} (so the scope guard blocks it at any threshold)")

    ok = [t for t in sorted(summary) if summary[t][1] == 0]
    print(f"\nlowest threshold with zero false hits among those tried: {ok[0] if ok else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
