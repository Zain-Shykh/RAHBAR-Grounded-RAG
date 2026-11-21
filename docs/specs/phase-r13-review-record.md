# Phase R13 spec: record the human review of 8 synthetic golden questions

| | |
| --- | --- |
| Phase | R13 (after R12), `docs/IMPLEMENTATION_PLAN_A3.md` |
| Branch | `feat/rag-r13-review-record` off `dev`, PR into `dev` |
| Stage | READY FOR TEST |
| Gate | waived (D-124) |

## 1. Objective
Zain reviewed g19 g20 g21 g23 (source pages in the original PDFs) and g28 g29 g30 g33 (clauses in the invented Batch B files, correct by construction) and approved them without wording fixes (D-147). Record it so R3-B-2 is met and no file lists it as open.

## 2. Acceptance criteria
- **R13-AC1** In `eval/golden.jsonl` exactly g19 g20 g21 g23 g28 g29 g30 g33 are synthetic with `reviewed: true`; they keep `origin: synthetic`; no other line differs from `git show origin/dev:eval/golden.jsonl`; question text unchanged.
- **R13-AC2** `python -m eval.suite.golden --check` exits 0 and shows `synthetic_reviewed` 8; `docs/evidence/a3/b1-golden-check.txt` and `eval/results/golden-check-20261121.json` hold that result.
- **R13-AC3** `python scripts/build_golden_jsonl.py` regenerates `eval/golden.jsonl` byte-identical (test `test_builder_reproduces_committed_golden`).
- **R13-AC4** No file says the review is still open: `docs/report/report.md`, `README.md`, `eval/HUMAN_TODO.md`, `docs/IMPLEMENTATION_PLAN_A3.md` (H3-4, R4-AC1, current focus), `docs/rubric_checklist.md` F.2 B, the audit (R3-B-2 MET, summary counts match rows). The report and audit state that four of the eight are about invented Batch B files. Historic log lines and measured-run records (0 reviewed in the 50-question runs) may stay.
- **R13-AC5** `docs/report/report.pdf` has at most 8 body pages; `python scripts/check_numbers_a3.py` exits 0; `make test` and `make lint` pass.
- **R13-AC6** D-147 exists in `docs/OPEN_DECISIONS.md`; `docs/AI-USAGE.md` has an R13 line; no secret or `corpus/raw` in the diff.

## 3. Test strategy
Fresh tester subagent, spec path only: runs the commands above and a diff against `origin/dev`.

## 4. Test report
| Round | Result |
| --- | --- |
