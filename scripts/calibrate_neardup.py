#!/usr/bin/env python3
"""Calibrate the near-duplicate threshold (D-113): distinct real pairs versus planted near-duplicates.

    python scripts/calibrate_neardup.py --real corpus/raw --batch corpus/batch_b \
        --models hashing-bow-768,nomic-embed-text --out eval/results

Text is extracted once, signatures are computed per model, and eval/results/neardup-calibration-<ts>.json
records every pairwise cosine, the largest distinct-pair value, the smallest planted value, the margin
and the midpoint suggested as the threshold. checks.NEARDUP_THRESHOLD must sit inside the margin.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "indexer"))

from pipeline.config import get_settings  # noqa: E402
from pipeline.embed import embed  # noqa: E402
from pipeline.extract import extract  # noqa: E402
from pipeline.manifest import load_manifest  # noqa: E402
from pipeline.verification import checks as C  # noqa: E402

PLANTED_NEAR = [("b01-library-policy-2026.md", "b05-library-policy-2026-reissue.md")]
# documents planted as copies of one another are one cluster: pairs inside it are not "distinct" pairs
CLUSTERS = [{"b01-library-policy-2026.md", "b03-library-policy-2026-copy.md", "b05-library-policy-2026-reissue.md"},
            {"b02-lab-safety-rules-2026.md", "b04-lab-safety-rules-2026-copy.md"}]


def texts_of(directory: str, skip: set[str]) -> dict[str, tuple[str, str, str]]:
    out = {}
    for e in load_manifest(directory):
        p = Path(directory) / e.file
        if e.file in skip or not p.is_file():
            continue
        try:
            doc = extract(str(p), e.doc_version or "unknown", e.superseded)
        except Exception:
            continue
        out[e.file] = ("\n".join(pg.text for pg in doc.pages), e.family, e.doc_version or "")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", default="corpus/raw")
    ap.add_argument("--batch", default="corpus/batch_b")
    ap.add_argument("--models", default="hashing-bow-768")
    ap.add_argument("--out", default="eval/results")
    ap.add_argument("--cache", help="JSON file caching the extracted real-corpus texts (extraction takes minutes)")
    a = ap.parse_args()
    cache = Path(a.cache) if a.cache else None
    if cache and cache.exists():
        real = {k: tuple(v) for k, v in json.loads(cache.read_text()).items()}
    else:
        real = texts_of(a.real, set())
        if cache:
            cache.write_text(json.dumps(real))
    batch = texts_of(a.batch, {"b07-transport-policy-2026-truncated.pdf", "b08-transport-notice-corrupt.pdf"})
    allt = {**real, **batch}
    result: dict = {"created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "real": sorted(real),
                    "batch": sorted(batch), "models": {}}
    for model in a.models.split(","):
        s = get_settings()
        s = type(s)(**{**s.__dict__, "embed_model": model})
        sig = {k: C.signature(v[0], lambda t, s=s: embed(t, s)) for k, v in allt.items()}
        distinct, planted = [], []
        for x, y in itertools.combinations(sorted(allt), 2):
            c = C.cosine(sig[x], sig[y])
            same_fam_other_ver = allt[x][1] == allt[y][1] and allt[x][2] != allt[y][2]
            row = {"a": x, "b": y, "cosine": round(c, 4), "same_family_other_version": same_fam_other_ver}
            if (x, y) in PLANTED_NEAR:
                planted.append(row)
            elif not same_fam_other_ver and not any({x, y} <= c for c in CLUSTERS):
                distinct.append(row)
        top = max(distinct, key=lambda r: r["cosine"])
        low = min(planted, key=lambda r: r["cosine"])
        result["models"][model] = {
            "max_distinct": top, "min_planted_near_duplicate": low,
            "margin": round(low["cosine"] - top["cosine"], 4),
            "suggested_threshold": round((low["cosine"] + top["cosine"]) / 2, 3),
            "configured_threshold": C.NEARDUP_THRESHOLD.get(model),
            "distinct_pairs": sorted(distinct, key=lambda r: -r["cosine"])[:15], "planted": planted}
        print(model, "max distinct", top["cosine"], "min planted", low["cosine"],
              "suggest", result["models"][model]["suggested_threshold"])
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"neardup-calibration-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    dest.write_text(json.dumps(result, indent=2) + "\n")
    print("wrote", dest)


if __name__ == "__main__":
    main()
