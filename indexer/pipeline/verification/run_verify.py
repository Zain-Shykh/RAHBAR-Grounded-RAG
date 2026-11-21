"""`python -m pipeline.run --verify-only` and `python -m pipeline.report <run_id>`: A1 without indexing."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from ..config import IndexerSettings
from ..manifest import load_manifest
from .checks import NEARDUP_THRESHOLD
from .lake import Lake, new_run_id
from .report import build_report, render_text
from .stage import Candidate, Verdict, build_candidate, decide


def verify_candidates(settings: IndexerSettings, lake: Lake, *, run_id: str,
                      registry: dict[str, dict] | None = None, only: set[str] | None = None,
                      write: bool = True) -> tuple[dict, list[Candidate], list[Verdict]]:
    """Extract, check and decide every manifest entry (or `only`); quarantine failures; write the report.
    Returns the report plus the candidates (with their extracted documents) and the verdicts."""
    from ..embed import embed
    from ..extract import extract

    embed_texts = lambda texts: embed(texts, settings)  # noqa: E731
    threshold = NEARDUP_THRESHOLD.get(settings.embed_model, 0.97)
    entries = [e for e in load_manifest(settings.corpus_dir) if only is None or e.file in only]
    cands = [build_candidate(e, settings.corpus_dir, extract=extract, embed_texts=embed_texts) for e in entries]
    verdicts = decide(cands, registry or {}, threshold=threshold)
    by_file = {c.entry.file: c for c in cands}
    for v in verdicts:
        if v.action == "quarantine" and write:
            c = by_file[v.source]
            lake.quarantine(run_id, v.source, c.path, v.reasons(), c.file_sha or None)
    report = build_report(run_id, settings.corpus_dir, settings.embed_model, verdicts, threshold)
    if write:
        lake.write_report(run_id, "verification.json", report)
    return report, cands, verdicts


def verify_corpus(settings: IndexerSettings, lake: Lake, *, run_id: str | None = None,
                  registry: dict[str, dict] | None = None, only: set[str] | None = None) -> dict:
    return verify_candidates(settings, lake, run_id=run_id or new_run_id(), registry=registry, only=only)[0]


def verify_only(settings: IndexerSettings) -> int:
    from ..run import log

    lake = Lake(os.environ.get("LAKE_DIR", "/lake"))
    report = verify_corpus(settings, lake)
    print(render_text(report), flush=True)
    log("verification done", run_id=report["run_id"], **report["totals"])
    return 0


def main() -> int:
    lake = Lake(os.environ.get("LAKE_DIR", "/lake"))
    run_id = sys.argv[1] if len(sys.argv) > 1 else lake.latest_run()
    if not run_id or not Path(lake.root / "reports" / run_id / "verification.json").exists():
        print("no such run", file=sys.stderr)
        return 1
    print(render_text(lake.read_report(run_id)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
