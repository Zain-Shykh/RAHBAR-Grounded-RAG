# Phase R11 spec and plan: evidence, report, README, final verification (with the E3 drift write-up)

| | |
| --- | --- |
| Phase | R11 (and the pending Part E3 of R10), from `docs/IMPLEMENTATION_PLAN_A3.md` |
| Work plan task | none (A3 plan; Ahmad out, D-108) |
| Branch | `feat/rag-r04-eval-suite` (PR 48 into `dev`); release PR `dev` to `main` |
| Stage | TESTING |
| Started | 2026-11-21 |
| Approved (spec and plan) | gate waived (D-124) |
| Depends on | R2 to R10 evidence files |

## 1. Objective

The repository and the PDF are the submission: an E3 data-drift write-up, 14 screenshots, an 8-page report whose every number is in a committed file, a finalized README, the checklists, a rehearsal on a deleted-and-recreated cluster, and the pull requests to `dev` and `main`.

## 2. Context

- Requirements: `requirements-a3.md` section G (R3-G-1 to 5), Screenshots (R3-S-*), R3-LOG-6, 8 to 11, R3-E3-1, R3-F5-2. Invariant I-25 (every report number is in a committed file). Paper: Figure 3 stages, Table 2 qualities (`docs/reference/RAGOPS_paper.pdf`, text extracted to /tmp).
- Decisions: D-125 (pandoc to HTML to headless Chrome), D-115 (no judge), D-126 (human work left to Zain), D-137 onward (this phase).
- Code and data used: `eval.suite.compare`, `eval/results/suite-*`, `docs/evidence/a3/*`, `k8s/README.md`.

## 3. Scope

In: `scripts/drift_report.py`, `docs/evidence/a3/e3-data-drift.md`, `eval/results/drift-*.json`; `scripts/render_screenshot.py` and 14 PNGs; `docs/report/report.md`, `print.css`, `fig-candidates.svg`, `report.pdf`; `scripts/build_report.sh`; `scripts/check_numbers_a3.py`; README, rubric section F, plan checklist and register; `corpus/demo_batch/` (3 synthetic documents), `QUESTION_LIMIT` smoke option for the eval Job; the fresh-cluster rehearsal; history scan; PRs.
Out: new features; any LLM suite run; merging the production release of 600/100 (Zain).

## 4. Interfaces

- `python scripts/drift_report.py <suite A.json> <suite A+B.json>` writes `eval/results/drift-<ts>.json`, prints the compare table and the like-for-like table.
- `python scripts/render_screenshot.py [ids]` writes `docs/evidence/a3/screenshots/<id>-<name>.png`.
- `scripts/build_report.sh` writes `docs/report/report.pdf` and prints the body page count.
- `python scripts/check_numbers_a3.py [report.md]` exits 1 and lists decimals of the report that appear in no committed file under `eval/results`, `docs/evidence`, `traces`, `docs/specs`, `eval/gate.yaml`, `eval/coverage.yaml`, `corpus/batch_b/PLANTED.json`. A decimal matches if its digits occur in a file or a file number rounds (half up) to it at the report's precision.
- `make eval-job LIMIT=N` (env `QUESTION_LIMIT`): the Job scores the first N questions only (smoke run for the rehearsal, never for a gate decision).

## 5. Behaviour and design details

- Drift compares like with like: the second suite has 23 questions the first never saw, so the per-question view is restricted to the 27 baseline ids and the script first reproduces the first file's own recall@5, MRR, abstention and faithfulness (assertion).
- Causes in the drift file are stated only where a committed file shows the mechanism; otherwise the text says so.
- Screenshots render the saved text files; page height is measured by Chrome from the layout (plus padding) and every image ends with an `[end of captured output]` marker so a crop would be visible.
- The report has the body (at most 8 pages, A4) then an appendix page break and the 14 screenshots.

## 6. Acceptance criteria

- [ ] **R11-AC1** The report PDF has at most 8 body pages, names and roll-number placeholders on page 1, and items G-1 to G-5.
- [ ] **R11-AC2** `scripts/check_numbers_a3.py` exits 0 on the report.
- [ ] **R11-AC3** 14 screenshots exist, show command and output uncropped, carry their label, each maps to a cluster run in the evidence index.
- [ ] **R11-AC4** The README commands for A to F were executed once (local ones here, cluster ones in the rehearsal) and the result is logged; not by a second person (honest gap).
- [ ] **R11-AC5** The fresh-cluster rehearsal reaches a working pipeline from `k8s/README.md`; timings in `docs/evidence/a3/r11-fresh-cluster-rehearsal.txt`.
- [ ] **R11-AC6** Plan section 6 is ticked with pointers or each unticked item is an honest gap in report and README.
- [ ] **R11-AC7** `git log` shows commits by both members; the contribution table says what is true.
- [ ] **R11-AC8** History scan saved: no secret, `corpus/raw/`, model.
- [ ] **R10-AC5** (E3) The drift run states the metrics that moved, the questions that changed outcome, the version question and the injected document, each with a cause.

## 7. Test strategy and traceability

| AC | Level | Command | Needs |
| --- | --- | --- | --- |
| R11-AC1 | manual | `scripts/build_report.sh`; `pdftotext -f 1 -l 1`; `pdfinfo` | chrome, pandoc |
| R11-AC2 | unit and manual | `python scripts/check_numbers_a3.py`; tester edits a number and expects exit 1 | nothing |
| R11-AC3 | manual | open PNGs; compare the last line to the source file's last line | nothing |
| R11-AC4, 5 | manual | rehearsal transcript | cluster, Ollama |
| R11-AC6, 7, 8 | manual | read checklists; `git log --format=%an`; `docs/evidence/a3/r11-history-scan.txt` | nothing |
| R10-AC5 | manual | recompute from the two suite files | nothing |

## 8. Open questions

None asked (instruction: do not ask). Defaults logged as D-137 onward in `docs/OPEN_DECISIONS.md`.

## 9. Risks and assumptions

Roll numbers unknown (placeholder text, human item). The rehearsal's first image pulls are slow on a fresh cluster. CI scan may fail on base-image CVEs outside this work.

## 10. Plan

| Step | What | Verify | Commit |
| --- | --- | --- | --- |
| 1 | E3 drift script and write-up | `python scripts/drift_report.py ...` | `docs(a3): E3 data drift` |
| 2 | Screenshot renderer, 14 PNGs, evidence index | look at PNGs | `docs(a3): screenshots` |
| 3 | Report, build script, number checker | `scripts/build_report.sh`, `check_numbers_a3.py` | `docs(a3): report` |
| 4 | Rehearsal on a recreated cluster; fix `k8s/README.md` and Makefile | transcript | `docs(a3): fresh cluster rehearsal` |
| 5 | README, rubric F, plan, AI-USAGE | `make test && make lint`, `scripts/check_submission.py` | `docs(a3): final` |
| 6 | Independent tester, fixes | spec section 12 | `test: phase r11 report` |
| 7 | PR 48 into dev, release PR | `gh pr checks` | |

Rollback: every step is a separate commit; the cluster rehearsal changes nothing in Git except fixes.

## 11. Implementation notes

- E3: the like-for-like view (27 ids) showed a larger drop than the compare table (-0.0952 recall@5 against -0.0147) because the second suite's 23 new questions raise the averages. Two corrections found while writing: the baseline-ab index had no `b12` (A2 delete test), and the live rail check showed the rail drops the whole chunk (D-137).
- Screenshots: Chrome headless crops its viewport below the window height, so the renderer pads the measured height by 110 px and ends each image with `[end of captured output]`.
- Report: 5 body pages at 10 pt (limit 8); appendix = 14 screenshots (19 pages in all). Roll numbers are the placeholder text.
- Number check: permissive for 1-decimal numbers (rounding rule), see D-138; the tester reads tables against sources.
- Rehearsal: findings and fixes in `docs/evidence/a3/r11-fresh-cluster-rehearsal.txt` (helper-pod wait, empty-inbox first Job, smoke run without an unanswerable question). Cluster left running with the live collection `rahbar`.
- CI: `scan` failed on six nginx CVEs of the ui base image, not on this work: `.trivyignore`, D-142.
- Not done and why: README commands were not run by a second person (R11-AC4 gap); the 8 synthetic reviews, roll numbers and contribution check are human items.

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan | 2026-11-21 | gate waived (D-124) | |
| Tester verdict PASS | | | rounds: |
| Merged | | | PR # |
