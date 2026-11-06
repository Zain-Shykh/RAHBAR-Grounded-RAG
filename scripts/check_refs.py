"""Check that every `path:LINE` reference in the given markdown files resolves to a real line.

usage: python3 scripts/check_refs.py docs/ENGINEERING-NOTES.md docs/adr/0001-indexer-as-job.md
Prints one line per reference; exit 1 if any file is missing or too short.
"""
import re
import sys
from pathlib import Path

REF = re.compile(r"((?:k8s|api|indexer|eval|\.github|ui|scripts|docs)/[\w./-]*\w\.(?:yaml|yml|py|md|json)):(\d+)")
root = Path(__file__).resolve().parent.parent
bad = n = 0
for doc in sys.argv[1:]:
    for ref, line in sorted(set(REF.findall(Path(doc).read_text()))):
        n += 1
        p = root / ref
        total = len(p.read_text().splitlines()) if p.is_file() else 0
        ok = int(line) <= total and int(line) >= 1
        bad += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {ref}:{line}" + ("" if ok else f"  (file has {total} lines)"))
print(f"{n} references, {bad} unresolved")
sys.exit(1 if bad else 0)
