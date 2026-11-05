# Phase 11 spec and plan: Semantic cache

| | |
| --- | --- |
| Phase | 11, from `docs/IMPLEMENTATION_PLAN.md` |
| Work plan task | Z-10 |
| Branch | `feat/rag-z10-semantic-cache` |
| Stage | IMPLEMENTING |
| Started | 2026-11-05 |
| Approved (spec and plan) | 2026-11-05, pre-approved by Zain (no gate for this run) |
| Depends on | phase 2 (Redis Stack 7.4.0-v8 verified), phase 8 (`IndexState`, `index_id`), phase 10 (the seam in `services/answer.py`, `/readyz`, metrics) |

## 1. Objective

A Redis Stack vector cache in the API that returns a stored, validated answer for a repeated or paraphrased question, never serves a stale, wrong-version or unsafe answer, invalidates itself when the index is rebuilt, and never fails a request when Redis is down. `CACHE_THRESHOLD` is chosen from real nomic embeddings (R-CAC-3), moved here from phase 12 by Zain's instruction for this run.

## 2. Context

- Architecture: 5.9 (all), 5.5.1 to 5.5.4 (sequence, step 4 and 10, headers, single turn), 5.6.2 (scope key), 4.8 (readiness: Redis PING and cache index present), 4.14 (log field `cache`, metrics), 4.4 (`CACHE_THRESHOLD`, `CACHE_TTL_SECONDS`), AD-03, AD-04, AD-05, AD-15, AD-16, invariants I-3, I-10, I-16.
- Requirements: R-CAC-1..5, R-PRB-2.
- Rubric deductions touched: serving a stale answer after re-index; caching an abstention or fallback; cache hit across versions; a 500 when Redis is down; Redis written by the indexer.
- Decisions: D-001 (Redis Stack, decided), D-027 (invalidation by `index_id`, provisional), D-67/D-68 (readyz `skipped`, `X-Cache: SKIP` until now). New: D-71..D-75.
- Phase 2 verified (spec `phase-02-local-services.md` section 11): `FT.CREATE ... HNSW 6 TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE` with a `scope TAG`, `KNN 1 ... DIALECT 2` filtered by tag, per-entry TTL (`EXPIRE`), `FT.DROPINDEX ... DD`, `FT._LIST`, all on `redis/redis-stack-server:7.4.0-v8`.
- Existing code: `answer.py` (cache seam, `follow_up`, `cache="SKIP"`, log `cache=skipped`), `scope.py` (`Scope.tag`), `index_state.py` (`Snapshot.index_id`, `.dimension`), `routes/metrics.py` (`CACHE_LOOKUPS`, `CACHE_HIT_RATIO` defined, unused), `routes/health.py` (`redis: skipped`), `config.py` (`redis_host`, `redis_port`, `cache_threshold`, `cache_ttl_seconds`), `redis==5.2.1` already pinned.

## 3. Scope

**In scope**

- `api/app/services/cache.py`: `SemanticCache` (Redis Stack), `MemoryCache` (same interface, for unit tests), `get_cache(settings)`.
- Wire into `answer.py` (lookup at step 4, store at step 10), `routes/ask.py`, `main.py` (`app.state.cache`), `routes/health.py` (real Redis check), `routes/metrics.py` (`record_lookup`).
- Tests: unit (cache logic, write rule, scope isolation, degrade on Redis error, readyz), one integration test file run only when `REDIS_URL` is set.
- `scripts/calibrate_cache.py`: the threshold experiment on real nomic embeddings against real Redis Stack. `scripts/live_check_phase11.py`: HIT vs MISS latency and re-index invalidation against a running API.
- Threshold calibration with 0.88, 0.92, 0.96 (and the table) in the plan results register.

**Out of scope**

- Chunking, floor and baselines (phase 12). Calibrating `RELEVANCE_FLOOR`.
- `k8s/` (Ahmad): Redis manifest and ConfigMap keys go in a hand-off.
- `docs/PIPELINE.md` and ADR 0002/0003 text (phase 14); the numbers are recorded in the results register for it.
- Follow-up history field (AD-16); the `follow_up` flag already bypasses the cache.

## 4. Interfaces and contracts

```python
# api/app/services/cache.py
class SemanticCache:                      # name = "redis"
    def __init__(self, client: redis.Redis, threshold: float, ttl_seconds: int, *,
                 clock: Callable[[], float] = time.monotonic, backoff_seconds: float = 5.0) -> None
    def maintain(self, index_id: str, dimension: int) -> bool
        # Idempotent, cheap when index_id is the one already maintained. Creates idx:cache:{index_id}
        # (ignore "already exists"), then FT.DROPINDEX ... DD every other idx:cache:* (ignore "unknown").
        # True when the cache is usable for this index_id. False (and a warning) on any Redis error.
    def lookup(self, index_id: str, vector: Sequence[float], tag: str) -> AskResponse | None
        # KNN 1 filtered by tag; hit iff 1 - dist >= threshold. None on miss, Redis error or bad entry.
    def store(self, index_id: str, vector: Sequence[float], tag: str, question: str,
              response: AskResponse) -> None      # HSET + EXPIRE; never raises
    def check(self, index_id: str, dimension: int) -> None
        # /readyz: PING, then maintain, then the index is in FT._LIST. Raises CacheError on failure.

class MemoryCache:                        # same four methods, in-process, cosine in pure Python
    def __init__(self, threshold: float = 0.92) -> None

def get_cache(settings: Settings) -> SemanticCache      # redis.Redis(host, port, socket_timeout=1, socket_connect_timeout=1)

# answer.py
def answer_question(question, retriever, provider, settings, *, follow_up=False, cache=None) -> AskResult
```

`CacheHeader` stays `HIT | MISS | SKIP`; `Outcome` stays `answered | abstained | fallback | cached`.

Config keys read (already exist): `REDIS_HOST` (`redis`), `REDIS_PORT` (`6379`), `CACHE_THRESHOLD` (`0.92`, replaced by the calibrated value), `CACHE_TTL_SECONDS` (`86400`). No new keys. Redis index name `idx:cache:{index_id}`, entry key `cache:{index_id}:{uuid4 hex}`.

Headers on `/api/ask`: `X-Cache: HIT` with `X-Outcome: cached`; `X-Cache: MISS` (lookup made, or Redis unusable); `X-Cache: SKIP` (no cache wired: stub retriever, no vector because the embedding failed, or `follow_up=True`). HTTP shapes and contracts C-1 to C-8 unchanged.

`/readyz`: `checks.redis` is `ok` or `failed` (503, `failed: ["redis"]`) when a cache is wired; `skipped` when there is none (stub retriever).

## 5. Behaviour and design details

1. **Lookup (step 4).** Only when a cache is wired, a vector exists, the index snapshot has a non-empty `index_id`, and `follow_up` is false. `cache.maintain(snap.index_id, snap.dimension)` first. Then `lookup`. Hit: return the stored `AskResponse` with a fresh `request_id`, outcome `cached`, header `HIT`; retrieval and the model are not called. Anything else: header `MISS`, continue. Every lookup counts `rahbar_cache_lookups_total{result}` and updates `rahbar_cache_hit_ratio = hits / lookups` for the process. A follow-up or a missing vector is `SKIP` and not counted.
2. **Vector length guard.** `lookup` and `store` skip when `len(vector) != dimension` of the maintained index (a model swap cannot write a wrong-size blob).
3. **Write rule (step 10), all must hold:** outcome is `answered`; `answered_from_context` true; at least one citation and every citation names a retrieved `(source, section)` (checked again here, defence in depth); `follow_up` false; a vector exists; the cache was usable at lookup time. Abstentions (below floor or model), fallbacks of every reason, validation failures never reach `store`. `_cacheable(answer, outcome, retrieved, follow_up)` is a pure function with its own tests.
4. **Key includes `index_id` and scope.** The search index and entry prefix carry `index_id`; the `scope` TAG is `Scope.tag` (sha1 of `current`, `all`, or the matched versions). A 2023-rules question and a 2026-rules question have different tags and cannot hit each other even with similarity 1.0. A new `index_id` queries a different, empty index.
5. **Invalidation (AD-04).** `maintain` on a new `index_id` creates the new index and drops all other `idx:cache:*` with `DD`. It runs from `answer_question` (every request, no-op when unchanged) and from `/readyz` (every probe), both fed by the same `IndexState` snapshot, so within `INDEX_REFRESH_SECONDS` of a swap the pod stops seeing old entries. Concurrent pods: create and drop are idempotent, errors "already exists" and "unknown index" are ignored. A request that fetched an old snapshot just before a swap may store under the old prefix: no search index covers it, it is never found and expires by TTL (5.9.4 item 5). Only the API touches Redis; the indexer has no Redis client or setting (grep test).
6. **Redis down degrades to a miss (I-16).** Every Redis call is wrapped in `except (redis.RedisError, OSError, ValueError)`: warning log (`cache unavailable`, error, operation), return miss / do nothing. After a failure the cache is marked down for `backoff_seconds` (5 s): during that time `maintain` returns False without touching Redis, so a dead Redis costs one 1 s timeout per 5 s, not per request. The request still returns 200, header `MISS`, log `cache=miss`. A corrupt stored `response` JSON counts as a miss and is logged.
7. **Log and metrics.** The `answered` line carries `cache` = `hit | miss | skipped`; on a hit it carries `outcome=cached`, `ms_embed`, zero retrieve/generate times. Metric names unchanged (4.14).
8. **`/readyz`.** After the Chroma checks, if a cache is wired and the failure so far is none or `embed_dimension`: `cache.check(index_id, dimension)` (PING, maintain, index present in `FT._LIST`). Failure: `failed: ["redis"]`, 503, per the 4.8 order (chroma, collection, embed_pin, redis, embed_dimension). The Redis client has 1 s socket timeouts, so the check cannot hang a probe.
9. **TTL.** `EXPIRE` of `CACHE_TTL_SECONDS` on every entry, set in the same pipeline as `HSET`.
10. **Threshold experiment.** `scripts/calibrate_cache.py` embeds each pair with real `nomic-embed-text` (`search_query: ` prefix), stores the first question into a throwaway index with the real `SemanticCache` and looks up the second with the same tag at thresholds 0.88, 0.92 and 0.96. The pairs (listed in the script) are paraphrases that should hit and near-misses that must not: withdrawal deadline 2023 vs 2026, clause 1.21 vs 1.22, two different fees, plus others. Same tag is used on purpose: it measures the embedding, not the scope guard. A near-miss that hits is a false hit. Ship the lowest threshold with zero false hits.

## 6. Acceptance criteria

- [ ] **AC-1**: Same question twice against Redis Stack (real API): `X-Cache: MISS` then `HIT`, `X-Outcome: cached` on the hit, same answer and citations, different `request_id`; the hit is faster than the miss by an order of magnitude (numbers recorded).
- [ ] **AC-2**: A 2023-scope question and a 2026-scope question with identical wording apart from the year never hit each other (unit: different `scope.tag`, and a stored entry under one tag is invisible under the other at similarity 1.0).
- [ ] **AC-3**: Abstention (below floor and model), fallback (all three reasons), `follow_up=True` and a response whose citations are not all retrieved are never stored (unit tests on the write rule and on `answer_question`).
- [ ] **AC-4**: The cache key includes `index_id`: an entry written under index A is not returned after `maintain` for index B, and `idx:cache:A` no longer exists in `FT._LIST` (integration, real Redis). End to end: after a re-index and a wait past `INDEX_REFRESH_SECONDS`, the earlier question is `MISS`.
- [ ] **AC-5**: Redis unreachable: `/api/ask` returns 200 with `X-Cache: MISS`, a warning is logged, no exception escapes; `/readyz` returns 503 with `failed: ["redis"]` (unit with a failing client; live with the container stopped).
- [ ] **AC-6**: `/readyz` runs a real Redis check (`ok` when PING works and the current `idx:cache:{index_id}` exists); `skipped` only when no cache is wired.
- [ ] **AC-7**: `rahbar_cache_lookups_total{result="hit"|"miss"}` and `rahbar_cache_hit_ratio` are exposed and move correctly (unit).
- [ ] **AC-8**: `CACHE_THRESHOLD`, `CACHE_TTL_SECONDS`, `REDIS_HOST`, `REDIS_PORT` are read from the environment; entries carry a TTL (integration: `TTL key` > 0 and <= `CACHE_TTL_SECONDS`).
- [ ] **AC-9**: Only the API touches Redis: no `redis` import or `REDIS_*` setting under `indexer/` (test greps), and the API never writes Chroma (existing invariant test still passes).
- [ ] **AC-10**: Threshold table for 0.88, 0.92, 0.96 on real nomic embeddings, the false hit that ruled out each rejected value, the shipped value, justified in the ConfigMap hand-off (one line).
- [ ] **AC-11**: `make test && make lint` green; coverage of `app` not below 60% (target 95%+).

## 7. Test strategy and traceability

| AC | Level | Test or command | Needs |
| --- | --- | --- | --- |
| AC-1 | unit + manual | `api/tests/test_cache_answer.py::test_second_call_is_a_hit_with_fresh_request_id`; `scripts/live_check_phase11.py hit` against a running API | nothing / dev-services, Ollama, index |
| AC-2 | unit | `test_cache_answer.py::test_scope_isolation`, `test_cache.py::test_scope_tag_separates_entries` | nothing |
| AC-3 | unit | `test_cache_answer.py::test_unsafe_outcomes_are_not_stored` (abstain floor/model, fallback x3, follow_up), `test_cacheable_*` | nothing |
| AC-4 | integration + manual | `test_cache_redis.py::test_new_index_id_drops_old_index` (needs `REDIS_URL`); `live_check_phase11.py reindex` | dev-services (+ indexer run) |
| AC-5 | unit + manual | `test_cache.py::test_redis_error_is_a_miss`, `test_cache_answer.py::test_redis_down_still_answers`, `test_health.py::test_redis_failure_is_503`; stop container, curl | nothing / dev-services |
| AC-6 | unit + integration | `test_health.py::test_redis_ok_with_cache`, `test_cache_redis.py::test_check` | nothing / `REDIS_URL` |
| AC-7 | unit | `test_cache_answer.py::test_cache_metrics` | nothing |
| AC-8 | unit + integration | `test_cache.py::test_get_cache_reads_settings`, `test_cache_redis.py::test_entry_has_ttl` | `REDIS_URL` |
| AC-9 | unit | `test_cache.py::test_indexer_has_no_redis` | nothing |
| AC-10 | script | `python scripts/calibrate_cache.py` | dev-services, Ollama |
| AC-11 | command | `make test && make lint`; `cd api && ../.venv/bin/pytest -q --cov=app` | nothing |

Tester extras: stop Redis mid-run; FT index dropped by hand while the API runs (lookup error becomes a miss, `maintain` recreates it? see risk 3); vector of wrong length; very long question; two tags, same vector; TTL expiry.

## 8. Open questions

None blocking; all decided under the pre-approval.

| # | Question | Options and recommendation | Decision entry | Answer |
| --- | --- | --- | --- | --- |
| Q1 | Where does `maintain` run? | A. From `answer_question` and `/readyz`, on each snapshot (rec). B. Inside `IndexState.get`. | D-71 | A |
| Q2 | `X-Cache` when Redis is down | A. `MISS` (architecture 5.5.2 step 4, rec). B. new value `BYPASS`. | D-72 | A |
| Q3 | Threshold calibration lives in phase 11, not 12 | A. Do it now with real embeddings (rec, Zain's instruction). B. Wait. | D-73 | A |
| Q4 | Down-backoff so a dead Redis is not retried per request | A. 5 s circuit (rec). B. none. | D-74 | A |
| Q5 | Store gate re-checks citations | A. yes, defence in depth (rec). B. trust `validate`. | D-75 | A |

## 9. Risks and assumptions

1. **False hits at a low threshold.** nomic embeddings give high cosine to questions that differ by one number or clause. That is exactly what the experiment measures; if no value at or below 0.96 has zero false hits, ship the lowest above the worst false hit and say so.
2. **Real embeddings needed.** The hashing embedder cannot show this; the experiment needs Ollama and `make dev-services`. The index in `rahbar-dev-chroma` may have to be rebuilt (about 10 minutes).
3. **Index dropped behind our back.** If `idx:cache:{id}` is dropped while a pod believes it is maintained, `FT.SEARCH` errors, the lookup is a miss, and store writes under a prefix with no index. To heal, a "no such index" error clears the maintained marker so the next request recreates it. Covered by a unit test.
4. **Snapshot race** (5.9.4 item 4 and 5): a request can store under the old `index_id` just as a swap happens. Harmless by design (unreachable, TTL).
5. **redis-py 5.2.1 and RESP2 reply parsing** of `FT.SEARCH`: parsed by hand from `execute_command`, verified live against 7.4.0-v8.
6. **Memory:** HNSW float32 768 dims is about 3 KB per entry, far under the 512Mi limit at our scale; TTL bounds growth.
7. Redis `maxmemory` policy is not set (Ahmad's manifest). Eviction is not relied on.

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit |
| --- | --- | --- | --- | --- |
| 1 | `MemoryCache`, `_cacheable`, `record_lookup`; unit tests for write rule, scope isolation, index_id isolation | `services/cache.py`, `routes/metrics.py`, `tests/test_cache.py` | `pytest tests/test_cache.py` | `feat(api): cache interface, memory cache and write rule` |
| 2 | `SemanticCache` on Redis Stack: maintain, lookup, store, check, backoff, `get_cache`; recording-fake unit tests (command shape, errors, backoff, heal) | `services/cache.py`, `tests/test_cache.py` | `pytest tests/test_cache.py` | `feat(api): Redis Stack semantic cache` |
| 3 | Wire into `answer_question`, route, `main.py`; answer-level tests (HIT/MISS/SKIP, fresh request_id, unsafe never stored, Redis down) | `services/answer.py`, `routes/ask.py`, `main.py`, `tests/test_cache_answer.py` | `make test && make lint` | `feat(api): cache lookup and store in the query pipeline` |
| 4 | `/readyz` real Redis check; tests | `routes/health.py`, `tests/test_health.py` | `make test` | `feat(api): readyz checks Redis and the cache index` |
| 5 | Integration tests against real Redis (skipped without `REDIS_URL`) | `tests/test_cache_redis.py` | `make dev-services`; `REDIS_URL=redis://localhost:6379 pytest tests/test_cache_redis.py` | `test(api): cache integration tests on Redis Stack` |
| 6 | Threshold experiment script; run with real nomic; record table; set the default `CACHE_THRESHOLD` | `scripts/calibrate_cache.py`, `config.py`, `docs/IMPLEMENTATION_PLAN.md` | `python scripts/calibrate_cache.py` | `feat(scripts): cache threshold experiment on real embeddings` |
| 7 | Live check script; run HIT vs MISS and the re-index invalidation; record | `scripts/live_check_phase11.py` | run with the API, Ollama, Chroma, Redis up | `feat(scripts): live cache checks (hit speed, re-index)` |
| 8 | Docs: spec 11, plan results and hand-offs, AI-USAGE, rubric ticks, deviations if any; testing subagent; fixes; PR | docs | tester PASS | `docs(progress): phase 11 done` |

### 10.2 Test plan

Written with their step (the memory cache and rule first). The tester runs `make test`, `make lint`, coverage, the integration file with `REDIS_URL=redis://localhost:6379`, the live checks, and the extras listed in section 7.

### 10.3 Rollback and risks

Each step is its own commit and leaves `make test` green. If Redis Stack misbehaves in a way phase 2 did not predict, record a deviation and fall back to the plain-Redis app-side cosine (D-001) only with Zain's word (hard stop).

### 10.4 Estimate

3 h in the plan: steps 1 to 5 about 2 h, experiment and live checks about 1 h (plus up to 10 min of re-indexing), docs and tester 1 h. Within 30% of the plan except the tester rounds.

## 11. Implementation notes

<!-- Filled during IMPLEMENT. -->

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |

Coverage of `app`: `__`%

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | 2026-11-05 | Zain (pre-approved, no gate this run) | |
| Tester verdict PASS | | | rounds: |
| Merged | | | PR # |
