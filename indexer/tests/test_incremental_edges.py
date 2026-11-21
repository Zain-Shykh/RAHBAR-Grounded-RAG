# ruff: noqa: F811
"""Independent-tester edge cases for phases R1 to R3 (incremental update, registry, restore)."""

from __future__ import annotations

import pytest
from pipeline import embed as embedmod
from pipeline.incremental import run_incremental
from pipeline.registry import Registry
from pipeline.restore import restore
from pipeline.verification.lake import Lake
from test_incremental import doc, env, ids_of, settings, vecs_of, write  # noqa: F401


def run(env_, **kw):  # noqa: ANN001
    corpus, lake, client, _ = env_
    return run_incremental(settings(corpus, lake), client=client, lake=Lake(lake), **kw)


def test_unicode_file_name_roundtrip(env):
    corpus, lake, client, calls = env
    name = "Ünïcödé-نامہ-規則.md"
    write(corpus, {name: (doc("Alpha", 3), {}), "b.md": (doc("Beta", 2), {})})
    assert run(env)["new"] == 2 and ids_of(client, name)
    n = len(calls)
    s = run(env)
    assert (s["unchanged"], s["chunks_embedded"], s["index_swapped"]) == (2, 0, False) and len(calls) == n


def test_empty_corpus_exits_cleanly(env):
    corpus, *_ = env
    (corpus / "_index.json").write_text("[]")
    with pytest.raises(SystemExit, match="no documents"):
        run(env)


def test_registry_without_collection_rebuilds_everything(env):
    corpus, lake, client, calls = env
    write(corpus, {"a.md": (doc("Alpha", 3), {})})
    run(env)
    del client.cols["rahbar"]  # collection lost, registry survives
    s = run(env)
    assert s["mode"] == "full" and "disagree" in s["note"] and s["chunks_embedded"] > 0
    assert client.cols["rahbar"].count() == Registry.load(lake, "rahbar").total_chunks()


def test_collection_without_registry_rebuilds_everything(env):
    corpus, lake, client, _ = env
    write(corpus, {"a.md": (doc("Alpha", 3), {})})
    run(env)
    (lake / "registry" / "rahbar.json").unlink()
    s = run(env)
    assert s["mode"] == "full" and s["chunks_embedded"] > 0
    assert client.cols["rahbar"].count() == Registry.load(lake, "rahbar").total_chunks()


def test_embedder_failure_before_swap_changes_nothing(env, monkeypatch):
    corpus, lake, client, _ = env
    write(corpus, {"a.md": (doc("Alpha", 3), {})})
    run(env)
    ids, reg = list(client.cols["rahbar"].ids), (lake / "registry" / "rahbar.json").read_text()
    write(corpus, {"a.md": (doc("Alpha", 3), {}), "c.md": (doc("Gamma", 2), {})})

    def boom(texts, s):
        raise RuntimeError("embedder down")

    monkeypatch.setattr(embedmod, "embed", boom)
    with pytest.raises(RuntimeError, match="embedder down"):
        run(env)
    assert client.cols["rahbar"].ids == ids and (lake / "registry" / "rahbar.json").read_text() == reg


def test_registry_save_failure_keeps_live_collection_consistent_with_old_registry_file(env, monkeypatch):
    corpus, lake, client, _ = env
    write(corpus, {"a.md": (doc("Alpha", 3), {})})
    run(env)
    reg_before = (lake / "registry" / "rahbar.json").read_text()
    write(corpus, {"a.md": (doc("Alpha", 3), {}), "c.md": (doc("Gamma", 2), {})})

    def boom(self, **meta):
        raise OSError("disk full")

    monkeypatch.setattr(Registry, "save", boom)
    with pytest.raises(OSError):
        run(env)
    # the registry file is not corrupted; the next run reconciles (the new document is simply re-embedded)
    assert (lake / "registry" / "rahbar.json").read_text() == reg_before
    monkeypatch.undo()
    s = run(env)
    assert s["chunks_embedded"] > 0 or s["unchanged"] == 2
    assert client.cols["rahbar"].count() == Registry.load(lake, "rahbar").total_chunks()


def test_quarantined_document_fixed_later_is_indexed(env):
    corpus, lake, client, _ = env
    write(corpus, {"a.md": (doc("Alpha", 3), {}), "dup.md": (doc("Alpha", 3), {})})
    assert run(env)["quarantined"] == 1
    write(corpus, {"a.md": (doc("Alpha", 3), {}), "dup.md": (doc("Delta", 3), {})})
    s = run(env)
    assert s["new"] == 1 and s["quarantined"] == 0 and ids_of(client, "dup.md")
    assert "dup.md" not in Registry.load(lake, "rahbar").quarantined


def test_document_changed_and_changed_back_returns_to_original_ids_and_vectors(env):
    corpus, lake, client, _ = env
    write(corpus, {"a.md": (doc("Alpha", 3), {}), "b.md": (doc("Beta", 2), {})})
    run(env)
    original = vecs_of(client, "a.md")
    write(corpus, {"a.md": (doc("Alpha CHANGED", 2), {}), "b.md": (doc("Beta", 2), {})})
    assert run(env)["changed"] == 1
    write(corpus, {"a.md": (doc("Alpha", 3), {}), "b.md": (doc("Beta", 2), {})})
    assert run(env)["changed"] == 1
    assert vecs_of(client, "a.md") == original
    assert client.cols["rahbar"].count() == Registry.load(lake, "rahbar").total_chunks()


def test_restore_twice_is_idempotent(env):
    corpus, lake, client, calls = env
    write(corpus, {"r23.md": (doc("Rules old", 2), {"v": "2023", "family": "rules"})})
    run(env)
    write(corpus, {"r23.md": (doc("Rules old", 2), {"v": "2023", "family": "rules"}),
                   "r26.md": (doc("Rules new", 2), {"v": "2026", "family": "rules"})})
    run(env)
    st = settings(corpus, lake)
    restore(st, "r23.md", supersede="r26.md", client=client, lake=Lake(lake))
    n, flags = len(calls), sorted((m["source"], m["superseded"]) for m in client.cols["rahbar"].metas)
    r2 = restore(st, "r23.md", supersede="r26.md", client=client, lake=Lake(lake))
    assert r2["index_swapped"] is False and r2["chunks_embedded"] == 0 and len(calls) == n
    assert sorted((m["source"], m["superseded"]) for m in client.cols["rahbar"].metas) == flags


def test_restore_unknown_source_refused_and_nothing_changes(env):
    corpus, lake, client, _ = env
    write(corpus, {"a.md": (doc("Alpha", 3), {})})
    run(env)
    before = (lake / "registry" / "rahbar.json").read_text()
    with pytest.raises(SystemExit, match="not in the registry"):
        restore(settings(corpus, lake), "nope.md", client=client, lake=Lake(lake))
    with pytest.raises(SystemExit, match="not in the registry"):
        restore(settings(corpus, lake), "a.md", supersede="nope.md", client=client, lake=Lake(lake))
    assert (lake / "registry" / "rahbar.json").read_text() == before


def test_deleting_the_superseded_old_version_keeps_the_new_one_active(env):
    corpus, lake, client, _ = env
    write(corpus, {"r23.md": (doc("Rules old", 2), {"v": "2023", "family": "rules"}),
                   "r26.md": (doc("Rules new", 2), {"v": "2026", "family": "rules"})})
    run(env)
    write(corpus, {"r26.md": (doc("Rules new", 2), {"v": "2026", "family": "rules"})})
    (corpus / "r23.md").unlink()
    s = run(env)
    assert s["deleted"] == 1 and ids_of(client, "r23.md") == [] and ids_of(client, "r26.md")
    assert {m["superseded"] for m in client.cols["rahbar"].metas} == {False}
    assert list((lake / "archive" / "r23.md").glob("*/r23.md"))
    assert client.cols["rahbar"].count() == Registry.load(lake, "rahbar").total_chunks()


@pytest.mark.parametrize(("strict", "code"), [(False, 0), (True, 1)])
def test_verify_strict_controls_exit_code(monkeypatch, strict, code):
    from pipeline import config as cfgmod
    from pipeline import incremental as incmod
    from pipeline import run as runmod

    s = settings(__import__("pathlib").Path("."), __import__("pathlib").Path("."), verify_strict=strict)
    monkeypatch.setattr(cfgmod, "get_settings", lambda: s)
    monkeypatch.setattr(runmod, "get_settings", lambda: s)
    monkeypatch.setattr(incmod, "run_incremental", lambda *a, **k: {"chunks_total": 3, "quarantined": 2})
    monkeypatch.setattr("sys.argv", ["run", "--incremental"])
    assert runmod.main() == code
