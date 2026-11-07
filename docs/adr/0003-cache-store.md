# ADR 0003: The semantic cache lives in Redis Stack, threshold 0.96

## Status
Accepted · 2026-11-05 (phase 11, D-71 to D-75; DEV-006)

## Context
A miss costs a generation on a CPU model: 36 to 49 s per question on a warm model and up to 139 s for the slowest golden questions (p50 39.0 s, p95 138.6 s over 18 questions). A repeated or reworded question should not pay that again. The cache must also be correct: a hit must never return the answer to a different question, and it must expire when the index is rebuilt (R-CAC-5).

The assignment requires Redis or a second Chroma collection and wants the choice defended (R-CAC-1). Two invariants shape it: only the indexer writes to Chroma (I-1), and Redis is reachable from the API only.

## Decision
**Redis Stack** (`redis/redis-stack-server:7.4.0-v8`, a PVC with AOF) with a real HNSW vector index, cosine distance. One search index per live index: `idx:cache:{index_id}` over hashes `cache:{index_id}:{uuid}` holding the question, a `scope` tag, the float32 embedding and the stored `AskResponse` JSON (`api/app/services/cache.py`, `SemanticCache`). A lookup is a KNN 1 search filtered by the scope tag; it is a hit if similarity (`1 - dist`) is at least `CACHE_THRESHOLD`. Entries have `CACHE_TTL_SECONDS` (86 400) as a safety net.

- **Threshold 0.96.** Measured with real `nomic-embed-text` on 9 paraphrase and 9 near-miss pairs (`scripts/calibrate_cache.py`): 0.88 hit 8 of 9 paraphrases with 7 false hits; 0.90 hit 7 of 9 with 5 false hits; 0.92 hit 7 of 9 with 4 false hits (clause 1.21 against 1.22 at 0.927; BS against MS fee per credit hour at 0.924; 2023 against 2026 withdrawal deadline at 0.934); 0.94 still had one (undergraduate against graduate attendance, 0.958); 0.96 hit 4 of 9 with **0** false hits. Shipped the lowest of five measured thresholds with none (original Phase 11 results register in `docs/IMPLEMENTATION_PLAN.md` section 5). The margin is thin: 0.958 against 0.96 is 0.002, on 18 pairs.
- **Scope tag.** The key includes the version intent (`current`, or a named year) so a question about the 2023 rules cannot hit a cached 2026 answer at any threshold (AD-05).
- **Write rule.** `cacheable()` stores only a validated, answered, from-context, non-follow-up response whose citations all match its own retrieved chunks. Abstentions, fallbacks and validation failures are never stored (R-CAC-4; live check: q10, q14, q16, q17 were a MISS every time).
- **Invalidation without the indexer.** The indexer stamps a new `index_id`; each API pod creates the new cache index and drops the older `idx:cache:*` indexes with their entries on its next request or readiness probe (AD-04, DEV-006). The Job never talks to Redis.
- **Failure.** A Redis error is a miss, never a failed request: with Redis stopped, `/api/ask` answered 200 `X-Cache: MISS` and `/readyz` returned 503 `failed:["redis"]`; after restart, entries were intact (AOF).

## Options considered
- **A second Chroma collection.** One fewer service, but the API would write to Chroma, which breaks I-1 and the stage-and-swap that the indexer relies on; the cache would also be deleted by a re-index only if the indexer knew about it. Rejected.
- **Plain Redis with app-side cosine (D-001 B).** Works without the search module, but scans every entry in Python on every request and has no index. Kept as the documented fallback if Redis Stack could not run non-root; it did (phase 2, UID 10001 read-only), so it was not needed.
- **In-process dictionary per pod.** Three pods would each warm separately and a re-index would need a broadcast. Kept only as `MemoryCache`, for tests.
- **Exact-match key (hash of the question).** Safe, but a reworded question never hits; the semantic cache earns its place only where it hits paraphrases.
- **Lower threshold (0.92, one of the three starting candidates).** Rejected by the measurement: four false hits, each a different clause, year or programme.

## Consequences
- A hit costs about one query embedding: 0.12 to 0.20 s against 36 to 73 s for a miss (q07: MISS 48 106 ms, HIT 187 ms and 165 ms), roughly 250 times faster. The cost of the safety margin is a low hit rate: at 0.96 only 4 of 9 paraphrases hit; a control wording at cosine 0.9504 is a MISS, as intended.
- The key is the question vector and scope only. It does not contain `TEMPERATURE`, `TOP_K` or the retrieval code, so answers made under a bad setting are served until the TTL or the next re-index. Found in the failure analysis; the cache was flushed before each experiment (D-85).
- Redis memory is small (about 3 KB per entry) and needs the search module, so plain Redis images do not work; `/readyz` includes a Redis check, so a Redis outage makes the pod not ready while `/api/ask` still answers.
- Watch `rahbar_cache_lookups_total{result}` and `rahbar_cache_hit_ratio`. The 18-pair test set is small; widen it before lowering the threshold.
