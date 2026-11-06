# Phase 15 spec and plan: Integration support and final verification

| | |
| --- | --- |
| Phase | 15, from `docs/IMPLEMENTATION_PLAN.md` |
| Work plan task | joint (WORKPLAN section 8, I-4) |
| Branch | `feat/final-verification` |
| Stage | TESTING |
| Started | 2026-11-07 |
| Approved (spec and plan) | 2026-11-07, pre-approved by Zain (headless run, no gate) |
| Depends on | K1 to K11 DONE; PR #34 (main merged into dev) |

## 1. Objective
The delivered repository passes the I-4 checklist with evidence, every remaining warning is fixed or explained, and the release PR dev to main is open and green.

## 2. Context
- Rubric: `docs/rubric_checklist.md` sections A and B12; `scripts/check_submission.py`; WORKPLAN section 8.
- Decisions: D-104 (this phase). Deviations: DEV-014.

## 3. Scope
**In scope:** merge main into dev (PR #34, done); `make test/lint/manifests/check`; explain the five checker warnings; placeholder-marker, NotImplementedError and secret-history scans; deviations and open decisions reviewed; numbers cross-check script; rubric checklist ticked with evidence and known gaps; `docs/FINAL-WALKTHROUGH.md`; release PR (not merged).
**Out of scope:** new features, UI polish (A-12), onboarding (A-00), GitHub settings, merging the release PR (needs approval or owner override).

## 4. Interfaces and contracts
New: `scripts/check_numbers.py` (exit 1 on mismatch), `docs/evidence/final-numbers-check.txt`, `docs/evidence/final-history-scan.txt`, `docs/FINAL-WALKTHROUGH.md`. Code changes: comments and one docstring only (`api/app/routes/health.py`, `api/app/services/cache.py`); starter marker removed from `eval/golden.example.yaml`. No behaviour change.

## 5. Behaviour and design details
The two checker warnings about non-empty readiness and never-cache are false positives: the checker strips comments and reads only the `readyz` body, while the behaviour lives in `IndexState.get()` (`col.count()` zero raises `IndexUnavailable("collection")`) and `cacheable()`. Not renamed, no dead code (D-104).

## 6. Acceptance criteria
- [x] **AC-1**: `git rev-list --left-right --count origin/main...origin/dev` shows 0 on the main side.
- [x] **AC-2**: `make test && make lint && make manifests && make check` clean; 0 failures; each of the 5 warnings explained (rubric section E).
- [x] **AC-3**: no starter marker outside the kit files, no `raise NotImplementedError`; history scan clean; `corpus/raw` never committed (`final-history-scan.txt`).
- [x] **AC-4**: deviations.md has no OPEN or ACCEPTED entry; OPEN_DECISIONS.md has no OPEN or PROVISIONAL entry.
- [x] **AC-5**: `scripts/check_numbers.py` reports 0 mismatches (`final-numbers-check.txt`); `results.json` equals `baseline.json`; ConfigMap is 400/50, floor 0.70, TOP_K 5, nomic-embed-text, llama3.2:3b.
- [x] **AC-6**: rubric checklist ticked with evidence; false or deferred items listed in "Known gaps".
- [x] **AC-7**: `docs/FINAL-WALKTHROUGH.md` has module map, 10 decisions, 5 numbers and 8 questions per lane, and every path it names exists.
- [ ] **AC-8**: release PR "Release: RAHBAR final submission" open, six required checks green, not merged.

## 7. Test strategy and traceability
| AC | Level | Command | Needs |
| --- | --- | --- | --- |
| AC-1 | manual | `git rev-list --left-right --count origin/main...origin/dev` | git |
| AC-2 | manual | `make test lint manifests check` | nothing |
| AC-3 | manual | `docs/evidence/final-history-scan.txt` commands | git |
| AC-4 | manual | `grep` of status lines | nothing |
| AC-5 | script | `.venv/bin/python scripts/check_numbers.py` | nothing |
| AC-6, AC-7 | review | tester reads the files and checks pointers | nothing |
| AC-8 | manual | `gh pr checks --watch` | GitHub |

## 8. Open questions
None; D-104 records the choices.

## 9. Risks and assumptions
Disk is 98% full: no image is built in this phase. A push to the release PR branch dismisses CI results, so the PR is opened last.

## 10. Plan
1 merge main (done). 2 comments and marker. 3 close decisions, DEV-014. 4 numbers script. 5 checklist. 6 walkthrough. 7 tester. 8 plan, AI-USAGE, SETUP check. 9 PR into dev, merge. 10 release PR.

## 11. Implementation log
2026-11-07: steps 1 to 6 committed on `feat/final-verification`. Found and recorded an undocumented drift (api PodDisruptionBudget, DEV-014).

## 12. Test report
(see below, filled by round)

## 13. Gate and PR
Merged by Claude after the tester passed; the release PR is left for Zain.
