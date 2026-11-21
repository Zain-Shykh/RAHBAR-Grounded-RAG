# Phase R5 spec and plan: end-to-end level, stochasticity, one command

| | |
| --- | --- |
| Phase | R5, from `docs/IMPLEMENTATION_PLAN_A3.md` |
| Work plan task | none (A3 plan; Ahmad out, D-108) |
| Branch | `feat/rag-r04-eval-suite` (planned name `feat/rag-r05-e2e-suite`) |
| Stage | IMPLEMENTED BEFORE SPEC (retroactive, D-127). Tested round 1; real runs pending |
| Started | 2026-11-21 |
| Approved (spec and plan) | gate waived (D-124); everything approved as recommended |
| Depends on | R4, A02 API (`/api/ask`, cache, Ollama provider) |

## 1. Objective

The answer-level measurements, the two-run reproducibility report and one command that runs all three levels and writes one timestamped result. The plan's LLM judge is dropped (D-115): faithfulness is a deterministic overlap score.

## 2. Context

- Architecture: `architecture-a3.md` 6.4 to 6.6, AD-36, AD-38, A3-R3, A3-R4.
- Requirements: R3-B-6, R3-B-8, R3-B-9. R3-B-7 applies only "if an LLM judges faithfulness"; no judge is used, so it does not apply (D-115, D-126).
- Decisions: D-115 (no judge; overlap threshold 0.6 to be calibrated), D-117 (seeds and cache bypass).
- Code: `eval/suite/e2e_level.py`, `run_suite.py`, `stochasticity.py`, `client.py`, `job.py`, `compare.py`; API `config.py` (`LLM_SEED`), `providers/llm/ollama.py`, `routes/ask.py`; `Makefile` targets `suite`, `suite-twice`.

## 3. Scope

**In scope**: `LLM_SEED` into Ollama `options.seed`; `X-Cache-Bypass: 1`; e2e metrics; the one command with `.json` and `.md` output; stochasticity compare; `make suite`, `make suite-twice`; the cluster Job entry point `job.py` (manifests belong to R8).

**Out of scope**: the LLM judge and its hand labels (dropped, D-115); the gate (R7); calibration of the 0.6 threshold and the two real runs (pending, below).

## 4. Interfaces and contracts

- `LLM_SEED` env: integer; empty or unset means none. When set, Ollama request carries `options.seed`; unset means no `seed` key (A02 behaviour).
- `X-Cache-Bypass: 1` request header: the route passes `cache=None, bypass=True`, response header `X-Cache: SKIP`, trace `cache: "bypassed"`.
- `e2e_level.run(api, rows, threshold=0.6) -> dict` keys: `n, abstention_correctness, abstention_n, abstention_failed, false_abstention_rate, citation_validity, citations_total, faithfulness_overlap_mean, faithfulness_supported_rate, support_threshold, answered_n, expect_hit_rate, fallback_rate, latency_p50_s, latency_p95_s, per_question[]`.
- `python -m eval.suite.run_suite --api URL --label L --subset A|B|all [--seed N] [--skip-e2e] [--out DIR]` writes `eval/results/suite-<UTC>-<label>.json` and `.md`; exit 0 ran, 1 on any exception (`SUITE FAILED`). `python -m eval.suite.stochasticity A.json B.json` writes `stochasticity-<ts>.json`.
- Cluster: `eval.suite.job` env `API_URL, RUN_LABEL, SUBSET, SEED, RESULTS_DIR, BASELINE, GATE_CONFIG, SET_BASELINE`; exit 0 pass, 1 gate failed, 2 unusable.

## 5. Behaviour and design details

- Faithfulness: share of the answer's content tokens (stop words removed, tokens of 2 or more characters) found in the text of the passages it cites; passages are fetched from `/api/retrieve` for the same question. Supported means overlap at or above 0.6.
- Abstention correctness is the share of unanswerable questions that were not answered; false abstention rate is the share of answerable questions not answered.
- Citation validity reuses A02 `_citation_counts` (same source and section as a retrieved passage).
- Every question is asked with the cache bypassed so runs are comparable. The suite never writes a result file if a level raises.
- Stochasticity compares per-metric absolute difference and lists question ids whose answer text differed, and those whose outcome or citations differed.

## 6. Acceptance criteria

- [x] **R5-AC1** With `LLM_SEED` set, `options.seed` is in the Ollama request; unset means no `seed` key.
- [x] **R5-AC2** `X-Cache-Bypass: 1` never reads or writes the cache and returns `X-Cache: SKIP`; without it behaviour is A02's (A02 cache tests unchanged).
- [ ] **R5-AC3** One command runs module, component (clean and noisy) and e2e levels and writes the timestamped JSON and `.md` table with all three levels.
- [ ] **R5-AC4** The e2e section reports faithfulness (overlap), abstention correctness, false abstention rate, citation validity, p50 and p95 with counts (numerator or denominator) in the file.
- [ ] **R5-AC5** (plan: 12 hand labels and kappa) NOT APPLICABLE: no LLM judge (D-115). The overlap threshold 0.6 is calibrated on real answers (pending real run; the report names overlap as the metric trusted least).
- [ ] **R5-AC6** `make suite-twice` produces two result files and `stochasticity-<ts>.json` with per-metric absolute difference and the differing questions; explanation committed in section 12 (pending real runs).
- [x] **R5-AC7** The suite exits non-zero when the API is unreachable or a level fails, with a clear message and no result file.
- [ ] **R5-AC8** `make test` green; `make eval-fixtures` gate green (needs a local API with the CI embedder; pending, port 8000 is in use by a real run).

## 7. Test strategy and traceability

| AC | Level | Test file and name, or command | Needs |
| --- | --- | --- | --- |
| AC1 | unit | `api/tests/test_eval_support.py::test_seed_setting_from_env`, `::test_seed_in_ollama_options_only_when_set` | nothing |
| AC2 | unit | `api/tests/test_eval_support.py::test_cache_bypass_header_reports_skip`; `api/tests/test_trace_adversarial.py::test_bypass_trace_says_bypassed_and_route_never_touches_the_cache`; A02 `api/tests/test_cache_answer.py` unchanged | nothing |
| AC3 | unit (fakes) / integration | `eval/tests/test_suite_adversarial.py::test_one_command_writes_both_files_with_all_three_levels`; real: `make suite` | Ollama, stack for real |
| AC4 | unit (fakes) | same test (asserts every e2e number) | nothing |
| AC5 | n/a | D-115 | |
| AC6 | unit / integration | `eval/tests/test_suite_metrics.py::test_stochasticity_compare`; real: `make suite-twice` | stack |
| AC7 | unit | `test_suite_adversarial.py::test_suite_exits_nonzero_and_writes_no_file_when_api_is_down` | nothing |
| AC8 | command | `make test`; `make eval-fixtures` | local API for the second |

## 8. Open questions

| # | Question | Options and recommendation | Decision entry | Answer |
| --- | --- | --- | --- | --- |
| Q1 | LLM judge or overlap only? | overlap only (time, no hand labels) | D-115 | DECIDED: no judge |
| Q2 | Seeds and cache bypass | `LLM_SEED`, `X-Cache-Bypass` | D-117 | PROVISIONAL, accepted |

## 9. Risks and assumptions

- Overlap is a weak proxy: a faithful paraphrase scores low, a copied but wrong passage scores high. The report must say so.
- The passages used for overlap come from a second `/api/retrieve` call, not from the exact context of the answered request (same question, same index, so normally identical; differs if the injection rail dropped a passage). The trace holds the exact context.
- Each question takes 75 to 110 s on this CPU, so a full run is long; `--subset A` is the default.
- `--skip-e2e` writes a partial file with an empty e2e section; the gate then fails on missing metrics (intended).

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit message |
| --- | --- | --- | --- | --- |
| 1 | `LLM_SEED`, bypass header | `api/app/config.py`, `providers/llm/ollama.py`, `routes/ask.py` | `test_eval_support.py` | `feat(api): llm seed and cache bypass` |
| 2 | e2e level | `e2e_level.py`, `client.py` | tests | `feat(eval): end-to-end level` |
| 3 | one command, table | `run_suite.py`, `Makefile` | fake-API test | `feat(eval): one command suite` |
| 4 | stochasticity | `stochasticity.py` | test | `feat(eval): two-run difference` |
| 5 | real baseline twice | `eval/results/` | register | (pending) |

### 10.2 Test plan
Unit tests with mock transport and fake API; independent tester runs the whole suite offline against a fake API.

### 10.3 Rollback and risks
Seed and bypass are opt-in; reverting leaves A02 behaviour.

### 10.4 Estimate
Plan estimate 7 h (judge work removed).

## 11. Implementation notes

- Implemented by the orchestrator session before this spec (D-127). The judge, its labels and kappa were not built (D-115). ConfigMap key `LLM_SEED` and the API additions are recorded under DEV-017.
- `job.py` is the Job entry point used by R8.

## 12. Test report

Round 1, 2026-11-21, branch `feat/rag-r04-eval-suite`, base 64464d3. No Ollama, docker, network.

| AC | Result | Evidence |
| --- | --- | --- |
| R5-AC1 | PASS | `api/tests/test_eval_support.py` 2 tests pass (`seed` key only when set; env `""` gives None) |
| R5-AC2 | PASS | `test_cache_bypass_header_reports_skip` (header `X-Cache: SKIP`); trace shows `bypassed`; A02 cache tests all pass unchanged. Note: the route, not the service, enforces no cache use (`cache=None if bypass`); `answer_question(cache=c, bypass=True)` would still look up (not reachable from HTTP). |
| R5-AC3 | PARTIAL | offline run with fake API and fake embedder writes `suite-<ts>-t.json` and `.md` with Module, Component, End-to-end sections; real `make suite` pending |
| R5-AC4 | PASS (code) | e2e dict asserted: abstention 1.0, false abstention 0.0, citation validity 1.0 with `citations_total`, overlap mean, supported rate, expect hit rate, p50 and p95; counts `abstention_n`, `answered_n`, `citations_total` present; the numerator for the supported rate is not stored (derivable from `per_question`) |
| R5-AC5 | N/A | D-115 no judge. Threshold calibration pending real answers |
| R5-AC6 | PENDING | `compare` unit-tested; `make suite-twice` and the explanation need two real runs |
| R5-AC7 | PASS | `test_suite_exits_nonzero_and_writes_no_file_when_api_is_down`: exit 1, `SUITE FAILED` on stderr, no `.json` |
| R5-AC8 | PARTIAL | `make test` green (api 330 passed, 19 skipped, 5 xfailed; eval 139 passed, 3 xfailed); `make eval-fixtures` not run (needs its own API; port 8000 is busy with a real run) |

Extra tests: `eval/tests/test_suite_adversarial.py::test_one_command_writes_both_files_with_all_three_levels`, `::test_suite_exits_nonzero_and_writes_no_file_when_api_is_down`, `api/tests/test_trace_adversarial.py::test_bypass_trace_*`.

Defects found:

- **T-6 (info)** overlap context is a second retrieval, see section 9. No action needed unless the rail is on during a run.
- **T-2 (medium, shared with R7)** `eval/suite/job.py` and `gate.py` do not catch `yaml.YAMLError` (see R7).

Coverage: `app` 98%; `eval/suite` has no target.

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-21 | `make test`; offline suite probe | PASS with pending items | pending: AC3 real, AC5 calibration, AC6, AC8 fixtures |

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | 2026-11-21 | waived (D-124, D-127) | retroactive |
| Tester verdict PASS | | | round 1: PASS for code ACs; real runs pending |
| Merged | | | |
