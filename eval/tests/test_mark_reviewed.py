import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("mark_reviewed", Path(__file__).resolve().parents[2] / "scripts" / "mark_reviewed.py")
mr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mr)


def _write(tmp_path):
    p = tmp_path / "g.jsonl"
    rows = [{"id": "g1", "origin": "synthetic", "reviewed": False}, {"id": "g2", "origin": "synthetic", "reviewed": False},
            {"id": "q1", "origin": "human", "reviewed": True}]
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def test_marks_only_given_ids(tmp_path):
    p = _write(tmp_path)
    assert mr.mark(["g1"], p) == 1
    got = {r["id"]: r["reviewed"] for r in map(json.loads, p.read_text().splitlines())}
    assert got == {"g1": True, "g2": False, "q1": True}


def test_refuses_human_and_unknown_and_changes_nothing(tmp_path):
    p = _write(tmp_path)
    before = p.read_text()
    for bad in (["g1", "q1"], ["g9"]):
        with pytest.raises(SystemExit):
            mr.mark(bad, p)
    assert p.read_text() == before


def test_builder_reproduces_committed_golden():
    bg = importlib.util.spec_from_file_location("bg", Path(__file__).resolve().parents[2] / "scripts" / "build_golden_jsonl.py")
    m = importlib.util.module_from_spec(bg)
    bg.loader.exec_module(m)
    want = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in m.build())
    assert (Path(__file__).resolve().parents[1] / "golden.jsonl").read_text(encoding="utf-8") == want
