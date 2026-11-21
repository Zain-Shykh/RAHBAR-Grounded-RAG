# Phase R8 spec and plan: Kubernetes deployment of RAGOps

| | |
| --- | --- |
| Phase | R8, from `docs/IMPLEMENTATION_PLAN_A3.md` |
| Work plan task | A3 R-08 (Ahmad out, D-108) |
| Branch | `feat/rag-r04-eval-suite` (PR #48; planned name `feat/k8s-r08-ragops`) |
| Stage | TESTING (cluster runs done 2026-11-21; independent tester next) |
| Started | 2026-11-21 |
| Approved (spec and plan) | gate waived (D-124) |
| Depends on | R1 to R7 |

## 1. Objective

The A1 and A2 ingestion, the suite, the gate and the traces run on the minikube cluster from the manifests: PVCs, Jobs, a CronJob, ConfigMaps, measured resources, and a README that rebuilds a cluster (architecture 9).

## 2. Context

- Architecture: `architecture-a3.md` 9.1 to 9.5, I-12, I-15, I-18, AD-43.
- Requirements: R3-F1-1, R3-F1-2, R3-F2-1 to R3-F2-3, R3-F4-1, R3-F4-2, R3-F5-1, R3-F5-2, R3-LOG-11.
- Decisions: D-121 (eval image and Job path), D-128 onward (made in this phase).
- Code and manifests: `k8s/base/ragops-pvc.yaml`, `k8s/eval-job.yaml`, `k8s/trace-report-job.yaml`, `k8s/candidate/*`, `k8s/tools/volume-viewer.yaml`, `k8s/base/networkpolicy.yaml`, `eval/Dockerfile`, `eval/suite/job.py`, Makefile A3 targets.

## 3. Scope

**In scope**: apply and run everything on the real cluster; fix manifests and code found wrong; `scripts/measure_resources.sh`; requests and limits from measurements; `GATE_ONLY` in `eval/suite/job.py`; `k8s/tools/restore-job.yaml`; evidence under `docs/evidence/a3/` and `docs/evidence/f5-resources.txt`; README update.

**Out of scope**: candidate rollout (R9), coverage (R10), report and screenshots (R11; evidence files here are the screenshot sources). Full delete-and-recreate rehearsal of the cluster is R11-AC5; the cluster was stopped, not deleted, at the start of this phase (see 11).

## 4. Interfaces and contracts

- `GATE_ONLY=<result file>` (env of the eval Job, Makefile var `GATE_ONLY`): skip the suite, gate the given result file against `BASELINE` with `GATE_CONFIG`; same exit codes (0 pass, 1 fail, 2 unusable).
- `scripts/measure_resources.sh <label> <seconds>`: samples `kubectl top pod -n rahbar` every 5 s to stdout (`epoch pod cpu mem`).
- `k8s/tools/restore-job.yaml`: one-off Job running `python -m pipeline.restore` with the lake mounted read-write.

## 5. Behaviour and design details

Indexer and CronJob mount `lake-data` rw, `corpus-data` ro. API mounts `traces-data`. Eval Job: `backoffLimit 0`, exit code = gate. Limits rule: request about the median of sampled usage, limit about 1.5 x peak, rounded up (R3-F5-1).

## 6. Acceptance criteria

R8-AC1 to R8-AC11 exactly as in `IMPLEMENTATION_PLAN_A3.md` phase R8; they are not restated here. Tick each in section 12 with its evidence file.

## 7. Test strategy and traceability

| AC | Level | Command or evidence | Needs |
| --- | --- | --- | --- |
| AC1 | manual | `make manifests`; `kubectl apply -k k8s/overlays/dev`; `a3/f0-cluster.txt`, `a3/f1-get-all.txt` | cluster |
| AC2 | manual | `a3/f1-get-all.txt` | cluster |
| AC3 | manual | `a3/f2-ingest-job-logs.txt`, `a3/a1-verification-report*.txt`, `a3/lake-survives.txt` | cluster, Ollama |
| AC4 | manual | `a3/a2-unchanged-run.txt`, `a3/a2-cronjob-run.txt` | cluster |
| AC5 | unit + manual | `api/tests` search test; `a3/r8-netpol.txt` | cluster |
| AC6 | manual | `a3/f3-eval-job-logs.txt` (Complete, Failed) | cluster, Ollama |
| AC7 | unit + manual | `eval/tests/test_job.py`; `a3/f4-gate-change.txt` | cluster |
| AC8 | manual | `a3/d1-trace-record.txt`, `a3/d2-trace-tool.txt`, `a3/f-metrics.txt` | cluster |
| AC9 | manual | `docs/evidence/f5-resources.txt`, `k8s/base/*.yaml` | cluster |
| AC10 | manual | `make images` tags; CI run on PR #48; `grep -r ':latest' k8s` | |
| AC11 | manual | `a3/r8-regression.txt` | cluster |

## 8. Open questions

None; decisions D-128 onward are logged in `OPEN_DECISIONS.md`.

## 9. Risks and assumptions

Ollama is one process, about 80 s per answer: only one LLM job at a time. Chroma host port-forward needed for `check_registry.py`. A false-positive quarantine of a real document is a defect in the verification code.

## 10. Plan

| Step | What | Verify |
| --- | --- | --- |
| 1 | cluster, images, apply, get all | `f1-get-all.txt` |
| 2 | corpus, gate-config, `make index`, second `make index`, check_registry | a1/a2 files |
| 3 | measure resources script, apply limits, DEV note | `f5-resources.txt` |
| 4 | eval baseline, live2, stochasticity, GATE_ONLY failing run | f3, f4 |
| 5 | traces and metrics | d1, d2 |
| 6 | Batch B, delete, restore | a1 report, a2-restore |
| 7 | NetworkPolicy proof, README, regression | r8-netpol, r8-regression |
| 8 | independent tester, fix rounds | section 12 |

Rollback: `make down` and re-apply. Estimate 5 h (compressed schedule).

## 11. Implementation notes

Evidence is in `docs/evidence/a3/` (one text file per command, screenshot sources) and `docs/evidence/f5-resources.txt`.

- The cluster was a stopped minikube with the A02 deployment (not deleted): `make cluster` restarted it, `make images` rebuilt four images (tag `dev`, as in A02; commit-SHA tags are set by CI), `kubectl apply -k k8s/overlays/dev` created the three new PVCs. R8-AC1's delete-and-recreate rehearsal is left to R11-AC5.
- Ingestion of the real corpus: 9 of 9 pass verification (8 indexed, 1 superseded, 0 quarantined), 980 chunks, 1396 s; unchanged re-run 0 embedded, no swap, same index id; `check_registry` PASS. Batch B: 44 s, 6 indexed, 6 quarantined with the planted reasons, fee page superseded by the amendment; file deleted: `deleted_chunks_remaining 0`; restore Job rolls the fee page back and forward with zero embeddings; the end state is Batch A plus Batch B.
- Defects found and fixed: (1) eval client `ReadTimeout` equal to the API's own 300 s model timeout, the first baseline Job failed (client 420 s, D-128); (2) indexer Job deadline 1800 s was too close to the 1396 s run (3600 s); (3) gate placeholders did not fit the measured baseline (D-129); (4) CI overlay patched volume index 0, which is the lake volume since R8, so the CI e2e job could not apply (patch index 1); (5) a file removed from the inbox without its manifest entry is quarantined, not deleted: documented, `make inbox-delete` added (D-130).
- Open: CI `scan` fails on nginx CVEs in the ui base image (fixed in nginx 1.30.7; `apk upgrade` in `ui/Dockerfile` picks them up when the Alpine mirror has them, re-run CI).
- Resource values: `f5-resources.txt`, DEV-018, D-131.

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-21 | independent tester, live cluster | AC2-AC9, AC11 PASS; AC1 caveat (no delete-and-recreate, deferred to R11-AC5); AC10 NOT PROVEN (images tagged dev; CI scan fails on nginx CVEs) | defects fixed: live api CPU limit drift (make apply), f5 tables regenerated from committed samples; low: quarantine dir clutter on a missing-file run, netpol proof file dated before the eval pod was replaced |

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan | 2026-11-21 | waived (D-124) | retroactive for the manifests |
| Tester verdict PASS | 2026-11-21 | tester agent | rounds: 1, AC1/AC10 open (see above) |
| Merged | | | PR #48 |
