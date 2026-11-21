# Final requirements audit, Assignment 03 (R12, 2026-11-21)

Source: `Assignment_03.md` read line by line against `docs/requirements-a3.md` (ids R3-*). Status words: MET, MET WITH CAVEAT, NOT MET. Evidence is a committed file or a command that can be re-run. Written by the AI session; the tester checks it (spec `docs/specs/phase-r12-closeout.md`).

## Summary

| Status | Count |
| --- | --- |
| MET | 56 |
| MET WITH CAVEAT | 21 (7 table rows plus the 14 screenshot ids R3-S-*, all with the same rendering caveat) |
| NOT MET | 1 (R3-B-2, second half: waits for Zain's review) |
| Not applicable (decision) | 1 (R3-B-7, no LLM judge, D-115) |

79 ids in all (65 table rows plus 14 screenshot ids). Items not met or with a caveat are listed again at the end.

## 0. Logistics

| Id | Status | Evidence |
| --- | --- | --- |
| R3-LOG-1 | MET WITH CAVEAT | Both members must explain everything at the demo. Ahmad did no Assignment 03 work (D-108), accepted risk; the report says so (`docs/report/report.md` section 5). |
| R3-LOG-2 | MET | No late submission planned; own work and AI use declared (`docs/AI-USAGE.md`). |
| R3-LOG-3 | MET | Fixed names kept: `eval/golden.jsonl`, `k8s/eval-job.yaml`, minimum 25 questions (52 in the file). |
| R3-LOG-4 | MET | `python scripts/check_numbers_a3.py` exits 0 (100 decimals, 0 unmatched); result files committed under `eval/results/`. |
| R3-LOG-5 | MET | Kubernetes (minikube, namespace `rahbar`): `docs/evidence/a3/f1-get-all-final.txt`; no Docker-only path. Demo itself is live and cannot be proved by a file. |
| R3-LOG-6 | MET WITH CAVEAT | Commits by both members exist (Ahmad: 2 non-merge commits, all Assignment 02, none for Assignment 03). Stated in the report. |
| R3-LOG-7 | MET | `docs/reference/RAGOPS_paper.pdf`; Figure 3 and Table 2 tables in the report. |
| R3-LOG-8 | MET | Repository plus `docs/report/report.pdf` (5 body pages, appendix from page 6, 19 pages in all). |
| R3-LOG-9 | MET | `eval/results/` (suite, gate, compare, coverage, drift, stochasticity files), `traces/cluster/`, `traces/samples/`, `k8s/`. |
| R3-LOG-10 | MET | `README.md` section "Assignment 03: RAGOps (parts A to F)". |
| R3-LOG-11 | MET WITH CAVEAT | Eval Job, trace open, ingestion of an unseen batch (`corpus/demo_batch/`) rehearsed on a deleted-and-rebuilt cluster: `docs/evidence/a3/r11-fresh-cluster-rehearsal.txt`. The live demo with both members is not provable here. |

## A. Data management

| Id | Status | Evidence |
| --- | --- | --- |
| R3-A1-1 | MET | `indexer/pipeline/verification/`, runs after extraction and before chunking (`indexer/pipeline/run.py`). |
| R3-A1-2 | MET | Four checks with reason per document: `docs/evidence/a3/a1-verification-report.txt`. |
| R3-A1-3 | MET | Quarantine folder on the lake PVC with `.reason.json`: same file. |
| R3-A1-4 | MET | Report per run: `a1-verification-report.txt`, `a1-verification-report-batch-a.txt`. |
| R3-A2-1 | MET | `a2-unchanged-run.txt` (0 chunks embedded). |
| R3-A2-2 | MET | `a2-batch-b-ingest.txt`, `a2-check-registry*.txt` (copy-forward, only changed document re-embedded). |
| R3-A2-3 | MET | `a2-delete-no-orphans.txt` (count by document id). |
| R3-A2-4 | MET | Archive and `restore`: `a2-restore.txt`; superseded excluded by metadata (`indexer/pipeline/store.py`). |
| R3-AB-1 | MET | `corpus/batch_b/` (12 documents), `PLANTED.json`; generator `scripts/make_batch_b.py`. |
| R3-AB-2 | MET | Both batches through A1 and A2: `a1-verification-report-batch-a.txt`, `a2-batch-b-ingest.txt`. |

## B. Offline testing

| Id | Status | Evidence |
| --- | --- | --- |
| R3-B-1 | MET | `python -m eval.suite.golden --check`: 52 questions, 41 answerable, 11 unanswerable, 25 hard (g51 and g52 were added in R12). |
| R3-B-2 | NOT MET (second half) | First half met: 18 `human` questions (Assignment 02, written by the group) and every question labelled. Second half: 0 of 34 synthetic questions are reviewed (`reviewed: false`). Zain reviews from `eval/REVIEW_SHEET.md`; then `python scripts/mark_reviewed.py <ids>`. |
| R3-B-3 | MET | 15 paraphrase and 15 unrelated pairs, gap 0.2663, 285.3 ms per chunk, determinism 0.0: `eval/results/suite-20261121T021833Z-baseline-ab.md`. |
| R3-B-4 | MET | recall@3, recall@5, MRR, nDCG@5: same file. |
| R3-B-5 | MET | Typo noise, deltas per metric (D-116): same file, section noise. |
| R3-B-6 | MET | Faithfulness (overlap), abstention, citation validity, p50 and p95: same file. |
| R3-B-7 | Not applicable | No LLM judge (D-115): faithfulness is token overlap, so no judge to calibrate. |
| R3-B-8 | MET | `eval/results/stochasticity-20261121T003255Z.json`, `docs/evidence/a3/f3-stochasticity.txt` (two runs, per-metric difference, explanation). |
| R3-B-9 | MET | `make suite` / `python -m eval.suite.run_suite`; timestamped `suite-*.json` and `.md` in `eval/results/`. |

## C. Change experiment and gate

| Id | Status | Evidence |
| --- | --- | --- |
| R3-C1-1 | MET | Chunk size and overlap. |
| R3-C1-2 | MET | `eval/results/compare-cand-*.txt` (all three levels, three candidates). |
| R3-C2-1 | MET | `eval/gate.yaml`, ConfigMap `rahbar-gate`. |
| R3-C2-2 | MET | `eval/suite/gate.py` exits 0 or 1. |
| R3-C2-3 | MET WITH CAVEAT | Fail (100/0) and pass (300/50, 600/100): `eval/results/gate-cand-*.txt`. The faithfulness limit was changed after the 100/0 result was seen (D-134, disclosed in `docs/evidence/r7-decision.md` and the report); both outputs are committed. |
| R3-C3-1 | MET | `docs/evidence/a3/r9-release.txt`. |

## D. Observability

| Id | Status | Evidence |
| --- | --- | --- |
| R3-D1-1 | MET | `d1-trace-record.txt`; `api/app/services/trace.py`; samples in `traces/`. |
| R3-D2-1 | MET | `scripts/trace_tool.py`; `d2-trace-tool.txt` (rebuilds prompt, verifies hash). |
| R3-D3-1 | MET | `/metrics` (`f-metrics.txt`) and `d2-trace-report-job.txt`. |
| R3-D3-2 | MET | `scripts/trace_report.py` (time window), `k8s/trace-report-job.yaml`. |
| R3-D4-1 | MET | Rail action in the trace: `e3-injection-rail-live.txt`. |
| R3-D5-1 | MET | `docs/evidence/a3/d5-root-cause.md` and the report. |

## E. Drift and coverage

| Id | Status | Evidence |
| --- | --- | --- |
| R3-E1-1 | MET | `eval/live_queries.jsonl`: 40 queries. |
| R3-E2-1 | MET | `eval.suite.coverage`, threshold 0.72 calibrated (`e2-coverage-calibration.txt`), uncovered topics `e2-uncovered-topics.md`. |
| R3-E3-1 | MET | `docs/evidence/a3/e3-data-drift.md`, `eval/results/drift-20261121T083232Z.json`. |
| R3-E4-1 | MET WITH CAVEAT | 16 questions added; share rose from 0.300 to 0.675 (`e1-coverage-before.txt`, `e1-coverage-after.txt`); the 0.85 target is not reached and the report says why. |
| R3-E4-2 | MET | `eval.suite.coverage` exits 1 below target (both runs show exit code 1). |

## F. Kubernetes

| Id | Status | Evidence |
| --- | --- | --- |
| R3-F1-1 | MET | `k8s/base/api.yaml`, `chroma-statefulset.yaml`, `services.yaml`. |
| R3-F1-2 | MET | `k8s/base/ragops-pvc.yaml` (`lake-data`), `lake-survives.txt`. |
| R3-F2-1 | MET | `k8s/base/indexer-job.yaml`, `reindex-cronjob.yaml`; Chroma accepts writes only from the indexer (`k8s/base/networkpolicy.yaml`, `r8-netpol.txt`). |
| R3-F2-2 | MET | `k8s/eval-job.yaml`; Job fails when the gate fails (`f3-*`, `r9-gate-fail.txt`). |
| R3-F2-3 | MET | `f4-gate-change.txt` (ConfigMap edit, same image). |
| R3-F3-1 | MET | `k8s/candidate/api-candidate.yaml`, own Service and collection. |
| R3-F3-2 | MET | `r9-release.txt` (`maxUnavailable: 0`, 64 of 64 requests HTTP 200 during the rollout). |
| R3-F3-3 | MET | `r9-gate-fail.txt`, `r9-bad-release.txt`, `r9-rollout-undo.txt`. |
| R3-F3-4 | MET | `r9-trace-after-undo.txt`. |
| R3-F4-1 | MET | `d1-trace-lines-in-pod-logs.txt`, `traces-data` volume, `d1-traces-pull.txt`. |
| R3-F4-2 | MET | `f-metrics.txt`. |
| R3-F5-1 | MET | `docs/evidence/f5-resources.txt`, `f5-samples-*.txt`, numbers in the report. |
| R3-F5-2 | MET WITH CAVEAT | `k8s/README.md`; rehearsed once on a deleted cluster (`r11-fresh-cluster-rehearsal.txt`); not by a second person. The indexer Job created by `kubectl apply -k` fails once on an empty inbox (expected, documented). |

## G. Report

| Id | Status | Evidence |
| --- | --- | --- |
| R3-G-1 | MET | Report section 1 (Figure 3 table). |
| R3-G-2 | MET | Report section 2 (Table 2). |
| R3-G-3 | MET | Report section 3, release decision "reject 100/0, release 600/100". The production release of 600/100 is Zain's step (not done). |
| R3-G-4 | MET | Report section 4, answers (a) to (f). |
| R3-G-5 | MET WITH CAVEAT | Contribution table and AI statement written; Zain should read both. Page 1 now has the roll numbers 24i-3126 (Zain) and 24i-3006 (Ahmad). Body is 5 pages (limit 8). |

## Screenshots

R3-S-A1, A2, B, C1, C2, D1, D2, E1, E2, F1, F2, F3, F4, F5: all 14 PNGs exist in `docs/evidence/a3/screenshots/`, labelled, with command first and an end marker; index `docs/evidence/a3/README.md`. Status for each: **MET WITH CAVEAT**: they are renderings of terminal output saved when the commands ran on the cluster (D-139), not captures of a live terminal window, and E1 and E2 show the documented command although the saved file holds only its output. (Counted as 14 caveats in the summary.)

## Open items

1. R3-B-2 second half: Zain reviews 8 synthetic questions (`eval/REVIEW_SHEET.md`).
2. g51 and g52 (version-aware pair for the superseded refund page) were added after the final result files: they are in `eval/golden.jsonl` (52 questions) but not in the measured runs (50). No LLM suite was run for them; the retrieval of both was checked on the live index (rank 1 and rank 2).
3. Screenshot rendering (D-139), thin commit history of Ahmad, rehearsal by one person, coverage target 0.85 not reached, gate limit set after a result (D-134).
4. The production release of 600/100 is not done (Zain's decision).
5. CI scan carries a time-limited Trivy ignore for six nginx CVEs of the ui base image (D-142, expires 2026-12-15).
