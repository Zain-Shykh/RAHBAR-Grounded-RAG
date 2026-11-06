# Phase K7 spec and plan: CI part 2 (e2e-eval on kind)

| | |
| --- | --- |
| Phase | K7, from `docs/IMPLEMENTATION_PLAN_PLATFORM.md` |
| Work plan task | A-09 |
| Branch | `ci/k07-e2e-eval` |
| Stage | READY FOR PR |
| Started | 2026-11-06 |
| Approved (spec and plan) | pre-approved by Zain, platform plan 0.1 |
| Depends on | K5 (`ci` overlay, DEV-011 / D-096), K6 (`build` artifact) |

## 1. Objective
A sixth job `e2e-eval` in `.github/workflows/ci.yml` creates a kind cluster, deploys the `ci` overlay, indexes the fixture corpus with the Job, runs `eval/run_eval.py` through the Ingress and fails the pull request when the gate fails.

## 2. Context
Architecture 4.15 (e2e-eval row), 5.13, AD-19, AD-27; R-CI-6; risk R-07 (kind default CNI does not enforce NetworkPolicy); H-8 (`RELEVANCE_FLOOR=0.20` in `ci`). K5 rehearsal: `docs/evidence/k05-ci-overlay-rehearsal.txt` (Job 8 s, 16 chunks, gate passed).

## 3. Scope
In: the `e2e-eval` job, `workflow_dispatch` trigger, evidence (`k07-*.txt`), results register, check_submission section I, five prose rewordings of the old starter-kit marker name (the checker greps that literal). Out: CD (K8), repo settings (K9), pushing images.

## 4. Interfaces and contracts
- Job name exactly `e2e-eval`, `needs: build`, `timeout-minutes: 20`. Other job names unchanged.
- Reuses the `images` artifact from `build` (SHA-tagged); retag to `rahbar-*:ci`, `kind load docker-image`. No rebuild.
- kind binary v0.33.0 downloaded from the release (pinned; no third-party action), default node image of that release. ingress-nginx `controller-v1.15.1` `provider/kind` manifest (pinned tag). Both verified with `gh api .../releases`.
- kind config: one control-plane node labelled `ingress-ready=true`, `extraPortMappings` 80 -> 80, so the runner reaches the Ingress on `http://localhost` with `Host: rahbar.local` (`--host`).
- `kustomize` 5.8.3 as in `manifests`; `kustomize build --load-restrictor LoadRestrictionsNone k8s/overlays/ci | kubectl apply -f -` (DEV-011).
- On failure: `kubectl get pods,jobs,ingress -A`, `describe`, logs of api, chroma, redis, indexer Job. `results.fixture.json` uploaded always (`if: always()`, `if-no-files-found: warn`).

## 5. Behaviour and design details
Order: checkout, download artifact, `docker load`, retag, install kind and kustomize, create cluster, load images, install ingress-nginx and wait for the controller, apply overlay, `kubectl wait` Job complete (300 s), api rollout status (180 s), chroma/redis/ui rollouts, run the eval, upload. No `|| true`; any non-zero step fails the job. NetworkPolicies stay in the overlay: kind does not enforce them, so CI proves behaviour not isolation; isolation is proven on minikube (K4, `docs/evidence/k04-*`), risk R-07 (D-100).

## 6. Acceptance criteria
- [ ] **AC-1**: job green on the PR and on `dev`; `results.fixture.json` uploaded; metrics and wall time in the results register.
- [ ] **AC-2**: a branch that breaks retrieval turns `e2e-eval` red with the gate message; `docs/evidence/k07-gate-fail.txt`; PR closed unmerged.
- [ ] **AC-3**: fails closed (no `|| true`, timeouts set, failure dump present).
- [ ] **AC-4**: `check_submission.py` section I shows kind and `needs:` satisfied; starter-kit section has no old marker failure from docs.
- [ ] **AC-5**: `make test && make lint` green; other five jobs still green.

## 7. Test strategy and traceability
| AC | Level | Command | Needs |
| --- | --- | --- | --- |
| AC-1 | manual | `gh run view <id>`, evidence `k07-e2e-green.txt` | Actions |
| AC-2 | manual | throwaway PR, `docs/evidence/k07-gate-fail.txt` | Actions |
| AC-3 | review | `grep -n '|| true' .github/workflows/ci.yml` empty | nothing |
| AC-4 | manual | `python3 scripts/check_submission.py` | nothing |
| AC-5 | unit | `make test && make lint` | nothing |

## 8. Open questions
None open. D-099 (reuse artifact, kind binary, no helm/kind-action), D-100 (keep policies in `ci`, enforcement on minikube).

## 9. Risks and assumptions
Image loading, ingress readiness and Host routing are the likely CI-only failures; cluster time ~5 min. kind needs port 80 free on the runner (it is). Disk on the laptop is irrelevant: everything runs on the runner.

## 10. Plan
| Step | What | Verify | Commit |
| --- | --- | --- | --- |
| 1 | spec | pushed | `docs(spec): K7 spec and plan` |
| 2 | marker rewording | checker section | `docs: reword the starter-kit marker name` |
| 3 | `e2e-eval` job | PR run green | `ci: e2e-eval on kind` |
| 4 | gate-fail demo (throwaway branch) | red run, PR closed | evidence commit |
| 5 | tester, docs, plan, PR, merge | tester PASS | `docs(k7): ...` |
Estimate 4 h.

## 11. Implementation notes
- First push went green (run 42238088989, 2 m 39 s). The only YAML slip was a colon inside a step `name:` (fixed before the first push), so the list of CI-only failures the plan predicted (image loading, ingress readiness, Host routing) did not occur: kind config with the `ingress-ready` label and 80:80 mapping plus the `provider/kind` ingress-nginx manifest worked as is.
- Race found by the second run (42241904298): `kubectl apply` of the overlay hit `connection refused` from the ingress-nginx admission webhook although the controller pod was Ready. The job failed closed. Fix: build to `ci.yaml`, retry the apply up to 6 times 10 s apart, `exit 1` if it never works (final run 42242724142 green).
- Second race (run 42243531531): the apply retry worked, but the first `POST /api/ask` got nginx's own 503 because ingress-nginx had not yet synced the api endpoints (`Service rahbar/api does not have any active Endpoint`) although the api rollout was done. Fix: a bounded poll of `GET /api/ask` (405 from the api once routed) before the eval, `exit 1` after 60 s. Two races out of the three predicted failure classes (Host routing and image loading did not occur).
- eval needs only `httpx` and `pyyaml`: installed with pinned versions in the job, no new requirements file.
- RELEVANCE_FLOOR=0.0 does not break the gate (f05 abstains on no hits). RETRIEVER=stub does (recall@5 0.80 -> 0.00). Evidence: `docs/evidence/k07-gate-fail.txt`.
- Failure dump step uses `set +e` instead of `|| true` so every diagnostic prints; the gate steps have no `|| true`.
- No deviation from the architecture (4.15 row matches); D-099, D-100.

## 12. Test report
| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-06 | independent subagent: make test, make lint, coverage 98%, gh runs, evidence cross-check, workflow review | PASS | AC-1..5 PASS (green-on-dev is observable only after merge). Three low doc defects (plan wording before merge, checker remark, 5m33s vs 5m36s) fixed. |

## 13. Sign-offs
| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan | 2026-11-06 | pre-approved by Zain | platform plan 0.1 |
| Tester verdict PASS | 2026-11-06 | independent subagent | rounds: 1 |
| Merged | | | PR # |
