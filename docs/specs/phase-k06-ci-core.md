# Phase K6 spec and plan: CI part 1 (lint, test, manifests, build, scan)

| | |
| --- | --- |
| Phase | K6, from `docs/IMPLEMENTATION_PLAN_PLATFORM.md` |
| Work plan task | A-08 |
| Branch | `ci/k06-ci-core` |
| Stage | MERGED |
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
- [x] AC-1 PR into dev shows the five jobs, all green on the final commit.
- [x] AC-2 A broken manifest fails `manifests` (`docs/evidence/k06-failing-check.txt`, PR closed).
- [x] AC-3 `permissions:` block, pinned actions, `needs:` on build and scan, no `:latest`.
- [x] AC-4 Trivy ran on all three images; findings and action in the results register.
- [x] AC-5 `check_submission.py` section I has no failure for what exists.
- [x] AC-6 README badge points at ci.yml.
- [x] AC-7 `make test && make lint` green.

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

### Round 1 (independent tester)

| AC | Result | Evidence |
| --- | --- | --- |
| AC-1 | PASS | Run 42236140181 on head 2b11c19: lint, test, manifests, build, scan all pass (`gh pr checks 25`, run conclusion success). |
| AC-2 | PASS | `docs/evidence/k06-failing-check.txt` shows run 42235467712, manifests fail, build/scan skipping; PR #26 CLOSED, mergedAt null; `ci/k06-rehearsal-broken` absent on origin. |
| AC-3 | PASS | actionlint clean; top-level `permissions`; all 8 `uses:` pinned to 40-char SHA with tag comment; build `needs: [lint, test, manifests]`, scan `needs: build`; no login/push/secrets. `:latest` grep only hits Ollama model-name handling in indexer code/tests (not images). |
| AC-4 | PASS | Results register has the Trivy row (3 / 22 / 63 findings, fixes, final 0). Scan job green. |
| AC-5 | PASS | Section I FAILs left: kind job, rollout status, registry login, eval runner in CI (K7 / K8 only). |
| AC-6 | PASS | README line 5 badge -> actions/workflows/ci.yml. |
| AC-7 | PASS | `make test` 257 + 91 passed; `make lint` ruff and mypy clean; api `pytest --cov=app` 283 passed, 19 skipped (no local Redis), 98% coverage. |

Break attempts: ui/Dockerfile still ends `USER 101` (USER root only for `apk upgrade`); diff does not touch ui/index.html, ui/nginx.conf, settings or secrets; installed venv already has fastapi 0.135.4, starlette 1.10.0, pdfplumber 0.11.10, pypdf 7.0.0, so tests ran on the bumped deps; no secret/token/password strings in the diff. Cluster: api x3, ui, redis, chroma Ready; indexer Completed.

Defects: none. Note: the final-commit run was still in progress when tester started; waited until success.

Verdict: PASS
