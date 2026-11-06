# Phase K10 spec and plan: cluster evidence

| | |
| --- | --- |
| Phase | K10, from `docs/IMPLEMENTATION_PLAN_PLATFORM.md` |
| Work plan task | A-13 |
| Branch | `docs/k10-evidence` |
| Stage | IMPLEMENTING |
| Started | 2026-11-06 |
| Approved (spec and plan) | pre-approved by Zain (no gate in the platform plan) |
| Depends on | K1 to K9 |

## 1. Objective
`docs/evidence/` holds one plain-text file per demonstration the assignment asks for (command, then real output, from the running minikube cluster), `resources.md` justifies the requests and limits with measurements, and a final `make eval` through the Ingress against rebuilt images shows the gate.

## 2. Context
R-RES-2, R-ROL-2/3, R-SEC-4, R-PIN-3, R-CAC-*, R-CD-6; `docs/FAILURE-ANALYSIS.md` stage C (pin capture format); `scripts/check_submission.py`; K1 to K9 evidence. Index in the cluster has 980 chunks (DEV-010: Tesseract in the container makes 39 chunks for the faculty policy, 40 on the host). K6 bumped api dependencies; the deployed images predate it, so all three are rebuilt first.

## 3. Scope
In: rebuild and roll out images; the ten evidence files; `docs/evidence/README.md`; `resources.md`; `k8s/base` requests/limits updated to measurements; plan, AI-USAGE, results register. Out: new features; UI screenshots (browser tooling not used here; hand-off); editing `eval/baseline.json`.

## 4. Interfaces and contracts
No new config keys. Only `resources:` values in `k8s/base/*.yaml` may change. A `v2` image is the rebuilt image under a second tag with `APP_VERSION=2.0.0` set via `kubectl set env`/the manifest-free path, visible in `/healthz`.

## 5. Behaviour and design details
Evidence files are `k10-<topic>.txt`, names containing `top`, `endpoints`, `hpa`, `branch`, `blocked` where the checker needs them (K9 files already match branch/blocked; K10 copies/reference them). Command line first, real output unedited. Rollout/pod-delete/endpoints demonstrations run a 0.5 s request loop with a cached question through the Ingress and count non-200. Pin demonstration reverts the ConfigMap afterwards. `make eval` runs once, in the background, after the other heavy jobs.

## 6. Acceptance criteria
- [ ] **AC-1**: at least ten evidence files with command and output; `docs/evidence/README.md` indexes them.
- [ ] **AC-2**: `resources.md` justifies every request/limit with a measurement; `k8s/base` matches; `make manifests` passes.
- [ ] **AC-3**: rollout, pod deletion, endpoints: zero failed requests, 3+ IPs.
- [ ] **AC-4**: pin demo shows `0/1`, 503 `embed_pin`, log line, recovery.
- [ ] **AC-5**: cache sequence MISS, HIT, re-index, MISS, HIT.
- [ ] **AC-6**: `make eval` through the Ingress passes the gate; numbers recorded.
- [ ] **AC-7**: `check_submission.py` shows no evidence failure; `make test && make lint` green; CI green on the PR.

## 7. Test strategy and traceability
All manual on the real cluster; commands in the evidence files. Tester subagent re-runs the read-only commands and checks the files.

| AC | Level | Command |
| --- | --- | --- |
| AC-1..6 | manual | evidence files, `kubectl`, `make eval` |
| AC-7 | manual | `python3 scripts/check_submission.py`, `make test && make lint`, `gh pr checks` |

## 8. Open questions
None. D-102 (how the v2 image and the resource numbers are derived) is recorded.

## 9. Risks and assumptions
Laptop load: one heavy job at a time (images, then re-index, then eval). Re-index while Ollama is busy may be slow. A gate miss in the eval is diagnosed and reported, never fixed by editing the baseline.

## 10. Plan
| Step | What | Commit |
| --- | --- | --- |
| 1 | spec | `docs(k10): spec and plan` |
| 2 | rebuild images, roll out, endpoints/hpa/top/rollout/pod-delete/pin/cache evidence | `docs(k10): cluster evidence` |
| 3 | resources.md and k8s/base numbers | `feat(k8s): requests and limits from measurements` |
| 4 | final eval, README index, plan, AI-USAGE, tester | `docs(k10): eval, index, plan, AI-USAGE` |

Rollback: revert the `k8s/base` resource commit; evidence files are additive.
