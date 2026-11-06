# Phase K8 spec and plan: CD (Docker Hub, build-push, deploy)

| | |
| --- | --- |
| Phase | K8, from `docs/IMPLEMENTATION_PLAN_PLATFORM.md` |
| Work plan task | A-10 |
| Branch | `ci/k08-cd` |
| Stage | READY FOR PR |
| Started | 2026-11-06 |
| Approved (spec and plan) | pre-approved by Zain, platform plan 0.1 |
| Depends on | K5 (`ci`, `prod` overlays), K6/K7 (`ci.yml` pieces), HP-1 (done: namespace `zain13sv`, secrets set) |

## 1. Objective
`.github/workflows/cd.yml`: on push to `main`, `test` then `build-push` (three images to Docker Hub, tag = commit SHA only) then `deploy` (ephemeral kind, `ci` overlay with the pushed images, rollout wait, smoke test through the Ingress). Needed for R-SUB-2 and R-SUB-3.

## 2. Context
Architecture 4.15 (CD diagram and table), AD-07, AD-19; R-CD-1..5, R-SUB-2, R-SUB-3; rubric: publishing job without `needs:`, `:latest`, secrets in logs; D-013 (decided), D-101 (this phase).

## 3. Scope
In: `cd.yml`; Docker Hub repos created by the first push (public); run summary with names and digests; no-documents check on the pushed images; evidence; docs.
Out: cloud deploy; branch protection (K9, not touched here); settings and secrets (never changed by this session).

## 4. Interfaces and contracts
- Triggers: `push` to `main`, `workflow_dispatch`. Top-level `permissions: contents: read`; no job widens it.
- Jobs and names: `test`, `build-push` (`needs: test`), `deploy` (`needs: build-push`).
- Secrets referenced only as `${{ secrets.DOCKERHUB_USERNAME }}`, `${{ secrets.DOCKERHUB_TOKEN }}` in `docker/login-action`. Namespace `zain13sv` as `env.IMAGE_NS` (literal, public).
- Images `zain13sv/rahbar-{api,indexer,ui}:${{ github.sha }}`; no other tag, never `latest`. `push:` is true only on refs `main` and `dev`, so a dispatch from any other branch only builds.
- Actions pinned by SHA: login-action v4.8.0, build-push-action v7.4.0 (latest releases, checked with `gh api`), the rest as in `ci.yml`.
- Deploy: `kustomize edit set image` on `k8s/overlays/ci` (fixture corpus, `hashing-bow-768`, extractive: AD-07), kind v0.33.0, ingress-nginx `controller-v1.15.1`; the deploy job does not log in to Docker Hub, so the pull proves the images are public.

## 5. Behaviour and design details
`test` re-runs `make lint` and `make test` (Redis service container, as `ci.yml`). `build-push`: buildx, login, three `build-push-action` steps (`provenance: false` keeps the tag a plain image manifest), then a step writing the Docker Hub URLs, SHA and digests to `$GITHUB_STEP_SUMMARY`. `deploy`: pull the three images anonymously and check `/corpus` is absent or empty and print id/size; kind cluster with the `ingress-ready` label and port 80 mapping; apply with the bounded retry for the ingress webhook race (K7); fail if the rendered manifests contain `:latest` or `:ci`; wait for the Job and rollouts; poll until the Ingress routes `/api` (K7 second race); smoke test: BS fee question must return `answered_from_context: true` with at least one citation, hostel question must return `false`; print both JSON bodies; fixed failure dump. No `|| true`.
Honesty: the first run that counts for R-SUB-2 happens after the `dev` to `main` merge (Phase 15). Before that, the rehearsal runs from `dev` by `workflow_dispatch` and pushes SHA tags of a `dev` commit.

## 6. Acceptance criteria
- [x] **AC-1**: `cd.yml` has `test` -> `build-push` (`needs: test`) -> `deploy` (`needs: build-push`), `permissions:`, pinned actions, SHA tags only.
- [x] **AC-2**: rehearsal run green from `dev`: three images on Docker Hub tagged with the SHA, smoke test passed.
- [x] **AC-3**: no secret in any log or file; run logs show `***` for secrets only; `git log -p | grep -iE "dckr_pat|password"` empty.
- [x] **AC-4**: `check_submission.py` section I has no CD, `needs:`, `permissions:` or `:latest` failure.
- [x] **AC-5**: `make test && make lint` green; public images contain no documents.

## 7. Test strategy and traceability
| AC | Level | Command | Needs |
| --- | --- | --- | --- |
| AC-1 | review | `python3 scripts/check_submission.py`, workflow read | nothing |
| AC-2 | manual | `gh workflow run cd.yml --ref dev`, `gh run view`, evidence `k08-cd-run.txt` | Actions, Docker Hub |
| AC-3 | manual | `git log -p | grep ...`, `gh run view --log | grep -c '\*\*\*'` | Actions |
| AC-4 | manual | check_submission | nothing |
| AC-5 | unit/manual | `make test && make lint`; the `/corpus` step in the run | nothing |

## 8. Open questions
None open. D-013 decided by Zain (HP-1); D-101 decided here.

## 9. Risks and assumptions
Docker Hub anonymous pull rate limit (3 images, one pull each in `deploy` plus kind: well below the limit). Repositories are created public on first push if the account default is public; checked after the first run with an anonymous pull (the `deploy` job logs nothing in). The token expires about 6 Dec 2026, after the deadline.

## 10. Plan
| Step | What | Verify | Commit |
| --- | --- | --- | --- |
| 1 | HP-1, D-013 | docs | `docs: record the Docker Hub namespace (HP-1, D-013)` |
| 2 | spec, `cd.yml`, D-101 | check_submission | `ci: cd workflow` |
| 3 | rehearsal run from dev | green, evidence | `docs(k8): ...` |
| 4 | tester, docs, plan, PR, merge | PASS | `docs(k8): ...` |
Estimate 3 h.

## 11. Implementation notes
- `workflow_dispatch` is not offered until the file is on the default branch (`gh workflow run` returned HTTP 404), so the rehearsal used a temporary `push` trigger on `ci/k08-cd` (and the push guard allowed that ref), both removed before the PR. DEV-012.
- Run 42246763004 green on the first try (three jobs about 5 min 40 s). Run 42247612689 (evidence) after moving the summary: Actions masked the namespace in `build-push` because it equals the username secret (`https://hub.docker.com/r/***/...`); the summary is now written in `deploy`, which has no secret, from `build-push` job outputs (digests).
- `deploy` pulls the images with no login: proves they are public. Docker Hub API (anonymous) returned HTTP 200 for the three repos and the SHA tag.
- Sizes: compressed api 90.4 MB, indexer 151.9 MB, ui 27.9 MB; uncompressed 263 / 407 / 64.8 MB.
- `provenance: false` keeps the pushed object a plain image manifest (no attestation index).
- AC-4: `python3 scripts/check_submission.py` section I all ok, 0 failures.

## 12. Test report
| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |

## 13. Sign-offs
| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan | 2026-11-06 | pre-approved by Zain | |
