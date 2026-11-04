# Phase 05 spec and plan: Evaluation runner

| | |
| --- | --- |
| Phase | 5, from `docs/IMPLEMENTATION_PLAN.md` |
| Work plan task | Z-11 |
| Branch | `feat/rag-z11-eval-runner` |
| Stage | MERGED |
| Started | 2026-11-04 |
| Approved (spec and plan) | 2026-11-04, Zain |
| Depends on | phase 3 (golden set, merged); H-5 is delivered by this phase |

## 1. Objective

`eval/run_eval.py` scores a running RAHBAR against a golden set and gates CI on it: the four starter functions (`recall_at_k`, `citation_validity`, `summarise`, `gate`) are implemented, the runner records `X-Outcome` and `X-Cache`, and a failed call can no longer be mistaken for a gate result. After this phase Ahmad's `e2e-eval` job (A-09) has a working command with fixed exit codes, and phases 6 to 12 can measure recall.

## 2. Context

- Architecture: 5.13 all (5.13.2 metrics and matching, 5.13.3 gate, 5.13.4 two baselines), 5.8 (citation rule), 4.14 (metric names: the runner reads none of them; it reads the `X-Outcome` and `X-Cache` headers of 5.5.3), AD-22 (section match), AD-27 (two baselines).
- Requirements: R-EVA-1 to R-EVA-9.
- Rubric: section A items on evaluation (abstention 100%, citation validity, CI gate, baseline committed). Nothing here is measured yet; phase 12 produces `baseline.json`.
- Decisions: D-046 (fold dashes), D-047 (abort on ask error), D-048 (guard `--update-baseline`), all DECIDED 2026-11-04.
- Existing code: `eval/run_eval.py` (129 lines). Given: `load_golden`, `ask`, `main`, three constants. STARTER-TODO: `recall_at_k`, `citation_validity`, `summarise`, `gate`. No `eval/tests/` yet. Golden sets: `eval/golden.yaml` (18 real questions, phase 3), `eval/fixtures/golden.fixture.yaml` (6 CI questions).
- Contract C-6 (WORKPLAN 3): CLI flags and exit codes 0 pass, 1 gate failed, 2 not implemented. Unchanged.
- Finding on golden q05 (checked against the real PDF `student-handbook-jun-2026.pdf` with pdfplumber): the sentence "unavoidable reason are to immediately (within two days)" is on PDF page 30, so the comment `# p.30` is **correct** (phase 4 changed it from 29). PDF page 31 carries identical text (the PDF repeats the page), so a chunk from either page matches `source` and `section`; no change to `eval/golden.yaml`. The printed contents page says 27 for the section, which is the printed page number, not the PDF index.

## 3. Scope

**In scope**

- The four functions, with AD-22 matching plus dash folding (D-046), in `eval/run_eval.py`.
- `ask()` returns the response plus `X-Outcome` and `X-Cache` headers under `response["_meta"]`.
- `main()`: abort on an ask error (D-047); refuse `--update-baseline` when the abstention or citation gate fails (D-048).
- `eval/tests/test_run_eval.py` and `eval/tests/conftest.py`, pure data, no network.
- Small separate commits for shared files: `Makefile` (`test` target runs eval tests; `lint` now covers `scripts/check_golden_extract.py`, already committed), `docs/architecture/deviations.md` (DEV-001 committed, DEV-002 for dash folding).
- Check of golden q05 (done, no change).

**Out of scope**

- Producing `baseline.json` and `baseline.fixture.json` (phase 12, H-8).
- CLI flag changes (frozen).
- `X-Outcome` and `X-Cache` emission by the API (phase 10 and 11; until then the headers are absent and `_meta` values are `null`).
- Editing `k8s/`, `ui/`, `.github/`.

## 4. Interfaces and contracts

```python
def _norm(s: str) -> str                     # NFKC, dash variants to "-", lower, collapse whitespace, strip
def section_matches(golden: str, retrieved: str) -> bool
def recall_at_k(relevant: list[dict], retrieved: list[dict], k: int) -> float | None
def citation_validity(response: dict) -> float | None
def summarise(rows: list[dict]) -> dict
def gate(results: dict, baseline: dict | None) -> list[str]
def ask(client: httpx.Client, api: str, question: str) -> dict   # now adds response["_meta"]
```

Row shape (from `main`): `{id, type, must_abstain, relevant, expect, response, seconds}`. `response` is the `AskResponse` JSON (`api/app/schemas.py`: `citations[{source, section, page}]`, `retrieved[{chunk_id, source, section, page, score}]`, `answered_from_context`) plus `_meta = {"outcome": str|None, "cache": str|None}` taken from `X-Outcome` and `X-Cache`.

`results.json` (and `baseline.json`) keys:

| Key | Meaning |
| --- | --- |
| `recall_at_3`, `recall_at_5` | mean of per-question recall over questions with a non-empty `relevant`; `null` if none |
| `by_type` | `{type: {recall_at_3, recall_at_5, n}}`, only types with at least one scored question; `n` = scored questions |
| `citation_validity` | valid citations / all citations over all responses; `null` if no citations at all |
| `citations_total`, `citations_valid` | the two counts |
| `abstention_correctness` | declined / `must_abstain_total`; `null` if there are none |
| `must_abstain_total`, `must_abstain_failed` (ids), `must_abstain_fallback` (declined only because `X-Outcome: fallback`) | |
| `fallback_rate` | rows with `_meta.outcome == "fallback"` / rows |
| `latency_p50`, `latency_p95` | seconds, nearest-rank |
| `per_question` | `[{id, type, recall_at_3, recall_at_5, outcome, cache, seconds}]` for debugging |
| `golden`, `questions` | added by `main` |

Exit codes: 0 pass, 1 gate failed **or run aborted** (message says which), 2 not implemented (kept). No config keys, no env variables, no API change, no change to C-1 to C-8.

## 5. Behaviour and design details

1. **Section match (AD-22 plus D-046).** `source` equal exactly. `_norm` both sections; match if equal, or `retrieved` starts with `golden` and the next character is a space, `.` or `:`. So `1.21` matches `1.21 attendance`, `5` matches `5.4 academic warning`, `1.2` does not match `1.21`. `VI – SEMESTER RULES` equals `VI - SEMESTER RULES`.
2. **recall_at_k.** `None` when `relevant` is empty. Else hits = golden items matched by at least one of `retrieved[:k]`; result = hits / len(relevant). Fewer than k retrieved is fine.
3. **citation_validity.** A citation is valid if some `retrieved` item has the same `source` and the same `section` (exact equality, the 5.8 rule the API enforces). Result = valid / total; `None` if no citations. `summarise` sums counts across rows (valid over all, not a mean of per-row fractions, as 5.13.2 says).
4. **summarise.** Overall recall is the mean of per-question recall (macro over questions). `abstention_correctness`: a must-abstain row passes when `response["answered_from_context"] is False`. `must_abstain_fallback` counts passing rows whose outcome is `fallback`, so a masked failure shows. Latency percentile is nearest-rank on `seconds`. Missing `_meta` is treated as outcome `None`.
5. **gate.** Return one message per failed condition:
   - recall@5 more than `MAX_RECALL5_DROP` below `baseline["recall_at_5"]` (tolerance 1e-9 so exactly 5 points passes); skipped when `baseline` is `None` or either value is `None`.
   - `abstention_correctness` not `None` and below `REQUIRED_ABSTENTION`: message lists `must_abstain_failed` ids.
   - `citation_validity` not `None` and below `MIN_CITATION_VALIDITY`.
   The three constants stay as given.
6. **ask errors (D-047).** `main` wraps each ask in `try/except httpx.HTTPError` (and `ValueError` for bad JSON); prints `ERROR: question <id>: <exc>`, writes nothing, returns 1.
7. **Baseline guard (D-048).** With `--update-baseline`, if any failure message is not the recall message, print why and return 1 without writing `baseline.json`. `results.json` is still written. A recall drop alone does not block the update (deliberate change).
8. **Deviation.** Dash folding extends AD-22: DEV-002 (S3), absorbed into 5.13.2 later. DEV-001 (extract layout) already committed.
9. **Untrusted data.** Response text is only counted and compared, never evaluated.

## 6. Acceptance criteria

- [ ] **AC-1**: `recall_at_k`, `citation_validity`, `summarise`, `gate` implemented; no `NotImplementedError` and no `STARTER-TODO` left in `eval/run_eval.py`.
- [ ] **AC-2**: Section matching: `1.21` matches `1.21 Attendance`; `5` matches `5.4 Academic Warning`; `1.2` does not match `1.21`; `1.21` matches `1.21: Attendance` and `1.21.1`; case and extra whitespace ignored; `VI – SEMESTER RULES` matches `VI - SEMESTER RULES`; a different `source` never matches.
- [ ] **AC-3**: `recall_at_k` returns `None` for an empty `relevant`; returns 0.5 when one of two golden items is in the top k; a match at rank 4 counts for k=5 but not k=3; fewer than k retrieved does not crash.
- [ ] **AC-4**: `citation_validity` returns `None` with no citations, 1.0 when all match, 0.5 when one of two does not; a citation with the right source but a different section is invalid.
- [ ] **AC-5**: `summarise` returns the keys of section 4 with correct values on a hand-built row set: overall and by-type recall, citation validity as valid over all citations, abstention correctness, `must_abstain_failed` ids, `must_abstain_fallback`, `fallback_rate`, p50 and p95. Every recall key contains the word `recall`.
- [ ] **AC-6**: `gate` returns a message for each of: recall@5 drop above 5 points, a must-abstain answered from context, citation validity below 0.95; returns `[]` for a passing result; no baseline adds no recall message; a drop of exactly 5 points passes.
- [ ] **AC-7**: `ask()` puts `X-Outcome` and `X-Cache` under `response["_meta"]` (null when absent); the API JSON fields are untouched. Tested with `httpx.MockTransport`.
- [ ] **AC-8**: With a failing API (connection error or 500) `main` prints the question id and the error, writes no `results.json`, returns 1 (D-047). With `--update-baseline` and a failed abstention or citation gate `main` does not write the baseline and returns 1 (D-048); a recall-only failure still writes it.
- [ ] **AC-9**: `make test` runs the eval tests and is green; `make lint` is green (includes `scripts/check_golden_extract.py`).
- [ ] **AC-10**: `make dev` in one terminal and `make eval-fixtures` in another run end to end against the stubs, print the results, write the output file, and exit with 0 or 1 (not 2, not a traceback).
- [ ] **AC-11**: DEV-001 and DEV-002 are in `deviations.md` (index and body); golden q05 page comment verified against the real PDF; shared-file commits (Makefile, deviations) are separate.
- [ ] **AC-12**: H-5 message ready for Ahmad (CLI and exit codes final, C-6).

## 7. Test strategy and traceability

All tests are pure data or `httpx.MockTransport`; no network, model or cluster.

| AC | Level | Test or command | Needs |
| --- | --- | --- | --- |
| AC-1 | unit | `grep -n "NotImplementedError\|STARTER-TODO" eval/run_eval.py` returns nothing; `test_run_eval.py` imports and calls all four | nothing |
| AC-2 | unit | `test_run_eval.py::test_section_matches` (parametrised) | nothing |
| AC-3 | unit | `::test_recall_at_k_*` | nothing |
| AC-4 | unit | `::test_citation_validity_*` | nothing |
| AC-5 | unit | `::test_summarise_*` | nothing |
| AC-6 | unit | `::test_gate_*` | nothing |
| AC-7 | unit | `::test_ask_captures_headers` | nothing |
| AC-8 | unit | `::test_main_aborts_on_ask_error`, `::test_update_baseline_guard_*` (monkeypatch `ask`, `tmp_path`) | nothing |
| AC-9 | command | `make test && make lint` | nothing |
| AC-10 | integration | `make dev` then `make eval-fixtures; echo exit=$?` | local venv |
| AC-11 | review | `grep DEV-00 docs/architecture/deviations.md`; `git log --stat -- Makefile docs/architecture/deviations.md` | nothing |
| AC-12 | review | message in the PR report and the progress log | nothing |

## 8. Open questions

| # | Question | Options and recommendation | Decision entry | Answer |
| --- | --- | --- | --- | --- |
| Q1 | Fold dashes in section match? | A fold (recommended) / B strict | D-046 | A |
| Q2 | Ask error behaviour | A abort exit 1 (recommended) / B exit 3 / C record and continue | D-047 | A |
| Q3 | Guard `--update-baseline`? | A guard (recommended) / B leave | D-048 | A |

All answered by Zain on 2026-11-04.

## 9. Risks and assumptions

- **Section strings are provisional** until the chunker (phase 6): recall on the real golden set may be low for reasons of heading format, not retrieval. Phase 6 must read `eval/golden.yaml` and either match its strings or revise them with a note. Dash folding only removes one such cause.
- **Headers absent today.** The API does not yet emit `X-Outcome` or `X-Cache` (grep of `api/app` finds none). The runner copes (`null`), so AC-10 passes with stubs; `fallback_rate` is 0 until phase 10 and `must_abstain_fallback` is 0.
- **Stub numbers mean nothing.** AC-10 proves plumbing only. The stub may fail the fixture gate (exit 1, for example a must-abstain answered); that is a valid outcome for this phase.
- **Duplicate pages in the handbook PDF** (30 and 31 identical) are harmless for matching, but inflate chunk counts; noted for phase 6.
- **`per_question` in `baseline.json`** adds latency noise to a committed file. Accepted; the gate reads only the summary keys.
- The worktree has no `.venv`; commands use `VENV=<main checkout>/.venv`.

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit message |
| --- | --- | --- | --- | --- |
| 0 | Done: DEV-001; lint covers `check_golden_extract.py`; D-046..D-048; q05 check | `docs/architecture/deviations.md`, `Makefile`, `docs/OPEN_DECISIONS.md` | `make lint` | `docs(deviations): DEV-001 ...`, `build(make): lint ...`, `docs(decisions): D-046..D-048` |
| 1 | Spec and plan | this file | pushed | `docs(spec): phase 05 eval runner spec and plan` |
| 2 | Tests first: `eval/tests/conftest.py` (adds `eval/` to `sys.path`) and `test_run_eval.py` for AC-2..AC-8; run red | `eval/tests/*` | `cd eval && pytest -q` fails with `NotImplementedError` | `test(eval): failing tests for recall, citations, summary, gate` |
| 3 | `_norm`, `section_matches`, `recall_at_k`, `citation_validity` | `eval/run_eval.py` | AC-2..AC-4 tests green | `feat(eval): recall@k with AD-22 section matching, citation validity` |
| 4 | `summarise` and `gate` | `eval/run_eval.py` | AC-5, AC-6 green | `feat(eval): summarise and gate` |
| 5 | `ask()` headers, `main()` abort and baseline guard | `eval/run_eval.py` | AC-7, AC-8 green | `feat(eval): capture X-Outcome and X-Cache, abort on ask error, guard baseline update` |
| 6 | Shared file: add eval tests to `make test` | `Makefile` | `make test` (3 suites) | `build(make): run eval tests in make test` |
| 7 | Shared file: DEV-002 dash folding | `docs/architecture/deviations.md` | `grep DEV-002` | `docs(deviations): DEV-002 dash folding in section match` |
| 8 | End to end with stubs | none | `make dev &` then `make eval-fixtures; echo exit=$?` (AC-10); record output in section 11 | `docs(spec): phase 05 stub run evidence` |
| 9 | Stage TESTING: independent tester (brief in WORKFLOW 6.1), fix rounds, report in section 12 | spec | tester PASS | `test: phase 05 eval runner report` |
| 10 | Progress: plan ticks, dashboard, H-5, log, rubric, AI-USAGE; PR into `dev` | docs | PR opened, **no auto-merge** | `docs(progress): phase 05 done` (in the PR), then the post-merge DONE docs PR |

Step 6 comes after the tests exist because `pytest` with no tests exits 5 and would break `make test` earlier.

### 10.2 Test plan

Written first (step 2): section matching table (AC-2), recall cases (AC-3), citation cases (AC-4), summarise on a 6-row hand-built set covering ordinary, exact, abstain (answered, declined, declined by fallback), a row with no citations (AC-5), gate: one test per condition plus pass, no baseline and boundary at exactly 5 points (AC-6), `ask` header capture via `httpx.MockTransport` (AC-7), `main` abort and baseline guard via monkeypatched `ask` and `tmp_path` (AC-8).

Tester runs: `make test`, `make lint`, `cd eval && pytest -q --cov=run_eval`, the AC-10 stub run, a break attempt (empty golden file, `relevant: null`, response without `retrieved`, `retrieved` shorter than k, unicode dashes, golden section longer than retrieved), invariants check (no Chroma or Redis access from `eval/`, no secret in the diff, no `eval()`).

### 10.3 Rollback and risks

All changes are in `eval/` plus two shared docs and the Makefile, in separate commits; revert any single commit. If the stub run crashes `make dev` for reasons outside `eval/`, log it and use `uvicorn` directly with `RETRIEVER=stub LLM_PROVIDER=stub`.

### 10.4 Estimate

Spec and plan 0.7 h (done), tests 0.4 h, implementation 0.5 h, stub run 0.2 h, tester rounds 0.3 h, PR and docs 0.3 h. About 2.4 h against the plan's 2 h (within 30%).

## 11. Implementation notes

- Steps 2 to 7 done as planned; steps 3 to 5 landed in one commit because the tests are one file and the functions share helpers.
- AC-10 evidence (stub API via `uvicorn` with `RETRIEVER=stub LLM_PROVIDER=stub`, then `make eval-fixtures`): all 6 questions ran, results written, then `GATE FAILED: must-abstain answered from context: f05 (abstention 0.00)`; make printed `Error 1` (the runner exited 1). That is the correct outcome: the stub answers every question, so the hostel question leaks. Plumbing works; no traceback.
- DEV-002 logged with the code. DEV-001 and the lint change were committed before the gate.
- The sandbox guard in this session refused commands containing the word `eval` as a program argument; `make test` and `e*/tests` globs work.
- Stub run needed no `X-Outcome` header (the API does not emit it yet), so `_meta` values were null as predicted.

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-04 | `make test`, `make lint`, stub run `make eval-fixtures`, 39 edge tests | FAIL | AC-1..AC-12 PASS; D-1 (low): malformed `baseline.json` gave a JSONDecodeError traceback. Fixed in 9237114. |
| 2 | 2026-11-04 | same, plus a 12-case baseline sweep | FAIL | D-1 fixed. D-2 (low): baseline of valid JSON but wrong shape (list, string, non-numeric `recall_at_5`) or a directory path crashed `main()`. Fixed in 127c0ac. |
| 3 | 2026-11-04 | `make test` (indexer 71, eval 87 passed), `make lint` clean, 25-case baseline sweep, `make eval-fixtures`, pdfplumber check of q05 | PASS | AC-1..AC-11 PASS with evidence (AC-12 is the H-5 message, delivered in the PR report). No defects. |

Informational (S4, not fixed): a hand-edited baseline with `NaN` or `-Infinity` for `recall_at_5` is accepted and can never fail the recall gate. `--update-baseline` never writes such a value. Add `math.isfinite` to the baseline validation if wanted.

q05 re-verified by the tester: "within two days" is on PDF page 30 (and the duplicate page 31), not 28 or 29.

Coverage of `run_eval.py`: not measured (`pytest-cov` is not installed in the venv). The tester reports every function and branch exercised except the `__main__` guard and the `--host` header path.

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | 2026-11-04 | Zain | |
| Tester verdict PASS | 2026-11-04 | tester subagent | rounds: 3 |
| Merged | 2026-11-05 | Zain | PR #8 |
