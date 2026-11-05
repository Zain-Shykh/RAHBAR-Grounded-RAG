# Phase K1 spec and plan: `ui` image and base workloads on minikube

| | |
| --- | --- |
| Phase | K1, from `docs/IMPLEMENTATION_PLAN_PLATFORM.md` |
| Work plan task | A-01, A-02, A-03 |
| Branch | `feat/k8s-k01-base-workloads` |
| Stage | IMPLEMENTING (no gate: platform plan 0.1) |
| Started | 2026-11-05 |
| Approved (spec and plan) | pre-approved by Zain, platform plan 0.1 |
| Depends on | RAG phases 0 to 14 DONE; H-2, H-3, H-7, H-11 (texts in `IMPLEMENTATION_PLAN.md` log) |

## 1. Objective

`kubectl apply -k k8s/overlays/dev` runs `api` (3, `0/1` until K2), `ui`, `chroma-0` and `redis` in minikube with persistent storage, hardened security contexts and requests and limits. The three images build and load into minikube.

## 2. Context

- Architecture 4.1 to 4.12, 4.13 (api `0/1` is correct), section 9 (A-5, R-01, R-02).
- Requirements R-K8S-NS/API/UI/CHROMA/REDIS/SVC/CM/SEC, R-IMG-1..5, R-SEC-1..3, R-RES-1, R-PRB-1/2.
- H-7 values override the 0.50 in the architecture 4.4 table (`RELEVANCE_FLOOR=0.70`); fix the table in this PR.
- H-2 Redis Stack `redis/redis-stack-server:7.4.0-v8`, UID 10001, `/data`, `REDIS_ARGS=--appendonly yes`. H-3 `chromadb/chroma:1.0.12`, UID 10001, `/data`, heartbeat `/api/v2/heartbeat`.
- `ui/nginx.conf` already serves `/healthz` on 8080 and writes only under `/tmp`. Not edited.

## 3. Scope

In: `ui/Dockerfile`, `ui/.dockerignore`; `make images` working for three images; `k8s/base/*` (namespace, serviceaccounts, configmap, secret placeholder, api, ui, chroma StatefulSet, redis Deployment + PVC, services, kustomization); `k8s/overlays/dev`; `make apply`; evidence files; architecture 9 and 4.4 updates; deviations if reality differs.

Out: indexer Job and CronJob and `corpus-data` (K2), Ingress, HPA, PDB (K3), NetworkPolicy (K4), `ci` and `prod` overlays (K5), CI. `k8s/overlays/prod/.gitkeep` stays.

## 4. Interfaces and contracts

- Image tags: `rahbar-api:dev`, `rahbar-indexer:dev`, `rahbar-ui:dev` (base uses `rahbar-<name>:dev` names; dev overlay sets them via `images:`).
- ConfigMap `rahbar-config` with every key of architecture 4.4 (contract C-2: no extra keys). Secret `rahbar-secret` key `LLM_API_KEY`, `optional: true` via `secretKeyRef`.
- Services: `ui` 80 to 8080, `api` 8000, `chroma` 8000, `redis` 6379, all ClusterIP. Labels `app.kubernetes.io/name`, `app.kubernetes.io/part-of: rahbar` on every object.
- ui image: `nginxinc/nginx-unprivileged:1.27-alpine` (pulled, nginx 1.27.5), user 101, port 8080.

## 5. Behaviour and design details

- Security on every pod: `runAsNonRoot`, UID/GID 10001 (ui 101), `fsGroup` 10001 for chroma and redis, `seccompProfile: RuntimeDefault`; containers `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `drop: [ALL]`; `automountServiceAccountToken: false`; one ServiceAccount per workload (api, ui, chroma, redis, indexer; indexer SA is created now, used in K2).
- api: replicas 3, RollingUpdate maxSurge 1 / maxUnavailable 0, grace 30, `preStop.sleep.seconds: 10`, probes per 4.8, 100m/256Mi to 500m/512Mi, `emptyDir` `/tmp`, `envFrom` ConfigMap.
- ui: probes on `/healthz` 8080, 25m/32Mi to 100m/64Mi, `emptyDir` `/tmp`, 1 replica.
- chroma: StatefulSet, `serviceName: chroma`, 1 replica, `volumeClaimTemplates chroma-data` 2Gi, env per H-3, probes `GET /api/v2/heartbeat`, 100m/256Mi to 500m/1Gi, `emptyDir` `/tmp`.
- redis: Deployment, strategy Recreate, PVC `cache-data` 1Gi, env `REDIS_ARGS`, probes `redis-cli ping`, 100m/256Mi to 500m/512Mi.
- Redis and Chroma probe exec/HTTP use only the pod's own port. The chroma image may lack `curl`; use `httpGet` (kubelet side).
- dev overlay: `namespace: rahbar`, `images:` with `newName/newTag`, patch `imagePullPolicy: IfNotPresent` on all app containers. Base sets `imagePullPolicy: IfNotPresent` too (R-IMG-4).
- Secret placeholder exists but is in no kustomization; `.gitignore` covers `*secret*.yaml`: check, and force-add if needed (placeholder must be tracked).

## 6. Acceptance criteria

- [ ] **AC-1** `sg docker -c "make images"` builds three images and loads them; ui runs with `--read-only --tmpfs /tmp --user 101` and serves `/` and `/healthz` on 8080.
- [ ] **AC-2** `kustomize build k8s/overlays/dev | kubeconform -strict -summary` passes.
- [ ] **AC-3** After apply: 3 api pods Running `0/1`, ui `1/1`, `chroma-0` `1/1` with PVC Bound, redis `1/1` with `cache-data` Bound; every container has requests and limits.
- [ ] **AC-4** Data survives pod deletion: Chroma collection, Redis key.
- [ ] **AC-5** `/readyz` 503 `failed: ["collection"]`, `/healthz` 200 via port-forward; `docs/evidence/k01-api-before-index.txt`.
- [ ] **AC-6** `check_submission.py` section G has no failure for existing objects.
- [ ] **AC-7** No `Secret` in the build output; no secret in Git.
- [ ] **AC-8** A-5 and PVC `fsGroup` verified and recorded in architecture 9.
- [ ] **AC-9** `make test && make lint` green.

## 7. Test strategy and traceability

All are cluster or command proofs (no Python code changes). Evidence in `docs/evidence/k01-*.txt`.

| AC | Level | Command |
| --- | --- | --- |
| AC-1 | manual | `make images`, `docker run --read-only ...`, `curl` |
| AC-2 | manual | `kustomize build ... \| kubeconform -strict -summary` |
| AC-3 | manual | `kubectl get pods,pvc -n rahbar`, `kubectl get ... -o json` resources check |
| AC-4 | manual | port-forward + chroma/redis write, delete pod, read |
| AC-5 | manual | port-forward + curl |
| AC-6 | manual | `check_submission.py` |
| AC-7 | manual | `kustomize build \| grep -c '^kind: Secret'` |
| AC-8 | manual | `kubectl exec ... ls -ln /data`, `kubectl get pod -o yaml` preStop, timing of termination |

## 8. Open questions

None blocking. Decisions taken (logged in `OPEN_DECISIONS.md` as D-057 to D-059, Decided by Claude, pre-approved by Zain): ui base image tag, redis probe form, base `imagePullPolicy`.

## 9. Risks and assumptions

- Chroma image has no curl: use `httpGet`. Redis Stack `redis-cli` exists in the image (verify).
- A-5: field exists in the API (`kubectl explain` ok); verify actual sleep behaviour by timing a pod deletion.
- `fsGroup` on minikube hostPath provisioner may not chown: verify with `ls -ln /data`; if it fails, log a deviation (initContainer or chown).
- `.gitignore` may swallow `secret.placeholder.yaml`.

## 10. Plan

| Step | What | Files | Verify | Commit |
| --- | --- | --- | --- | --- |
| 1 | ui Dockerfile and dockerignore, Makefile `images` and `apply` | `ui/Dockerfile`, `ui/.dockerignore`, `Makefile` | `make images`, run ui read-only | `feat(ui): nginx-unprivileged image` |
| 2 | base manifests and dev overlay | `k8s/base/*`, `k8s/overlays/dev/kustomization.yaml` | kustomize + kubeconform | `feat(k8s): base workloads and dev overlay` |
| 3 | apply and prove on minikube | `docs/evidence/k01-*.txt` | AC-3 to AC-8 | `docs(evidence): K1 cluster proof` |
| 4 | architecture 4.4 and 9, deviations, decisions, plan, AI-USAGE | docs | `make test && make lint` | `docs: K1 results` |

Test plan: independent testing subagent (WORKFLOW 6) re-runs all commands. Rollback: `kubectl delete ns rahbar`, revert commits. Estimate 5 h.

## 11. Implementation notes

(filled during implementation)

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan | 2026-11-05 | pre-approved by Zain (platform plan 0.1) | no gate |
| Tester verdict PASS | | | rounds: |
| Merged | | | PR # |
