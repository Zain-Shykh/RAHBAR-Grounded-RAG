# Phase 10 spec and plan: Generation, orchestration, readiness, metrics

| | |
| --- | --- |
| Phase | 10, from `docs/IMPLEMENTATION_PLAN.md` |
| Work plan task | Z-09 |
| Branch | `feat/rag-z09-generation` |
| Stage | SPEC DRAFT |
| Started | 2026-11-05 |
| Approved (spec and plan) | 2026-11-05, pre-approved by Zain (no gate for this run) |
| Depends on | phases 8 and 9 (retriever, index state, prompt, validate, extractive provider) |

## 1. Objective

The whole query pipeline minus the cache: embed, scope, retrieve, floor, prompt, generate, validate, one retry, canned fallback, headers, log line, metrics; a real Ollama provider; an honest `/readyz`; every metric of architecture 4.14. After it, `make dev` with `RETRIEVER=chroma LLM_PROVIDER=ollama-host` answers cited questions from the real index.

## 2. Context

- Architecture: 4.8 (probes), 4.14 (observability), 5.5.1 to 5.5.4 (query pipeline, headers, single turn), 5.6.3 (floor), 5.7.2 to 5.7.4 (provider, validate, fallback), 5.12 (Ollama), AD-12, AD-13, AD-15, AD-16, AD-21, AD-24, AD-25; invariants I-1 (no Chroma write), I-16 (no 500 from bad model output).
- Requirements: R-QRY-1..8, R-GEN-1..5, R-PRB-2, R-PIN-3, R-OBS-1..4.
- Rubric deductions touched: fabricated citation, a must-abstain answered after a model failure (-10), a lying `/readyz`, `/healthz` that touches a dependency, missing metrics.
- Phase 8 notes for this phase (`phase-08-retriever.md`): `EmbedError` is not wrapped by the retriever, map it to the fallback; `IndexUnavailable` maps to 503 `{"detail": "index unavailable"}`; `/readyz` reads `IndexState.problem()`.
- Phase 9 gives: `build_messages`, `validate`, `abstention`, `fallback`, `retry_hint`, `GenerationResult`, `InvalidModelOutput`, `ProviderError`, `ExtractiveProvider`; `get_provider` raises for `ollama-*` (D-63).
- Existing code to change: `api/app/services/answer.py` (kit stub), `routes/ask.py`, `routes/health.py`, `routes/metrics.py`, `main.py`, `providers/llm/{ollama,base,__init__}.py`, `services/validate.py` (extract `parse_answer`), `tests/test_starter.py` (`/healthz` body gains `version`, per 4.8).
- Open decisions taken here: D-65..D-70 in `docs/OPEN_DECISIONS.md`.

## 3. Scope

**In scope**

- `OllamaProvider` (`POST {OLLAMA_URL}/api/chat`, schema `format`, options, timeout, token counts, concurrency semaphore).
- `answer_question` orchestrator with the cache seam and `follow_up` parameter (no cache yet).
- `/api/ask` headers `X-Outcome`, `X-Cache`; 503 body for an unreachable or unusable index.
- `/healthz` with version; `/readyz` per 4.8; metrics per 4.14; the `answered` log line.
- Tests; A-6 verification on the real model; live runs recorded in the results register.

**Out of scope**

- Semantic cache and the Redis check (phase 11; `/readyz` reports redis `skipped`).
- Floor calibration, hostel-curfew fix (phase 12), hosted provider, streaming.
- `k8s/`, `ui/`, `.github/` (Ahmad).

## 4. Interfaces and contracts

```python
# providers/llm/base.py
class ProviderError(Exception):
    def __init__(self, message: str, *, transient: bool = False) -> None: ...   # .transient

# services/validate.py (extracted from validate())
def parse_answer(raw: str) -> Answer          # InvalidModelOutput("not_json" | "schema")

# providers/llm/ollama.py
class OllamaProvider:
    name: str                                  # settings.llm_provider ("ollama-host" or "ollama-incluster")
    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None) -> None
    def generate(self, question, passages, *, hint=None) -> GenerationResult

# services/answer.py
@dataclass
class AskResult:
    response: AskResponse
    outcome: Literal["answered", "abstained", "fallback", "cached"]
    cache: Literal["HIT", "MISS", "SKIP"]

def answer_question(question: str, retriever: Retriever, provider: LLMProvider,
                    settings: Settings, *, follow_up: bool = False) -> AskResult
```

- Route returns `AskResponse` unchanged (JSON contract frozen, C-1) and sets `X-Outcome`, `X-Cache`.
- `IndexUnavailable` (from the orchestrator) becomes HTTP 503 `{"detail": "index unavailable"}` through an exception handler in `main.py`.
- `GET /healthz` returns `{"status": "alive", "version": settings.app_version}`.
- `GET /readyz` returns 200 `{"status": "ready", "checks": {...}}` or 503 `{"status": "not_ready", "failed": [name], "checks": {...}}`. Names: `chroma`, `collection`, `embed_pin`, `embed_dimension` (from `IndexUnavailable.reason` `dimension`), `redis`.
- Config keys: all exist already (`llm_*`, `ollama_url`, `temperature`, `relevance_floor`). No new keys (ConfigMap contract C-2 unchanged).
- Metrics (exact names, 4.14): `rahbar_requests_total`, `rahbar_request_duration_seconds` and the kit's `rahbar_request_seconds` (D-66), `rahbar_embed_seconds`, `rahbar_retrieval_seconds`, `rahbar_generation_seconds{provider}`, `rahbar_cache_lookups_total{result}`, `rahbar_cache_hit_ratio`, `rahbar_abstentions_total{reason}`, `rahbar_fallbacks_total{reason}`, `rahbar_tokens{direction}`, `rahbar_top_score`, `rahbar_index_info{embed_model,index_id,chunks}`.

## 5. Behaviour and design details

**Orchestrator order** (5.5.2): scope (needs `doc_versions`, so first `state.get()` and `require_pin`) → embed → cache seam (a no-op; `X-Cache: SKIP`) → retrieve with `vector` and `where` → floor → prompt → generate → validate → one retry → fallback → respond.

- Index step: when the retriever has an `index_state` (`state` attribute; the stub has none), `snap = state.get()`; `IndexUnavailable` propagates to the 503 handler. `state.require_pin(snap)` runs before embedding so a wrong-model question never calls Ollama. Stub: `doc_versions=[]`, scope `current`, no embedding.
- Embed: only when the retriever exposes an `embedder`; `EmbedError` gives the fallback outcome with `reason=provider_error`, `retrieved=[]`, nothing cached. `ms_embed` and `rahbar_embed_seconds` observed.
- Retrieve: `retriever.retrieve(question, k, vector=..., where=scope.where)`; `IndexUnavailable` propagates (503). `retrieved` lists all passages returned.
- Floor: `max(score) < RELEVANCE_FLOOR` or no passage → abstention (`abstention()`), no provider call, `abstentions{below_floor}`, `X-Outcome: abstained`. Passages below the floor are not shown to the model, and citations are validated against the shown set.
- Generate loop, at most 2 attempts: `InvalidModelOutput` (from the provider's parse or from `validate`) → second attempt with `retry_hint(exc)`; `ProviderError` with `transient=True` on the first attempt → second attempt without hint; any other `ProviderError` or any other provider exception → fallback `provider_error`. Failure on attempt 2 → fallback; reason `bad_citation` when the last reason starts with `bad_citation`, else `invalid_output`, or `provider_error` for a provider failure. HTTP 200, canned text, never cached.
- Valid `answered_from_context=false` from the model → outcome `abstained`, `abstentions{model}`, `abstain_reason=model`.
- Tokens: sum of `tokens_in`/`tokens_out` over successful provider returns; `rahbar_tokens` observed once per request that made a model call. `ms_generate` covers all attempts.
- `provider` in the response is `provider.name` in every outcome. `reasoning` never leaves `answer_question` (`AskResponse` has no such field).
- `answered` log line (one per request, level INFO, logger `rahbar.answer`): `request_id` (formatter), `top_k`, `chunk_ids`, `scores`, `scope`, `cache` (`skipped` now), `outcome`, `abstain_reason`, `fallback_reason`, `provider`, `tokens_in`, `tokens_out`, `ms_embed`, `ms_retrieve`, `ms_generate`. Question text is not added beyond the existing `request` line.
- `rahbar_top_score` observed with `max(score)` when passages exist. `rahbar_index_info` set to 1 for the live `(embed_model, index_id, chunks)` and the previous label set removed.

**OllamaProvider.** Body `{"model": llm_model, "messages": build_messages(...), "stream": false, "format": Answer.model_json_schema(), "options": {"temperature", "num_ctx", "num_predict"}}`. One reused `httpx.Client(timeout=llm_timeout_seconds)`. `threading.BoundedSemaphore(llm_max_concurrency)` acquired with `timeout=llm_timeout_seconds`; failing to acquire is a non-transient `ProviderError("busy")` (fallback without a retry, 5.12.4). Errors: `httpx.TimeoutException`, `ConnectError`, `ReadError`, `RemoteProtocolError` are transient; HTTP status errors and a malformed envelope (no `message.content`) are not transient. The content string goes through `parse_answer` (`InvalidModelOutput` on failure). Token counts from `prompt_eval_count` and `eval_count` (0 when absent). The provider has no retry, no fallback and no citation check.

**`/readyz`** (4.8): runs `state.get(force=True)` under a 2 s wall-clock limit (Chroma's client has no timeout, so the call runs in a thread; a hung call reports `chroma`). Failure sources: `IndexUnavailable.reason` (`chroma`, `collection`), then `state.problem()` (`embed_pin`, `dimension` reported as `embed_dimension`). Redis: `skipped` and not failing until phase 11. Stub retriever: 200 with `checks: {"retriever": "stub"}`. It never calls Ollama.

**`/healthz`**: no state access, no I/O.

**Lifespan**: unchanged, no Chroma write, no index build; `get_provider` now builds `OllamaProvider` for `ollama-host` and `ollama-incluster` (D-63 closed).

## 6. Acceptance criteria

- [ ] **AC-1**: Real stack (Chroma, real index, Ollama): a golden question returns 200 with a cited answer whose citations all appear in `retrieved`; headers `X-Outcome: answered`, `X-Cache: SKIP`, `X-Request-ID`.
- [ ] **AC-2**: Below-floor question: `answered_from_context=false`, `X-Outcome: abstained`, zero provider calls, log `abstain_reason=below_floor` (unit test); the hostel question on the real model is recorded (abstains or not) without tuning.
- [ ] **AC-3**: `/readyz` 200 with a good index; 503 with `failed: ["embed_pin"]` when `EMBED_MODEL` differs, with the pin-conflict log; 503 `collection` for an empty or missing collection; 503 `chroma` when Chroma is unreachable or hangs more than 2 s; 503 `embed_dimension` after a dimension conflict.
- [ ] **AC-4**: `/healthz` returns `{"status": "alive", "version": ...}` and makes no outbound call (test with every dependency raising on use).
- [ ] **AC-5**: `/metrics` exposes every name of 4.14 (test asserts the list); counters move: `rahbar_abstentions_total{reason="below_floor"}`, `rahbar_fallbacks_total{reason=...}`, `rahbar_tokens`, `rahbar_top_score`.
- [ ] **AC-6**: Each `/api/ask` emits one `answered` JSON line with the fields in section 5 (test captures the log).
- [ ] **AC-7**: Scripted fake provider: invalid then valid output answers after one retry (retry call carries the hint); invalid twice returns the canned fallback, HTTP 200, `X-Outcome: fallback`, `fallbacks{invalid_output}`; bad citation twice gives `{bad_citation}`; a transient `ProviderError` then success answers; a transient error twice and a non-transient error give `{provider_error}`; model abstention is `abstained` with `abstentions{model}`.
- [ ] **AC-8**: `EmbedError` gives a fallback `provider_error`, no retrieval, 200; `IndexUnavailable` from the index or retriever gives 503 `{"detail": "index unavailable"}`, never a 500 traceback.
- [ ] **AC-9**: OllamaProvider (mock transport): request body has `stream=false`, `format` equal to `Answer.model_json_schema()`, `options` with temperature, num_ctx, num_predict; tokens read from `prompt_eval_count`/`eval_count`; timeout and connect errors are transient `ProviderError`, HTTP 500 is not; non-JSON content raises `InvalidModelOutput`; the semaphore limits concurrent calls to `LLM_MAX_CONCURRENCY` and a wait longer than the timeout raises `ProviderError`.
- [ ] **AC-10**: `follow_up=True` is accepted and bypasses the cache seam (`X-Cache: SKIP`); nothing is ever cached or stored by this phase.
- [ ] **AC-11**: `make test && make lint` green; coverage of `app` at least 60% (target 90%); no Chroma write and no indexing in `main.py` (check_submission "G" lines pass).
- [ ] **AC-12**: Live checks recorded in the results register: A-6 on the real model; 3 golden questions; the hostel-curfew question; a live injection check with the planted line from `eval/fixtures/academic-rules-2026.md`; each with latency.
- [ ] **AC-13**: Poisoned-evidence unit test: a fake provider that obeys the planted text yields an answer whose citations still must match, and the prompt contains the evidence only inside delimited blocks.

## 7. Test strategy and traceability

| AC | Level | Test file and name, or command | Needs |
| --- | --- | --- | --- |
| AC-1 | integration, manual | live run script `scripts/live_check_phase10.py` plus curl in Verify | Chroma, Ollama |
| AC-2 | unit and manual | `api/tests/test_answer.py::test_floor_abstains_without_model_call`; live hostel run | nothing; Ollama |
| AC-3 | unit | `api/tests/test_health.py` (fake index state, hung chroma, pin, empty, dimension) | nothing |
| AC-4 | unit | `api/tests/test_health.py::test_healthz_touches_nothing` | nothing |
| AC-5 | unit | `api/tests/test_metrics.py` | nothing |
| AC-6 | unit | `api/tests/test_answer.py::test_answered_log_line_fields` | nothing |
| AC-7 | unit | `api/tests/test_answer.py` retry, fallback, transient, abstain tests | nothing |
| AC-8 | unit | `api/tests/test_answer.py::test_embed_error_falls_back`, `test_index_unavailable_is_503` | nothing |
| AC-9 | unit | `api/tests/test_ollama_provider.py` | nothing (httpx MockTransport) |
| AC-10 | unit | `api/tests/test_answer.py::test_follow_up_skips_cache_seam` | nothing |
| AC-11 | command | `make test && make lint`; `cd api && ../.venv/bin/pytest -q --cov=app`; `python3 scripts/check_submission.py` | nothing |
| AC-12 | manual | `scripts/live_check_phase10.py` output recorded in the register | Chroma, Ollama |
| AC-13 | unit | `api/tests/test_answer.py::test_poisoned_evidence_is_delimited` | nothing |

## 8. Open questions

None blocking. All taken as pre-approved recommendations: D-65..D-70 (`OPEN_DECISIONS.md`). No conflict between the assignment and the architecture was found; the one internal inconsistency (kit metric name vs the 4.14 table) is D-66.

## 9. Risks and assumptions

- A-6 (Ollama honours `format=<schema>` with `num_ctx: 8192`): verified first on the real model; a miss is a deviation.
- The model is slow (10 to 20 s warm, minutes cold): timeouts come from config (90 s); live calls are few. Unit tests never call a model.
- The hostel-curfew question scored 0.594 retrieval, above the 0.50 floor. The live model may invent an answer; phase 10 only records it. Phase 12 owns the fix.
- Chroma's Python client has no timeout: `/readyz` bounds the call with a thread; a hung request from the retrieval path is outside this phase (noted for phase 12 / Ahmad's probes).
- An injection line in evidence may be obeyed by a 3B model; the defence here is the delimiters, the schema, the citation check, and "citations must match": recorded honestly.

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit message |
| --- | --- | --- | --- | --- |
| 0 | A-6 on the real model; record | log, this spec | `scripts/verify_ollama.py` output | `docs(progress): phase 10 A-6 result` |
| 1 | `ProviderError.transient`, `parse_answer`, `OllamaProvider`, `get_provider` wiring + tests | `providers/llm/{base,ollama,__init__}.py`, `services/validate.py`, `tests/test_ollama_provider.py` | `pytest api/tests/test_ollama_provider.py` | `feat(api): OllamaProvider with schema format, semaphore and transient errors` |
| 2 | Metrics module (all 4.14 names) + tests | `routes/metrics.py`, `tests/test_metrics.py` | `pytest -k metrics` | `feat(api): metrics of architecture 4.14` |
| 3 | Orchestrator, headers, 503 handler, `answered` log + tests | `services/answer.py`, `routes/ask.py`, `main.py`, `tests/test_answer.py` | `pytest -k answer` | `feat(api): answer pipeline with floor, retry, fallback, headers` |
| 4 | `/healthz` version, `/readyz` + tests | `routes/health.py`, `main.py`, `tests/test_health.py`, `tests/test_starter.py` | `pytest -k health` | `feat(api): honest /readyz and /healthz` |
| 5 | Live checks script and runs, register | `scripts/live_check_phase10.py` | live output | `test(api): live checks for phase 10` |
| 6 | Tester rounds, deviations, plan, AI-USAGE, PR | docs | `make test && make lint` | per round |

### 10.2 Test plan

Tests are written with each step. The tester brief is `docs/WORKFLOW.md` 6.1: run `make test`, `make lint`, coverage, the live commands, and try to break retry, fallback, readiness (hung Chroma, wrong pin), `/healthz` isolation, and the 503 path.

### 10.3 Rollback and risks

Each step is its own commit; revert the step. The kit stub path (`RETRIEVER=stub LLM_PROVIDER=stub`) must keep working at every commit.

### 10.4 Estimate

About 4 h against 4 h in the work plan.

## 11. Implementation notes

<!-- Filled during IMPLEMENT. -->

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |

Coverage of `app`: `__`%

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | 2026-11-05 | Zain (pre-approved, no gate) | recommended options |
| Tester verdict PASS | | | rounds: |
| Merged | | | PR # |
