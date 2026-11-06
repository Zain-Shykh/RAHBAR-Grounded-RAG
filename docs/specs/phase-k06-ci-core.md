# Phase K6 spec and plan: CI part 1 (lint, test, manifests, build, scan)

| | |
| --- | --- |
| Phase | K6, from `docs/IMPLEMENTATION_PLAN_PLATFORM.md` |
| Work plan task | A-08 |
| Branch | `ci/k06-ci-core` |
| Stage | IMPLEMENTING |
| Started | 2026-11-06 |
| Approved (spec and plan) | pre-approved by Zain, platform plan 0.1 |
| Depends on | K5 (`make manifests`, DEV-011 / D-096) |

## 1. Objective
A pull request into `dev` or `main` runs five jobs in GitHub Actions, any of which fails it: `lint`, `test`, `manifests`, `build`, `scan`.

## 2. Context
Architecture 4.15, AD-27; R-CI-1..5, R-CD-5; rubric deductions: no `needs:`, no `permissions:`, `:latest`, unpinned actions. D-096: the `ci` overlay needs the load restrictor off, so `manifests` calls `make manifests`.

## 3. Scope
In: `.github/workflows/ci.yml`, README badge, evidence, results register. Out: e2e-eval (K7), CD (K8), branch protection (K9).

## 4. Interfaces and contracts
- Triggers: `pull_request` to `main`, `dev`; `push` to `dev`. Top-level `permissions: contents: read`; no secrets.
- Job names exactly `lint`, `test`, `manifests`, `build`, `scan` (future required checks), so no matrix (a matrix renames the check).
- All actions pinned to a commit SHA with the tag in a comment (versions checked with `gh api .../releases/latest`): checkout v7.0.1, setup-python v7.1.0, setup-buildx v4.4.1, upload-artifact v7.0.2, download-artifact v8.0.2, trivy-action v0.36.0. kustomize 5.8.3 and kubeconform 0.8.0 as in SETUP.md.

## 5. Behaviour and design details
- `lint`, `test`: `make install` then `make lint` / `make test`. `test` also has a `redis/redis-stack-server:7.4.0-v8` service container and `REDIS_URL`, so the 19 Redis tests run, and a second step enforces api coverage >= 60%.
- `manifests`: `make manifests` (dev, ci, prod, `kubeconform -strict`).
- `build`: `needs: [lint, test, manifests]`; `docker buildx build --load` of three images tagged with the commit SHA, saved to one tar artifact (1 day). Nothing is pushed.
- `scan`: `needs: build`; loads the tar; Trivy per image, HIGH,CRITICAL, `--ignore-unfixed`, exit 1. Three steps (not a matrix) so the job keeps its name.

## 6. Acceptance criteria
- [ ] AC-1 PR into dev shows the five jobs, all green on the final commit.
- [ ] AC-2 A broken manifest fails `manifests` (`docs/evidence/k06-failing-check.txt`, PR closed).
- [ ] AC-3 `permissions:` block, pinned actions, `needs:` on build and scan, no `:latest`.
- [ ] AC-4 Trivy ran on all three images; findings and action in the results register.
- [ ] AC-5 `check_submission.py` section I has no failure for what exists.
- [ ] AC-6 README badge points at ci.yml.
- [ ] AC-7 `make test && make lint` green.

## 7. Test strategy
`actionlint` locally; real runs on Actions; throwaway branch with an invalid `apiVersion`; tester subagent re-checks.

## 8. Open questions
None blocking. D-097 (Redis service container), D-098 (pin by SHA, one scan job).

## 9. Risks and assumptions
Trivy may flag base images: bump tag or record accepted risk (ADR 0004). Redis service flakiness: fall back to skipped tests.

## 10. Plan
1. Workflow + badge, actionlint. 2. Push, open PR, iterate to green. 3. Rehearsal branch. 4. Tester. 5. Docs, merge.

## 11. Implementation log
(see platform plan progress log)

## 12. Test report
(tester rounds below)
