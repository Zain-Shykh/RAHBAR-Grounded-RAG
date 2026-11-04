"""Run extract + clean on the real corpus and check the result (phase 4 spec AC-1, 2, 3, 6, 8, 9).

    .venv/bin/python scripts/check_golden_extract.py [--corpus corpus/raw] [--only SUBSTRING]

Needs the real documents (gitignored) and tesseract. Exits 1 on any failed check.
Inside the indexer image: PYTHONPATH=/app, corpus mounted read-only, e.g. --corpus /corpus --only policy.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "indexer"))

from pipeline.clean import clean  # noqa: E402
from pipeline.extract import extract  # noqa: E402
from pipeline.models import Document  # noqa: E402
from pipeline.run import discover  # noqa: E402

HEADER = "NATIONAL UNIVERSITY OF COMPUTER AND EMERGING SCIENCES"
PROSPECTUS = "prospectus-2026-academic-rules-and-regulations.pdf"
ITEM = re.compile(r"^\s*- \{source:\s*([\w.-]+),.*#\s*(p\.(\d+)|html)\b")


def norm(text: str) -> str:
    return " ".join(text.split())


def golden_checks(golden: Path) -> list[tuple[str, str, int, str]]:
    """(question id, source, page, expect) for every question with a relevant item."""
    questions = {q["id"]: q for q in yaml.safe_load(golden.read_text(encoding="utf-8"))["questions"]}
    out, current = [], ""
    for line in golden.read_text(encoding="utf-8").splitlines():
        if m := re.match(r"\s*- id:\s*(q\d+)", line):
            current = m.group(1)
        elif (m := ITEM.match(line)) and questions[current].get("expect"):
            out.append((current, m.group(1), int(m.group(3) or 1), questions[current]["expect"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(ROOT / "corpus" / "raw"))
    ap.add_argument("--only", default="", help="only documents whose file name contains this")
    args = ap.parse_args()

    docs: dict[str, Document] = {}
    print(f"{'document':58} {'pages':>5} {'ocr':>4} {'words':>7}")
    for path, version, superseded in discover(args.corpus):
        if args.only in path.name:
            d = clean(extract(str(path), version, superseded))
            docs[path.name] = d
            words = sum(len(p.text.split()) for p in d.pages)
            print(f"{path.name:58} {len(d.pages):5d} {sum(p.ocr for p in d.pages):4d} {words:7d}")

    failures: list[str] = []
    if not docs:
        print(f"FAIL no documents found in {args.corpus} (filter {args.only!r})")
        return 1

    def check(ok: bool, label: str) -> None:
        print(("PASS " if ok else "FAIL ") + label)
        if not ok:
            failures.append(label)

    def page_text(source: str, n: int) -> str | None:
        d = docs.get(source)
        return norm(d.pages[n - 1].text) if d and n <= len(d.pages) else None

    for source in ("academic-rules-handbook-jun-2026.pdf", "student-handbook-jun-2026.pdf"):
        if source in docs:
            check(all(HEADER not in p.text for p in docs[source].pages), f"no repeating header in {source}")
    if (t := page_text("annual-report-2023-24.pdf", 13)) is not None:
        check("Islamabad 19 14 46 16 83 50 8 236" in t, "annual report 2023-24 p13 row on one line")
    if (t := page_text(PROSPECTUS, 1)) is not None:
        check("Graduate and Post Graduate degree programs are 75%" in t, "prospectus p1 sentence contiguous")
    if (t := page_text("undergraduate-academic-rules-aug-2023.pdf", 16)) is not None:
        check("4.25" in t and "last day of classes" in t, "OCR: 2023 rules p16 has 4.25 and wording")
    for source in ("fee-structure-page.html", "grading-page.html"):
        if source in docs:
            lines = docs[source].pages[0].text.split("\n")
            check(any(" | " in ln for ln in lines) and not any("<" in ln for ln in lines),
                  f"{source} table rows have ' | ', no markup")

    print("\ngolden expect strings in cleaned source page")
    for qid, source, page, expect in golden_checks(ROOT / "eval" / "golden.yaml"):
        if (t := page_text(source, page)) is not None:
            check(norm(expect) in t, f"{qid} {source} p{page}: {expect!r}")

    print(f"\n{len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
