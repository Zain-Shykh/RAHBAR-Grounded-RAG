# Final walkthrough (for the oral check)

Two pages, one per lane. Every pointer is a file you can open. Numbers come from `eval/results.json` and are cross-checked by `scripts/check_numbers.py` (`docs/evidence/final-numbers-check.txt`).

---

## Lane 1: RAG (API, indexer, evaluation)

### Map of modules

| Path | What it does | Remember |
| --- | --- | --- |
| `api/app/main.py` | builds the FastAPI app, wires retriever, embedder, provider, cache | reads the index, never builds it |
| `api/app/config.py` | every setting, read once from env (the ConfigMap) | one `EMBED_MODEL` key |
| `api/app/routes/ask.py` | `POST /api/ask` | single turn, so `follow_up=False` |
| `api/app/routes/health.py` | `/healthz` (touches nothing), `/readyz` (503 naming the failing check) | order: chroma, collection, embed_pin, redis, embed_dimension |
| `api/app/routes/metrics.py` | Prometheus `/metrics`, names fixed by architecture 4.14 | |
| `api/app/services/answer.py` | the pipeline: validate, embed, cache lookup, retrieve, floor, prompt, generate, validate, retry once, fallback, store | the order is the design |
| `api/app/services/scope.py` | version intent by rules (years, phrases), no model | decides `superseded` filter and the cache `scope` tag |
| `api/app/services/prompt.py` | numbered, delimited evidence, instructions, first injection defence | |
| `api/app/services/validate.py` | schema check, citation check against retrieved chunks, canned abstention and fallback | no 500 from model output |
| `api/app/services/cache.py` | Redis Stack vector cache (HNSW, cosine), `cacheable()` write rule, `index_id` invalidation | |
| `api/app/services/index_state.py` | the API's read-only view of the live Chroma collection; pin and dimension checks; empty collection is unavailable | |
| `api/app/retrieval/chroma.py` | read-only top-k query, `score = 1 - distance` | only `query`, never a write |
| `api/app/embedding/*`, `providers/llm/*` | Ollama and hashing embedders; ollama, extractive, stub providers | swap = one file |
| `indexer/pipeline/run.py` | the Job entry: verify, extract, clean, chunk, embed, store | runs once, exits |
| `indexer/pipeline/store.py` | the only code that writes to Chroma; stage `rahbar_next`, verify, swap | failed Job leaves `rahbar` untouched |
| `indexer/pipeline/extract.py`, `clean.py`, `chunk.py`, `embed.py`, `verify.py` | pdfplumber + Tesseract OCR; header/footer removal; section-aware 400/50-word chunks; pinned embedder; SHA-256 check | |
| `eval/run_eval.py` | recall@3/5 (by type), citation validity, abstention, gate; `eval/retrieval_only.py` for tuning | gate: recall@5 drop > 5 points, any must-abstain answered, validity < 95% |
| `eval/golden.yaml`, `results.json`, `baseline.json` | 18 questions; shipped numbers | |

### Ten decisions and why

1. **Indexer is a Job, the API only reads** (AD-01, ADR 0001): three API replicas indexing at start would race on one Chroma volume and delay readiness; the assignment also deducts for it.
2. **Stage-and-swap re-index** (AD-02): build `rahbar_next`, verify, then rename. A failed run never damages the live index.
3. **One pinned embedding model** checked against collection metadata (AD-06, `index_state.py`): a mismatch gives `/readyz` 503 `embed_pin` instead of silently wrong retrieval.
4. **Words, not tokens, for chunking; 400/50** (AD-10, ADR 0002): no tokenizer dependency; three configs measured, recall identical, 400/50 gives 981 chunks and amplification 1.04.
5. **Relevance floor 0.70, checked before any model call** (AD-12): the gap between the best out-of-scope score (0.658) and the lowest answerable (0.746); abstention costs no generation.
6. **Citations must match retrieved chunks; one retry; then a canned fallback with HTTP 200** (AD-13, AD-25, `validate.py`): the model is untrusted, a bad output never reaches the user as a 500 or a fake citation.
7. **Version scope by rules, not by the model** (AD-11, `scope.py`): superseded documents are excluded unless the question asks for an old version; the cache is keyed by the same scope (AD-05).
8. **Semantic cache in Redis Stack, threshold 0.96** (AD-03, ADR 0003, `scripts/calibrate_cache.py`): lowest tested value (0.88, 0.90, 0.92, 0.94, 0.96; Phase 11 results register) with no false hit; worst near-miss 0.958.
9. **Cache invalidation by `index_id`, indexer never touches Redis** (AD-04): the indexer stamps the collection; the API drops caches that belong to an older id. Only validated, answered, from-context responses are stored (`cacheable()`).
10. **Ollama on the host, CI with a deterministic embedder and an extractive provider** (AD-06, AD-07): the cluster needs no model weights; CI needs no network and still exercises the whole pipeline.

### The five headline numbers

| Number | Value | Source |
| --- | --- | --- |
| recall@5 (overall) | **0.875** (14 of 16 answerable); ordinary 0.909, version 1.0, exact **0.5**, injection 1.0 | `eval/results.json` |
| citation validity | **1.0** (16 of 16) | same |
| abstention correctness | **1.0** (2 of 2, both stopped at the floor) | same |
| chunks | **981** on the host (all measurements), **980** in the cluster (Tesseract difference, DEV-010) | `docs/PIPELINE.md`, `deviations.md` |
| latency per uncached question | p50 **39.0 s**, p95 **138.6 s** on CPU llama3.2:3b; cache HIT about 0.1 s | `results.json`; `docs/specs/phase-11-semantic-cache.md` |

### Eight questions an examiner will ask

1. **Why can't the API index at start-up?** Three replicas, one Chroma volume: duplicated work, write races, probes failing for minutes. `docs/ENGINEERING-NOTES.md` section 1, `docs/adr/0001-indexer-as-job.md`, `indexer/pipeline/run.py`.
2. **Where is recall worst and what would fix it?** The `exact` type, 0.5: q14 asks for "clause 1.21" and the embedding cannot match a literal number. Hybrid retrieval (BM25 or clause-number match fused with the vector score) would address it; not built, it is a stated non-goal. `ENGINEERING-NOTES.md` section 5, `PIPELINE.md`.
3. **What happens if `EMBED_MODEL` changes on the API only?** The collection metadata says `nomic-embed-text`; `index_state.py` sees the pin differs, `/readyz` returns 503 `embed_pin`, the pod sits at `0/1` and no traffic reaches it. `docs/evidence/k10-embed-pin-mismatch.txt`, `FAILURE-ANALYSIS.md` stage C.
4. **How do you stop a hallucinated citation?** `validate.py` compares every citation to the passages retrieved for this request; mismatch means retry once, then the canned fallback. Tested in `api/tests/test_prompt_validate.py`, measured as validity 1.0.
5. **How did you choose the relevance floor and the cache threshold?** From scores, not by feel: floor 0.70 is the midpoint of 0.658 and 0.746 (`PIPELINE.md`); cache 0.96 is the lowest of five measured values with no false hit (`calibrate_cache.py`, ConfigMap comments).
6. **What does the cache never store, and what happens after a re-index?** Abstentions, fallbacks, validation failures, follow-ups (`cacheable()`, `cache.py:35`). After `make index` the `index_id` changes, the old cache index is dropped, the next request is a MISS (`k10-cache-and-reindex.txt`).
7. **A prompt-injection chunk says "ignore your instructions". What happens?** The evidence is delimited and labelled untrusted in the prompt, the output is schema-validated, citations are checked, nothing is evaluated or executed. Golden question q18 is an injection; `api/tests/test_safety.py`.
8. **Why 980 chunks in the cluster and 981 on the host?** The indexer image has its own Tesseract build and OCRs the 8-page faculty policy into 39 chunks instead of 40. Recorded as DEV-010; every measurement uses the host build.

---

## Lane 2: Platform (Kubernetes, images, CI/CD)

### Map of modules

| Path | What it does |
| --- | --- |
| `k8s/base/namespace.yaml`, `kustomization.yaml` | namespace `rahbar`; the Secret placeholder is deliberately not listed |
| `api.yaml` | Deployment x3, 3 probes (`startup` /healthz up to 30 failures, `readiness` /readyz, `liveness` /healthz), `maxSurge: 1`, `maxUnavailable: 0`, `preStop`, requests and limits |
| `chroma-statefulset.yaml` | StatefulSet, 1 replica, `volumeClaimTemplates` (stable identity and disk) |
| `redis.yaml` | Redis Stack Deployment + PVC (the cache survives a restart) |
| `indexer-job.yaml`, `reindex-cronjob.yaml` | the indexer Job; the weekly CronJob reuses its spec; `make index` creates a Job from the CronJob |
| `corpus-pvc.yaml` | `corpus-data` PVC filled by `make corpus` (AD-08) |
| `services.yaml`, `ingress.yaml` | four ClusterIP Services; one host, `/` to ui, `/api` to api |
| `configmap.yaml` | every tunable, with a one-line justification for the measured ones |
| `networkpolicy.yaml` | default deny, DNS egress, Ollama `ipBlock`, one allow per edge |
| `hpa.yaml`, `pdb.yaml`, `serviceaccounts.yaml` | HPA 3 to 8 on CPU; PDB `minAvailable: 2` (DEV-014); one ServiceAccount per workload |
| `overlays/dev`, `ci`, `prod` | minikube; kind with no model; registry images tagged by SHA |
| `ui/Dockerfile` | nginx, non-root, `/tmp` emptyDir |
| `.github/workflows/ci.yml` | six jobs: `lint`, `test`, `manifests`, `build`, `scan`, `e2e-eval` (kind, fixture corpus, the eval gate) |
| `.github/workflows/cd.yml` | on `main`: `test` then `build-push` (`needs: test`, tag = SHA) then `deploy` (`needs: build-push`, ephemeral cluster, rollout status, Ingress smoke test) |

### Ten decisions and why

1. **Chroma is a StatefulSet, Redis a Deployment with a PVC** (architecture 4.2): Chroma needs a stable volume and identity; Redis is a disposable cache whose data merely survives a restart.
2. **Three probes with different jobs**: `startup` checks process startup through `/healthz`; `readiness` waits for a usable index and removes a pod without restarting it, `liveness` only says the process is alive and touches nothing (so a slow Chroma cannot cause a restart storm). `ENGINEERING-NOTES.md` section 2.
3. **Rolling update `maxUnavailable: 0`, `maxSurge: 1`, `preStop` sleep** so a pod leaves the Service before it stops; measured with zero failed requests (`k10-rollout-update-undo.txt`, `k10-pod-delete.txt`).
4. **Default-deny NetworkPolicy** with one rule per edge: ui cannot reach chroma, api can (`k10-networkpolicy-proof.txt`). Calico is required, so minikube starts with `--cni=calico`.
5. **HPA on CPU, honestly limited** (`ENGINEERING-NOTES.md` section 3): generation runs on the host, so API CPU barely moves while a request waits; in-flight requests would be a better signal. We show the CPU HPA working (`k10-hpa.txt`) and describe the better one.
6. **Requests and limits from measurement** (DEV-013, `docs/evidence/resources.md`): indexer peak 428 to 484 MiB, limit 1Gi; exit 137 means OOMKilled.
7. **Kustomize with `dev`, `ci`, `prod`** (AD-18): the same base, images and Ollama address differ per overlay. The `ci` overlay needs `--load-restrictor LoadRestrictionsNone` (DEV-011).
8. **Secrets**: only a placeholder is in Git; the real Secret is created from an environment variable by `make secret`; CI reads GitHub Secrets (`cd.yml`).
9. **Gate in CI**: six required checks on `main`, strict, one approval (`k09-branch-protection.txt`); a red check blocks the merge (`k09-blocked-merge.txt`). Admin enforcement is off because Ahmad is unavailable (D-014).
10. **CD publishes by commit SHA only, behind `needs:`** (R-DED-9, DEV-012): never `:latest`; the workflow also fails if a mutable tag appears in the rendered manifests.

### The five headline numbers

| Number | Value | Source |
| --- | --- | --- |
| api replicas / HPA range | **3**, scaling **3 to 8** | `k10-hpa.txt` |
| indexer | **980** chunks in about **10 min** in the cluster, peak memory **428 to 484 MiB**, limit 1Gi | `k11-clean-clone.txt`, `k10-resources-applied.txt` (484 Mi under the 1Gi limit; 428 Mi in `k10-indexer-peak.txt` was under the old limit) |
| rolling update / pod delete | **0** failed requests | `k10-rollout-update-undo.txt`, `k10-pod-delete.txt` |
| cache | MISS 32.8 s then HIT **0.098 s** (about 330 times faster, phase 11 live run); HIT, re-index, new `index_id`, MISS, HIT on the cluster | `docs/specs/phase-11-semantic-cache.md` line 188; `k10-cache-and-reindex.txt` |
| CI | **6** jobs, all required; `e2e-eval` on kind about 3 min | `ci.yml`, `k07-e2e-green.txt` |

### Eight questions an examiner will ask

1. **Why is Chroma a StatefulSet?** One replica with its own `volumeClaimTemplates`: the index survives pod deletion and keeps a stable name. `k8s/base/chroma-statefulset.yaml`, architecture 4.2.
2. **What if liveness and readiness are swapped and Chroma is slow for 90 s?** A slow dependency would restart every pod (liveness hitting `/readyz`), and a dead pod would stay in the Service. `ENGINEERING-NOTES.md` section 2, `k8s/base/api.yaml` probes.
3. **Why is CPU a poor HPA signal here and what would be better?** Generation waits on the host's Ollama over HTTP; in-flight requests (the semaphore, `LLM_MAX_CONCURRENCY`, AD-21) or queue depth track load. `ENGINEERING-NOTES.md` section 3.
4. **How big can the indexer get and what is the failure signature?** Peak 428 to 484 MiB, limit 1Gi; if too low the pod is OOMKilled with exit code 137 and the Job retries up to `backoffLimit`. `ENGINEERING-NOTES.md` section 4, `k10-indexer-peak.txt`.
5. **How do you prove the NetworkPolicies work?** `kubectl exec` from a ui pod to chroma times out; from an api pod it succeeds. `docs/evidence/k10-networkpolicy-proof.txt`.
6. **How does CI prevent a bad merge, and how did you show it?** Six required checks; a PR with a failing check had a greyed-out merge button (`k09-blocked-merge.txt`), the same PR green afterwards (`k09-green-pr.txt`). The e2e job runs the gate on fixtures with no model.
7. **How does the deploy job avoid shipping an untested image?** `build-push` needs `test`, `deploy` needs `build-push`; images are tagged by SHA; the deploy runs in an ephemeral kind cluster with rollout status and a smoke test. `.github/workflows/cd.yml`; [main CD run 42297154091](https://github.com/Zain-Shykh/RAHBAR-Grounded-RAG/actions/runs/42297154091) passed all three jobs after release #36. It deployed the SHA images with the fixture overlay; it does not establish a new real-model evaluation or browser screenshot.
8. **How do you re-index without downtime?** `kubectl create job --from=cronjob/reindex manual-reindex-1 -n rahbar` (or `make index`): the Job builds `rahbar_next` and swaps; the API re-resolves the collection, the cache invalidates by `index_id`. `k10-cache-and-reindex.txt`.

---

## Known gaps to say out loud

UI polish and screenshots were not done; there is one commit author because Ahmad was unavailable; Ahmad has not reviewed ADR 0001 and the Kubernetes answers in the engineering notes; hybrid retrieval, `hosted` and `ollama-incluster` are non-goals. Full list: `docs/rubric_checklist.md` section E.
