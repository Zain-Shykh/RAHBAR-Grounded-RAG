"""verify.py: hashes against _index.json (phase 4 spec 5.6, AC-5)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pipeline import run
from pipeline.config import IndexerSettings
from pipeline.verify import VerifyError, verify


def _corpus(tmp_path: Path) -> Path:
    entries = []
    for name, data in (("a.pdf", b"alpha"), ("b.html", b"bravo")):
        (tmp_path / name).write_bytes(data)
        entries.append({"file": name, "sha256": hashlib.sha256(data).hexdigest()})
    (tmp_path / "_index.json").write_text(json.dumps(entries), encoding="utf-8")
    return tmp_path


def test_ok(tmp_path: Path) -> None:
    assert verify(str(_corpus(tmp_path))) == 2


def test_mismatch(tmp_path: Path) -> None:
    d = _corpus(tmp_path)
    (d / "a.pdf").write_bytes(b"tampered")
    with pytest.raises(VerifyError) as e:
        verify(str(d))
    msg = str(e.value)
    assert "sha256 mismatch: a.pdf" in msg and "expected " + hashlib.sha256(b"alpha").hexdigest()[:12] in msg
    assert "got " + hashlib.sha256(b"tampered").hexdigest()[:12] in msg
    assert "b.html" not in msg


def test_missing(tmp_path: Path) -> None:
    d = _corpus(tmp_path)
    (d / "b.html").unlink()
    with pytest.raises(VerifyError, match="missing: b.html"):
        verify(str(d))


def test_all_listed(tmp_path: Path) -> None:
    d = _corpus(tmp_path)
    (d / "a.pdf").write_bytes(b"x")
    (d / "b.html").unlink()
    lines = _err(d).split("\n")
    assert len(lines) == 2


def _err(d: Path) -> str:
    with pytest.raises(VerifyError) as e:
        verify(str(d))
    return str(e.value)


def test_no_index(tmp_path: Path) -> None:
    with pytest.raises(VerifyError, match="no _index.json"):
        verify(str(tmp_path))


def test_run_pipeline_exits_nonzero_before_extract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    d = _corpus(tmp_path)
    (d / "a.pdf").write_bytes(b"tampered")
    called: list[str] = []
    import pipeline.extract as ex

    monkeypatch.setattr(ex, "extract", lambda *a, **k: called.append("extract"))
    monkeypatch.setattr(run, "get_settings", lambda: IndexerSettings("m", "h", 1, "c", str(d), 400, 50, "u"))
    monkeypatch.setattr("sys.argv", ["run"])
    assert run.main() == 1
    assert called == []
