# Phase K4 spec and plan: NetworkPolicies and proof

| | |
| --- | --- |
| Phase | K4, from `docs/IMPLEMENTATION_PLAN_PLATFORM.md` |
| Work plan task | A-06 |
| Branch | `feat/k8s-k04-networkpolicy` |
| Stage | TESTING |
| Started | 2026-11-06 |
| Approved (spec and plan) | pre-approved by Zain, platform plan 0.1 |
| Depends on | K1 to K3 (system works before the deny is applied) |

## 1. Objective
Default deny plus eight policies (architecture 4.6); the system still works; a captured experiment shows `ui` cannot reach `chroma` or `redis`, `indexer` cannot reach `redis`, `api` can reach both.

## 2. Context
Architecture 4.6, 4.7; R-K8S-NP, R-SEC-4. Calico enforces (minikube `--cni=calico`). Ollama host `192.168.49.1` (confirmed with `minikube ssh`).

## 3. Scope
In: `k8s/base/networkpolicy.yaml`, kustomization entry, `dev` overlay patch for the Ollama `ipBlock`, evidence, SETUP note. Out: TLS, hosted-mode 443 egress.

## 4. Interfaces and contracts
Eight policies named as in 4.6. Selectors: `app.kubernetes.io/name` and namespace `kubernetes.io/metadata.name` only. Base `ipBlock` is the placeholder `203.0.113.1/32` (TEST-NET-3), patched in `dev` to `192.168.49.1/32`. No ConfigMap key added.

## 5. Behaviour and design details
- "Before" is captured with policies absent; then applied; then re-proved. `ui` image has no curl: use `wget` if present, else a `kubectl debug` ephemeral container; api uses `python -c`.
- Indexer proof: a throwaway pod labelled `app.kubernetes.io/name=indexer` (same policy match as the Job) tests `redis:6379`; plus `make index`-style Job completion is re-run by creating a Job from the CronJob.
- `ui` to `api` is allowed (assignment) and checked.

## 6. Acceptance criteria
- [x] AC-1: `kubectl get netpol -n rahbar` lists 8.
- [x] AC-2: pods Ready, UI loads via Ingress, `make ask` answers incl. a cache-miss question, an indexer Job completes.
- [x] AC-3: `docs/evidence/k04-networkpolicy-proof.txt` shows before/after as required.
- [x] AC-4: kubeconform -strict passes; selectors restricted as above.
- [x] AC-5: `make test && make lint` green.

## 7. Test strategy
Cluster-level; evidence file. Tester subagent re-runs the Verify commands.

## 8. Open questions
None.

## 9. Risks
R-07 policy unenforced: proven not assumed. Ollama needed for cache-miss and indexer (start `OLLAMA_HOST=0.0.0.0 ollama serve`, stop after).

## 10. Plan
| Step | What | Verify | Commit |
| --- | --- | --- | --- |
| 1 | manifests + dev patch | kubeconform | `feat(k8s): K4 network policies` |
| 2 | before capture, apply, proof, regression checks | evidence | `docs(evidence): K4 proof` |
| 3 | docs, plan, tester, PR | PASS | `docs(progress): K4` |

## 11. Implementation notes
See progress log.

## 12. Test report
(filled after tester)
