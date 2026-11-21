# Phase R2 spec and plan: Verification stage (A1)

| | |
| --- | --- |
| Phase | R2, from `docs/IMPLEMENTATION_PLAN_A3.md` |
| Work plan task | R3-A1-1 to R3-A1-4 |
| Branch | `feat/rag-r02-verification` (code landed on `feat/rag-r04-eval-suite`, PR #48) |
| Stage | IMPLEMENTED BEFORE SPEC (retroactive, D-127) |
| Started | 2026-11-21 |
| Approved (spec and plan) | 2026-11-21, gate waived (D-124), as recommended |
| Depends on | R1 (manifest, Batch B) |

## 1. Objective

After extraction and before chunking every new or changed document gets a pass or fail with a reason for quality, completeness, recency and uniqueness; failures are quarantined and never indexed; a report is written per run.

## 2. Context

- Architecture: `architecture-a3.md` 3, 5.1, 5.3, 5.4; invariant I-19.
- Requirements: R3-A1-1 to R3-A1-4.
- Decisions: D-113 (near duplicate method and threshold), D-127.
- Code: `indexer/pipeline/extract.py`, `embed.py`.

## 3. Scope

**In scope**

- `indexer/pipeline/verification/{checks,stage,lake,report,run_verify}.py`.
- `python -m pipeline.run --verify-only`; `python -m pipeline.verification.run_verify <run_id>` text table.
- `scripts/calibrate_neardup.py` and `eval/results/neardup-calibration-*.json`.
- `VERIFY_STRICT` (exit 1 when anything is quarantined).

**Out of scope**

- Registry and incremental swap (R3). Kubernetes (R8). Injection rail (R6): b11 passes verification by design.

## 4. Interfaces and contracts

Pure checks: `check_quality`, `check_completeness`, `check_recency`, `check_uniqueness`, `signature`. Orchestration: `build_candidate`, `decide(cands, registry, threshold) -> list[Verdict]`, `verify_candidates(...)`, `verify_corpus(...) -> report dict`. Actions: `index`, `supersede`, `supersede_registry`, `quarantine`. Lake: `Lake.quarantine/archive/write_report/read_report/latest_run`. Report file `reports/<run_id>/verification.json` with `documents[]` (`source`, `action`, `checks.<name>.{pass,reason}`) and `totals`. Config: `NEARDUP_THRESHOLD = {{nomic-embed-text: 0.97, hashing-bow-768: 0.85}}`, env `LAKE_DIR`, `VERIFY_STRICT`.

## 5. Behaviour and design details

Near duplicate = cosine of the mean embedding of three 300-word windows against every other candidate and registry document; exact duplicate = same file or normalised text sha256. A document with an older version/date in the same family is not quarantined: it gets `supersede`; if the newer one is in the registry the registry document gets `supersede_registry`. A manifest `superseded: true` flag is respected. Missing file, unreadable PDF, sha256 mismatch, garbled text, empty text, zero pages: quality fail. Missing title, version and date, zero pages, declared pages differing from actual, no `%%EOF`, HTML without `</html>`, Markdown ending without a stop: completeness fail. One bad document never aborts the run.

## 6. Acceptance criteria

- [x] **R2-AC1**: Each check is a pure function with tests for pass, fail, and edge cases (empty text, one page, Unicode, unreadable bytes).
- [x] **R2-AC2**: On Batch B, the report has an entry per file and matches `PLANTED.json` (6 quarantined, injected passes, older version flagged `supersede`).
- [x] **R2-AC3**: The 9 real documents all pass, including the A02 version pair (recency, not uniqueness).
- [x] **R2-AC4**: A failed document is copied to `quarantine/<run_id>/` with a `.reason.json`; its chunks never reach embed.
- [x] **R2-AC5**: `verification.json` exists per run and has the expected shape; the text table prints one line per document.
- [x] **R2-AC6**: One bad document does not abort the run (exit 0) unless `VERIFY_STRICT=true` (exit 1); a missing file is reported, not fatal.
- [x] **R2-AC7**: The near-duplicate threshold lies between the largest distinct real pair and the smallest planted near duplicate in the calibration file, which states the margin.
- [x] **R2-AC8**: `make test && make lint` green; coverage of `pipeline/verification` at least 85 percent.

## 7. Test strategy and traceability

All unit tests use the hashing embedder (`EMBED_MODEL=hashing-bow-768`) and `indexer/tests/fakechroma.py`: no network, no model, no cluster.

| AC | Level | Test file and name, or command | Needs |
| --- | --- | --- | --- |
| R2-AC1 | unit | `test_verification.py::test_quality_cases`, `test_completeness_and_truncation`, `test_recency_ordering`, `test_uniqueness_rules`, `test_signature_windows_and_normalisation` | nothing |
| R2-AC2 | unit | `test_verification.py::test_batch_b_matches_planted`, `test_newer_candidate_supersedes_registry_document` | nothing |
| R2-AC3 | command | `EMBED_MODEL=hashing-bow-768 CORPUS_DIR=../corpus/raw LAKE_DIR=/tmp/x python -m pipeline.run --verify-only`; `test_verification.py::test_older_candidate_is_superseded_not_quarantined` | corpus/raw (gitignored) |
| R2-AC4 | unit | `test_verification.py::test_quarantine_files_and_report_on_disk`; `test_incremental.py::test_quarantined_document_is_not_indexed_and_not_retried` | nothing |
| R2-AC5 | unit | `test_verification.py::test_quarantine_files_and_report_on_disk` (render_text, read_report) | nothing |
| R2-AC6 | unit | `test_verification.py::test_one_bad_document_does_not_abort_and_no_false_positive_on_manifest_flag`; `run.py` main strict branch (code read) | nothing |
| R2-AC7 | file | `eval/results/neardup-calibration-*.json`, `checks.NEARDUP_THRESHOLD` | nothing |
| R2-AC8 | command | `make test && make lint`; `pytest --cov=pipeline` | nothing |

## 8. Open questions

| # | Question | Options and recommendation | Decision entry | Answer |
| --- | --- | --- | --- | --- |
| Q1 | none: everything taken as recommended (D-124, D-127) | | | |

## 9. Risks and assumptions

- Nomic margin is narrow (0.0619): a different embedding model needs a new calibration (D-113 stays PROVISIONAL).
- Real PDF extraction is slow (OCR), so the real-corpus check is a command, not a unit test.

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit message |
| --- | --- | --- | --- | --- |
| 1 | Pure checks and Candidate | verification/checks.py, stage.py | test_verification.py | feat(indexer): verification checks |
| 2 | Lake, report, quarantine | verification/lake.py, report.py, run_verify.py | test_verification.py | feat(indexer): quarantine and report |
| 3 | Calibration | scripts/calibrate_neardup.py | file in eval/results | feat(eval): near-duplicate calibration |
| 4 | CLI | run.py --verify-only, VERIFY_STRICT | manual run | feat(indexer): --verify-only |

### 10.2 Test plan

Tests ship with the code (listed in section 7). The independent tester (WORKFLOW 6.1) re-runs `make test && make lint`, coverage, judges every AC, and adds edge-case tests in `indexer/tests/test_incremental_edges.py`. It does not edit application code.

### 10.3 Rollback and risks

Revert the phase commits; Assignment 02 behaviour is reachable with `--full` and `index_mode=full`.

### 10.4 Estimate

See the plan table (R2); written retroactively, so no separate estimate.

## 11. Implementation notes

Four checks as pure functions; `decide` produces `index`, `supersede`, `supersede_registry`, `quarantine`. Hashing threshold 0.85 (distinct max 0.6222, planted near duplicate 0.9805); nomic 0.97 (distinct max 0.9379, planted 0.9998, margin 0.0619). Calibration file: `eval/results/neardup-calibration-20261120T221945Z.json`.

## 12. Test report

Independent tester (D-127), branch `feat/rag-r04-eval-suite`, hashing embedder and fake Chroma, no network.

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-21 | `make test && make lint` | PASS | |
| 1 | 2026-11-21 | `EMBED_MODEL=hashing-bow-768 CORPUS_DIR=../corpus/raw LAKE_DIR=/tmp/lakeT_raw python -m pipeline.run --verify-only` | PASS: `totals: checked 9, indexed 9, quarantined 0` | AC3; took several minutes (OCR) |
| 1 | 2026-11-21 | same on `../corpus/batch_b` | PASS: `checked 12, indexed 6, quarantined 6`; b03, b04 exact duplicate, b05 near duplicate (cosine 0.980 >= 0.85), b07 truncated, b08 sha256 mismatch, b09 missing title; b11 (injected) indexed | AC2 |
| 1 | 2026-11-21 | `pytest --cov=pipeline` | PASS: checks 97%, stage 98%, lake 100%, report 100%, `__init__` 100%, run_verify 70% (CLI wrappers) | package total over 85% |
| 1 | 2026-11-21 | `pytest tests/test_incremental_edges.py::test_verify_strict_controls_exit_code` | PASS: strict false exit 0, true exit 1 when quarantined | AC6 (added) |

Coverage `pipeline/verification` (weighted): about 93%. Note: the lazy `run_verify.py` CLI functions are the uncovered lines.

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | 2026-11-21 | waived (D-124), as recommended | retroactive spec, D-127 |
| Tester verdict | 2026-11-21 | independent tester subagent | PASS all AC; see Test report. Observation: the real-corpus run exercised the hashing embedder only; nomic is covered by the calibration file. |
| Merged | | | PR #48 (shared with R4 to R8) |
