# ADR 0001: Indexing runs as a Kubernetes Job, never in the API

> Authored by Zain's session from the architecture and the code (D-86), because the checker reads this file first. **Ahmad owns it: review it, add the manifest lines (Job, CronJob, `corpus-data` PVC, NetworkPolicy) and rewrite it in your own words.**

## Status
Accepted · 2026-11-05

## Context
RAHBAR has two paths: a slow, heavy path that turns nine documents into 981 vectors, and a fast, light path that answers a question. On the real corpus the heavy path took **9 min 39 s** (41 OCR pages in 4 min 17 s, embedding 422 s) and **438 MB** peak memory (`/usr/bin/time -v`, two runs); the light path needs about 0.1 s of retrieval. The API runs as three replicas (HPA 3 to 8) over one Chroma volume, so anything the API does at start-up, it does three or more times, at the same moment, to the same store.

The assignment forbids indexing at API start-up (R-IDX-10, R-K8S-JOB, deduction R-DED-3, −10).

## Decision
The indexer is its own image (`indexer/Dockerfile`, entry `python -m pipeline.run`) run as a Job, and as a weekly CronJob for scheduled refreshes. It is the only writer to Chroma. The API has no write path: `grep -rn "upsert\|\.add(\|create_collection\|delete_collection" api/app` finds nothing, and the API image has no OCR packages.

The Job builds a staging collection `rahbar_next`, checks `count()` equals the number of chunks, deletes `rahbar` and renames `rahbar_next` to `rahbar` (`indexer/pipeline/store.py`, lines 82 to 111; architecture AD-02). A run that fails before the delete leaves the live index untouched. Every run stamps a new `index_id` in the collection metadata; the API notices it, re-resolves the collection (AD-20) and drops cache indexes that belong to an older `index_id` (AD-04), so the indexer never needs to reach Redis.

The Job exits 0 on success and 1 on any failure, each as a JSON log line (`indexer/pipeline/run.py`, `main`): a wrong `EMBED_MODEL` fails before any wait (`dimension()` raises), a corpus file whose SHA-256 differs from `corpus/_index.json` fails in `verify`. The documents arrive on a PVC (`corpus-data`) filled by `make corpus`, not baked into the image (AD-08), so a corpus change is a data change, not an image rebuild.

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
- Watch: the Job needs a memory limit above 438 MB with headroom, `activeDeadlineSeconds` above the 9 min 39 s run time (1800 s in the architecture), and an Ollama reachable from the Job's pod.
