# Phase K3 spec and plan: Ingress, HPA, rollout hardening

| | |
| --- | --- |
| Phase | K3, from `docs/IMPLEMENTATION_PLAN_PLATFORM.md` |
| Work plan task | A-05 |
| Branch | `feat/k8s-k03-ingress-hpa` |
| Stage | MERGED |
| Started | 2026-11-06 |
| Approved (spec and plan) | pre-approved by Zain, platform plan 0.1 |
| Depends on | K1 (#20), K2 (#21: real index, api 3/3 Ready) |

## 1. Objective

Questions reach the api through one Ingress host `rahbar.local`; the api scales on CPU between 3 and 8 pods with a real percentage; a rolling restart drops no request; a PodDisruptionBudget keeps two pods during node drains.

## 2. Context

- Architecture 4.3 (Ingress), 4.9 (rollouts, HPA, graceful shutdown); requirements R-K8S-ING, R-K8S-HPA, R-RES-4, R-RES-5, R-ROL-1..3; `docs/ENGINEERING-NOTES.md` Q3 (CPU is a weak signal for an I/O-bound generation service).
- K1 already set `maxSurge 1 / maxUnavailable 0`, `preStop sleep 10`, `requests.cpu 100m`; ingress and metrics-server addons are enabled by `make cluster`.

## 3. Scope

**In scope**: `k8s/base/ingress.yaml`, `hpa.yaml`, `pdb.yaml` and their kustomization entries; confirm `make ask` / `make eval` (Host header, `INGRESS_IP`); cluster proof and evidence.

**Out of scope**: NetworkPolicies (K4), TLS (plan 0.7), overlays (K5), the full rollout demonstration set (K10).

## 4. Interfaces and contracts

- Ingress `rahbar`: class `nginx`, host `rahbar.local`, `/api` Prefix to `api:8000` (no rewrite), `/` Prefix to `ui:80`, annotations `proxy-read-timeout: "310"`, `proxy-body-size: "16k"`.
- HPA `api`: `autoscaling/v2`, 3 to 8, CPU `averageUtilization: 70`.
- PDB `api`: `minAvailable: 2`, selector `app.kubernetes.io/name=api`. With min 3 replicas one disruption is allowed; no conflict with the rollout (voluntary evictions only).
- No ConfigMap key added (C-2 untouched).

## 5. Behaviour and design details

- `/healthz`, `/readyz`, `/metrics` are not routed to the api: `/healthz` on the host is the UI's own nginx probe, `/metrics` falls through to the UI.
- Forced scale test: CPU stays low under generation load, so the target is lowered to 5% with a light cached-question loop, replicas must rise, then the target is reverted and replicas return to 3 after the 300 s stabilization window.
- Rollout test: loop of cached `/api/ask` through the Ingress every 0.5 s during `kubectl rollout restart deploy/api`; count non-200.
- On this laptop `minikube ip` needs the docker group: run `make ask`/`make eval` under `sg docker -c` or pass `INGRESS_IP=192.168.49.2`.

## 6. Acceptance criteria

- [ ] **AC-1**: Ingress has host `rahbar.local` and an address; `make ask` returns a cited answer through it; `/` returns the UI HTML.
- [ ] **AC-2**: HPA shows a real `x%/70%`, min 3, max 8.
- [ ] **AC-3**: forced scale test: replicas rise above 3 and fall back; output saved.
- [ ] **AC-4**: zero failed requests during `rollout restart`; count in results register.
- [ ] **AC-5**: `kubectl get endpoints api` lists 3 pod IPs.
- [ ] **AC-6**: `kustomize build k8s/overlays/dev | kubeconform -strict` passes; `make test && make lint` green.

## 7. Test strategy and traceability

All cluster-level, commands and output in `docs/evidence/k03-*.txt` (ingress, rollout, hpa-scale).

## 8. Open questions

None. D-095 (PDB `minAvailable: 2`).

## 9. Risks and assumptions

Laptop sleep can distort timings: re-run. Ollama must run for cache lookups (query embedding).

## 10. Plan

| Step | What | Verify | Commit |
| --- | --- | --- | --- |
| 1 | manifests + kustomization | kubeconform, `kubectl apply -k k8s/overlays/dev` | `feat(k8s): K3 ingress, hpa, pdb` |
| 2 | ingress proof | `k03-ingress.txt` | `docs(evidence): K3 ingress` |
| 3 | rollout loop | `k03-rollout.txt` | `docs(evidence): K3 rollout` |
| 4 | HPA forced scale | `k03-hpa-scale.txt` | `docs(evidence): K3 hpa` |
| 5 | docs, plan, tester, PR | tester PASS | `docs(progress): K3` |

Estimate 2 h.

## 11. Implementation notes

See the progress log in the platform plan.

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-06 | AC-1..AC-6 re-run read-only, `make test && make lint` | PASS | no defects; 91+257+283 tests green, kubeconform 22 valid |

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan | 2026-11-06 | Zain (pre-approved) | |
| Tester verdict PASS | 2026-11-06 | independent subagent | rounds: 1 |
| Merged | 2026-11-06 | Claude (pre-approved) | PR on dev |
