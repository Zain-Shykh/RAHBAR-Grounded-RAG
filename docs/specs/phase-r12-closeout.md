# Phase R12 spec and plan: close-out (roll numbers, version-aware pair, review sheet, main check, final audit)

| | |
| --- | --- |
| Phase | R12 (after R11), `docs/IMPLEMENTATION_PLAN_A3.md` |
| Branch | `feat/rag-r12-closeout` off `dev`, PR into `dev`, then a release PR if `main` lacks the commits |
| Stage | READY FOR PR |
| Gate | waived (D-124, Zain: no approval gate) |

## 1. Objective
Close the human-fillable gaps Zain supplied (roll numbers), add the version-aware golden pair, prepare the 8-question review for Zain, verify the state of `main`, and audit every requirement against `Assignment_03.md`.

## 2. Scope
In: `docs/report/report.md` and `.pdf`, `scripts/build_golden_jsonl.py`, `eval/golden.jsonl`, `scripts/make_review_sheet.py`, `scripts/mark_reviewed.py`, `eval/tests/test_mark_reviewed.py`, `eval/REVIEW_SHEET.md`, `eval/HUMAN_TODO.md`, `docs/evidence/a3/final-requirements-audit.md`, README team and status lines, progress files, D-143 to D-146.
Out: running the LLM suite, setting `reviewed` on any question, secrets, the production release of 600/100.

## 3. Acceptance criteria
- **R12-AC1** Report page 1 shows `24i-3126` (Muhammad Zain) and `24i-3006` (Ahmad Jamal); the string `roll number to be filled` appears in no non-history file; contribution table names both; `docs/report/report.pdf` has at most 8 body pages (`scripts/build_report.sh` prints the count) and `python scripts/check_numbers_a3.py` exits 0.
- **R12-AC2** `eval/golden.jsonl` has 52 questions; g51 and g52 are answerable, origin synthetic, reviewed false, tag `version`, relevant `fee-structure-page.html` / `Fee Refund Policy` / page 1; `python -m eval.suite.golden --check` shows 52 questions (it still exits 1 only for `synthetic_reviewed`). The report says 50 in the measured runs and 52 in the file. Regenerating with `python scripts/build_golden_jsonl.py` gives the same file (idempotent).
- **R12-AC3** On the live cluster `POST /api/retrieve` with the g51 and g52 wording returns the `Fee Refund Policy` chunk in the top 5.
- **R12-AC4** `eval/REVIEW_SHEET.md` has 8 synthetic answerable questions, each with id, question, expected answer, ground truth source, section and page, the passage text (equal to the Chroma chunk), the reply format and the follow-up command. No question in `golden.jsonl` has `reviewed: true` for a synthetic id.
- **R12-AC5** `scripts/mark_reviewed.py <ids>` sets `reviewed: true` only for the given synthetic ids, refuses `human` and unknown ids without changing the file; `eval/tests/test_mark_reviewed.py` passes. `eval/HUMAN_TODO.md` points at the sheet.
- **R12-AC6** `make test` and `make lint` pass; the cluster is healthy (api 3/3, `/readyz` 200).
- **R12-AC7** `docs/evidence/a3/final-requirements-audit.md` lists every R3 id of `docs/requirements-a3.md` with a status and evidence; counts in its summary match its rows; R3-B-2 is NOT MET and R3-B-7 not applicable.
- **R12-AC8** Section 11 states the state of `main`, CD and the sync of `dev`.

## 4. Test strategy
Tester (fresh subagent, spec path only) runs: `scripts/build_report.sh`-free checks (`pdfinfo`, `pdftotext -f 1 -l 1`), `check_numbers_a3.py`, `python -m eval.suite.golden --check`, `make test && make lint`, the unit test, a dry run of `mark_reviewed.py` on a temp copy, comparison of each sheet passage with Chroma (`kubectl port-forward svc/chroma 18100:8000 -n rahbar`), `POST /api/retrieve` for g51 and g52 (`svc/api`), the audit counts, and `git diff` check that no `reviewed` flag changed.

## 5. Plan
1 roll numbers and report rebuild; 2 g51, g52; 3 sheet, script, test; 4 main check; 5 audit and progress files; 6 tester; 7 PR into dev, merge on green CI, release PR check.

## 11. Implementation notes
- Roll numbers from Zain (chat), D-145. Report body stays 5 pages.
- g51 retrieved at rank 1, g52 at rank 2 on the live index (D-143). They are not in the final result files; no suite was run.
- Sheet: passages come from a read-only Chroma `get` (source, page, matching section). g22 replaced by g23 (D-144). g19 is found only at rank 9 of 10 by the API (noted, retrieval weakness).
- Ruff: an unused variable in `scripts/drift_report.py` removed (lint over `scripts`).
- State of main at 2026-11-21: PR #49 (dev into main) MERGED 2026-11-21T10:24:44Z (review decision shown by GitHub: REVIEW_REQUIRED, merged by the owner under the branch rules at that time; not repeated here); the CD run `44894223325` on `main` completed with success (4m56s), so Docker Hub login and push worked. `origin/main` = a8f327d (merge of #49), whose tree equals `origin/dev` c9753ff (empty `git diff --stat`). Local `main` and `dev` are brought in sync with origin.

## 12. Test report
| Round | Result |
| --- | --- |
| 1 | Fresh tester subagent: AC2 to AC7 PASS; AC1 FAIL: stale sentence "Roll numbers on page 1 are to be filled" in report limitation 7 and README line 233 (fixed, PDF rebuilt, 5 body pages, number check exit 0); AC8 GitHub claims not checkable by the tester, checked by the developer session (PR #49 merged, CD run 44894223325 success). |

## 13. Sign-offs
| Gate | Date | By |
| --- | --- | --- |
| Tester verdict | | |
| Merged | | PR # |
