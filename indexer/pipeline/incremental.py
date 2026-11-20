"""Incremental update: embed the delta, copy the rest, stage-and-swap (architecture-a3 5.5, AD-32).

Unchanged documents are not extracted, chunked or embedded: their chunks, metadata and stored vectors are
read back from the live collection and written to the staging collection by `store()`, which keeps the
AD-02 swap. New and changed documents go through verify, clean, chunk and embed. Deleted documents are
simply not copied (no orphans by construction, I-21). A run that changes nothing embeds nothing, does not
swap and leaves `index_id` alone (I-20).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .config import IndexerSettings
from .manifest import load_manifest
from .models import Chunk
from .registry import Registry
from .run import log
from .verification.lake import Lake, new_run_id
from .verification.run_verify import verify_candidates
from .verification.stage import _sha256


class IncrementalRefused(RuntimeError):
    """The registry and the current settings disagree: run with --full (I-3)."""


def read_live(client: Any, name: str) -> tuple[dict, dict[str, list[dict]]] | None:
    """(collection metadata, rows grouped by source) of the live collection, or None if absent."""
    try:
        col = client.get_collection(name)
    except Exception:
        return None
    rows: dict[str, list[dict]] = {}
    offset = 0
    while True:
        got = col.get(include=["documents", "metadatas", "embeddings"], limit=500, offset=offset)
        ids = list(got["ids"])
        for i, cid in enumerate(ids):
            md = got["metadatas"][i]
            rows.setdefault(md["source"], []).append(
                {"id": cid, "doc": got["documents"][i], "meta": dict(md),
                 "emb": [float(x) for x in got["embeddings"][i]]})
        if len(ids) < 500:
            break
        offset += 500
    return dict(col.metadata or {}), rows


def _chunk_of(row: dict, superseded: bool) -> Chunk:
    m = row["meta"]
    return Chunk(row["id"], row["doc"], m["source"], m["section"], int(m["page"]), str(m["doc_version"]), superseded)


def _view(docs: dict[str, dict]) -> dict[str, dict]:
    return {s: {**d, "superseded": d.get("status") == "superseded"} for s, d in docs.items()}


def run_incremental(settings: IndexerSettings, *, client: Any = None, lake: Lake | None = None,
                    full: bool = False, dry_run: bool = False) -> dict:
    from .chunk import chunk
    from .clean import clean
    from .embed import dimension, document_text, embed, wait_for_ollama
    from .store import get_client, store, wait_for_chroma

    started = time.perf_counter()
    lake = lake or Lake(settings.lake_dir)
    run_id = new_run_id()
    dim = dimension(settings.embed_model)
    if client is None:
        wait_for_chroma(settings, settings.chroma_wait_seconds)
        client = get_client(settings)
    wait_for_ollama(settings, settings.ollama_wait_seconds)

    reg = Registry.load(lake.root, settings.collection)
    live = read_live(client, settings.collection)
    live_rows = live[1] if live else {}
    note = ""
    if not full:
        diff = reg.settings_diff(embed_model=settings.embed_model, dimension=dim,
                                 chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
        if diff:
            raise IncrementalRefused("incremental mode refused, run with --full: " + "; ".join(diff))
        if (live is None) != (not reg.docs):
            note, full = "registry and collection disagree: building everything", True
    if full:
        reg = Registry(reg.path)
        note = note or "full build"
    docs = reg.docs

    entries = {e.file: e for e in load_manifest(settings.corpus_dir)}
    if not entries:
        raise SystemExit(f"no documents found in {settings.corpus_dir}")
    shas = {n: _sha256(Path(settings.corpus_dir) / n) for n in entries if (Path(settings.corpus_dir) / n).is_file()}
    new, changed, unchanged, qbefore, stale = [], [], [], [], []
    for name in sorted(entries):
        sha = shas.get(name)
        d = docs.get(name)
        if d and sha == d["sha256"]:
            if len(live_rows.get(name, [])) != d["chunks"]:
                stale.append(name)
                changed.append(name)
            else:
                unchanged.append(name)
        elif reg.quarantined.get(name, {}).get("sha256") == sha and sha is not None:
            qbefore.append(name)
        elif d:
            changed.append(name)
        else:
            new.append(name)
    deleted = sorted(set(docs) - set(entries))

    to_check = set(new) | set(changed)
    view = _view({s: d for s, d in docs.items() if s in unchanged})
    report, cands, verdicts = verify_candidates(settings, lake, run_id=run_id, registry=view,
                                                only=to_check or {"\0none"}, write=bool(to_check))
    by_src = {c.entry.file: c for c in cands}
    quarantined = [v.source for v in verdicts if v.action == "quarantine"]
    passing = [v for v in verdicts if v.action in ("index", "supersede") and v.source in by_src]
    flips_to_superseded = {v.source for v in verdicts if v.action == "supersede_registry"}

    # desired superseded flag of every unchanged document, versus what the live chunks carry
    flip: list[str] = []
    for s in unchanged:
        want = docs[s].get("status") == "superseded" or s in flips_to_superseded
        have = bool(live_rows[s][0]["meta"].get("superseded")) if live_rows.get(s) else want
        if want != have:
            flip.append(s)

    new_chunks: list[Chunk] = []
    superseded_new: set[str] = set()
    for v in passing:
        c = by_src[v.source]
        doc = clean(c.doc)  # type: ignore[arg-type]
        doc.superseded = c.entry.superseded or v.action == "supersede"
        if doc.superseded:
            superseded_new.add(v.source)
        pieces = chunk(doc, settings.chunk_size, settings.chunk_overlap)
        if not pieces:
            log("document produced no chunks", source=v.source)
        new_chunks += pieces

    summary: dict[str, Any] = {
        "run_id": run_id, "mode": "full" if full else "incremental", "note": note, "dry_run": dry_run,
        "new": len(new), "changed": len(changed), "unchanged": len(unchanged), "deleted": len(deleted),
        "quarantined": len(quarantined), "quarantined_before": len(qbefore),
        "superseded": len(superseded_new) + len(flips_to_superseded), "flipped": len(flip),
        "chunks_embedded": 0, "chunks_copied": 0, "chunks_total": reg.total_chunks(),
        "index_swapped": False, "index_id": (live[0].get("index_id") if live else None)}
    index_changes = bool(passing or deleted or flip or stale or full)
    if dry_run or not index_changes:
        summary["chunks_total"] = sum(d["chunks"] for s, d in docs.items() if s in unchanged) if dry_run else summary["chunks_total"]
        if not dry_run:
            _record_quarantine(reg, verdicts, by_src, run_id)
            reg.save()
        summary["seconds"] = round(time.perf_counter() - started, 1)
        lake.write_report(run_id, "summary.json", summary)
        log("ingest summary", **summary)
        print(render_summary(summary), flush=True)
        return summary

    started_embed = time.perf_counter()
    vectors = embed([document_text(c) for c in new_chunks], settings) if new_chunks else []
    log("embedded", vectors=len(vectors), model=settings.embed_model,
        seconds=round(time.perf_counter() - started_embed, 1))
    copied: list[Chunk] = []
    copied_vecs: list[list[float]] = []
    for s in unchanged:
        want = docs[s].get("status") == "superseded" or s in flips_to_superseded
        for r in sorted(live_rows[s], key=lambda r: r["id"]):
            copied.append(_chunk_of(r, want))
            copied_vecs.append(r["emb"])
    all_chunks, all_vecs = copied + new_chunks, copied_vecs + vectors
    store(all_chunks, all_vecs, settings, client)
    col = client.get_collection(settings.collection)
    index_id = (col.metadata or {}).get("index_id")

    # registry (after the swap) and the archive of every indexed version
    per_doc: dict[str, int] = {}
    for nc in new_chunks:
        per_doc[nc.source] = per_doc.get(nc.source, 0) + 1
    for s in deleted:
        docs.pop(s, None)
    for s in unchanged:
        if s in flips_to_superseded or s in flip:
            docs[s]["status"] = "superseded" if (s in flips_to_superseded or docs[s].get("status") == "superseded") else "active"
    for v in passing:
        c = by_src[v.source]
        e = c.entry
        docs[v.source] = {"sha256": c.file_sha, "text_sha256": c.text_sha, "signature": c.signature,
                          "doc_version": e.doc_version, "date": e.date, "family": e.family, "title": e.title,
                          "pages": c.pages, "status": "superseded" if v.source in superseded_new else "active",
                          "pinned": False, "chunks": per_doc.get(v.source, 0), "last_run": run_id}
        reg.quarantined.pop(v.source, None)
        if not dry_run:
            lake.archive(v.source, c.path, c.file_sha)
    for s in unchanged:  # carry the chunk count of every copied document unchanged
        docs[s]["chunks"] = len(live_rows[s])
    _record_quarantine(reg, verdicts, by_src, run_id)
    if col.count() != reg.total_chunks():
        raise RuntimeError(f"registry says {reg.total_chunks()} chunks, collection has {col.count()} (I-21)")
    reg.save(collection=settings.collection, embed_model=settings.embed_model, dimension=dim,
             chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap, index_id=index_id)
    # the orphan proof (R3-A2-3): chunks still stored under the id of every deleted document, counted in the store
    remaining = {s: len(col.get(where={"source": s}, include=[])["ids"]) for s in deleted}
    summary.update(deleted_chunks_remaining=remaining,
                   chunks_by_source={s: d["chunks"] for s, d in sorted(docs.items())})
    summary.update(chunks_embedded=len(new_chunks), chunks_copied=len(copied), chunks_total=col.count(),
                   index_swapped=True, index_id=index_id, seconds=round(time.perf_counter() - started, 1))
    lake.write_report(run_id, "summary.json", summary)
    log("ingest summary", **summary)
    print(render_summary(summary), flush=True)
    return summary


def render_summary(s: dict) -> str:
    """The human-readable table printed after the JSON line (screenshot R3-S-A2)."""
    rows = [("mode", s["mode"]), ("documents new / changed / unchanged / deleted",
                                  f"{s['new']} / {s['changed']} / {s['unchanged']} / {s['deleted']}"),
            ("quarantined now / quarantined before", f"{s['quarantined']} / {s['quarantined_before']}"),
            ("superseded / flags flipped", f"{s['superseded']} / {s['flipped']}"),
            ("chunks embedded", s["chunks_embedded"]), ("chunks copied forward", s["chunks_copied"]),
            ("chunks in the index", s["chunks_total"]), ("index swapped", s["index_swapped"]),
            ("index_id", s["index_id"])]
    if s.get("deleted_chunks_remaining"):
        rows.append(("chunks left under deleted documents", s["deleted_chunks_remaining"]))
    w = max(len(k) for k, _ in rows)
    return "\n".join(["ingest summary " + s["run_id"]] + [f"  {k:<{w}}  {v}" for k, v in rows])


def _record_quarantine(reg: Registry, verdicts: list, by_src: dict, run_id: str) -> None:
    for v in verdicts:
        if v.action == "quarantine" and v.source in by_src:
            reg.quarantined[v.source] = {"sha256": by_src[v.source].file_sha or None, "run_id": run_id,
                                         "reasons": v.reasons()}
