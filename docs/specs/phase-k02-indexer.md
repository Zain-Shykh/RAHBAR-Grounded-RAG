# Phase K2 spec and plan: Indexer Job, CronJob, corpus delivery, real index in the cluster

| | |
| --- | --- |
| Phase | K2, from `docs/IMPLEMENTATION_PLAN_PLATFORM.md` |
| Work plan task | A-04 (milestone I-2) |
| Branch | `feat/k8s-k02-indexer` |
| Stage | TESTING |
| Started | 2026-11-06 |
| Approved (spec and plan) | pre-approved by Zain, platform plan 0.1 |
| Depends on | K1 (#20); H-4 (indexer peak 438 MB, 9 min 40 s on host) |

## 1. Objective

The real index (981 chunks) exists in the cluster's Chroma, built by the `indexer` Job from documents delivered into the `corpus-data` PVC by `make corpus`. The api pods turn `1/1` because of it. `make index` re-indexes from the CronJob template with no failed request during the swap.

## 2. Context

- Architecture 4.2 (indexer, reindex rows), 4.5 (storage, corpus delivery, AD-08), 4.13 (bring-up order), 5.4 (stage-and-swap, AD-02), section 9 (A-1, A-4).
- Requirements R-K8S-JOB, R-K8S-CRON, R-RES-3.
- `indexer/pipeline/run.py` (C-4): waits Chroma 120 s, Ollama 60 s; verifies SHA-256 against `_index.json`; exit non-zero fails the Job.
- K1: every pod sets `enableServiceLinks: false` (DEV-008); `fsGroup` is a no-op on minikube hostPath, volumes are 0777 (DEV-009).
- Ollama on the host (`OLLAMA_HOST=0.0.0.0`), reached at `host.minikube.internal:11434` (ConfigMap `OLLAMA_URL`).

## 3. Scope

**In scope**

- `k8s/base/corpus-pvc.yaml`, `indexer-job.yaml`, `reindex-cronjob.yaml`; kustomization entries; a kustomize `replacements` rule copies the Job `spec` into the CronJob `jobTemplate.spec`, so the two cannot drift.
- `k8s/tools/corpus-loader.yaml`: helper pod (pinned busybox, non-root), not part of any kustomization.
- Makefile: `corpus`, `apply` (delete finished Job first), `down`.
- Real deployment on minikube and the evidence files.

**Out of scope**: Ingress, HPA (K3), NetworkPolicy (K4, re-verify Ollama egress there), CI (K6+).

## 4. Interfaces and contracts

- Job `indexer`: image `rahbar-indexer:dev`, `envFrom` `rahbar-config`, PVC `corpus-data` read-only `/corpus`, `emptyDir` `/tmp`, UID 10001, readOnlyRootFilesystem, drop ALL, SA `indexer`, `restartPolicy: OnFailure`, `backoffLimit: 2`, `activeDeadlineSeconds: 1800`, requests 250m/512Mi, limits 1/2Gi.
- CronJob `reindex`: `0 3 * * 0`, `concurrencyPolicy: Forbid`, history 1/1.
- No Redis access, no ConfigMap key added (C-2 untouched).

## 5. Behaviour and design details

- Pod labels `app.kubernetes.io/name: indexer`, `part-of: rahbar`.
- `make corpus`: apply namespace and PVC, run helper, `kubectl cp corpus/raw/. ...:/corpus` and `corpus/MANIFEST.md`, list `/corpus`, delete helper.
- `make apply` runs `kubectl delete job indexer --ignore-not-found` before apply (immutable template).
- Re-index proof: loop of `/api/ask` against an api pod through port-forward while `make index` runs; count non-200.

## 6. Acceptance criteria

Same as platform plan K2 section (9 boxes), numbered AC-1..AC-9 in order: corpus delivery, Job completes with 981 chunks, api `1/1`, cited answer plus `X-Cache: HIT`, `make index` with no failed request and new `index_id`, A-1/A-4 recorded, results register and H-9/H-10, evidence files, kubeconform plus `make test && make lint`.

## 7. Test strategy and traceability

All cluster-level (manual, commands saved in `docs/evidence/k02-*.txt`). `kubeconform -strict` on `kustomize build`. Template-equality of Job and CronJob checked by diffing the rendered output. `make test && make lint` unchanged.

## 8. Open questions

None blocking. Decisions logged: D-093 (replacements vs anchors), D-094 (busybox helper image).

## 9. Risks and assumptions

- A-1: `host.minikube.internal` may not resolve in pods; fallback node IP, log a deviation.
- A-4: `kubectl cp` needs `tar` in the helper; busybox has it.
- OOMKill at 2Gi or deadline 1800 s too tight on 1 CPU: raise and say why.
- Re-running `make apply` re-runs the indexer (Job deleted and recreated); documented.

## 10. Plan

| Step | What | Files | Verify | Commit |
| --- | --- | --- | --- | --- |
| 1 | corpus PVC and helper pod | `k8s/base/corpus-pvc.yaml`, `k8s/tools/corpus-loader.yaml` | `kubeconform` | feat(k8s): corpus-data PVC and loader pod |
| 2 | Job, CronJob, replacement | `indexer-job.yaml`, `reindex-cronjob.yaml`, `kustomization.yaml` | `kustomize build` shows identical templates | feat(k8s): indexer Job and reindex CronJob |
| 3 | Makefile targets | `Makefile` | `make -n corpus apply down` | feat(make): corpus, apply pre-step, down |
| 4 | Deploy for real, evidence | `docs/evidence/k02-*.txt` | acceptance commands | feat(k8s): K2 cluster proof |
| 5 | Docs, tester, PR | plan, AI-USAGE, deviations, architecture 9 | tester PASS | docs: K2 |

Rollback: `make down` and revert the step. Estimate 3 h.

## 11. Implementation notes

- Replacement works: `kustomize build` renders the CronJob `jobTemplate.spec` identical to the Job spec (image, limits, volumes, backoff, deadline). `kubeconform -strict`: 19 resources valid, loader pod valid.
- `kubectl cp` needs the source path to exist locally; `corpus/raw` is gitignored and absent in a worktree, so the Makefile has `CORPUS_SRC` (default `corpus/raw`).
- Job 1 was marked `DeadlineExceeded` (laptop slept about 15 h with the pod finished). Re-run clean under `systemd-inhibit`. `activeDeadlineSeconds` stays 1800 (13 min measured).
- api pods turned 1/1 by themselves after the index appeared (no restart).
- 980 chunks, not 981: DEV-010.
- Results and evidence: `docs/evidence/k02-indexer-job.txt`, `k02-first-answer.txt`.

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan | 2026-11-06 | pre-approved by Zain | |
| Tester verdict PASS | | | rounds: |
| Merged | | | PR # |
