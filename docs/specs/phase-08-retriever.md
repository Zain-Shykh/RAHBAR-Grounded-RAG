# Phase 08 spec and plan: Retriever, index state, version scope

| | |
| --- | --- |
| Phase | 8, from `docs/IMPLEMENTATION_PLAN.md` |
| Work plan task | Z-07 |
| Branch | `feat/rag-z07-retriever` |
| Stage | READY FOR PR |
| Started | 2026-11-05 |
| Approved (spec and plan) | 2026-11-05, Zain (pre-approved: no gate this session) |
| Depends on | phase 7 (real index, `scripts/check_index.py`) |

## 1. Objective

The API can embed a question with the pinned model, query the live Chroma collection under the right version filter, survive an index swap, and detect an embedding-pin or dimension mismatch. It never writes to Chroma.

## 2. Context

- Architecture: 5.3 (pin, prefixes, parity), 5.5.2 steps 2, 3, 5, 5.6.1 to 5.6.4, 4.8 (readiness diagram), AD-05, AD-09, AD-11, AD-20. Invariants: only the indexer writes; one pinned model; superseded excluded by default.
- Requirements: R-QRY-3 (version-aware retrieval), R-QRY-4 (`score = 1 - distance`, input to the floor), R-PIN-3 (embedding mismatch detected).
- Code this builds on: `api/app/{config,main,schemas}.py`, `api/app/retrieval/{base,chroma,stub,__init__}.py`; the indexer's `pipeline/embedding/` (copied exactly), `pipeline/embed.py` (prefix rule), `pipeline/store.py` (collection metadata, `doc_versions` JSON).
- Decisions: D-57 to D-60 (OPEN_DECISIONS.md), all decided.

## 3. Scope

**In scope**

- `api/app/embedding/{__init__,base,hashing,ollama}.py`: `get_embedder(settings)`; `embed_query(text)` adds the `search_query: ` prefix for `nomic-embed-text*`.
- `api/app/services/scope.py`: pure `scope(question, doc_versions) -> Scope`.
- `api/app/services/index_state.py`: thread-safe snapshot, pin check, dimension check.
- `api/app/retrieval/chroma.py`: `ChromaRetriever.retrieve(question, k, *, vector=None, where=None)`; stub and protocol extended.
- `api/app/config.py`: new settings from architecture 4.4.
- `api/app/main.py` lifespan: embedder, state, retriever; pin problem logged at start.
- `eval/retrieval_only.py`: dev tool: ask, loop, recall@3/@5 over the golden set with `run_eval.summarise`.
- Tests with fakes (no network).

**Out of scope**

- Cache (phase 11), prompt/validate (9), generation, `/readyz` wiring and metrics (10), floor calibration (12). Phase 10 reads `IndexState.problem()`; it is built here but not wired to `/readyz`.

## 4. Interfaces and contracts

```python
# embedding
class Embedder(Protocol):
    model: str
    def embed_query(self, question: str) -> list[float]: ...
class EmbedError(RuntimeError)
def get_embedder(settings: Settings) -> Embedder   # hashing-bow-768 | nomic-embed-text*; else ValueError

# services/scope.py
@dataclass(frozen=True)
class Scope:
    where: dict | None
    key: str                 # "current" | "all" | "2023-08+2023-24"
    tag: str                 # sha1(key)[:12], the cache scope tag
def scope(question: str, doc_versions: Iterable[str]) -> Scope

# services/index_state.py
class IndexUnavailable(RuntimeError)   # Chroma down, collection missing or empty, pin or dimension conflict
@dataclass(frozen=True)
class Snapshot: index_id, embed_model, dimension, doc_versions: list[str], chunk_count, collection, fetched_at
class IndexState:
    def __init__(self, settings, *, client=None, clock=time.monotonic)
    def get(self, *, force: bool = False) -> Snapshot   # refresh if older than INDEX_REFRESH_SECONDS or force
    def check_dimension(self, snap: Snapshot, n: int) -> None
    def problem(self) -> str | None   # None | "chroma" | "collection" | "embed_pin" | "dimension"

# retrieval
Retriever.retrieve(question, k, *, vector: list[float] | None = None, where: dict | None = None) -> list[Passage]
```

New `Settings` keys (defaults from 4.4): `redis_host=redis`, `redis_port=6379`, `relevance_floor=0.50`, `cache_threshold=0.92`, `cache_ttl_seconds=86400`, `llm_num_ctx=8192`, `llm_max_tokens=512`, `llm_timeout_seconds=90`, `llm_max_concurrency=2`, `index_refresh_seconds=10`, `app_version="0.1.0"`. All are already ConfigMap names in architecture 4.4 and have defaults, so no ConfigMap change is required (C-2 unchanged).

## 5. Behaviour and design details

- **Scope (AD-11).** Year tokens `\b20\d\d(?:-\d\d)?\b`; a token matches a known `doc_version` if the version starts with it. Matched versions (union over tokens, sorted) give `where={"doc_version": {"$in": [...]}}`, key = `"+".join(matched)`. No match: older-phrase regex (`old|older|previous|former|earlier|prior|superseded|repealed|before|used to`, word-bounded, case-insensitive) gives `where=None`, key `all`. Else `where={"superseded": False}`, key `current`. A year matching nothing falls through.
- **Embed.** Prefix rule per 5.3; Ollama `POST {OLLAMA_URL}/api/embed`, 3 attempts, 1 s and 2 s back-off (same as the indexer copy), then `EmbedError`. The hashing embedder is a byte-identical copy; the same golden buckets are asserted.
- **Index state (AD-20).** The snapshot re-fetches the collection by name at most every `INDEX_REFRESH_SECONDS`, or on `force`. Lock-protected. `doc_versions` is read from the collection metadata JSON and reduced to unique version strings. Refresh failure with a previous snapshot keeps serving it (logged warning); with none it raises `IndexUnavailable`. Empty collection raises `IndexUnavailable("collection")`.
- **Pin.** `snap.embed_model != settings.embed_model` logs once per `index_id` the exact line from 5.3 (`embedding pin conflict` with `collection_embed_model`, `api_embed_model`, `collection`, `action`), and `retrieve` raises `IndexUnavailable("embed_pin")`: never query with the wrong model.
- **Dimension.** On the first query per `index_id`, `len(vector)` is compared with `snap.dimension`; mismatch logs both numbers and sets `problem() == "dimension"`.
- **Retrieve.** `collection.query(query_embeddings=[vec], n_results=k, where=where, include=[documents, metadatas, distances])`; `score = 1 - distance`; no client-side re-filtering. Not-found error (collection swapped): `state.get(force=True)`, retry once. Any other Chroma/connection error: `IndexUnavailable("chroma")` (phase 10 turns it into 503 `index unavailable`). A missing `page` maps to `None`.
- **Read-only.** The api code calls only `get_collection`, `query`, `count`, `heartbeat`. AC-7's grep enforces it.
- `RETRIEVER=stub` builds no embedder or state; `app.state.index_state` is `None`.

## 6. Acceptance criteria

- [x] **AC-1**: Real index: the withdrawal-deadline question (clause 4.25) returns the 2026 handbook first; with "in 2023" it returns the 2023 rules first.
- [x] **AC-2**: `scope()` tests: year match, older phrase, default, year matching nothing, year matching a superseded and a current version.
- [x] **AC-3**: Re-running the indexer while a script queries in a loop: zero unhandled exceptions in the retriever.
- [x] **AC-4**: `EMBED_MODEL=other` against the real index: pin conflict detected and logged with both names; `retrieve` raises `IndexUnavailable`.
- [x] **AC-5**: Embedder parity: the golden vector from `indexer/tests/test_embed_hashing.py` passes in the api.
- [x] **AC-6**: Stub mode and the existing 11 kit tests pass; `make test && make lint` green.
- [x] **AC-7**: `grep -rnE "\.(add|upsert|delete|modify|create_collection|delete_collection)\(" api/app` has no Chroma write.
- [x] **AC-8**: Retrieval-only recall@3/@5, overall and by type, on the golden set against the real index, in the results register.

## 7. Test strategy and traceability

| AC | Level | Test or command | Needs |
| --- | --- | --- | --- |
| AC-1 | integration | `eval/retrieval_only.py ask "..."` | dev Chroma, Ollama, indexed corpus |
| AC-2 | unit | `api/tests/test_scope.py` | nothing |
| AC-3 | integration + unit | `eval/retrieval_only.py loop` during a re-index; `test_retriever.py::test_swap_retry` (fake collection raises not-found once) | services |
| AC-4 | integration + unit | `EMBED_MODEL=other` run; `test_index_state.py::test_pin_conflict` | services |
| AC-5 | unit | `api/tests/test_embedding.py::test_golden_vector` | nothing |
| AC-6 | unit | `make test && make lint` | nothing |
| AC-7 | static | the grep | nothing |
| AC-8 | integration | `eval/retrieval_only.py recall` | services |

## 8. Open questions

None blocking. D-57 to D-60 are decided in `OPEN_DECISIONS.md`.

## 9. Risks and assumptions

- Chroma 1.0.12's not-found exception class: confirmed against the installed client in step 3.
- "before" in a question ("before the exam") switches to all versions; accepted per 5.6.2, measured in phase 12.
- Query-time behaviour during a swap is checked by the live loop, not only by the fake.

## 10. Plan

| Step | What | Files | Verify | Commit |
| --- | --- | --- | --- | --- |
| 1 | settings + embedders + parity test | `config.py`, `embedding/*`, `tests/test_embedding.py` | `make test` | `feat(api): embedders and settings` |
| 2 | scope | `services/scope.py`, `tests/test_scope.py` | tests | `feat(api): version scope` |
| 3 | index state | `services/index_state.py`, tests | tests | `feat(api): index state with pin check` |
| 4 | retriever, protocol, lifespan | `retrieval/*`, `main.py`, tests | tests, lint | `feat(api): chroma retriever` |
| 5 | dev tool, live checks (AC-1,3,4,8) | `eval/retrieval_only.py` | real index | `feat(eval): retrieval-only runner` |
| 6 | docs, tester, PR | plan, AI-USAGE, deviations | tester PASS | `docs: phase 08` |

Test plan: tests ship with each step; the tester subagent re-runs everything and the live checks. Rollback: revert the step commit; stub mode is untouched. Estimate: 3 h.

## 11. Implementation notes

- Hashing queries add no prefix (the indexer copy strips only `search_document: `); Ollama queries add `search_query: `.
- `ChromaRetriever` tolerates an unknown `EMBED_MODEL` (embedder None, retrieve raises `IndexUnavailable("embed_pin")`) so the pod is not-ready rather than crash-looping.
- Malformed collection metadata raises `IndexUnavailable("collection")` (tester D-T1).
- Phase 10 must map `EmbedError` (Ollama down) to a fallback/503; the retriever does not wrap it.
- Real runs: loop 1 and 2 spanned two swaps, 1689 queries, 0 errors. Early recall (retrieval only): @3 0.875, @5 0.875; misses q10, q14.
- No deviation from the architecture.

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan | 2026-11-05 | Zain (pre-approved) | |
| Tester verdict PASS | | | rounds: |
| Merged | | | PR # |
