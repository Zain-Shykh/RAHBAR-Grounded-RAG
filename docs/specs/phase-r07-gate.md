# Phase R7 spec and plan: change experiment and release gate

| | |
| --- | --- |
| Phase | R7, from `docs/IMPLEMENTATION_PLAN_A3.md` |
| Work plan task | none (A3 plan; Ahmad out, D-108) |
| Branch | `feat/rag-r04-eval-suite` (planned name `feat/rag-r07-gate`) |
| Stage | IMPLEMENTED BEFORE SPEC (retroactive, D-127). Gate and compare tested; candidate runs and limits pending |
| Started | 2026-11-21 |
| Approved (spec and plan) | gate waived (D-124); everything approved as recommended |
| Depends on | R4, R5 (baseline result files) |

## 1. Objective

A release gate that reads its limits from one config file and exits pass or fail, a compare table across all three levels, and (pending) a measured change experiment with one failing and one passing candidate and the release decision.

## 2. Context

- Architecture: `architecture-a3.md` 8, I-24 (no limit in code).
- Requirements: R3-C1-1, R3-C1-2, R3-C2-1, R3-C2-2, R3-C2-3 (R3-C3-1 is R9).
- Decisions: D-120 (change is chunk size and overlap).
- Code: `eval/suite/gate.py`, `compare.py`, `eval/gate.yaml`, `eval/suite/job.py`, `Makefile` `gate-config`.

## 3. Scope

**In scope**: `gate.py` (ops `at_least`, `at_most`, `not_below_baseline_by`, `not_below_baseline`, `not_above_baseline_by_pct`), `gate.yaml`, `compare.py`, tests with canned files.

**Out of scope, pending real runs**: at least three candidate collections measured, the committed `eval/results/gate-*.txt` for a failing and a passing candidate, `docs/evidence/r7-decision.md`, and the final numeric limits (two placeholders remain in `gate.yaml`: faithfulness 0.70 and p95 latency 120 s). Cluster use is R8/R9.

## 4. Interfaces and contracts

- `python -m eval.suite.gate --baseline B.json --candidate C.json [--config eval/gate.yaml]` (env `BASELINE`, `CANDIDATE`, `GATE_CONFIG`). Exit 0 pass, 1 any rule failed, 2 unreadable or malformed input. Output: one `PASS`/`FAIL` line per rule with the `why`, then `GATE PASSED|FAILED: n of m rules pass`.
- Rule: `{metric: dotted.path, op, value, why}`. A metric missing in the candidate fails; missing in the baseline fails for baseline-relative ops.
- `python -m eval.suite.compare base.json cand.json` prints a markdown table of 19 metrics over module, component, e2e with deltas.
- `eval/gate.yaml` is the only file with numbers; on the cluster it is the ConfigMap `rahbar-gate`.

## 5. Behaviour and design details

- Comparisons use a 1e-12 tolerance so a candidate exactly at the limit passes (inclusive boundary).
- Output is deterministic for the same two files (no timestamps).
- Limits are to be set from the baseline numbers, the two-run noise level and the measured p95; each rule's `why` names the committed number it rests on.

## 6. Acceptance criteria

- [ ] **R7-AC1** `gate.py` returns 0 on a candidate equal to the baseline, 1 on a candidate violating any single rule (one test per rule), 2 on a malformed file; no numeric limit in code.
- [ ] **R7-AC2** Thresholds only in `eval/gate.yaml`, each with a justification referencing a committed number (code proven; two limits are placeholders and the justifications await the baseline: pending real run).
- [ ] **R7-AC3** `compare.py` covers module, component and e2e metrics, committed for every candidate run (code proven; runs pending).
- [ ] **R7-AC4** At least three candidates measured; one fails and one passes; both gate outputs committed as `eval/results/gate-*.txt` (pending real runs).
- [ ] **R7-AC5** Release decision names the candidate, deltas, a reason either way, and the metric that would have made us reject (pending).
- [x] **R7-AC6** Re-running the gate on the same two files gives identical output.
- [x] **R7-AC7** `make test` green.

## 7. Test strategy and traceability

| AC | Level | Test file and name, or command | Needs |
| --- | --- | --- | --- |
| AC1 | unit | `eval/tests/test_gate.py::test_equal_candidate_passes`, `::test_each_rule_can_fail_alone` (6 cases), `::test_cli_exit_codes_and_determinism`, `::test_no_numeric_limit_in_gate_code_and_config_has_reasons`; `test_suite_adversarial.py::test_gate_missing_baseline_metric_fails_relative_rules_only`, `::test_gate_nan_and_none_candidate_values_fail`, `::test_gate_bad_config_exits_2`, `::test_gate_missing_files_exit_2`, `::test_gate_malformed_yaml_exits_2` (strict xfail) | nothing |
| AC2 | unit + review | `test_gate.py::test_no_numeric_limit_in_gate_code_and_config_has_reasons`; `test_suite_adversarial.py::test_gate_config_every_rule_names_a_metric_that_compare_shows`; read `eval/gate.yaml` | nothing |
| AC3 | unit | `test_gate.py::test_compare_table_has_all_three_levels`; run on real files pending | real result files |
| AC4, AC5 | manual | build candidates with the indexer, run `make suite`, `python -m eval.suite.gate ...; echo $?` | Ollama, indexer, API |
| AC6 | unit | `test_gate.py::test_cli_exit_codes_and_determinism`, `test_suite_adversarial.py::test_gate_baseline_is_equal_to_itself_and_output_is_stable` | nothing |
| AC7 | command | `make test` | nothing |

## 8. Open questions

| # | Question | Options and recommendation | Decision entry | Answer |
| --- | --- | --- | --- | --- |
| Q1 | Which change to test? | chunk size and overlap | D-120 | PROVISIONAL, accepted |
| Q2 | Final numeric limits | from baseline, noise and p95 | D-120 | pending real run |

## 9. Risks and assumptions

- A gate limit set before the noise is measured may be tighter than the run-to-run variation and fail an identical candidate; the plan sets the MRR slack above the stochasticity result.
- A malformed YAML config crashes with a traceback (T-2); on the cluster Job the exit code would be 1, read as a failed gate.
- Latency p95 depends on this CPU; the budget must come from measurement.

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit message |
| --- | --- | --- | --- | --- |
| 1 | Gate, config, compare, tests | `gate.py`, `gate.yaml`, `compare.py`, `test_gate.py` | `make test` | `feat(eval): release gate` |
| 2 | Three candidate collections | indexer env `CHUNK_SIZE`, `CHUNK_OVERLAP`, `CHROMA_COLLECTION` | `make suite` per candidate | (pending) |
| 3 | Limits, gate outputs, decision | `gate.yaml`, `eval/results/gate-*.txt`, `docs/evidence/r7-decision.md` | exit codes 1 and 0 | (pending) |

### 10.2 Test plan
Unit tests with canned result files, one per rule; independent tester adds missing metric, NaN, None, bad config and missing file cases.

### 10.3 Rollback and risks
Config only; edit `gate.yaml`.

### 10.4 Estimate
Plan estimate 6 h, mostly the candidate runs.

## 11. Implementation notes

- Implemented by the orchestrator session before this spec (D-127). `job.py` imports `gate.yaml` through the gate module (works, but couples the two).

## 12. Test report

Round 1, 2026-11-21, branch `feat/rag-r04-eval-suite`, base 64464d3.

| AC | Result | Evidence |
| --- | --- | --- |
| R7-AC1 | PASS (with defect T-2) | exit 0 equal, 1 per single rule (6 parametrised cases, exactly one FAIL line each), 2 for bad JSON, missing files, `rules: 5`, missing `rules`, rule without `op`. NaN and None candidate values fail. A missing baseline metric fails only baseline-relative rules. Grep test finds no numeric limit in `gate.py`. Defect T-2: malformed YAML (`rules: [unclosed`) raises `yaml.YAMLError`, uncaught: exit 1 (traceback) instead of 2 |
| R7-AC2 | PARTIAL | all limits in `eval/gate.yaml`, every rule has a `why` (test), every rule metric appears in `compare` rows. The `why` of faithfulness and latency say "placeholder until R7 measures the baseline": pending real run |
| R7-AC3 | PARTIAL | table covers module, component, e2e (test; offline full run also passes the table); committed comparisons pending |
| R7-AC4 | PENDING | no candidate collections or `gate-*.txt` yet |
| R7-AC5 | PENDING | `docs/evidence/r7-decision.md` not written |
| R7-AC6 | PASS | identical stdout on two runs; `gate.run(BASE, BASE, CFG)` equal twice |
| R7-AC7 | PASS | `make test`: eval 139 passed, 3 xfailed; api 330 passed, 19 skipped, 5 xfailed |

Extra tests: eight gate tests in `eval/tests/test_suite_adversarial.py` (missing baseline metric, NaN/None, bad config x3, malformed YAML xfail, missing files, config-versus-compare consistency).

Defects found:

- **T-2 (medium)** `eval/suite/gate.py::main` catches `(OSError, ValueError, KeyError, TypeError)` but not `yaml.YAMLError`; `eval/suite/job.py` also does not. A malformed `gate.yaml` or ConfigMap exits 1, indistinguishable from "gate failed", contradicting the exit-2 contract. Fix: add `yaml.YAMLError` to the except tuples. Strict xfail `test_gate_malformed_yaml_exits_2` turns into a failure (XPASS) once fixed, then remove the marker.
- **T-8 (info)** `gate.yaml` rule `e2e.abstention_correctness` uses `not_below_baseline` with `value: 0` (ignored): fine, but a reader may expect a value.

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-21 | `make test`; probes | PASS with defect T-2 and pending items | pending: AC2 limits, AC3 to AC5 real runs |

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | 2026-11-21 | waived (D-124, D-127) | retroactive |
| Tester verdict PASS | | | round 1: gate code PASS except T-2; candidates and decision pending |
| Merged | | | |
