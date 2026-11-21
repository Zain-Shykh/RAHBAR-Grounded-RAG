#!/usr/bin/env python3
"""Show where a golden question's answer is written in the downloaded documents (for the human review).

    python scripts/show_source.py g19 g20 ...        # prints the page text, highlights the expected text
    python scripts/show_source.py --extract g19 ...  # also writes the one page as a file in eval/review/

The file is the ORIGINAL document in corpus/raw (or corpus/batch_b), read at the page named in eval/golden.jsonl,
not the index. PDF pages are extracted with pdftotext; the extract (a one-page PDF) can be opened in any viewer.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def find(name: str) -> Path | None:
    for d in ("corpus/raw", "corpus/batch_b"):
        p = ROOT / d / name
        if p.exists():
            return p
    return None


def page_text(p: Path, page: int) -> str:
    if p.suffix == ".pdf":
        return subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(p), "-"],
                              capture_output=True, text=True).stdout
    return p.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    args = sys.argv[1:]
    extract = "--extract" in args
    ids = [a for a in args if not a.startswith("--")]
    rows = {json.loads(ln)["id"]: json.loads(ln) for ln in (ROOT / "eval/golden.jsonl").read_text().splitlines()}
    for i in ids:
        q = rows[i]
        print("=" * 100, f"\n{i}  [{q['origin']}]  {q['question']}\nexpected answer text: {q.get('expect')!r}")
        for rel in q["relevant"]:
            p = find(rel["source"])
            print(f"\n--- {rel['source']}  page {rel['page']}  section {rel['section']!r}\n    file: {p}")
            if p is None:
                print("    NOT FOUND on this machine")
                continue
            text = page_text(p, rel["page"])
            if q.get("expect"):
                text = re.sub(f"({re.escape(q['expect'])})", r">>>\1<<<", text, flags=re.I)
            print(text.rstrip())
            if extract:
                out = ROOT / "eval" / "review"
                out.mkdir(exist_ok=True)
                dest = out / f"{i}-{p.stem}-p{rel['page']}{p.suffix}"
                if p.suffix == ".pdf":
                    subprocess.run(["pdfseparate", "-f", str(rel["page"]), "-l", str(rel["page"]), str(p),
                                    str(dest).replace(".pdf", "-%d.pdf")], check=False)
                else:
                    shutil.copyfile(p, dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
