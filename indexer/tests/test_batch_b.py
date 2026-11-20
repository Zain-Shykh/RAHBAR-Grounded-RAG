"""Batch B generator and the manifest contract (phase R1: AC1 to AC5)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "indexer"))

from pipeline.manifest import load_manifest  # noqa: E402
from pipeline.run import discover  # noqa: E402

_spec = importlib.util.spec_from_file_location("make_batch_b", ROOT / "scripts" / "make_batch_b.py")
mb = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(mb)  # type: ignore[union-attr]


def test_counts_and_planted_rows():
    files, manifest, planted = mb.build()
    assert len(files) >= 10 and len(manifest) == len(files) == len(planted)
    kinds = [p["problem"] for p in planted]
    assert kinds.count("exact_duplicate") == 2 and kinds.count("near_duplicate") == 1
    for k in ("truncated", "corrupt", "missing_metadata", "newer_version", "injected_instruction"):
        assert kinds.count(k) == 1
    assert kinds.count("control") >= 2


def test_duplicate_and_damage_properties():
    files, manifest, _ = mb.build()
    sha = {e["file"]: e["sha256"] for e in manifest}
    h = lambda b: hashlib.sha256(b).hexdigest()  # noqa: E731
    assert h(files["b01-library-policy-2026.md"]) == h(files["b03-library-policy-2026-copy.md"])
    assert h(files["b02-lab-safety-rules-2026.md"]) == h(files["b04-lab-safety-rules-2026-copy.md"])
    a = files["b01-library-policy-2026.md"].decode().split()
    b = files["b05-library-policy-2026-reissue.md"].decode().split()
    changed = sum(x != y for x, y in zip(a, b, strict=False)) + abs(len(a) - len(b))
    assert 0 < changed / len(a) < 0.05
    full = files["b06-transport-policy-2026.pdf"]
    assert full.startswith(files["b07-transport-policy-2026-truncated.pdf"]) and b"%%EOF" not in files["b07-transport-policy-2026-truncated.pdf"]
    assert h(files["b08-transport-notice-corrupt.pdf"]) != sha["b08-transport-notice-corrupt.pdf"]
    assert h(full) == sha["b08-transport-notice-corrupt.pdf"]  # manifest keeps the real hash


def test_idempotent(tmp_path):
    for d in ("a", "b"):
        files, manifest, planted = mb.build()
        out = tmp_path / d
        out.mkdir()
        for n, data in files.items():
            (out / n).write_bytes(data)
    assert {p.name: p.read_bytes() for p in (tmp_path / "a").iterdir()} == \
           {p.name: p.read_bytes() for p in (tmp_path / "b").iterdir()}


def test_manifest_new_fields_and_old_manifest(tmp_path):
    files, manifest, _ = mb.build()
    (tmp_path / "_index.json").write_text(json.dumps(manifest))
    by = {e.file: e for e in load_manifest(str(tmp_path))}
    assert by["b09-merit-scholarship-notes.md"].title is None and not by["b09-merit-scholarship-notes.md"].has_version_or_date
    assert by["b10-fee-structure-amendment-2027.md"].family == "fee-structure"
    old = [{"file": "x.pdf", "name": "X", "sha256": "0" * 64, "doc_version": "2023-08", "superseded": True}]
    (tmp_path / "_index.json").write_text(json.dumps(old))
    e = load_manifest(str(tmp_path))[0]
    assert (e.title, e.family, e.superseded) == ("X", "x.pdf", True)
    assert discover(str(tmp_path)) == [(tmp_path / "x.pdf", "2023-08", True)]


def test_front_matter_manifest(tmp_path):
    (tmp_path / "a.md").write_text("---\ndoc_version: 2026\nsuperseded: false\ntitle: T\n---\nbody")
    e = load_manifest(str(tmp_path))[0]
    assert (e.doc_version, e.title, e.family) == ("2026", "T", "a.md")
