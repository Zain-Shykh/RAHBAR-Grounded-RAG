"""Stage 0: verify. Re-hash every corpus file against _index.json (architecture 5.4.2)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class VerifyError(Exception):
    """The corpus does not match _index.json. The message has one line per problem."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(1 << 20):
            h.update(block)
    return h.hexdigest()


def verify(corpus_dir: str) -> int:
    """Return the number of files checked; raise VerifyError listing every problem."""
    root = Path(corpus_dir)
    index = root / "_index.json"
    if not index.exists():
        raise VerifyError(f"no _index.json in {corpus_dir}")
    entries = json.loads(index.read_text(encoding="utf-8"))
    problems: list[str] = []
    for entry in entries:
        path = root / entry["file"]
        if not path.is_file():
            problems.append(f"missing: {entry['file']}")
            continue
        actual = _sha256(path)
        if actual != entry["sha256"]:
            problems.append(f"sha256 mismatch: {entry['file']} "
                            f"expected {entry['sha256'][:12]} got {actual[:12]}")
    if problems:
        raise VerifyError("\n".join(problems))
    return len(entries)
