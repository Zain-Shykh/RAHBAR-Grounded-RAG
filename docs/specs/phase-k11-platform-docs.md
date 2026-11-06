# Phase K11 spec and plan: platform documents

| | |
| --- | --- |
| Phase | K11, from `docs/IMPLEMENTATION_PLAN_PLATFORM.md` |
| Work plan task | A-14 |
| Branch | `docs/k11-platform-docs` |
| Stage | READY FOR PR |
| Started | 2026-11-07 |
| Approved (spec and plan) | pre-approved by Zain (no gate in the platform plan) |
| Depends on | K1 to K10 |

## 1. Objective
The documents that explain the platform are accurate and specific: engineering notes Q1 to Q4 and Q6 answered from the deployment with `k8s/...:line` references that resolve, ADR 0001 linked to manifests and evidence, README and SETUP proven by a clean-clone run, deviations all decided, architecture amended where deviations are absorbed.

## 2. Context
R-ENG-*, R-DOC-*, rubric (README order -5, generic answers score zero). Architecture 4.10, 4.13, 4.15, 9. Carry-overs from K10: chunk count 981 (host) vs 980 (cluster, DEV-010); DEV-012 absorb into 4.15; the K10 limits were never exercised under a real cache-miss load.

## 3. Scope
In: `docs/ENGINEERING-NOTES.md` (all AHMAD markers, chunk-count wording), `docs/adr/0001-indexer-as-job.md`, `README.md`, `docs/SETUP.md`, `docs/AI-USAGE.md`, architecture 4.11, 4.15, 9 (and 5.4 note), `deviations.md` statuses, `docs/IMPLEMENTATION_PLAN.md` section 3, platform plan; evidence `k11-limits-sanity.txt`, `k11-clean-clone.txt`, `k11-reference-check.txt`; a small reference-check script `scripts/check_refs.py`.
Out: UI polish (A-12), new features, browser screenshots (no browser session; stays a hand-off).

## 4. Interfaces and contracts
No config keys, no code. `scripts/check_refs.py <md files>` prints each `path:line` reference in the given docs and whether the file has that line; exit 1 on a miss. Makefile: only if the clean clone finds a failing step.

## 5. Behaviour and design details
Answers are first person plural (the team); one italic line at the top of the answer sections says the Kubernetes parts were written from the deployment by Zain's session because Ahmad was unavailable. HPA answer uses K3/K10 numbers and the I/O-bound explanation, and only metrics the API exports. Chunk counts: 981 = host run (RAG evaluation, `eval/results.json`, baselines); 980 = in-cluster index (DEV-010). Clean clone: fresh directory outside the repo, `make down`, then README line by line.

## 6. Acceptance criteria
- [x] **AC-1**: no AHMAD marker in `docs/ENGINEERING-NOTES.md`; `docs/evidence/k11-reference-check.txt` shows every `k8s/...:NN` reference resolving.
- [x] **AC-2**: `docs/evidence/k11-clean-clone.txt` exists; every README step worked or the README/Makefile was fixed; cluster healthy afterwards (api x3, ui, chroma-0, redis, index present).
- [x] **AC-3**: `docs/evidence/k11-limits-sanity.txt`: six different cache-miss questions via the Ingress, `kubectl top` samples, restartCount 0, no OOMKilled (or limit raised and noted in `resources.md`).
- [x] **AC-4**: `deviations.md`: no entry OPEN without a decision; DEV-011/012 absorbed in architecture 4.11/4.15; index table complete.
- [x] **AC-5**: `check_submission.py` shows no failure; `make test && make lint` green; 981/980 stated consistently.
- [x] **AC-6**: ADR 0001 has manifest and evidence references and a status line saying Ahmad has not reviewed it; README badges point at real workflow files; no claim of a green `cd.yml` run on `main`.

## 7. Test strategy and traceability
| AC | Level | Command |
| --- | --- | --- |
| AC-1 | manual | `python3 scripts/check_refs.py docs/ENGINEERING-NOTES.md docs/adr/0001-indexer-as-job.md`; `grep -n AHMAD docs/ENGINEERING-NOTES.md` |
| AC-2 | manual | transcript in `k11-clean-clone.txt`; `kubectl get pods -n rahbar`; `make ask` |
| AC-3 | manual | `docs/evidence/k11-limits-sanity.txt` |
| AC-4 | manual | `grep -n "Status |" docs/architecture/deviations.md` |
| AC-5 | automated | `python3 scripts/check_submission.py`; `make test && make lint`; `grep -rn 981 docs README.md` |
| AC-6 | manual | read ADR, `README.md` badge URLs vs `.github/workflows/` |

## 8. Plan
1. Spec (this file). 2. Clean-clone run (Ollama up) and limits sanity on the rebuilt cluster. 3. Fix README/Makefile/SETUP from failures. 4. Notes, ADR, reference script. 5. Deviations and architecture. 6. Plan, AI-USAGE, results register. 7. Tester, PR, merge.

## 12. Test report
Round 1, 2026-11-07, branch `docs/k11-platform-docs`, commit 0016b64: **PASS**, all six ACs. Three low defects, all fixed: L-1 `api.yaml:5` cited for the Deployment (kind is line 2), L-2 "9 min 43 s" had no saved evidence (now cites the 9 min 59 s Job and the 578.8 to 599.7 s pipeline timers), L-3 PR number not yet existing (PR opened as #33). Tester verified every cited k8s and api line semantically, all quoted numbers against the evidence files, Q3 metrics against `metrics.py`, 981/980 consistency, deviations statuses against architecture 4.11/4.15 and the workflows, no secret/`:latest`/ui edits. Note from the tester: the fixed README order was not re-run end to end after the edits; its commands match the Makefile and the transcript.
