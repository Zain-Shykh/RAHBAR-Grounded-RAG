# Phase K9 spec and plan: branch protection and the gate demonstration

| | |
| --- | --- |
| Phase | K9, from `docs/IMPLEMENTATION_PLAN_PLATFORM.md` |
| Work plan task | A-11 |
| Branch | `docs/k09-gate-demo` |
| Stage | IMPLEMENTING |
| Started | 2026-11-06 |
| Approved (spec and plan) | pre-approved by Zain (HP-2 done by the orchestrator) |
| Depends on | K6, K7, K8 |

## 1. Objective
`main` accepts changes only through a PR with the six required checks green and one approval; the repo holds the evidence (settings, a blocked merge, the same PR green after the fix).

## 2. Context
R-CD-6, rubric branch-protection rows, D-014. Settings were applied by the orchestrator (this session may not change settings); this phase only reads them back and demonstrates the gate.

## 3. Scope
In: read back protection; throwaway branch + PR into `main` with a broken manifest; evidence; D-014 decided; docs. Out: protecting `dev`; any merge into `main` (Phase 15); settings changes.

## 4. Interfaces and contracts
Required checks `lint, test, manifests, build, scan, e2e-eval` (strict), 1 approval (dismiss stale), conversation resolution, no force push/deletion, `enforce_admins` OFF (Ahmad, the only second approver, is unavailable).

## 5. Behaviour and design details
Demo branch `demo/k09-red-gate` from `dev`: invalid `apiVersion` in a `k8s/` manifest turns `manifests` red (K6 rehearsal), PR base `main`. `gh pr merge --merge` without `--admin` must be refused. Fix pushed to the same branch; checks green; PR still blocked by the missing approval. Close the PR unmerged, delete the branch.

## 6. Acceptance criteria
- [ ] **AC-1**: `k09-branch-protection.txt` shows the six checks, one approval, no force push/deletion.
- [ ] **AC-2**: `k09-blocked-merge.txt` (red PR, refused merge) and `k09-green-pr.txt` (green, still blocked on review) with PR numbers.
- [ ] **AC-3**: D-014 DECIDED; `make test && make lint` green.

## 7. Test strategy and traceability
Manual on GitHub: `gh api`, `gh pr checks`, `gh pr view --json`, `gh pr merge`. Evidence under `docs/evidence/`.

## 8. Open questions
None. D-014 decided here with the orchestrator's values.

## 9. Risks and assumptions
Enforcement off means the owner can merge past a red check; recorded honestly. A merge that unexpectedly succeeds = BLOCKED.

## 10. Plan
| Step | What | Commit |
| --- | --- | --- |
| 1 | spec, protection evidence | `docs(k9): spec and branch protection read-back` |
| 2 | red PR, refused merge, fix, green, close | `docs(k9): gate demonstration evidence` |
| 3 | plan, D-014, AI-USAGE, tester | `docs(k9): plan, D-014, AI-USAGE` |
