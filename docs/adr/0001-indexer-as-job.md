# ADR 0001: Indexing runs as a Kubernetes Job, never in the API

> Authored by Zain's session from the architecture, the code and the deployed manifests (D-86; manifest lines and evidence added at K11). **Ahmad has not reviewed this ADR.** He owns the Kubernetes lane and should read it, correct the manifest references and, if he wants, rewrite it in his own words. The decision itself was accepted on 2026-11-05.

## Status
Accepted · 2026-11-05

## Context
RAHBAR has two paths: a slow, heavy path that turns nine documents into 981 vectors (980 when built inside the cluster, DEV-010), and a fast, light path that answers a question. On the real corpus the heavy path took **9 min 39 s** (embedding alone 422 s; the 41 OCR pages about 88 s; only the wall total is quoted because the register's stage times do not add up to it) and **438 MB** peak memory (`/usr/bin/time -v`, two runs); the light path needs about 0.1 s of retrieval. The API runs as three replicas (HPA 3 to 8) over one Chroma volume, so anything the API does at start-up, it does three or more times, at the same moment, to the same store.

The assignment forbids indexing at API start-up (R-IDX-10, R-K8S-JOB, deduction R-DED-3, −10).

## Decision
The indexer is its own image (`indexer/Dockerfile`, entry `python -m pipeline.run`) run as a Job, and as a weekly CronJob for scheduled refreshes. It is the only writer to Chroma. The API has no write path: `grep -rn "upsert\|\.add(\|create_collection\|delete_collection" api/app` finds nothing, and the API image has no OCR packages.

The Job builds a staging collection `rahbar_next`, checks `count()` equals the number of chunks, deletes `rahbar` and renames `rahbar_next` to `rahbar` (`indexer/pipeline/store.py`, lines 82 to 111; architecture AD-02). A run that fails before the delete leaves the live index untouched. Every run stamps a new `index_id` in the collection metadata; the API notices it, re-resolves the collection (AD-20) and drops cache indexes that belong to an older `index_id` (AD-04), so the indexer never needs to reach Redis.

The Job exits 0 on success and 1 on any failure, each as a JSON log line (`indexer/pipeline/run.py`, `main`): a wrong `EMBED_MODEL` fails before any wait (`dimension()` raises), a corpus file whose SHA-256 differs from `corpus/_index.json` fails in `verify`. The documents arrive on a PVC (`corpus-data`) filled by `make corpus`, not baked into the image (AD-08), so a corpus change is a data change, not an image rebuild.

## In the cluster (manifests and evidence)
- **Job:** `k8s/base/indexer-job.yaml:5` (`backoffLimit: 2` at `:13`, `activeDeadlineSeconds: 1800` at `:14`, `restartPolicy: OnFailure` at `:24`), memory request 384Mi and limit 1Gi at `:41` and `:44`. It never touches Redis and carries its own service account (`k8s/base/serviceaccounts.yaml`).
- **CronJob:** `k8s/base/reindex-cronjob.yaml:12` (`0 3 * * 0`), `concurrencyPolicy: Forbid` at `:13`. Its `jobTemplate.spec` is copied from the Job by a kustomize replacement (`k8s/base/kustomization.yaml:31`), so a manual `make index` and the scheduled run use the same image, env and limits.
- **Corpus delivery:** the `corpus-data` PVC (`k8s/base/corpus-pvc.yaml`) filled by `make corpus` (`k8s/tools/corpus-loader.yaml`).
- **Network:** `chroma-ingress` (`k8s/base/networkpolicy.yaml:100`) admits `api` and `indexer` to Chroma; `indexer-egress` (`:137`) lets the indexer reach only Chroma and the Ollama host. The policy cannot separate a read from a write, so "the API never writes" rests on the code (see ENGINEERING-NOTES Q1).
- **Probes:** the API's are in `k8s/base/api.yaml:52` to `:63`, Chroma's in `k8s/base/chroma-statefulset.yaml:46` to `:57`; an index swap does not make a pod unready because the retriever re-resolves the collection once.
- **Evidence:** the first real run, 980 chunks in 13 min (`docs/evidence/k02-indexer-job.txt`); a manual re-index with memory sampled, peak 428Mi, no OOM (`docs/evidence/k10-indexer-peak.txt`); a re-run under the final limits, 484Mi peak, 9 min 59 s (`docs/evidence/k10-resources-applied.txt`); cache miss, re-index, new `index_id`, miss again (`docs/evidence/k10-cache-and-reindex.txt`); the whole path again from a clean clone (`docs/evidence/k11-clean-clone.txt`).

## Options considered
- **Index in API start-up, guarded by a lock.** Three replicas race on `add` into one Chroma; a leader election or lock is new machinery; every pod restart or scale-out event risks a 10-minute start-up, so readiness would flap; HPA could not add capacity quickly; and the API image would need OCR and 592 MB instead of 388 MB. Rejected.
- **Init container in the API pod.** Runs once per pod, so still three times, and blocks every restart. Rejected.
- **Index from a developer laptop into the cluster.** No cluster-visible record, not repeatable by the CronJob, and breaks "re-index with one command". Rejected.
- **One long-lived indexer Deployment.** A permanent idle pod holding 438 MB for a task that runs for ten minutes a week. Rejected.

## Consequences
- Re-indexing is one command (`kubectl create job --from=cronjob/reindex ...`) with no API redeploy, and a failed run costs nothing.
- The API and the Job can differ only by configuration; the pin (`EMBED_MODEL`, ADR 0004 and `docs/PIPELINE.md`) is what stops a mismatch becoming silent.
- There is a window of a fraction of a second between delete and rename in which the collection does not exist; the API tolerates it by re-resolving once (AD-20).
- A document that extracts to zero chunks does not fail the Job today (the Job exits 0 and logs `document produced no chunks`); this was found in the failure analysis (stage A) and is recommended as a hard failure, not yet built.
- Watch: the Job needs a memory limit above 438 MB with headroom (1Gi is set, measured peak 484Mi), `activeDeadlineSeconds` above the 9 min 39 s run time (1800 s in the architecture), and an Ollama reachable from the Job's pod.
