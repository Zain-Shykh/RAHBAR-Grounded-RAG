# Evidence index

Plain text, the command first (`$ ...`), then the real output, unedited. Cluster files were captured on minikube (Calico, docker driver), namespace `rahbar`; the index there has 980 chunks (DEV-010: the container's Tesseract makes 39 chunks for the faculty policy, the host makes 40). CI and branch-protection files come from GitHub. Each file starts with its date.

## Final release verification (2026-11-07)

Remote GitHub read-back during documentation reconciliation confirmed [Phase 15 PR #35](https://github.com/Zain-Shykh/RAHBAR-Grounded-RAG/pull/35) merged into `dev` at `f3bc39312d07e10c7251389a542b5469be1230dd`, and [release PR #36](https://github.com/Zain-Shykh/RAHBAR-Grounded-RAG/pull/36) merged into `main` at `f59cd9ba17e37468e3c014f15a4ce49546b37a80`. [Main CD run 42297154091](https://github.com/Zain-Shykh/RAHBAR-Grounded-RAG/actions/runs/42297154091) concluded `success`; `test`, `build-push` and `deploy` each concluded `success`.

Verification command: `gh run view 42297154091 --repo Zain-Shykh/RAHBAR-Grounded-RAG --json conclusion,headSha,jobs`. This is a verification summary with external source links, not an unedited raw-output capture. The existing K8 rehearsal logs are unchanged. The deploy uses the CI fixture overlay on ephemeral kind; success does not prove a new real-corpus/model evaluation or browser rendering.

Submission links: [public repository](https://github.com/Zain-Shykh/RAHBAR-Grounded-RAG), [successful main CD](https://github.com/Zain-Shykh/RAHBAR-Grounded-RAG/actions/runs/42297154091), Docker Hub [API](https://hub.docker.com/r/zain13sv/rahbar-api/tags), [indexer](https://hub.docker.com/r/zain13sv/rahbar-indexer/tags), [UI](https://hub.docker.com/r/zain13sv/rahbar-ui/tags). Final tag for all three: `f59cd9ba17e37468e3c014f15a4ce49546b37a80`. Anonymous Docker Hub tag checks in the final audit found all three active with digests matching the CD summary. [Results](../../eval/results.json) and [baseline](../../eval/baseline.json) are committed. Classroom submission remains a human action, due 8 November 2026 at 23:59 PKT (18:59 UTC).

## K11: clean clone, limits check, reference check (2026-11-07)

| File | Shows |
| --- | --- |
| `k11-clean-clone.txt` | the README followed line by line from a fresh clone outside the repository (no `.venv`, no `corpus/raw`): install, test, lint, fetch, `make down`, images, corpus, apply, indexer 980 chunks in 10 min, answer and abstention; what failed and was fixed |
| `k11-limits-sanity.txt` | six different cache-miss golden questions through the Ingress under the K10 limits, `kubectl top` every 10 s, restart counts 0, no OOMKilled |
| `k11-reference-check.txt` | `scripts/check_refs.py`: every `path:line` reference in `docs/ENGINEERING-NOTES.md` and ADR 0001 resolves; no AHMAD marker left |

## K10: final cluster evidence (2026-11-06/07, images rebuilt after the K6 dependency bumps)

| File | Shows |
| --- | --- |
| `k10-top-pods.txt` | `kubectl top pods` idle and during a cache-miss question; node usage |
| `k10-top-during-eval.txt` | `kubectl top` and HPA every 60 s during the 18-question evaluation |
| `k10-indexer-peak.txt` | indexer pod CPU and memory during a manual re-index (peak 428 Mi), no OOMKilled |
| `resources.md` | every request and limit, what was measured, what was set, why (DEV-013) |
| `k10-resources-applied.txt` | the measured numbers applied to the cluster and a re-index under the new limits |
| `k10-endpoints.txt` | `kubectl get endpoints api`: 3 IPs, scaled to 5 (all five listed), back to 3, zero failed requests |
| `k10-hpa.txt` | `kubectl get hpa` idle, scaled 3 to 8 under load with the target forced to 5 %, after revert |
| `k10-rollout-update-undo.txt` | rolling update to `rahbar-api:v2` (`/healthz` version 2.0.0), history, `rollout undo`, previous version serving, zero failed requests |
| `k10-pod-delete.txt` | one api pod deleted while a request loop runs, zero failed requests |
| `k10-embed-pin-mismatch.txt` | `EMBED_MODEL` changed: `0/1`, `/readyz` 503 `embed_pin`, the log line, recovery to `1/1` |
| `k10-cache-and-reindex.txt` | cache MISS, HIT, `make index`, new `index_id`, MISS, HIT |
| `k10-networkpolicy-proof.txt` | default-deny proof re-run on the final deployment |
| `k10-eval-gate.txt`, `k10-eval-results.json` | `make eval` through the Ingress: gate passed, numbers against `eval/baseline.json`; per-question results |

## Failure experiments B and D (phase 16, 2026-11-07, host stack)

Run on the dev Chroma (`:8100`) and host Ollama against the 981-chunk `rahbar` index and a throw-away `rahbar_exp_b` collection (deleted afterwards). The experiment scripts were throw-away (D-83) and are not in the repository; the command lines show what was run. Where a file says `grep` in its command, the echo of the system prompt was filtered out of the JSON lines; the JSON lines themselves are unedited.

| File | Shows |
| --- | --- |
| `k16-b-chunk-stats.txt` | chunk counts, words-per-chunk histogram, collection metadata, per source: 400/50 against 100/0 |
| `k16-b-recall.txt` | `eval/retrieval_only.py recall` on both collections (recall@3 and @5 0.875 on both) |
| `k16-b-expect-coverage.txt` | the golden `expect` text in the top 5: 14/16 against 13/16 |
| `k16-b-boundary-chunks.txt` | the retrieved chunk text for three questions whose answer sits on a chunk boundary (100/0) |
| `k16-b-answers.txt`, `k16-b-single-copy.txt` | the real pipeline's answers and citations on both collections, and with retrieval limited to one copy of the text |
| `k16-d-intact.txt`, `k16-d-d1.txt`, `k16-d-d2.txt` | the same 12 questions with the intact prompt, with "Use ONLY the evidence" removed (D1), and with the abstain rule removed as well (D2); each file starts with the patched system prompt |
| `k16-d-d2-fallback-log.txt` | a D2 rerun with JSON logging: `bad_citation` retry, then an answer with outside knowledge |
| `k16-d-golden-abstain-intact.txt`, `k16-d-golden-abstain-d2.txt` | golden q16, q17, q18 under both prompts |
| `k16-restore.txt` | experiment collection deleted, recall equal to `eval/baseline.json`, `git diff dev -- api indexer eval` empty |

## Earlier phases

| File | Shows |
| --- | --- |
| `k01-images-and-manifests.txt`, `k01-api-before-index.txt`, `k01-persistence-and-security.txt`, `k01-prestop-sleep.txt` | images built and loaded, the api before an index exists, fsGroup and ownership inside the pods, the native preStop sleep |
| `k02-indexer-job.txt`, `k02-first-answer.txt` | the indexer Job on the real corpus, `/readyz` ready and the first answer |
| `k03-ingress.txt`, `k03-hpa-scale.txt`, `k03-rollout.txt` | Ingress, HPA scale-up, a rolling restart with zero failures |
| `k04-networkpolicy-proof.txt` | NetworkPolicy before and after, flows that must work and must not |
| `k05-manifests.txt`, `k05-ci-overlay-rehearsal.txt` | the overlays applied; the `ci` overlay rehearsed on minikube in a throwaway namespace |
| `k06-failing-check.txt`, `k06-redeploy-bumped-images.txt` | a red `manifests` check on a throwaway PR, the redeploy with fastapi 0.135.4 and starlette 1.10.0 |
| `k07-e2e-green.txt`, `k07-gate-fail.txt` | `e2e-eval` on kind green, and failing when the gate is broken |
| `k08-cd-run.txt` | CD run: images pushed to Docker Hub by commit SHA |
| `k09-branch-protection.txt`, `k09-blocked-merge.txt`, `k09-green-pr.txt` | branch protection settings, a merge blocked by a red check, the same PR green and still waiting for review |

## Manually captured screenshots (verified 2026-11-07)

These PNGs were captured manually from real GitHub/RAHBAR interfaces. Codex visually inspected all four without editing them.

| Image | Shows and supporting text evidence |
| --- | --- |
| [Failed manifests job](screenshots/k09-failing-gate.png) | PR #30's failed `manifests` job, Actions run #26 ([42269897845](https://github.com/Zain-Shykh/RAHBAR-Grounded-RAG/actions/runs/42269897845)); UI Deployment schema validation fails and the process exits 2. The screenshot does not show a Merge button. PR/run association and refused merge are recorded in [K9 blocked merge](k09-blocked-merge.txt); settings in [K9 branch protection](k09-branch-protection.txt). |
| [Successful six-job CI](screenshots/k09-passing-gate.png) | PR #37, Actions run #42: lint, test, manifests, build, scan and e2e-eval all successful. This is a separate PR, not PR #30 after recovery. PR #30's actual fixed state is preserved in [K9 green PR](k09-green-pr.txt). |
| [Cited academic-warning answer](screenshots/k10-ui-cited-answer.png) | Real RAHBAR chat UI asks what CGPA puts a student on academic warning; answer `2.00`, with a source citing the June 2026 academic rules handbook, section 5.4, page 24. UI labels it “From the documents” and cache hit. Supporting runtime evaluation: [K10 eval gate](k10-eval-gate.txt) and [per-question results](k10-eval-results.json). |
| [Hostel-curfew abstention](screenshots/k10-ui-abstention.png) | Real RAHBAR chat UI asks the campus-hostel curfew time and responds “The documents in the corpus do not cover this question.” UI labels it “Not covered by the documents” and cache miss. Supporting runtime evaluation: [K10 eval gate](k10-eval-gate.txt) and [per-question results](k10-eval-results.json). |

The K10 text evidence supports runtime behavior; it is not a capture log for these manually taken screenshots.

## Still unresolved

R-CD-6's disabled Merge button and fixed-green state of the same failed PR are not shown by this screenshot pair. The original K9 text captures remain available, but full screenshot compliance is unresolved. Ahmad's ADR 0001, engineering-notes and walkthrough review is unconfirmed.
