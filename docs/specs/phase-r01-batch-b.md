# Phase R1 spec and plan: Batch B and the manifest contract

| | |
| --- | --- |
| Phase | R1, from `docs/IMPLEMENTATION_PLAN_A3.md` |
| Work plan task | R3-AB-1 |
| Branch | `feat/rag-r01-batch-b` (code landed on `feat/rag-r04-eval-suite`, PR #48) |
| Stage | IMPLEMENTED BEFORE SPEC (retroactive, D-127) |
| Started | 2026-11-21 |
| Approved (spec and plan) | 2026-11-21, gate waived (D-124), as recommended |
| Depends on | Assignment 02 phases 4 and 7 (extract, discover) |

## 1. Objective

A committed, deterministic Batch B of 12 documents with planted problems and a ground-truth file, plus the manifest fields that the verification stage needs.

## 2. Context

- Architecture: `architecture-a3.md` 5.2 (manifest), 5.6 (planted problems).
- Requirements: R3-AB-1.
- Decisions: D-124 (gate waived), D-127.
- Code: `corpus/fetch.py`, `indexer/pipeline/run.py` `discover()` (unchanged), new `indexer/pipeline/manifest.py`.

## 3. Scope

**In scope**

- `scripts/make_batch_b.py`: `build() -> (files, manifest, planted)`, `main()`; writes `corpus/batch_b/*`, `_index.json`, `PLANTED.json`.
- `scripts/enrich_manifest.py`: `enrich(corpus) -> int`, adds `title` and `family`, keeps `_index.a02.json`.
- `indexer/pipeline/manifest.py`: `Entry`, `load_manifest(corpus_dir)`.

**Out of scope**

- Verification logic (R2). Cluster ingestion of Batch B (R8).

## 4. Interfaces and contracts

`load_manifest(corpus_dir: str) -> list[Entry]`; `Entry(file, doc_version, superseded, title, date, family, sha256, bytes, pages)`; `family` defaults to the file name; `title` falls back to the old `name` key. Without `_index.json`, Markdown front matter is read. `discover()` is untouched (A02 regression). No frozen contract (C-1 to C-8) changes.

## 5. Behaviour and design details

Generator is pure and seedless (fixed text, no clock, no network): same bytes every run. PDFs are written by a stdlib mini writer. Planted problems: 2 exact duplicates (b03, b04), near duplicate (b05, under 5 percent of words differ), truncated PDF (b07, strict prefix of b06, no `%%EOF`), corrupt PDF (b08, manifest keeps the real sha256 of b06), missing metadata (b09, no title, version, date), newer version (b10, `family=fee-structure`), injected instruction (b11), controls (b01, b02, b06, b12).

## 6. Acceptance criteria

- [x] **R1-AC1**: `make_batch_b.py` is idempotent.
- [x] **R1-AC2**: `PLANTED.json` has at least 10 files; counts: 2 exact duplicates, 1 near duplicate, 1 truncated, 1 corrupt, 1 missing metadata, 1 newer version, 1 injected, at least 2 controls.
- [x] **R1-AC3**: Exact duplicates share sha256; near duplicate differs in under 5 percent of words; truncated is a strict prefix of a complete file; corrupt file's sha256 differs from its manifest entry.
- [x] **R1-AC4**: `discover()` on an old A02 manifest is unchanged; `load_manifest` returns the new fields on the new manifest and the defaults on an old one.
- [ ] **R1-AC5**: `make test && make lint` green; `corpus/raw/` content unchanged; `_index.a02.json` equals the original byte for byte.

## 7. Test strategy and traceability

All unit tests use the hashing embedder (`EMBED_MODEL=hashing-bow-768`) and `indexer/tests/fakechroma.py`: no network, no model, no cluster.

| AC | Level | Test file and name, or command | Needs |
| --- | --- | --- | --- |
| R1-AC1 | unit + command | `test_batch_b.py::test_idempotent`; `python scripts/make_batch_b.py --out corpus/batch_b && git diff --exit-code corpus/batch_b` | nothing |
| R1-AC2 | unit | `test_batch_b.py::test_counts_and_planted_rows` | nothing |
| R1-AC3 | unit | `test_batch_b.py::test_duplicate_and_damage_properties` | nothing |
| R1-AC4 | unit | `test_batch_b.py::test_manifest_new_fields_and_old_manifest`, `test_front_matter_manifest` | nothing |
| R1-AC5 | command | `make test && make lint`; `git status corpus/raw`; compare `corpus/raw/_index.a02.json` | corpus/raw (gitignored) |

## 8. Open questions

| # | Question | Options and recommendation | Decision entry | Answer |
| --- | --- | --- | --- | --- |
| Q1 | none: everything taken as recommended (D-124, D-127) | | | |

## 9. Risks and assumptions

- `corpus/raw/` is gitignored, so AC5 byte equality of `_index.a02.json` can only be checked on the machine that holds it.
- PDF writer output must be accepted by pdfplumber (proved in R2 by Batch B verification).

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit message |
| --- | --- | --- | --- | --- |
| 1 | Generator and planted file | scripts/make_batch_b.py, corpus/batch_b/ | script run twice, `git diff --exit-code` | feat(corpus): Batch B generator |
| 2 | Manifest loader | indexer/pipeline/manifest.py | test_batch_b.py | feat(indexer): manifest contract |
| 3 | Enrich script | scripts/enrich_manifest.py | run on a copy | feat(corpus): enrich manifest |

### 10.2 Test plan

Tests ship with the code (listed in section 7). The independent tester (WORKFLOW 6.1) re-runs `make test && make lint`, coverage, judges every AC, and adds edge-case tests in `indexer/tests/test_incremental_edges.py`. It does not edit application code.

### 10.3 Rollback and risks

Revert the phase commits; Assignment 02 behaviour is reachable with `--full` and `index_mode=full`.

### 10.4 Estimate

See the plan table (R1); written retroactively, so no separate estimate.

## 11. Implementation notes

Generator is deterministic; `PLANTED.json` has 12 rows (4 controls). `discover()` untouched; the new `manifest.py` is the single loader for the verification stage. No deviation.

## 12. Test report

Independent tester (D-127), branch `feat/rag-r04-eval-suite`, hashing embedder and fake Chroma, no network.

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-21 | `make test && make lint` | PASS (indexer 292, eval 139; ruff, mypy clean) | |
| 1 | 2026-11-21 | `python scripts/make_batch_b.py --out corpus/batch_b && git diff --exit-code --stat corpus/batch_b` | PASS: wrote 12 files, no diff | R1-AC1 |
| 1 | 2026-11-21 | `pytest tests/test_batch_b.py` | PASS: counts 2 exact, 1 near, 1 truncated, 1 corrupt, 1 missing metadata, 1 newer, 1 injected, 4 controls | AC2, AC3, AC4 |
| 1 | 2026-11-21 | `ls corpus/raw/_index.a02.json` | FAIL: file absent (`corpus/raw` is gitignored and `enrich_manifest.py` was not run here) | AC5 part: not provable, see defects |

Coverage of `pipeline/manifest.py`: 96%.

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | 2026-11-21 | waived (D-124), as recommended | retroactive spec, D-127 |
| Tester verdict | 2026-11-21 | independent tester subagent | R1-AC5 not ticked: `_index.a02.json` missing on this machine, so byte equality of the backup cannot be shown. `corpus/raw` PDFs and `_index.json` have no tracked change. Defect list in the tester report. |
| Merged | | | PR #48 (shared with R4 to R8) |
