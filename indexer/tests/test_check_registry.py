"""scripts/check_registry.py (R3-AC10) with a fake collection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_registry import compare  # noqa: E402


class Col:
    def __init__(self, sources):
        self.sources = sources

    def get(self, include):
        return {"metadatas": [{"source": s} for s in self.sources]}


def test_equal_passes() -> None:
    lines, ok = compare(Col(["a", "a", "b"]), {"a": {"chunks": 2}, "b": {"chunks": 1}})
    assert ok and not any(x.endswith(("DIFF", "ORPHAN")) for x in lines)


def test_difference_orphan_and_missing_fail() -> None:
    lines, ok = compare(Col(["a", "o"]), {"a": {"chunks": 2}, "m": {"chunks": 1}})
    t = "\n".join(lines)
    assert not ok and "ORPHAN" in t and t.count("DIFF") == 2
