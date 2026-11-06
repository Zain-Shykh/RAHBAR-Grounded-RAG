# Evidence index

Plain text, the command first (`$ ...`), then the real output, unedited. Cluster files were captured on minikube (Calico, docker driver), namespace `rahbar`; the index there has 980 chunks (DEV-010: the container's Tesseract makes 39 chunks for the faculty policy, the host makes 40). CI and branch-protection files come from GitHub. Each file starts with its date.

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

## Not captured

UI screenshots (chat answer with a citation, an abstention) need a browser against `http://rahbar.local`; they are not in this folder.
