"""Verification stage (phase R2): checks, decisions on Batch B, lake, report."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from pipeline.config import IndexerSettings
from pipeline.manifest import Entry
from pipeline.verification import checks as C
from pipeline.verification.lake import Lake
from pipeline.verification.report import render_text
from pipeline.verification.run_verify import verify_corpus

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("make_batch_b", ROOT / "scripts" / "make_batch_b.py")
mb = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(mb)  # type: ignore[union-attr]


def entry(**kw) -> Entry:
    base = dict(file="a.md", doc_version="2026", superseded=False, title="T", date=None, family="a.md",
                sha256=None, bytes=None, pages=None)
    base.update(kw)
    return Entry(**base)


GOOD = "The quick brown fox jumps over the lazy dog. " * 12


def test_quality_cases():
    ok = dict(text=GOOD, extract_error=None, integrity_error=None, pages=1)
    assert C.check_quality(**ok) == (True, "ok")
    assert not C.check_quality(**{**ok, "text": "hi"})[0]
    assert "garbled" in C.check_quality(**{**ok, "text": "#$%&*" * 80})[1]
    assert "garbled" in C.check_quality(**{**ok, "text": "ab�" * 100})[1]
    assert "extraction failed" in C.check_quality(**{**ok, "extract_error": "PdfminerException"})[1]
    assert "integrity" in C.check_quality(**{**ok, "integrity_error": "integrity: sha256 mismatch"})[1]
    assert "zero pages" in C.check_quality(**{**ok, "pages": 0})[1]
    assert "empty on 3 of 4" in C.check_quality(**{**ok, "pages": 4, "empty_pages": 3})[1]
    assert C.check_quality(**{**ok, "text": "Ünïcödé tëxt " * 40})[0]


def test_completeness_and_truncation():
    assert C.check_completeness(entry(), pages=1, truncated=None) == (True, "ok")
    assert C.check_completeness(entry(title=None), pages=1, truncated=None)[1] == "missing title"
    assert "date or doc_version" in C.check_completeness(entry(doc_version=None), pages=1, truncated=None)[1]
    assert C.check_completeness(entry(doc_version=None, date="2026-01-01"), pages=1, truncated=None)[0]
    assert "zero" in C.check_completeness(entry(), pages=0, truncated=None)[1]
    assert "declared 12" in C.check_completeness(entry(pages=12), pages=3, truncated=None)[1]
    assert C.check_completeness(entry(), pages=1, truncated="truncated: x") == (False, "truncated: x")
    assert C.truncation_reason(".pdf", b"abc", "") and not C.truncation_reason(".pdf", b"..%%EOF\n", "")
    assert C.truncation_reason(".html", b"<html>", "") and not C.truncation_reason(".html", b"</HTML>", "")
    assert C.truncation_reason(".md", b"", "ends without stop") and not C.truncation_reason(".md", b"", "Ends here.\n")


def test_recency_ordering():
    others = [{"source": "n.md", "family": "f", "doc_version": "2027-01", "date": None}]
    (ok, reason), src = C.check_recency(entry(family="f", doc_version="2026-27"), others)
    assert not ok and src == "n.md" and "superseded by n.md" in reason
    assert C.check_recency(entry(family="f", doc_version="2027-01"), others)[0][0]          # equal is not newer
    assert C.check_recency(entry(family="g", doc_version="2020"), others)[0][0]             # other family
    assert C.newer_than(None, "2019-20", None, "2023-24") and C.newer_than(None, "2026", None, "2026-06")
    assert C.newer_than("2026-01-01", None, "2027-01-05", None)


def test_uniqueness_rules():
    e = entry(file="b.md", family="x", doc_version="1")
    orig = [{"source": "a.md", "family": "x", "doc_version": "1", "sha256": "S", "text_sha256": "T", "signature": [1.0, 0.0]}]
    assert "exact duplicate of a.md" in C.check_uniqueness(e, file_sha="S", text_sha="z", signature=None, originals=orig, threshold=0.9)[1]
    assert "exact duplicate" in C.check_uniqueness(e, file_sha="q", text_sha="T", signature=None, originals=orig, threshold=0.9)[1]
    assert "near duplicate" in C.check_uniqueness(e, file_sha="q", text_sha="z", signature=[0.99, 0.14], originals=orig, threshold=0.95)[1]
    assert C.check_uniqueness(e, file_sha="q", text_sha="z", signature=[0.0, 1.0], originals=orig, threshold=0.95)[0]
    # same family, different version is recency's job, never near-duplicate
    e2 = entry(file="b.md", family="x", doc_version="2")
    assert C.check_uniqueness(e2, file_sha="q", text_sha="z", signature=[1.0, 0.0], originals=orig, threshold=0.5)[0]


def test_signature_windows_and_normalisation():
    calls = []

    def fake(texts):
        calls.append(len(texts))
        return [[1.0, 0.0] for _ in texts]

    assert C.signature("short text", fake) == [1.0, 0.0] and calls == [1]
    C.signature("w " * 1000, fake)
    assert calls == [1, 3]


@pytest.fixture()
def batch_b(tmp_path):
    files, manifest, planted = mb.build()
    d = tmp_path / "batch"
    d.mkdir()
    for n, data in files.items():
        (d / n).write_bytes(data)
    (d / "_index.json").write_text(json.dumps(manifest))
    return d, {p["file"]: p for p in planted}


def settings(corpus: Path) -> IndexerSettings:
    return IndexerSettings(embed_model="hashing-bow-768", chroma_host="h", chroma_port=1, collection="rahbar",
                           corpus_dir=str(corpus), chunk_size=400, chunk_overlap=50, ollama_url="http://o")


def test_batch_b_matches_planted(batch_b, tmp_path):
    d, planted = batch_b
    lake = Lake(tmp_path / "lake")
    rep = verify_corpus(settings(d), lake, run_id="r1")
    got = {x["source"]: x for x in rep["documents"]}
    assert len(got) == len(planted) >= 10
    for name, p in planted.items():
        x = got[name]
        if p["expect"] == "pass":
            assert x["action"] == "index", (name, x)
        else:
            check = p["expect"].split(":")[1]
            assert x["action"] == "quarantine" and not x["checks"][check]["pass"], (name, x)
    assert "exact duplicate of b01" in got["b03-library-policy-2026-copy.md"]["checks"]["uniqueness"]["reason"]
    assert "near duplicate of b01" in got["b05-library-policy-2026-reissue.md"]["checks"]["uniqueness"]["reason"]
    assert "no %%EOF" in got["b07-transport-policy-2026-truncated.pdf"]["checks"]["completeness"]["reason"]
    assert "sha256 mismatch" in got["b08-transport-notice-corrupt.pdf"]["checks"]["quality"]["reason"]
    assert got["b09-merit-scholarship-notes.md"]["checks"]["completeness"]["reason"].startswith("missing title")
    assert rep["totals"]["quarantined"] == 6


def test_quarantine_files_and_report_on_disk(batch_b, tmp_path):
    d, _ = batch_b
    lake = Lake(tmp_path / "lake")
    verify_corpus(settings(d), lake, run_id="r1")
    q = tmp_path / "lake" / "quarantine" / "r1"
    assert (q / "b03-library-policy-2026-copy.md").read_bytes() == (d / "b03-library-policy-2026-copy.md").read_bytes()
    reason = json.loads((q / "b03-library-policy-2026-copy.md.reason.json").read_text())
    assert reason["reasons"][0].startswith("uniqueness: exact duplicate")
    assert not (q / "b01-library-policy-2026.md").exists()
    rep = lake.read_report("r1")
    text = render_text(rep)
    assert text.count("\n") > 12 and "FAIL" in text and "reasons for failures" in text
    assert lake.latest_run() == "r1"


def test_newer_candidate_supersedes_registry_document(batch_b, tmp_path):
    d, _ = batch_b
    reg = {"fee-structure-page.html": {"family": "fee-structure", "doc_version": "2026-27", "date": None,
                                       "sha256": "x", "text_sha256": "y", "signature": None}}
    rep = verify_corpus(settings(d), Lake(tmp_path / "lake"), run_id="r2", registry=reg)
    acts = {x["source"]: x for x in rep["documents"]}
    assert acts["fee-structure-page.html"]["action"] == "supersede_registry"
    assert "superseded by b10-fee-structure-amendment-2027.md" in acts["fee-structure-page.html"]["checks"]["recency"]["reason"]
    assert acts["b10-fee-structure-amendment-2027.md"]["action"] == "index"
    assert rep["totals"]["superseded"] == 1


def test_older_candidate_is_superseded_not_quarantined(tmp_path):
    (tmp_path / "old.md").write_text("# Rules\n\n" + GOOD + "\n")
    (tmp_path / "new.md").write_text("# Rules\n\n" + GOOD.replace("fox", "cat") + "\n")
    (tmp_path / "_index.json").write_text(json.dumps([
        {"file": "old.md", "title": "R", "doc_version": "2023", "family": "r"},
        {"file": "new.md", "title": "R", "doc_version": "2026", "family": "r"}]))
    rep = verify_corpus(settings(tmp_path), Lake(tmp_path / "lake"), run_id="r3")
    a = {x["source"]: x["action"] for x in rep["documents"]}
    assert a == {"new.md": "index", "old.md": "supersede"}


def test_one_bad_document_does_not_abort_and_no_false_positive_on_manifest_flag(tmp_path):
    (tmp_path / "ok.md").write_text("# T\n\n" + GOOD + "\n")
    (tmp_path / "old.md").write_text("# T\n\n" + GOOD.replace("dog", "pig") + "\n")
    (tmp_path / "_index.json").write_text(json.dumps([
        {"file": "ok.md", "title": "T", "doc_version": "2026", "family": "t"},
        {"file": "old.md", "title": "T", "doc_version": "2023", "family": "t", "superseded": True},
        {"file": "gone.md", "title": "T", "doc_version": "2026", "family": "g"}]))
    rep = verify_corpus(settings(tmp_path), Lake(tmp_path / "lake"), run_id="r4")
    a = {x["source"]: x for x in rep["documents"]}
    assert "missing file" in a["gone.md"]["checks"]["quality"]["reason"]
    assert a["old.md"]["action"] == "index" and "already marked superseded" in a["old.md"]["checks"]["recency"]["reason"]
