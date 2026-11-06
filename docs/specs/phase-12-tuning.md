# Phase 12 spec and plan: Tuning, calibration, baselines

| | |
| --- | --- |
| Phase | 12, from `docs/IMPLEMENTATION_PLAN.md` |
| Work plan task | Z-12 |
| Branch | `feat/rag-z12-tuning` |
| Stage | READY FOR PR |
| Started | 2026-11-05 |
| Approved (spec and plan) | 2026-11-05, pre-approved by Zain (no gate for this run) |
| Depends on | phases 6 to 11 merged; hand-offs H-7, H-8 are outputs |

## 1. Objective

Choose the shipped numbers (`CHUNK_SIZE`, `CHUNK_OVERLAP`, `RELEVANCE_FLOOR`, `TOP_K`) by measurement, and commit the two baselines that gate CI and the submission. Hand the values to Ahmad (H-7, H-8).

## 2. Context

- Architecture: 5.4.2 (chunk), 5.6.3 (floor, AD-12), 5.9.3 (threshold, already measured in phase 11, D-73), 5.13.2 to 5.13.5 (metrics, gate, two baselines, experiments). Invariants I-5 (floor abstains with no model call), I-9 (citation validity), I-16.
- Requirements: R-IDX-7 (three configurations, table, justification), R-CAC-3 (threshold: done in phase 11; this phase only records demo paraphrase pairs), R-EVA-2 (recall@3, @5 overall and by type), R-EVA-6 (run, results.json, baseline.json).
- Rubric: "a sensible number with no measurement scores zero"; abstention must be 100%; exact-term recall gap is a required finding.
- Existing code: `indexer/pipeline/run.py` (reads `CHUNK_SIZE`, `CHUNK_OVERLAP`), `eval/run_eval.py` (`summarise`, `gate`, `--update-baseline`), `eval/retrieval_only.py` (recall without the model, same `summarise`), `scripts/calibrate_cache.py`, `scripts/live_check_phase10.py`.
- Decisions: D-76 to D-80 in `OPEN_DECISIONS.md`. Phase 10 left the hostel questions (q16, q17) with top scores 0.655 and 0.658, above the 0.50 floor; the live model abstained on its own.

## 3. Scope

**In scope**

1. Pre-work commits: DEV-004 absorbed; `ChromaRetriever._passages` malformed row becomes `IndexUnavailable` (done, 178d610 and 9583a00).
2. Chunking experiment at 200/25, 400/50, 600/100: re-index locally, record chunk count, amplification, recall@3 and @5 overall and by type, per-question best scores. Choose one.
3. Relevance floor from the per-question best scores (answerable versus must-abstain). Set it as the API default (`api/app/config.py`) and in the spec of H-7.
4. Real-model run of the chosen configuration through `eval/run_eval.py` against the local API: `eval/baseline.json`, `eval/results.json` (`--update-baseline`). Citation validity 100%, abstention 100%.
5. Fixture baseline `eval/fixtures/baseline.fixture.json` in CI mode.
6. Two or more real paraphrase pairs that hit the cache at 0.96, for the demo.
7. Exact-term finding (q10, q14) written up.
8. Docs: `PIPELINE.md` (chunking table, floor, cache pairs, evaluation method), results register, H-7 and H-8, `AI-USAGE.md`, deviations.

**Out of scope**

- Re-calibrating the cache threshold (done in phase 11, 0.96).
- Failure experiments (phase 13); new features; hybrid retrieval; edits to `eval/golden.yaml` (only a demonstrably wrong question, logged).
- `k8s/`, `ui/`, `.github/` (Ahmad). Changes needed there are hand-offs.

## 4. Interfaces and contracts

- `eval/retrieval_only.py recall` additionally prints and writes per-question `scores` (`top`, `hit`). Own lane (D-60). No other interface changes.
- Config defaults that may change: `api/app/config.py` `relevance_floor`, `top_k` (only if measured), `indexer/pipeline/config.py` `chunk_size`, `chunk_overlap` defaults. Contract C-2 (ConfigMap keys) is unchanged: same keys, new values, passed to Ahmad in H-7.
- Files created: `docs/specs/phase-12-tuning.md`, `eval/tuning/chunk-<size>-<overlap>.json`, `eval/baseline.json`, `eval/results.json`, `eval/fixtures/baseline.fixture.json`, `eval/fixtures/results.fixture.json`.

## 5. Behaviour and design details

**Chunking runs.** For each pair: `CHUNK_SIZE`, `CHUNK_OVERLAP` set, `python -m pipeline.run` on `corpus/raw` into local Chroma :8100 with the real `nomic-embed-text` (stage-and-swap, so the live collection is always complete); then `eval/retrieval_only.py recall --json`. Recall@k comes from the `retrieved` list the retriever builds before any model call, so it is identical to what `run_eval.py` computes through the API (same `summarise`). Chunk count and amplification come from the indexer log. The full model run is done on the chosen configuration (D-76).

**Choice rule (D-77).** Highest recall@5 overall; tie: higher recall@3; tie: fewer chunks (smaller prompt, cheaper index); then stored-word amplification. The justification cites the numbers and the per-question misses.

**Floor rule (D-78, AD-12).** Let `A_min` be the lowest "hit" score among answerable questions that have a retrieved golden passage, `X_max` the highest top score among must-abstain questions. If `X_max < A_min`, floor = midpoint rounded to 0.01. Answerable questions whose golden passage was not retrieved (q10, q14) cannot be saved by any floor; their top score is listed. If ranges overlap, choose to keep abstention at 100% and state the answerable questions lost. The floor is not the only defence (the model can abstain), but the target is that both hostel questions are abstained by the floor with no model call.

**Baselines.** Real: the chosen configuration, indexed, API started with `RETRIEVER=chroma LLM_PROVIDER=ollama-host RELEVANCE_FLOOR=<chosen>`, Redis up, run `eval/run_eval.py --api http://localhost:8000 --update-baseline`. The cache is cleared (index re-built) before the run so latencies are model latencies. Fixture: `EMBED_MODEL=hashing-bow-768 LLM_PROVIDER=extractive CORPUS_DIR=eval/fixtures`, index with the same chunk configuration, run `eval/run_eval.py --golden eval/fixtures/golden.fixture.yaml --baseline eval/fixtures/baseline.fixture.json --out eval/fixtures/results.fixture.json --update-baseline`; then a second run without `--update-baseline` must exit 0 (gate passes against its own baseline).

**Prompt wording.** Only if the real run shows answers too terse ("No", "60%"): adjust the instruction text in `api/app/services/prompt.py`, then re-run the golden set and show recall, citation validity and abstention did not worsen (D-79).

**Golden set.** Never edited to improve numbers.

## 6. Acceptance criteria

- [x] **AC-1**: Three-row chunking table (size, overlap, chunks, amplification, recall@3, recall@5, by type), the shipped pair, and a one-paragraph justification, in the results register and `PIPELINE.md`.
- [x] **AC-2**: `RELEVANCE_FLOOR` chosen with the answerable and must-abstain score ranges listed per question; both hostel questions abstain on the real run; trade-off stated.
- [x] **AC-3**: At least two real paraphrase pairs that hit the cache at 0.96 recorded (question, paraphrase, similarity, `X-Cache: hit`).
- [x] **AC-4**: `eval/baseline.json`, `eval/results.json` committed from the real run; `eval/fixtures/baseline.fixture.json` committed; both gates pass against their own baseline (`run_eval.py` exit 0); `baseline.json` contains `recall_at_5`.
- [x] **AC-5**: Real run: citation validity 100%, abstention correctness 100%; fallback rate and latency p50, p95 recorded.
- [x] **AC-6**: recall@3 and @5 overall and by type, and the exact-term finding with its explanation, in the results register.
- [x] **AC-7**: H-7 and H-8 text written (ConfigMap values with justifications, fixture baseline).
- [x] **AC-8**: `make test && make lint` green; the malformed-row test passes; DEV-004 ABSORBED.
- [x] **AC-9**: The shipped chunk configuration equals the indexer defaults and the value given in H-7.

## 7. Test strategy and traceability

| AC | Level | Test or command | Needs |
| --- | --- | --- | --- |
| AC-1 | manual | `eval/retrieval_only.py recall` per config, JSON in `eval/tuning/` | dev-services, Ollama |
| AC-2 | manual | scores table in `eval/tuning/chunk-<chosen>.json`; `live_check_phase10.py ask q16 q17` shows `abstain_reason=below_floor` | same |
| AC-3 | manual | `scripts/live_check_phase11.py` or two `/api/ask` calls with `X-Cache` | same plus Redis |
| AC-4 | manual | `run_eval.py ... ; echo $?` twice | same, API running |
| AC-5 | manual | `eval/results.json` fields | same |
| AC-6, AC-7 | doc | results register, H-7, H-8 | |
| AC-8 | unit | `api/tests/test_retriever.py::test_malformed_row_is_index_unavailable`; `make test && make lint` | nothing |
| AC-9 | unit | a test asserting `indexer` defaults and `api` `relevance_floor` default equal the chosen values (`api/tests/test_config_defaults.py`) | nothing |

## 8. Open questions

None are blocking. All decisions are recorded as D-76 to D-80 (decided by Claude, pre-approved by Zain).

## 9. Risks and assumptions

- Model latency (30 to 90 s per question) makes a full run 10 to 30 minutes; run in the background, one Ollama job at a time.
- 18 questions is a small set: the floor sits between 0.658 and 0.746 on the current index; the margin is stated, the risk of over-fitting is noted.
- The chosen chunk size changes the index: the cluster Job must run with the same `CHUNK_SIZE`, `CHUNK_OVERLAP` (H-7).
- A run that moves the abstention score is investigated, not tuned away.

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit |
| --- | --- | --- | --- | --- |
| 0 | DEV-004 absorbed; malformed row to 503 (done) | architecture, deviations, `chroma.py`, test | `make test` | done |
| 1 | This spec; scores in `retrieval_only.py` | spec, `eval/retrieval_only.py` | `make lint` | `docs(spec): phase 12 tuning spec and plan` |
| 2 | Three chunking runs (background) | `eval/tuning/*.json` | recall output | `test(eval): chunking experiment results` |
| 3 | Choose chunking; set defaults; config-defaults test | `indexer/pipeline/config.py`, tests | `make test` | `feat(indexer): ship chunk size X/Y` |
| 4 | Floor from scores; set default | `api/app/config.py`, test | `make test` | `feat(api): relevance floor Z from golden scores` |
| 5 | Real run, update baseline; fix if citation or abstention below 100% | `eval/baseline.json`, `eval/results.json` | exit 0 | `test(eval): real-corpus baseline` |
| 6 | Cache demo pairs | doc | two `X-Cache: hit` | `docs: cache demo pairs` |
| 7 | Fixture baseline in CI mode | `eval/fixtures/*.json` | exit 0 twice | `test(eval): fixture baseline` |
| 8 | Docs: PIPELINE, register, H-7, H-8, AI-USAGE, deviations, decisions | docs | `make check` | `docs: phase 12 results` |
| 9 | Independent tester, up to 3 rounds; PR; merge | spec section 12 | PASS | `test: phase 12 report` |

### 10.2 Test plan

Unit: malformed row (done), config-defaults test. The testing subagent runs `make test`, `make lint`, coverage, re-runs `retrieval_only.py recall` on the shipped index and checks that the numbers match the register, runs both gates, and tries abstention edge cases against the floor.

### 10.3 Rollback and risks

Defaults are one-line edits; baselines are regenerated by one command. A failed step is reverted on the branch.

### 10.4 Estimate

3 h of work plus about 1.5 h of unattended model time. Within the plan estimate plus the long unattended runs.

## 11. Implementation notes

- **Method (D-76).** The three chunking rows come from `eval/retrieval_only.py recall` (retrieval only, same `summarise`), not from three full model runs; the full real-model `run_eval.py` run was done once on the shipped configuration. Recall does not depend on the model, so the numbers are the same; the scores table was added to `retrieval_only.py` for the floor.
- **Chunking result (D-81).** The three pairs tie exactly (recall@3 = recall@5 = 0.875, every question's best score within 0.011); 400/50 stays. D-77's literal tie-break (fewer chunks) would have chosen 600/100 (3% fewer); D-81 amends the rule and says why.
- **Floor.** 0.70 (D-78). Both hostel questions now stop at the floor (0.1 to 0.3 s, no model call). Default changed in `api/app/config.py` (dataclass and env default).
- **Bug found and fixed (D-82).** The fixture run scored recall 0: the Markdown extractor kept `#` marks, so `## 1. Attendance` was never a heading. `strip_md_markers` in `indexer/pipeline/extract.py`; one existing test expectation (`test_markdown_and_unknown_suffix`) changed from `# H` to `H` because the behaviour it described ("headings stay") is what was wrong. No PDF or HTML path changes, so the real index is unaffected. Not a deviation from the architecture (5.4.2 lists Markdown as a source); noted here and in D-82.
- **Fixture CI floor.** The fixture embedder scores 0.00 to 0.43, so the `ci` overlay needs `RELEVANCE_FLOOR=0.20` (H-8). The fixture baseline was produced with that floor.
- **Prompt (D-79).** Answers are terse ("No", "60%", "10"). A schema `description` on `Answer.answer` was tried on four questions and did not change them; reverted. The prompt text is unchanged from phase 10, so no re-run was needed to show that recall, citations and abstention did not get worse.
- **Also changed.** `eval/run_eval.py` HTTP client timeout 120 s to 300 s (the API's own model timeout is 300 s; q04 and q09 took 123 s and 139 s). DEV-004 absorbed; `ChromaRetriever` malformed row becomes `IndexUnavailable` (503) with a test.
- **Observed, not changed.** After a Redis `FLUSHALL` under a running API, the first lookup logs `cache unavailable ... No such index idx:cache:<id>` and the answer is served uncached; caching resumed within two requests. Worth knowing for a Redis pod restart without its PVC; no action in this phase.

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-05 | `make test`, `make lint`, `--cov=app`, `retrieval_only.py recall` on the live index, live fixture gate (no `--update-baseline`), 2 real questions, 4 added test groups | PASS, AC-1 to AC-9 | Defect T12-D1 (NaN best score passed the floor, I-5): fixed in `answer.py` (`not (best >= floor)`), xfail removed. Two doc nits (q10 scores 0.821 and 0.811; stale chunk line in PIPELINE.md) fixed. After fixes: api 282 passed, indexer 257, eval 90. Coverage api 97%, indexer 97% |

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | 2026-11-05 | Zain (pre-approved, no gate this run) | |
| Tester verdict PASS | 2026-11-05 | independent subagent | rounds: 1 |
| Merged | 2026-11-05 | Claude (pre-approved by Zain) | PR #17 |
