# Engineering notes

Seven questions from section 7 of the case study. Questions 5, 6 and 7 are answered in full by the RAG lane (Zain). Questions 1 to 4 sit mostly in the Kubernetes lane: this file gives the facts the RAG code contributes, and a section marked **AHMAD** that he fills from his manifests and his `kubectl` output. Nothing is guessed on his behalf. Line numbers are on `dev` at the time of writing; a number is the line of the first statement named.

## 1. Indexing in API startup: what breaks with 3 replicas and one Chroma volume?

**RAG-lane facts.**
- The API has no write path to Chroma. `grep -rn "upsert\|\.add(\|create_collection\|delete_collection\|modify(" api/app` finds nothing. The only code that creates, fills, deletes or renames a collection is `indexer/pipeline/store.py` (`store`, lines 82 to 111).
- The API's start-up (`api/app/main.py:32` to `:50`, `lifespan`) builds the retriever, the provider and the cache, then calls `state.get()` once to log a pin conflict. It reads; it does not index. The design reason is time: the real indexer run takes **9 min 39 s** and **438 MB** (`/usr/bin/time -v`), with 41 OCR pages taking about 88 s of it. If three replicas did that at start, each would hold the collection name `rahbar` and run `add` into the same Chroma at once, no pod would be ready for ten minutes, and each restart or HPA scale-out (3 to 8) would start the ten minutes again.
- The thing that prevents it in our code is the stage-and-swap: even the Job builds `rahbar_next` and swaps it in only after `count()` matches (`store.py:103` to `:110`), so a concurrent second writer is already unsafe by design; one Job is the only writer.

**AHMAD: add the object that prevents it (Job and CronJob `concurrencyPolicy: Forbid`, Chroma StatefulSet with `volumeClaimTemplates`, the NetworkPolicy `chroma-ingress` that admits `indexer` for writes) and the file and line of each in `k8s/`.**

## 2. Readiness and liveness swapped, Chroma slow for 90 seconds: what happens?

**RAG-lane facts.**
- `/healthz` (`api/app/routes/health.py:24`) returns `{"status":"alive"}` and touches nothing. `/readyz` (`health.py:60`) checks Chroma, the collection, the embedding pin, Redis and the dimension, the Chroma-side checks bounded by `CHECK_TIMEOUT = 2.0` (`health.py:18`) through one shared probe thread (`_within`, `health.py:33`) so a hung Chroma cannot pile up threads; the Redis check is bounded by the client's 1 s socket timeouts. A slow Chroma therefore gives a 503 `failed:["chroma"]` in about 2 s, not a hang.
- Swapped, a 90 s Chroma slowdown would make the liveness probe fail on all three replicas at the same moment, and the kubelet would restart all three. The restarts would not help (Chroma, not the API, is slow), and every pod would be out of service together. Kept as designed, the same slowdown takes the pods out of the Service (0/1) while they stay alive, and they return when Chroma answers.
- The index is also protected on the request path: `ChromaRetriever.retrieve` (`api/app/retrieval/chroma.py:40`) re-resolves the collection once if it is not found, because the swap in AD-02 changes its id (AD-20).

**AHMAD: add the probe periods, thresholds and the manifest lines (`k8s/base/api.yaml`), and the evidence of the rollout.**

## 3. What does a CPU-based HPA measure on a generation service, and what should scale it?

**RAG-lane facts.**
- The API pod does almost no CPU work while a model generates: the model runs in **Ollama on the host**, outside the cluster, and the pod waits on an HTTP call (`api/app/providers/llm/ollama.py:28`, `httpx.Client(timeout=...)`). The route is a synchronous `def` (`api/app/routes/ask.py:14`) that holds a worker thread for the whole generation, 36 to 49 s per question on a warm model and up to 139 s measured (p50 39.0 s, p95 138.6 s).
- So a CPU-based HPA reads a pod that is waiting, not computing. Real saturation shows as threads and model slots: each pod allows `LLM_MAX_CONCURRENCY` (default 2, `api/app/config.py:55`) model calls through a bounded semaphore (`ollama.py:27`), and a call that cannot get a slot within the timeout becomes `provider_error`. Scaling the API from 3 to 8 pods does not make the laptop's single Ollama faster; it only lets more requests queue.
- Signals the RAG code already exports that would be better than CPU: `rahbar_request_duration_seconds`, `rahbar_generation_seconds`, `rahbar_cache_hit_ratio` (`api/app/routes/metrics.py`). A queue depth or in-flight gauge does not exist today; it would be the missing piece for a custom-metric HPA.

**AHMAD: what the HPA actually showed (`kubectl get hpa`, `kubectl top pods`), its target, and the manifest line.**

## 4. The indexer's peak memory, its limit, the margin, and the exit code when it is wrong

**RAG-lane facts.**
- Peak memory of the Job's process on the real corpus: **437 860 kB and 437 732 kB** in two runs (about 428 MiB; `/usr/bin/time -v`). The Ollama model is on the host and is not in that number. `docs/IMPLEMENTATION_PLAN.md` hand-off H-4 gave Ahmad this figure for the limit.
- The Job is set at a 384Mi request and a 1Gi limit (architecture 4.2 after K10, DEV-013), measured in the cluster at a peak of 428 to 484 MiB with no OOM (`docs/evidence/k10-indexer-peak.txt`); the original design numbers were 512Mi and 2Gi. Memory scales with the number of chunks held at once (all 981 chunks and their vectors are in memory before the store step, `indexer/pipeline/run.py:83` to `:101`), so a larger corpus raises it.
- Exit codes: our code returns 0 on success and **1** on any failure, always after a JSON log line (`indexer/pipeline/run.py:107` to `:139`). A wrong `EMBED_MODEL` is the typical bad setting: `dimension()` (`indexer/pipeline/embed.py:20`) raises `unknown EMBED_MODEL` before any wait, `main` logs `indexer failed` and returns 1. A corpus file that does not match `_index.json` returns 1 with `corpus verification failed`. A process killed for exceeding the memory limit is not ours: Kubernetes reports `OOMKilled` and the container exit code is 137. Exit 2 is reserved for an unimplemented stage and is no longer reachable from the real pipeline.

**AHMAD: the limit in `k8s/`, the `kubectl top` output taken during a real run (the checker warns that none is cited), and `OOMKilled` or backoff evidence if he provoked it.**

## 5. recall@5 by question type: where is it worst, and why?

Source: `eval/results.json` and `eval/tuning/chunk-400-50.json` (shipped index: 981 chunks, 400/50, floor 0.70), scored by `eval/run_eval.py` (`section_matches` line 62, `recall_at_k` line 69, `summarise` line 108) and, retrieval only, by `eval/retrieval_only.py recall` (line 45).

| Type | Questions | recall@5 |
| --- | ---: | ---: |
| ordinary (definitional) | 11 | 0.909 |
| version | 2 | 1.000 |
| **exact** | 2 | **0.500** |
| injection | 1 | 1.000 |
| overall (16 answerable) | 16 | 0.875 (14 of 16) |

**Where it is worst: `exact`, 0.500.** The type has two questions (q14 "clause 1.21" and q15); q14 is missed and q15 is found. The only other miss in the whole set, q10, is typed `ordinary` but is the same kind of failure (an exact section name). Both misses are the same at all three chunk sizes (200/25, 400/50, 600/100 all give recall@5 0.875), so they are not a chunking problem.

**Why embeddings struggle here.**
- **q14**, `eval/golden.yaml:105`: "What does clause 1.21 of the academic rules require?" The answer is `academic-rules-handbook-jun-2026.pdf`, section `1.21`, page 10, a text PDF (so not OCR). The question is almost all generic words ("academic rules require") plus one number. A dense embedding gives a digit string little weight and blurs it with its neighbours: 1.21 and 1.22 sit at cosine **0.927** (this is also why the cache threshold had to be 0.96, ADR 0003). The top 5 are generic "Academic Rules" chunks (Prospectus, Student Handbook, rule 5.3), best score **0.713**, and clause 1.21 is not among them. I first explained this wrongly as an OCR problem; the document has a text layer, and I corrected it after running the retrieval.
- **q10**, `eval/golden.yaml:76`: "How often must a faculty member's technical start-up report its progress?" The policy is a scanned PDF that was OCR'd (8 of 8 pages). OCR put clause numbers apart from their text, so the section is named by its title, `Mandatory periodic (six. monthly) deliverables of the start-up`, with `six. monthly` itself damaged. The question's words ("report its progress") match "Evaluation criteria" (0.821) and "Eligibility criteria" (0.811) of the same document better than the damaged title, so the right chunk is outside the top 5.
- Both are retrieval misses, not model errors: in the real run the model abstained on both (`answered_from_context: false`) instead of inventing an answer, so citation validity stayed 16 of 16 and abstention correctness 100%.

**Which technique addresses it.** **Hybrid retrieval**: a lexical score (BM25, or a direct clause-number match) fused with the vector score, so a literal `1.21` or `six monthly` counts. A re-ranker over the top 20 would be the second option. Both are listed as non-goals (architecture 1.2: no reranker, hybrid retrieval optional and not in the baseline, D-006) and are not built; the evidence for them is the 0.500 and the two top-5 lists above. What we did instead, because the miss is structural: keep clause numbers and headings in the text (`docs/PIPELINE.md`, "not stripped") so a lexical stage would have something to match, and set the floor at 0.70 so a near-miss does not reach the model (q14's best is 0.713, 0.013 above the floor).

## 6. EMBED_MODEL changed on the API only: what does the system do, and what would it have done without the guardrail?

**What it does.** The API reads the collection metadata that the indexer wrote (`embed_model`, `dimension`; `indexer/pipeline/store.py:94`) and compares it to its own `EMBED_MODEL`.
1. At start-up `state.get()` (`api/app/main.py:45`) logs the conflict once: `embedding pin conflict` with `collection_embed_model` and `api_embed_model` (`api/app/services/index_state.py:113` to `:122`).
2. `/readyz` returns **503** `{"status":"not_ready","failed":["embed_pin"],...}` (`api/app/routes/health.py:60`). On the cluster the pod stays `0/1` and takes no traffic; `/healthz` still returns 200, so it is not restarted in a loop.
3. `/api/ask` returns **503** `{"detail":"index unavailable"}` before any question is embedded: `require_pin` is called in `api/app/services/answer.py:100` and again in `api/app/retrieval/chroma.py:43`.
4. A different dimension is caught by a second check, `check_dimension` (`index_state.py:128`), which refuses a query vector of the wrong length.
The captured evidence (local run, `EMBED_MODEL=hashing-bow-768` on the API only) is in `docs/FAILURE-ANALYSIS.md`, stage C, with the exact `/readyz` body and log line. The fix is a config diff; re-running the indexer with the new model also fixes it (stage-and-swap, no API restart needed).

**Without it.** I chose `hashing-bow-768` on purpose: it has the same 768 dimensions as `nomic-embed-text`, so Chroma accepts the query with no error. With the pin bypassed, the question "Are mobile phones and smart watches allowed in the examination hall?" returned best scores **0.045, 0.039, 0.038, 0.035, 0.034** from unrelated chunks (an address, "Application to recheck a final exam"), against **0.908** for the right Student Handbook chunk with the right model. No exception, no log line: recall would silently fall to zero, and the only symptom would be abstentions (every score under the floor) or, with a low floor, a model answering from nonsense context.

**AHMAD: the cluster demonstration (H-14): ConfigMap change on the api only, `kubectl get pods` showing `0/1`, `curl /readyz`, then the revert, saved in `docs/evidence/`.**

## 7. The failure that cost us more than an hour

**The model timeout.** The failure that kept returning, across phases 2, 10 and 12, was generation latency on a CPU, and what it did to a timeout we had taken from the architecture. I did not time-box it, so I cannot honestly say "x hours"; it forced a re-run of the whole 18-question evaluation and a deviation record (DEV-007).

**Symptoms.**
- Phase 2: the first measurement of a 6510-token prompt (`scripts/verify_ollama.py`) took **171 s**; two warm reruns took 19.0 s and 19.8 s.
- Phase 10: the same script took **397.8 s** (17 tokens/s of prompt processing) against 20 s the day before (330 tokens/s).
- Phase 12: in the first full evaluation run, two of 18 uncached questions took **123 s (q04) and 139 s (q09)**; p50 39.0 s, p95 138.6 s. The architecture's model timeout was 90 s and the Ingress read timeout 120 s, so those two would have ended as `provider_error` fallbacks, or as a 504 from the Ingress first.

**What we wrongly believed first.** The phase 2 log records the plan: "use the warm number" (19 to 20 s) and treat the 171 s as a one-off from a busy host or a cold model, so the architecture took a 90 s model timeout and a 120 s Ingress timeout, and the real prompts (600 to 800 tokens, not the 6510-token test) looked comfortably inside it. The 398 s run in phase 10 was again put down to other work loading the CPU. Neither was treated as the normal tail until phase 12 measured it on 18 real questions.

**What told us the truth.** The per-stage timings already on every `answered` line (`ms_embed`, `ms_retrieve`, `ms_generate`, `api/app/services/answer.py`, the `log.info("answered", ...)` call) showed retrieval at 0.1 s and the whole delay in `ms_generate`; `scripts/verify_ollama.py` printed the tokens per second, which dropped from 330 to 17 with the same prompt while other work loaded the CPU; and the `rahbar_generation_seconds` histogram and `eval/results.json` showed the tail. So the delay was host CPU contention in Ollama, not our code, and the tail is real: a laptop that is doing anything else can triple the time. Fix: the timeout is **300 s** (`api/app/config.py:54`, `LLM_TIMEOUT_SECONDS`), the Ingress must stay above it (`proxy-read-timeout` of at least 310 s, hand-off H-13), `LLM_MAX_CONCURRENCY` is 2 so the laptop is not oversubscribed, and the cache (ADR 0003) makes a repeat cost 0.2 s.

**Two smaller ones from the same logs.**
- *Citation prefix (DEV-005).* The live model cited section "4.3" where the retrieved section is the long heading `4.3 ...`; the exact-match check rejected a correct answer twice and q01 fell to the canned fallback (77.3 s). The truth was the logged `model output rejected` line with `bad_citation` next to the retrieved `chunk_ids`. The fix is `citation_matches` (`api/app/services/validate.py:23`): a citation may name a retrieved section by its leading clause number, only if exactly one retrieved section matches, and never a bare parent number.
- *Zero chunks, exit 0.* A scanned PDF with no OCR indexed to 0 chunks and the Job still exited 0; the only trace is `document produced no chunks` (`indexer/pipeline/run.py:94`) and the user sees a legitimate-looking abstention. Reproduced on purpose in `docs/FAILURE-ANALYSIS.md`, stage A. Recommended fix, not built: fail the Job when a listed document yields no chunks.
