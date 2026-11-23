"""Incremental update (phase R3): zero-embed re-run, changed, deleted, superseded, restore, refusal, atomicity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fakechroma import FakeClient
from pipeline import embed as embedmod
from pipeline import store as storemod
from pipeline.config import IndexerSettings
from pipeline.incremental import IncrementalRefused, run_incremental
from pipeline.registry import Registry
from pipeline.restore import restore
from pipeline.verification.lake import Lake

def doc(title: str, n: int = 1) -> str:
    # words that depend on the title, so two documents are not near-duplicates of each other
    return "".join(f"# {i}. {title} part {i}\n\n{i}.1 " + " ".join(f"{title.lower()}{i}w{k}" for k in range(60)) +
                   f" {title}.\n\n" for i in range(1, n + 1))


def settings(corpus: Path, lake: Path, **kw) -> IndexerSettings:
    base = dict(embed_model="hashing-bow-768", chroma_host="h", chroma_port=1, collection="rahbar",
                corpus_dir=str(corpus), chunk_size=60, chunk_overlap=5, ollama_url="http://o",
                chroma_wait_seconds=0.0, lake_dir=str(lake), index_mode="incremental")
    base.update(kw)
    return IndexerSettings(**base)  # type: ignore[arg-type]


def write(corpus: Path, files: dict[str, tuple[str, dict]]) -> None:
    manifest = []
    for name, (text, meta) in files.items():
        (corpus / name).write_text(text)
        manifest.append({"file": name, "title": meta.get("title", name), "doc_version": meta.get("v", "2026"),
                         "family": meta.get("family", name), "superseded": meta.get("sup", False)})
    (corpus / "_index.json").write_text(json.dumps(manifest))


@pytest.fixture()
def env(tmp_path, monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(storemod, "get_client", lambda s: client)
    calls: list[int] = []
    real = embedmod.embed

    def spy(texts, s):
        calls.append(len(texts))
        return real(texts, s)

    monkeypatch.setattr(embedmod, "embed", spy)
    corpus, lake = tmp_path / "c", tmp_path / "l"
    corpus.mkdir()
    return corpus, lake, client, calls


def ids_of(client, source):
    c = client.cols["rahbar"]
    return sorted(i for i, m in zip(c.ids, c.metas, strict=True) if m["source"] == source)


def vecs_of(client, source):
    c = client.cols["rahbar"]
    return {i: tuple(e) for i, m, e in zip(c.ids, c.metas, c.embs, strict=True) if m["source"] == source}


def test_first_build_then_unchanged_embeds_zero(env):
    corpus, lake, client, calls = env
    write(corpus, {"a.md": (doc("Alpha", 3), {}), "b.md": (doc("Beta", 2), {})})
    s1 = run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    assert s1["new"] == 2 and s1["index_swapped"] and s1["chunks_embedded"] == client.cols["rahbar"].count() > 4
    reg = Registry.load(lake, "rahbar")
    assert reg.total_chunks() == client.cols["rahbar"].count()
    first_id = client.cols["rahbar"].metadata["index_id"]
    n_calls = len(calls)
    s2 = run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    assert (s2["chunks_embedded"], s2["index_swapped"], s2["unchanged"]) == (0, False, 2)
    assert len(calls) == n_calls                                    # the embedder was never called
    assert client.cols["rahbar"].metadata["index_id"] == first_id    # I-20: cache survives


def test_changed_document_replaces_only_its_chunks(env):
    corpus, lake, client, calls = env
    write(corpus, {"a.md": (doc("Alpha", 3), {}), "b.md": (doc("Beta", 2), {})})
    run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    b_before, a_before = vecs_of(client, "b.md"), ids_of(client, "a.md")
    old_id = client.cols["rahbar"].metadata["index_id"]
    write(corpus, {"a.md": (doc("Alpha CHANGED", 2), {}), "b.md": (doc("Beta", 2), {})})
    s = run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    assert s["changed"] == 1 and s["unchanged"] == 1 and s["index_swapped"]
    assert s["chunks_embedded"] == len(ids_of(client, "a.md")) != len(a_before)
    assert vecs_of(client, "b.md") == b_before                        # untouched document: same ids and vectors
    assert client.cols["rahbar"].metadata["index_id"] != old_id
    assert Registry.load(lake, "rahbar").total_chunks() == client.cols["rahbar"].count()


def test_deleted_document_leaves_no_orphans_and_is_archived(env):
    corpus, lake, client, _ = env
    write(corpus, {"a.md": (doc("Alpha", 3), {}), "b.md": (doc("Beta", 2), {})})
    run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    assert ids_of(client, "b.md")
    write(corpus, {"a.md": (doc("Alpha", 3), {})})
    (corpus / "b.md").unlink()
    s = run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    assert s["deleted"] == 1 and ids_of(client, "b.md") == [] and s["deleted_chunks_remaining"] == {"b.md": 0}
    assert set(s["chunks_by_source"]) == {"a.md"}
    assert client.cols["rahbar"].count() == Registry.load(lake, "rahbar").total_chunks()
    assert "b.md" not in Registry.load(lake, "rahbar").docs
    assert list((lake / "archive" / "b.md").glob("*/b.md"))            # last version kept


def test_newer_version_supersedes_old_without_reembedding_it_then_restore(env):
    corpus, lake, client, calls = env
    write(corpus, {"rules23.md": (doc("Rules old", 2), {"v": "2023", "family": "rules"})})
    run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    assert all(m["superseded"] is False for m in client.cols["rahbar"].metas)
    old_vecs = vecs_of(client, "rules23.md")
    write(corpus, {"rules23.md": (doc("Rules old", 2), {"v": "2023", "family": "rules"}),
                   "rules26.md": (doc("Rules new", 2), {"v": "2026", "family": "rules"})})
    s = run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    assert s["superseded"] == 1 and s["flipped"] == 1 and s["chunks_embedded"] == len(ids_of(client, "rules26.md"))
    flags = {m["source"]: m["superseded"] for m in client.cols["rahbar"].metas}
    assert flags == {"rules23.md": True, "rules26.md": False}
    assert vecs_of(client, "rules23.md") == old_vecs                   # copied, not re-embedded
    # rollback: restore the old version and supersede the new one, zero embeddings
    n = len(calls)
    r = restore(settings(corpus, lake), "rules23.md", supersede="rules26.md", client=client, lake=Lake(lake))
    assert r["chunks_embedded"] == 0 and len(calls) == n
    flags = {m["source"]: m["superseded"] for m in client.cols["rahbar"].metas}
    assert flags == {"rules23.md": False, "rules26.md": True}
    s3 = run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))   # pinned: no re-supersede
    assert s3["index_swapped"] is False


def test_quarantined_document_is_not_indexed_and_not_retried(env):
    corpus, lake, client, calls = env
    write(corpus, {"a.md": (doc("Alpha", 3), {}), "dup.md": (doc("Alpha", 3), {})})
    s = run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    assert s["quarantined"] == 1 and ids_of(client, "dup.md") == []
    assert list((lake / "quarantine").glob("*/dup.md"))
    s2 = run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    assert s2["quarantined_before"] == 1 and s2["chunks_embedded"] == 0 and not s2["index_swapped"]


def test_settings_change_refuses_incremental_but_full_works(env):
    corpus, lake, client, _ = env
    write(corpus, {"a.md": (doc("Alpha", 3), {})})
    run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    with pytest.raises(IncrementalRefused, match="chunk_size"):
        run_incremental(settings(corpus, lake, chunk_size=80), client=client, lake=Lake(lake))
    s = run_incremental(settings(corpus, lake, chunk_size=80), client=client, lake=Lake(lake), full=True)
    assert s["mode"] == "full" and s["chunks_embedded"] > 0
    assert Registry.load(lake, "rahbar").data["chunk_size"] == 80


def test_failure_before_swap_leaves_collection_and_registry_untouched(env):
    corpus, lake, client, _ = env
    write(corpus, {"a.md": (doc("Alpha", 3), {})})
    run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    before_ids, before_reg = list(client.cols["rahbar"].ids), (lake / "registry" / "rahbar.json").read_text()
    write(corpus, {"a.md": (doc("Alpha", 3), {}), "c.md": (doc("Gamma", 2), {})})
    client.fail_add_on_call = 1
    with pytest.raises(RuntimeError):
        run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    assert client.cols["rahbar"].ids == before_ids
    assert (lake / "registry" / "rahbar.json").read_text() == before_reg
    assert "rahbar_next" not in client.cols


def test_dry_run_writes_nothing(env):
    corpus, lake, client, _ = env
    write(corpus, {"a.md": (doc("Alpha", 3), {})})
    s = run_incremental(settings(corpus, lake), client=client, lake=Lake(lake), dry_run=True)
    assert s["dry_run"] and "rahbar" not in client.cols and not (lake / "registry").exists()


def test_reconcile_reembeds_a_document_whose_chunks_went_missing(env):
    corpus, lake, client, _ = env
    write(corpus, {"a.md": (doc("Alpha", 3), {}), "b.md": (doc("Beta", 2), {})})
    run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    col = client.cols["rahbar"]
    drop = [i for i, m in enumerate(col.metas) if m["source"] == "b.md"][:1]
    for i in reversed(drop):
        for lst in (col.ids, col.docs, col.metas, col.embs):
            del lst[i]
    s = run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    assert s["changed"] == 1 and client.cols["rahbar"].count() == Registry.load(lake, "rahbar").total_chunks()


def test_every_run_writes_a_verification_report_even_when_nothing_changed(env):
    corpus, lake, client, _ = env
    write(corpus, {"a.md": (doc("Alpha", 3), {}), "dup.md": (doc("Alpha", 3), {})})
    s1 = run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    s2 = run_incremental(settings(corpus, lake), client=client, lake=Lake(lake))
    r1 = Lake(lake).read_report(s1["run_id"])
    r2 = Lake(lake).read_report(s2["run_id"])
    assert r1["totals"]["checked"] == 2 and r1["totals"]["quarantined"] == 1
    assert r2["totals"]["checked"] == 0 and r2["unchanged"] == ["a.md"] and r2["previously_quarantined"] == ["dup.md"]


def test_dry_run_reports_but_quarantines_nothing(env):
    corpus, lake, client, _ = env
    write(corpus, {"a.md": (doc("Alpha", 3), {}), "dup.md": (doc("Alpha", 3), {})})
    s = run_incremental(settings(corpus, lake), client=client, lake=Lake(lake), dry_run=True)
    assert Lake(lake).read_report(s["run_id"])["totals"]["quarantined"] == 1
    assert not list((lake / "quarantine").glob("*/*"))
