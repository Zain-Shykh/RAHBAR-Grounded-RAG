# Phase K5 spec and plan: overlays `ci` and `prod`, manifest validation

| | |
| --- | --- |
| Phase | K5, from `docs/IMPLEMENTATION_PLAN_PLATFORM.md` |
| Work plan task | A-07 |
| Branch | `feat/k8s-k05-overlays` |
| Stage | READY FOR PR |
| Started | 2026-11-06 |
| Approved (spec and plan) | pre-approved by Zain, platform plan 0.1 |
| Depends on | K1 to K4 |

## 1. Objective
Three overlays build and validate: `dev`, `ci` (kind: fixtures, hashing embedder, extractive, no Ollama), `prod` (registry images by SHA).

## 2. Context
Architecture 4.11, 4.5, 4.15, AD-18, AD-27; R-CI-3, R-CI-6, R-CD-3; H-8 (floor 0.20 for hashing scores). `discover()` reads front matter when `_index.json` is absent and `verify` is skipped, so the fixtures need no index file (D-096).

## 3. Scope
In: `k8s/overlays/ci`, `k8s/overlays/prod`, `make manifests`, rehearsal evidence. Out: workflows (K6 to K8).

## 4. Interfaces and contracts
- `ci`: ConfigMap patch (`EMBED_MODEL`, `LLM_PROVIDER`, `RELEVANCE_FLOOR=0.20`, `CORPUS_DIR=/corpus`); `corpus-fixtures` generator (no hash suffix); Job and CronJob volume 0 replaced by the ConfigMap; Ollama egress rules removed from `api-egress` and `indexer-egress`; images `rahbar-*:ci`. No new ConfigMap keys.
- `prod`: images `docker.io/DOCKERHUB_NAMESPACE/rahbar-*:<40 zeros>`, set by `kustomize edit set image` in CD; Ollama ipBlock stays the base placeholder.
- `ci` must be built with `--load-restrictor LoadRestrictionsNone` (D-096).

## 5. Behaviour and design details
The base CronJob receives the Job spec by a `replacements` in base, so overlay patches target both objects. Rehearsal on kind if installable, else a throwaway namespace on minikube.

## 6. Acceptance criteria
- [x] AC-1 `make manifests` passes for dev, ci, prod.
- [x] AC-2 dev re-applies, pods Ready.
- [x] AC-3 ci rehearsal: Job indexed fixtures, api Ready, `run_eval.py` fixture golden/baseline exits 0 (`docs/evidence/k05-ci-overlay-rehearsal.txt`).
- [x] AC-4 prod builds, no `:latest`; `grep -rn ":latest" k8s` empty.
- [x] AC-5 `make test && make lint` green.

## 7. Test strategy
Cluster rehearsal plus the Verify commands; tester subagent re-runs them.

## 8. Open questions
None (D-096 decided).

## 9. Risks
CI-only failures: the rehearsal is the mitigation. Hashing floor 0.20 might fail some fixture questions: the gate result decides.

## 10. Plan
| Step | What | Verify | Commit |
| --- | --- | --- | --- |
| 1 | overlays, Makefile target | `make manifests` | `feat(k8s): K5 ci and prod overlays` |
| 2 | rehearsal, evidence | eval exit 0 | `docs(evidence): K5 rehearsal` |
| 3 | docs, tester, PR | PASS | `docs(progress): K5` |

## 11. Implementation notes
See progress log.

## 12. Test report
Round 1, 2026-11-06, branch feat/k8s-k05-overlays: **PASS**. AC-1..AC-5 PASS (make manifests 30/31/30 resources valid; dev diff vs origin/dev empty, server dry-run ok; ci build has no ipBlock, fixtures ConfigMap mounted in Job and CronJob, floor 0.20; prod pinned, no `:latest`; 257 + 91 tests, lint clean; make target fails loudly on a broken overlay). AC-3 checked from the evidence file only (disk). No defects.
