# Phase 07 spec and plan: Embed, store, full indexer run

| | |
| --- | --- |
| Phase | 7, from `docs/IMPLEMENTATION_PLAN.md` |
| Work plan task | Z-06 |
| Branch | `feat/rag-z06-embed-store` |
| Stage | SPEC DRAFT |
| Started | 2026-11-05 |
| Approved (spec and plan) | 2026-11-05, Zain (pre-approved: no gate this session) |
| Depends on | phases 2 (services verified), 4 (extract, clean), 6 (chunk); follow-ups D-052 (Handbook spreads), DEV-001..003 absorbed |

## 1. Objective

`python -m pipeline.run` builds the real index: extract, clean, chunk, embed with the pinned model, and store in Chroma by stage-and-swap, so `rahbar` always holds a complete, correctly labelled collection (or the previous one). Embedding code has two implementations behind one pin: Ollama `nomic-embed-text` and the offline `hashing-bow-768` for CI.

## 2. Context

- Architecture: 5.3 (embedding contract), 5.4.1 (run sequence), 5.4.2, 5.4.3 (record and collection metadata), 5.4.4 (swap), 4.4 (`EMBED_BATCH_SIZE`), AD-02, AD-06, AD-09, AD-23. Invariants: only the indexer writes Chroma; one pinned model; five metadata fields on every chunk.
- Requirements: R-IDX-4 (one vector per chunk, pinned model), R-IDX-5 (id, text, vector, metadata stored), R-PIN-2 (model and dimension in collection metadata).
- Verified in phase 2: `create_collection` with metadata, `modify(name=)` keeps metadata (A-2), 500 records per `add` (A-3), `/api/embed` returns 768-dim vectors for a batch of 32 (A-6).
- Existing code: `indexer/pipeline/{extract,clean,chunk,verify,run,config,models,dummy}.py` done; `embed.py` and `store.py` are `STARTER-TODO`. The api has no embedding code yet (phase 8 copies it); the parity test is a golden vector here.
- Open decisions: D-053..D-056 (this phase, section 8).

## 3. Scope

**In scope**

- `indexer/pipeline/embedding/{__init__,ollama,hashing}.py`, `embed.py` (dispatcher and prefix rule).
- `indexer/pipeline/store.py`: stage-and-swap, collection metadata, id guard.
- `indexer/pipeline/run.py`: waits, `verify`, per-stage JSON logs, amplification, exit codes; `--dummy` unchanged.
- `indexer/pipeline/config.py`: `embed_batch_size`, `chroma_wait_seconds`, `ollama_wait_seconds`.
- `scripts/check_index.py` (reads the live collection, checks it), tests in `indexer/tests/`.
- A real run on `corpus/raw/`, twice; numbers into the results register; H-4.

**Out of scope**

- API retrieval and the API's copy of the embedder (phase 8). Cache invalidation (`index_id` does it). Chunk size tuning (phase 12). Any `k8s/`, `ui/`, `.github/` change.

## 4. Interfaces and contracts

```python
# embed.py
def embed(texts: list[str], settings: IndexerSettings) -> list[list[float]]   # one vector per text, same order
def document_text(chunk: Chunk, model: str) -> str   # prefix rule (5.3): nomic -> "search_document: <section>\n<text>", hashing -> same string, prefix ignored by the embedder
# embedding/ollama.py
def embed_ollama(texts: list[str], model: str, url: str, batch_size: int, *, sleep=time.sleep) -> list[list[float]]
# embedding/hashing.py
def embed_hashing(texts: list[str]) -> list[list[float]]    # 768 dims, deterministic, unit length
DIM = 768; MODEL = "hashing-bow-768"
# store.py
class StoreError(RuntimeError)
def store(chunks, vectors, settings, client=None) -> int
def wait_for_chroma(settings, timeout: float) -> None      # raises TimeoutError
def wait_for_ollama(settings, timeout: float) -> None      # skipped for hashing-bow-768
```

Config (env, defaults only; not new ConfigMap keys except `EMBED_BATCH_SIZE`, already in 4.4): `EMBED_BATCH_SIZE=32`, `CHROMA_WAIT_SECONDS=120`, `OLLAMA_WAIT_SECONDS=60`. Exit codes: 0 ok, 1 failure (verify, wait timeout, embed, store, anything unexpected, always logged as JSON), 2 `NotImplementedError` (kept).

## 5. Behaviour and design details

- **Model dispatch.** `EMBED_MODEL == "hashing-bow-768"` uses the hashing embedder; a name starting `nomic-embed-text` uses Ollama with the document prefix; any other name is a `ValueError` (a new model needs its prefix rule written into 5.3 first).
- **Ollama.** `POST {OLLAMA_URL}/api/embed` `{"model", "input": [batch]}`; batches of `EMBED_BATCH_SIZE`; per batch 3 attempts with 1, 2, 4 s back-off (httpx errors, non-200, malformed body, wrong count); a failed batch fails the whole stage (all-or-nothing). Every vector must have the first vector's length, and the length must be 768 for the known models.
- **Hashing.** Lower-case; tokens `[a-z0-9]+`; drop a short English stop-word list; `h = int.from_bytes(blake2b(token, digest_size=8).digest(), "big")`; bucket `h % 768`, sign `+` when bit 63 is set else `-`; counts per token with value `1 + ln(tf)`; L2 normalise (all-zero text stays the zero vector). The `search_document: ` prefix is stripped first. A hard-coded prefix of eight numbers is the parity golden (AD-09).
- **Store (5.4.4).** (1) validate: equal lengths, ids unique, no empty text, vector length equal and equal to the model dimension; (2) delete leftover `rahbar_next`; (3) create it with metadata `hnsw:space=cosine, embed_model, dimension, index_id (YYYYMMDDTHHMMSSZ-<6 hex>), built_at (ISO UTC), chunk_count, chunk_size, chunk_overlap, doc_versions (JSON string of unique {source, doc_version, superseded})`; (4) `add` in batches of at most 500; (5) `count()` must equal `len(chunks)` else delete `rahbar_next` and raise `StoreError`; (6) delete `rahbar` if present; (7) `modify(name=collection)` on `rahbar_next` without metadata. Any exception before step 6 deletes `rahbar_next` (best effort) and leaves `rahbar` untouched.
- **Run order (5.4.1).** wait for Chroma, wait for Ollama (not for hashing), `verify`, then per document extract/clean/chunk (a document with 0 chunks is logged as a warning), embed, store.
- **Logs** (JSON, one line per stage): `extracted` (exists: pages, ocr_pages, seconds), `chunked` (per document: chunks, words, source_words, amplification) and one total, `embedded` (vectors, batches, seconds, model), `stored` (chunks, index_id, seconds), `indexer finished`.

## 6. Acceptance criteria

- [ ] **AC-1**: `python -m pipeline.run --dummy` still writes the three dummy chunks to local Chroma and exits 0.
- [ ] **AC-2**: With `make dev-services` and Ollama, `CORPUS_DIR=corpus/raw CHROMA_PORT=8100 python -m pipeline.run` exits 0; `scripts/check_index.py` shows collection `rahbar` with all ten metadata keys, `chunk_count` equal to `count()`, `embed_model=nomic-embed-text`, `dimension=768`, every record with the five fields, no `rahbar_next`.
- [ ] **AC-3**: A second run replaces the collection and `index_id` differs; `count()` is the same.
- [ ] **AC-4**: A failure injected in the second embed batch (unit test) leaves the previous collection and its `index_id` intact, and `rahbar_next` is not left behind; a failed `count()` check deletes `rahbar_next` and keeps `rahbar`.
- [ ] **AC-5**: Hashing embedder: 768 dims, unit length, deterministic, matches the hard-coded golden prefix, ignores the document prefix, stop words dropped.
- [ ] **AC-6**: Ollama client: batches of `EMBED_BATCH_SIZE`, 3 attempts with 1, 2, 4 s back-off, wrong count or wrong length fails, a failed batch fails the stage (all with a fake HTTP layer, no network).
- [ ] **AC-7**: Logs are JSON, one line per stage with timings, OCR page count, chunk count and amplification; exit code 1 and a logged error on Chroma or Ollama wait timeout.
- [ ] **AC-8**: Peak memory (`/usr/bin/time -v`) and wall time of the real run are in the results register; H-4 text written.
- [ ] **AC-9**: `make test && make lint` green; `--dummy` and unit tests need no network, model or cluster.

## 7. Test strategy and traceability

| AC | Level | Test or command | Needs |
| --- | --- | --- | --- |
| AC-1 | integration | `python -m pipeline.run --dummy` against `localhost:8100` | dev Chroma |
| AC-2 | integration | real run, then `scripts/check_index.py` | dev Chroma, Ollama, `corpus/raw` |
| AC-3 | integration | second run, `check_index.py --expect-new-index-id <id>` | same |
| AC-4 | unit | `indexer/tests/test_store.py` (in-memory fake client), `test_run.py::test_embed_failure_keeps_live` | nothing |
| AC-5 | unit | `indexer/tests/test_embed_hashing.py` | nothing |
| AC-6 | unit | `indexer/tests/test_embed_ollama.py` (`httpx.MockTransport`) | nothing |
| AC-7 | unit + integration | `test_run.py` (capsys, waits patched); log output of AC-2 | nothing / services |
| AC-8 | manual | `/usr/bin/time -v` on the AC-2 command | same as AC-2 |
| AC-9 | command | `make test && make lint` | nothing |

## 8. Open questions

All decided without a gate (pre-approved), see `docs/OPEN_DECISIONS.md`.

| # | Question | Recommendation | Decision entry | Answer |
| --- | --- | --- | --- | --- |
| Q1 | Embedding package layout and parity with the api | A. `embedding/{ollama,hashing}.py` as the plan says, golden vector test | D-053 | A |
| Q2 | What store validates before touching Chroma | A. fail fast on duplicate ids, empty text, ragged vectors | D-054 | A |
| Q3 | How the live run is proven (pytest skip or script) | A. `scripts/check_index.py`, never skipped | D-055 | A |
| Q4 | Wait timeouts and batch size as config | A. env defaults, only `EMBED_BATCH_SIZE` is a ConfigMap key | D-056 | A |

## 9. Risks and assumptions

- Ollama on the host plus Chroma plus OCR: memory is tight (15 GB host); the run is sequential, embeddings after chunking.
- A chunk longer than the model context is truncated by Ollama silently; the largest chunk is about 400 words (about 600 tokens), under 2048.
- The Student Handbook repeats some pages, so some chunk texts exist twice with different ids; harmless, reported.
- `modify(name=)` relies on A-2 (verified). The 0.x gap between delete and rename is accepted by the api (AD-20).

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit message |
| --- | --- | --- | --- | --- |
| 1 | Hashing embedder with golden prefix test | `embedding/hashing.py`, `tests/test_embed_hashing.py` | `pytest indexer/tests/test_embed_hashing.py` | `feat(indexer): hashing-bow-768 embedder with golden vector` |
| 2 | Ollama client with retries, dispatcher, prefix rule | `embedding/ollama.py`, `embed.py`, `config.py`, `tests/test_embed_ollama.py` | tests | `feat(indexer): embed stage with Ollama client and retries` |
| 3 | Stage-and-swap store, validation, waits | `store.py`, `tests/test_store.py` | tests | `feat(indexer): stage-and-swap store with collection metadata` |
| 4 | Wire `run.py`: waits, stage logs, amplification, exit codes | `run.py`, `tests/test_run.py` | `pytest`, `--dummy` | `feat(indexer): run the full pipeline with stage logs` |
| 5 | `scripts/check_index.py`, Makefile lint line (shared file, own commit) | `scripts/check_index.py`, `Makefile` | `make lint` | `feat(scripts): check_index for the live collection` |
| 6 | Real run twice, with `/usr/bin/time -v`; numbers in the spec section 11 | none | AC-2, AC-3, AC-8 | `docs(spec): phase 07 real run results` |
| 7 | Tester rounds; report in section 12 | tests | brief in WORKFLOW 6 | `test: phase 07 report` |
| 8 | Progress files, AI-USAGE, hand-off H-4, PR | docs | `check_submission.py` | `docs(progress): phase 07 done` |

### 10.2 Test plan

Steps 1 to 4 write their tests first. The tester runs `make test`, `make lint`, coverage for `pipeline`, the real run, `check_index.py`, tries a dead Chroma, a dead Ollama, a wrong model name, empty corpus.

### 10.3 Rollback and risks

Each step is one commit; revert it. A failed real run never alters `rahbar`. `make dev-services-reset` clears the dev Chroma.

### 10.4 Estimate

About 2 h of work plus the real run (OCR about 2 min, embedding of about 1000 chunks a few minutes). Matches the plan (2 h).

## 11. Implementation notes

(filled during IMPLEMENT)

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | 2026-11-05 | Zain (pre-approved) | |
| Tester verdict PASS | | | rounds: |
| Merged | | | PR # |
