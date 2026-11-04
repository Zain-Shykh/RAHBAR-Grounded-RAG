# Contributing to RAHBAR

This is a two-person project with a hard deadline, so the rules are few and they exist to prevent specific problems: broken `main`, merge conflicts, secrets in history, and code that quietly drifts from the design.

New here? Set up first: [`docs/SETUP.md`](docs/SETUP.md). Then read [`docs/architecture/architecture.md`](docs/architecture/architecture.md) and [`docs/WORKPLAN.md`](docs/WORKPLAN.md).

## 1. The ground rules

1. **The architecture is the source of truth.** If you are about to decide something `docs/architecture/architecture.md` already decides, follow it. If the code must differ, write an entry in [`docs/architecture/deviations.md`](docs/architecture/deviations.md) in the same pull request.
2. **Unsure? Write it down, do not guess.** Add an entry to [`docs/OPEN_DECISIONS.md`](docs/OPEN_DECISIONS.md) and carry on with whatever is not blocked.
3. **Never push to `main`.** It is protected: pull request, passing CI, one approval. A direct push costs marks.
4. **Never commit a secret.** Not an API key, not a Docker Hub token, not a kubeconfig, not a `.env`, even for a minute. A secret in Git history cannot be fully removed and costs 20 marks. Secrets live in GitHub Secrets and in `kubectl create secret`. If one leaks, tell the other person at once: it must be rotated.
5. **Never commit the documents.** `corpus/raw/` is gitignored. Only `corpus/sources.yaml` and `corpus/MANIFEST.md` go in.
6. **Stay in your lane's files** (section 3). Need a change in the other person's files? Ask, or open a small pull request for them to review.
7. **Disclose AI use.** Add what the AI wrote or shaped, and what you changed, to [`docs/AI-USAGE.md`](docs/AI-USAGE.md) as you go, not on the last day.

## 2. Branches and pull requests

```
main      protected. Only receives pull requests from dev. Always deployable.
dev       integration branch. Receives short-lived feature branches.
feat/*    one task, one branch, one pull request. Branch off dev.
```

| Branch name | For |
| --- | --- |
| `feat/<lane>-<topic>` | new work, for example `feat/rag-chunker`, `feat/k8s-networkpolicy` |
| `fix/<topic>` | a bug fix |
| `docs/<topic>` | documentation only |
| `ci/<topic>` | workflow changes |

Lanes: `rag` (RAG, API, indexer, eval) and `k8s` (Kubernetes, UI, CI/CD).

Day to day:

```bash
git checkout dev && git pull
git checkout -b feat/rag-chunker
# ...work, commit small...
make test && make lint                 # must be green before you push
git push -u origin feat/rag-chunker
gh pr create --base dev                # or use the GitHub page
```

Merging into `dev`:

- Change only touches files in **your own lane**: merge it yourself once `make test && make lint` pass locally (and CI is green, once CI exists).
- Change touches the **other lane's files**, `Makefile`, `requirements.txt`, `docs/architecture/*`, or a contract (schemas, metadata fields, ConfigMap keys, metric names): the other person reviews it first.
- Delete the branch after merging.

Merging `dev` into `main`: one pull request, when `dev` is green, approved by the other person. Use a merge commit (keep history). `main` is touched only through this.

Keep branches short: aim to merge within a day. Pull `dev` into your branch daily (`git pull origin dev`) so conflicts stay small.

## 3. Ownership

Each directory has one owner, so two people rarely edit the same file. The detailed task list is in [`docs/WORKPLAN.md`](docs/WORKPLAN.md).

| Owner | Files and directories |
| --- | --- |
| **Zain** (RAG lane) | `api/**` (including `api/Dockerfile`, `api/.dockerignore`), `indexer/**` (including its Dockerfile), `eval/**`, `corpus/**`, `docs/PIPELINE.md`, `docs/FAILURE-ANALYSIS.md`, ADRs 0002 to 0004 |
| **Ahmad** (platform lane) | `ui/**`, `k8s/**`, `.github/**`, `docs/evidence/**`, `docs/SETUP.md` upkeep, ADR 0001 |
| **Shared** (edit with care, tell the other person) | `Makefile`, `requirements.txt`, `README.md`, `docs/ENGINEERING-NOTES.md` (each writes their own questions), `docs/architecture/*`, `docs/OPEN_DECISIONS.md`, `docs/AI-USAGE.md`, `.gitignore` |

## 4. Commits

[Conventional Commits](https://www.conventionalcommits.org/), imperative mood, small and focused:

```
feat(indexer): add structure-aware chunker
fix(api): retry once when the model returns invalid JSON
docs(architecture): record cache invalidation design
ci: add kubeconform step
test(api): cover the prompt-injection case
chore: pin trivy action version
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `ci`, `chore`. Scope is the directory or area.

If an AI assistant wrote or substantially shaped the commit, end the message with the `Co-Authored-By:` line the tool provides, so the history is honest.

## 5. Pull request checklist

The pull request template shows this list. Do not tick a box you did not check.

- [ ] `make test` and `make lint` pass locally
- [ ] No secrets, keys, tokens or `.env` in the diff (`git diff --staged | grep -iE "key|token|secret|password"`)
- [ ] No `corpus/raw/` content in the diff
- [ ] Matches `docs/architecture/architecture.md`, or a `deviations.md` entry is included
- [ ] New behaviour has a test; no test was deleted or weakened to get green
- [ ] Docs updated if behaviour, config keys or commands changed
- [ ] `docs/AI-USAGE.md` updated if AI helped
- [ ] Anything unclear is recorded in `docs/OPEN_DECISIONS.md`

## 6. Code standards

**Python 3.12.** `ruff` and `mypy` clean (`make lint`). Type hints on public functions.

- Config comes from environment variables through `Settings`; no hard-coded tunables that belong in the ConfigMap.
- The API never writes to Chroma. The indexer never touches Redis. `/healthz` touches nothing else.
- Keep `api/app/services/answer.py` thin; each step lives in its own module with its own unit test.
- Logs are JSON on stdout through the shared logger; never `print` in the API, never log secrets.
- Retrieved text and model output are untrusted: never `eval`, never build queries from them.
- Tests need no network, no model and no cluster. A test that sleeps to wait for something is a flaky test.

**Kubernetes manifests.** Namespace `rahbar` on every object; labels `app.kubernetes.io/name` and `app.kubernetes.io/part-of`; requests and limits on every container; `runAsNonRoot`, `readOnlyRootFilesystem`, `capabilities.drop: [ALL]`; pinned image tags, never `:latest`. Validate with `kustomize build k8s/overlays/<x> | kubeconform -strict`.

**Workflows.** Every job that publishes or deploys has `needs:`. Every workflow has a least-privilege `permissions:` block. Actions are pinned to a version or SHA. Credentials come from GitHub Secrets.

**Docs.** Plain, specific, and tied to files and numbers. A generic answer scores zero in the engineering notes.

## 7. Daily rhythm

- Two short syncs a day (about 10 minutes): start of work, and evening. What merged, what is blocked, what you need from the other person.
- Before you stop for the day: push your branch, even unfinished, and update the status boxes in `docs/WORKPLAN.md`.
- Blocked on the other lane? Say so immediately and switch to the stand-in task listed in the work plan.

## 8. Reporting a problem

Open a GitHub issue, or message the team, with: the exact command, the full error, and `kubectl get pods -n rahbar` plus `kubectl describe pod <pod> -n rahbar` when it is a cluster problem. Diagnose in this order: status, events, logs.
