# Phase R3 spec and plan: Incremental update, archive, restore (A2)

| | |
| --- | --- |
| Phase | R3, from `docs/IMPLEMENTATION_PLAN_A3.md` |
| Work plan task | R3-A2-1 to R3-A2-4, R3-AB-2 |
| Branch | `feat/rag-r03-incremental` (code landed on `feat/rag-r04-eval-suite`, PR #48) |
| Stage | IMPLEMENTED BEFORE SPEC (retroactive, D-127) |
| Started | 2026-11-21 |
| Approved (spec and plan) | 2026-11-21, gate waived (D-124), as recommended |
| Depends on | R1, R2; A02 phase 7 (`store.py` swap, AD-02) |

## 1. Objective

Embed only the delta, copy the rest, swap atomically. An unchanged corpus embeds nothing; changed, deleted and superseded documents behave as the assignment says; superseded versions can be restored with no embedding.

## 2. Context

- Architecture: `architecture-a3.md` 5.4, 5.5, A3-R1, AD-32, I-20, I-21; A02 5.4.3 and 5.4.4.
- Requirements: R3-A2-1 to R3-A2-4, R3-AB-2.
- Decisions: D-127. Code: `indexer/pipeline/store.py` (`store()` swap, unchanged), `run.py`.

## 3. Scope

**In scope**

- `indexer/pipeline/registry.py`: `Registry.load/save/settings_diff/total_chunks`.
- `indexer/pipeline/incremental.py`: `run_incremental`, `read_live`, `render_summary`, `IncrementalRefused`.
- `indexer/pipeline/restore.py`: `restore(...)` and CLI.
- `run.py`: `--incremental`, `--full`, `--dry-run`; summary JSON line and text table.
- Archive of every indexed version under `archive/<source>/<sha12>/`.

**Out of scope**

- Cluster Jobs (R8). Candidate collections (R9).
- `scripts/check_registry.py` (R3-AC10) is not in the repository; the equivalent check is the I-21 assertion inside `run_incremental`.

## 4. Interfaces and contracts

`run_incremental(settings, *, client=None, lake=None, full=False, dry_run=False) -> dict` returns the summary (`new, changed, unchanged, deleted, quarantined, quarantined_before, superseded, flipped, chunks_embedded, chunks_copied, chunks_total, index_swapped, index_id, deleted_chunks_remaining, chunks_by_source`). `restore(settings, source, *, supersede=None, client=None, lake=None) -> dict`. Registry at `<lake>/registry/<collection>.json`, atomic write (tmp, fsync, replace). Settings: `index_mode` (`incremental` default), `lake_dir`.

## 5. Behaviour and design details

Classify each manifest file by sha256 against the registry: new, changed, unchanged, quarantined-before (same sha), deleted (in registry, not in manifest). An unchanged document whose live chunk count differs from the registry is treated as changed (reconcile). Unchanged chunks are copied with stored vectors; new and changed go through verify, clean, chunk, embed. `store()` builds the staging collection and swaps (AD-02). The registry is saved after the swap; before the swap a failure leaves collection and registry untouched. No change means no swap and the same `index_id` (I-20). Registry or collection missing while the other exists: full build with a note. Registry settings differing from now (embed model, dimension, chunk size or overlap): `IncrementalRefused` naming the difference; `--full` bypasses. Supersede and restore only flip the `superseded` metadata of copied chunks; restore pins the document.

## 6. Acceptance criteria

- [ ] **R3-AC1**: Spike result recorded: copied collection returns the same top 5 (A3-R1).
- [x] **R3-AC2**: First run on an empty lake builds everything; registry chunk counts sum to the collection count.
- [x] **R3-AC3**: Unchanged re-run: `chunks_embedded` 0, `index_swapped` false, `index_id` unchanged; embedder called zero times.
- [x] **R3-AC4**: Changed document: only its chunks are re-embedded; other sources keep ids and vectors; old chunks gone.
- [x] **R3-AC5**: Deleted document: zero chunks remain, collection count equals registry sum, last version archived.
- [x] **R3-AC6**: Superseded version: old chunks flagged `superseded=true` without re-embedding; old file archived.
- [x] **R3-AC7**: Restore makes the old version current again with zero embeddings; the newer one is superseded.
- [x] **R3-AC8**: Registry or settings mismatch refuses incremental mode naming the difference; `--full` works.
- [x] **R3-AC9**: A failure before the swap leaves collection and registry untouched.
- [ ] **R3-AC10**: Both batches pass A1 and A2 and the collection equals the registry (I-21), proven by `scripts/check_registry.py`.
- [ ] **R3-AC11**: `make test && make lint` green; `make eval-fixtures` green; coverage of new modules at least 85 percent.

## 7. Test strategy and traceability

All unit tests use the hashing embedder (`EMBED_MODEL=hashing-bow-768`) and `indexer/tests/fakechroma.py`: no network, no model, no cluster.

| AC | Level | Test file and name, or command | Needs |
| --- | --- | --- | --- |
| R3-AC1 | evidence | Plan log line 2026-11-21 R3 (spike on real Chroma 1.0.12: 26 of 26 chunks identical, same top 5); `/tmp/lake_spike`. Not re-runnable here (needs Chroma) | docker |
| R3-AC2 | unit | `test_incremental.py::test_first_build_then_unchanged_embeds_zero` | nothing |
| R3-AC3 | unit | same test (spy on embed) | nothing |
| R3-AC4 | unit | `test_incremental.py::test_changed_document_replaces_only_its_chunks`; edges `test_document_changed_and_changed_back_returns_to_original_ids_and_vectors` | nothing |
| R3-AC5 | unit | `test_incremental.py::test_deleted_document_leaves_no_orphans_and_is_archived`; edges `test_deleting_the_superseded_old_version_keeps_the_new_one_active` | nothing |
| R3-AC6 | unit | `test_incremental.py::test_newer_version_supersedes_old_without_reembedding_it_then_restore` | nothing |
| R3-AC7 | unit | same test (restore); edges `test_restore_twice_is_idempotent`, `test_restore_unknown_source_refused_and_nothing_changes` | nothing |
| R3-AC8 | unit | `test_incremental.py::test_settings_change_refuses_incremental_but_full_works`; edges `test_registry_without_collection_rebuilds_everything`, `test_collection_without_registry_rebuilds_everything` | nothing |
| R3-AC9 | unit | `test_incremental.py::test_failure_before_swap_leaves_collection_and_registry_untouched`; edges `test_embedder_failure_before_swap_changes_nothing`, `test_registry_save_failure_keeps_live_collection_consistent_with_old_registry_file` | nothing |
| R3-AC10 | command | `scripts/check_registry.py` does not exist; I-21 assert inside `run_incremental` plus `test_first_build...` cover the equality on fixtures | nothing |
| R3-AC11 | command | `make test && make lint`; `pytest --cov=pipeline`; `make eval-fixtures` (not run by the tester: needs services) | services |

## 8. Open questions

| # | Question | Options and recommendation | Decision entry | Answer |
| --- | --- | --- | --- | --- |
| Q1 | none: everything taken as recommended (D-124, D-127) | | | |

## 9. Risks and assumptions

- Copy-forward relies on Chroma returning stored embeddings exactly (spike on 1.0.12).
- A crash after the swap but before the registry save leaves the registry behind the collection; the next run re-embeds the affected documents (tested).

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit message |
| --- | --- | --- | --- | --- |
| 1 | Spike | scratch script | top 5 equal | docs: spike result |
| 2 | Registry | registry.py | test_incremental.py | feat(indexer): registry |
| 3 | Incremental flow | incremental.py, run.py | test_incremental.py | feat(indexer): incremental update |
| 4 | Restore | restore.py | test_incremental.py | feat(indexer): restore |

### 10.2 Test plan

Tests ship with the code (listed in section 7). The independent tester (WORKFLOW 6.1) re-runs `make test && make lint`, coverage, judges every AC, and adds edge-case tests in `indexer/tests/test_incremental_edges.py`. It does not edit application code.

### 10.3 Rollback and risks

Revert the phase commits; Assignment 02 behaviour is reachable with `--full` and `index_mode=full`.

### 10.4 Estimate

See the plan table (R3); written retroactively, so no separate estimate.

## 11. Implementation notes

Copy-forward reads live rows including embeddings, writes through the unchanged `store()` swap. Registry saved after the swap; mismatch of counts raises before the save (I-21).

## 12. Test report

Independent tester (D-127), branch `feat/rag-r04-eval-suite`, hashing embedder and fake Chroma, no network.

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-21 | `make test && make lint` | PASS | |
| 1 | 2026-11-21 | `pytest --cov=pipeline` | PASS: incremental 97%, registry 98%, restore 76% (CLI `main`), manifest 96% | |
| 1 | 2026-11-21 | `pytest tests/test_incremental.py tests/test_incremental_edges.py` | PASS: 9 original + 13 added tests | AC2 to AC9 |
| 1 | 2026-11-21 | `ls scripts/check_registry.py` | FAIL: file absent | AC10 |
| 1 | 2026-11-21 | spike (A3-R1) and `make eval-fixtures` | NOT RUN: need Chroma and services (forbidden here) | AC1, AC11 |

Coverage of new modules: incremental 97%, registry 98%, restore 76% (total over 85% except the CLI wrapper).

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | 2026-11-21 | waived (D-124), as recommended | retroactive spec, D-127 |
| Tester verdict | 2026-11-21 | independent tester subagent | AC1 (log evidence only), AC10 (script missing) and AC11 (eval-fixtures not run) not ticked. |
| Merged | | | PR #48 (shared with R4 to R8) |
