"""Chunk the real corpus and report (phase 6 spec AC-7, AC-8). Not part of the image.

    .venv/bin/python scripts/chunk_report.py --size 400 --overlap 50 [--only SUBSTR]
        [--sections] [--golden eval/golden.yaml] [--corpus corpus/raw]

Prints per document: chunks, words per chunk (min/median/max), stored words, source words,
storage amplification (stored / source, architecture 5.4.2). `--sections` lists the distinct
sections. `--golden` lists every golden (source, section) with no chunk that has that section and holds
the question's `expect` text, and exits 1.
Needs the real documents (gitignored) and Tesseract.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "indexer"))
sys.path.insert(0, str(ROOT / "eval"))

from pipeline.chunk import chunk  # noqa: E402
from pipeline.clean import clean  # noqa: E402
from pipeline.extract import extract  # noqa: E402
from pipeline.models import Chunk  # noqa: E402
from pipeline.run import discover  # noqa: E402
from run_eval import section_matches  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(ROOT / "corpus" / "raw"))
    ap.add_argument("--size", type=int, default=400)
    ap.add_argument("--overlap", type=int, default=50)
    ap.add_argument("--only", default="", help="only documents whose file name contains this")
    ap.add_argument("--sections", action="store_true", help="list the distinct sections")
    ap.add_argument("--golden", type=Path, help="check golden (source, section) items")
    args = ap.parse_args()

    all_chunks: list[Chunk] = []
    stored_total = source_total = 0
    print(f"size {args.size} words, overlap {args.overlap}")
    print(f"{'document':<58} {'chunks':>6} {'min':>4} {'med':>4} {'max':>5} {'stored':>8} {'source':>8} {'amp':>5}")
    for path, version, superseded in discover(args.corpus):
        if args.only not in path.name:
            continue
        doc = clean(extract(str(path), version, superseded))
        chunks = chunk(doc, args.size, args.overlap)
        counts = [len(c.text.split()) for c in chunks] or [0]
        stored = sum(counts)
        source = sum(len(p.text.split()) for p in doc.pages)
        stored_total, source_total = stored_total + stored, source_total + source
        all_chunks += chunks
        amp = stored / source if source else 0.0
        print(f"{doc.source:<58} {len(chunks):>6} {min(counts):>4} {int(statistics.median(counts)):>4} "
              f"{max(counts):>5} {stored:>8} {source:>8} {amp:>5.2f}")
        if args.sections:
            for s in dict.fromkeys(c.section for c in chunks):
                print(f"    {s}")
    amp = stored_total / source_total if source_total else 0.0
    print(f"{'TOTAL':<58} {len(all_chunks):>6} {'':>4} {'':>4} {'':>5} {stored_total:>8} {source_total:>8} {amp:>5.2f}")

    if not args.golden:
        return 0
    missing = 0
    for q in yaml.safe_load(args.golden.read_text(encoding="utf-8"))["questions"]:
        expect = " ".join(str(q.get("expect") or "").split()).lower()
        for item in q.get("relevant") or []:
            # the chunk that holds the expected wording must carry the golden section
            if not any(c.source == item["source"] and section_matches(item["section"], c.section)
                       and expect in " ".join(c.text.split()).lower() for c in all_chunks):
                missing += 1
                print(f"NO CHUNK  {q['id']}  {item['source']}  {item['section']!r}")
    print(f"golden items without a matching chunk: {missing}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
