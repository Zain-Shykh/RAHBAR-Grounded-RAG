# Phase 13 spec and plan: Failure analysis

| | |
| --- | --- |
| Phase | 13, from `docs/IMPLEMENTATION_PLAN.md` |
| Work plan task | Z-14 |
| Branch | `feat/rag-z14-failure-analysis` |
| Stage | TESTING |
| Started | 2026-11-05 |
| Approved (spec and plan) | 2026-11-05, pre-approved by Zain (no gate for this run) |
| Depends on | phases 10 to 12 merged; `eval/baseline.json` (recall@5 0.875) |

## 1. Objective

Break four of the six pipeline stages (A, C, E, F) on the real stack, one at a time, and write for each what was broken, the symptom, how it would be diagnosed by someone who did not cause it, the remedy, and the exact number or log line that shows it. Restore, and prove the baseline is back.

## 2. Context

- Architecture: 5.14 (map of breaks), 5.6.2 (scope and the superseded filter, AD-11), 5.6.3 (floor), 5.3 and 4.14 (pin, metrics), 5.4.2 (extract and OCR), 5.7.4 (retry and fallback).
- Requirements: R-FAI-A, R-FAI-C, R-FAI-E, R-FAI-F, R-FAI-0 (four of six, only F is the model's fault).
- Rubric: a generic answer scores zero; each stage needs a measured number or a quoted log line.
- Decisions: D-015 (A, C, E, F), D-83 (no experiment flag in the repo), D-84 (reduced corpus, separate collection), D-85 (flush the cache).
- Existing code: `indexer/pipeline/extract.py` (`needs_ocr`, `_ocr_page`), `api/app/services/scope.py` (`scope`), `api/app/main.py` (`/readyz`, pin check), `api/app/config.py`, `eval/retrieval_only.py`, `eval/run_eval.py`.

## 3. Scope

**In scope**

1. Pre-work commits: DEV-007 accepted (done), golden path relative (done), `LLM_TIMEOUT_SECONDS` default 300 (done).
2. Four experiments on the real stack (Chroma :8100, Redis Stack, Ollama `llama3.2:3b` and `nomic-embed-text`).
3. `docs/FAILURE-ANALYSIS.md`, four blocks plus the pin capture.
4. Restore check: `eval/retrieval_only.py recall` against `eval/baseline.json` (within 1 point), `git diff` shows no change to default behaviour.
5. Plan, `AI-USAGE.md`, results register, hand-off to Ahmad about the pin capture.

**Out of scope**

- Stages B and D (cheap extras, not run). Fixes for the findings (hybrid retrieval and similar stay out, 1.2). Any change in `k8s/`, `ui/`, `.github/`.

## 4. Interfaces and contracts

No new code, no new configuration key, no change to a frozen contract. Experiment tooling lives in the job's tmp directory, not in the repo (D-83). Environment variables used: `EMBED_MODEL`, `TOP_K` (not used), `TEMPERATURE`, `CHROMA_COLLECTION`, `RETRIEVER`, `LLM_PROVIDER`, `LLM_TIMEOUT_SECONDS`, `RELEVANCE_FLOOR`, `REDIS_HOST`.

## 5. Behaviour and design details

Common set-up: `CHROMA_HOST=localhost CHROMA_PORT=8100 REDIS_HOST=localhost`, API from `api/` with `RETRIEVER=chroma LLM_PROVIDER=ollama-host OLLAMA_URL=http://localhost:11434 LLM_TIMEOUT_SECONDS=300`, one Ollama job at a time. Capture: the API's JSON log lines (`request_id`, `answered`, `chunk_ids`), `/metrics` (`rahbar_top_score`, `rahbar_fallbacks_total`, `rahbar_abstentions_total`, `rahbar_tokens`), `/readyz`.

| Stage | Break | Question and measure | Expected |
| --- | --- | --- | --- |
| A | Script patches `pipeline.extract._ocr_page` to return `""` and runs the real pipeline on a copy of the policy PDF and the fee page, into `rahbar_exp_a` | indexer log (`ocr_pages`, `document produced no chunks`); a policy question that works at baseline (the eligibility criteria of the start-up policy), top 5 and `top` score against the experiment collection and against the baseline | policy chunks 40 at baseline against 0 or near 0; the question gets other documents' chunks below the floor, so an abstention |
| C | API only: `EMBED_MODEL=hashing-bow-768` (a 768-dimension model, so Chroma would not raise on the query). Then, with the check bypassed in a script, the query vectors of the wrong model against the nomic index | `/readyz` 503 body and the pin log line; best scores and recall of the wrong-model query | pod not ready, `failed:["index"]` style body naming the pin; without the check, wrong rankings and low scores, silently |
| E | Uncommitted one-line edit of `scope.py` so the default scope has no `superseded` filter, reverted with `git checkout` | q12 "What is the deadline to withdraw from a course?" through the API; `chunk_ids` in the `answered` line; retrieval recall of the version type | the 2023 document's chunks appear in `chunk_ids`; the answer can quote the superseded rule |
| F | API only: `TEMPERATURE=1.2` | 3 uncached questions; `rahbar_fallbacks_total`, validation-failure log lines, `rahbar_tokens{direction="out"}`, answer text compared with the baseline answers in `eval/results.json` | more retries, fallbacks or rambling, if the model degrades at all; the number is reported as measured, even if small |

Rules for the write-up: report what happened, not what the architecture predicts. If a break shows no symptom (for example F on a 3B model with a JSON schema), say so with the number. Diagnosis is written as the path from the symptom to the cause using only what a user of the system would see (a metric, a log field, a command), then the stage letter. Say that only F is the model's fault.

Restore: after the last revert, flush Redis, run `eval/retrieval_only.py recall` on the live collection, compare recall@5 with `eval/baseline.json` (0.875, within 0.01), run `git diff` and `git status` to show only docs changed. Drop `rahbar_exp_a`.

## 6. Acceptance criteria

- [ ] **AC-1**: `docs/FAILURE-ANALYSIS.md` has stages A, C, E, F; each lists how it was broken, symptom, diagnosis as if not caused, remedy, and the number or log line, taken from a real run.
- [ ] **AC-2**: The pin demonstration has the `/readyz` 503 body and the log line quoted.
- [ ] **AC-3**: After the last revert, recall@5 is within 1 point of `eval/baseline.json`.
- [ ] **AC-4**: `git diff dev -- api indexer eval` shows no experiment code (only the pre-work commits).
- [ ] **AC-5**: `python3 scripts/check_submission.py | grep -i "failure stages"` shows 4 of 6 or more.
- [ ] **AC-6**: The text says only F is the model's fault.

## 7. Test strategy and traceability

| AC | Level | Command | Needs |
| --- | --- | --- | --- |
| AC-1, AC-2, AC-6 | manual, tester reads the file against the captured outputs in the tmp directory | `docs/FAILURE-ANALYSIS.md` | none |
| AC-3 | integration | `eval/retrieval_only.py recall` | Chroma, Ollama embeddings |
| AC-4 | manual | `git diff dev --stat -- api indexer eval` | none |
| AC-5 | script | `python3 scripts/check_submission.py \| grep -i "failure stages"` | none |
| unit | `make test && make lint` stay green (golden path test added in pre-work) | | none |

## 8. Open questions

| # | Question | Options and recommendation | Decision entry | Answer |
| --- | --- | --- | --- | --- |
| Q1 | Which four stages | A, C, E, F | D-015 | A, C, E, F |
| Q2 | How the breaks are applied | no flag in the repo | D-83 | A |
| Q3 | A on the full corpus or reduced | reduced, separate collection | D-84 | A |
| Q4 | Cache | flush before runs | D-85 | A |

## 9. Risks and assumptions

- Each model call takes 30 to 90 s here (up to 139 s); `LLM_TIMEOUT_SECONDS=300` for all runs. Assumption: the 3B model with schema-constrained output may tolerate temperature 1.2 better than expected; the number is reported either way.
- Experiment A on a reduced corpus: the symptom does not depend on the other documents, but the "top score" comparison is made against the baseline collection for the same question.
- Experiment E edits an api file locally: it must be reverted before the commit (checked by AC-4).

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit message |
| --- | --- | --- | --- | --- |
| 0 | DEV-007, golden path, timeout default | docs, `eval/run_eval.py`, `api/app/config.py` | `make test && make lint` | done |
| 1 | This spec and decisions | `docs/specs/...`, `docs/OPEN_DECISIONS.md` | read | `docs(spec): phase 13 failure analysis` |
| 2 | Experiment A | tmp script | indexer log, retrieval | (notes kept for the write-up) |
| 3 | Experiment C | env only | `/readyz`, log | |
| 4 | Experiment E | temporary edit, reverted | `answered` log line | |
| 5 | Experiment F | env only | metrics | |
| 6 | Restore check | none | recall vs baseline, `git diff` | |
| 7 | Write FAILURE-ANALYSIS.md, plan, AI-USAGE | docs | `check_submission.py` | `docs(failure): four stages measured` |
| 8 | Tester, PR, merge | | | |

### 10.2 Test plan

No new unit tests (no new code). Tester runs `make test && make lint`, checks every number in FAILURE-ANALYSIS.md against the captured logs and `eval/results.json`, runs AC-3 and AC-5.

### 10.3 Rollback and risks

`git checkout -- api/app/services/scope.py` after E. Rebuild the live index with `make`-equivalent indexer run if the collection is damaged (about 10 minutes).

### 10.4 Estimate

2 h in the plan; about 2.5 h with the model latency.

## 11. Implementation notes

Experiments ran as designed (D-83 to D-85). Raw captures are in the job tmp directory (indexer log of A, `/readyz` body and log of C, `answered` lines of E and F, restore output). Decisions taken: the cache was flushed before C, E and F; F was compared with a second run of the same four questions at 0.2 (not planned, added because the answers were not stored in `eval/results.json`). `TOP_K=1` for C was not run. No new code, no deviation; DEV-007 was accepted and absorbed before the experiments, and the `LLM_TIMEOUT_SECONDS` code default moved to 300 to match.

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | 2026-11-05 | Zain (pre-approved) | |
| Tester verdict PASS | | | rounds: |
| Merged | | | PR # |
