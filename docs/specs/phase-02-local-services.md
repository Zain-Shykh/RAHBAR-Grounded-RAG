# Phase 02 spec and plan: Local services and assumption checks

| | |
| --- | --- |
| Phase | 2, from `docs/IMPLEMENTATION_PLAN.md` |
| Work plan task | Z-02 |
| Branch | `feat/rag-z02-local-services` (the plan says `-dev-services`; Zain's start prompt names this one) |
| Stage | SPEC DRAFT |
| Started | 2026-11-04 |
| Approved (spec and plan) | |
| Depends on | Phase 1 merged (PR #3). Feeds H-2, H-3 to Ahmad (A-03) |

## 1. Objective

Zain can run the same Chroma and Redis Stack images the cluster will use with one command, and every unverified assumption the later phases rest on (A-2, A-3, A-6, R-01, R-02) has a recorded PASS or a logged deviation, before any application code uses these services.

## 2. Context

- Architecture: 3 (technology table, Redis Stack tag), 4.5 (Redis AOF and RDB on a PVC, Chroma data on a PVC), 4.7 (non-root, read-only root, `capabilities.drop: [ALL]`), 5.4.4 (stage-and-swap: delete, `modify(name=)`), 5.9.1 (cache index: `FT.CREATE ... VECTOR HNSW 6 TYPE FLOAT32 DIM {n} DISTANCE_METRIC COSINE`, TAG `scope`), 5.9.2 (KNN 1, DIALECT 2), 5.7.3 (Ollama `format`, `num_ctx`), 5.12.2, 9.1 (A-2, A-3, A-6), 9.2 (R-01, R-02). AD-02, AD-03, AD-11, AD-20.
- Requirements: R-K8S-REDIS (Redis Stack deployment), R-CAC-1..5, R-IDX-5 (swap), R-PRB-2 (Chroma heartbeat probe path).
- Rubric: non-root and read-only root (security posture); "what Ahmad needs verified" is H-2, H-3.
- Decisions: D-001 (Redis Stack, fallback plain Redis app-side cosine), D-027. New this phase: D-038 to D-041 (section 8).
- Existing code: `api/requirements.txt` and `indexer/requirements.txt` already pin `chromadb-client==1.0.12`; `redis==5.2.1` is in the api requirements. Nothing in `api/` or `indexer/` uses either service yet. `.venv` has `chromadb-client 1.0.12`, `redis 5.2.1`, `httpx 0.28.1`. No Chroma or Redis image is pulled yet. Host Ollama is up with `llama3.2:3b` and `nomic-embed-text`.
- Docker: until Zain re-logs, every docker command, `make dev-services` and `verify_services.py` run under `sg docker -c "..."`.
- Work happens in the git worktree `.claude/worktrees/z02` (background-session rule); the `.venv` is the one at the repo root.

## 3. Scope

**In scope**

- Makefile targets `dev-services`, `dev-services-stop`, `dev-services-reset` (shared file: separate small commit, tell Ahmad).
- `scripts/verify_services.py`: items 1 to 4 below, PASS/FAIL/SKIP per item, exit 1 on any FAIL.
- `scripts/verify_ollama.py`: assumption A-6 and the embedding endpoint contract, manual (needs host Ollama).
- Results recorded in `docs/architecture/architecture.md` section 9 (a "Verified" note per row), the Redis Stack tag in section 3 (separate commit), `deviations.md` if reality differs, the progress log, `AI-USAGE.md`, H-2 and H-3 text.

**Out of scope**

- Kubernetes manifests, securityContext YAML (Ahmad A-03). This phase gives him the facts.
- Any application code using Chroma, Redis or Ollama (phases 7, 8, 10, 11).
- Cache threshold calibration (phase 12).

## 4. Interfaces and contracts

### 4.1 Makefile

```make
CHROMA_IMAGE ?= chromadb/chroma:1.0.12
REDIS_IMAGE  ?= redis/redis-stack-server:7.4.0-v8

dev-services:       ## start Chroma :8100 and Redis Stack :6379 in Docker (use: sg docker -c "make dev-services")
dev-services-stop:  ## stop and remove the two containers (data volumes are kept)
dev-services-reset: ## stop, remove the containers AND the data volumes
```

- Containers `rahbar-dev-chroma` (host 8100 to container 8000) and `rahbar-dev-redis` (host 6379 to 6379), named volumes `rahbar-dev-chroma` (`/data`) and `rahbar-dev-redis` (`/data`). No `--restart` policy: they die with the machine on purpose. Ports bind `127.0.0.1` only.
- Chroma env: `IS_PERSISTENT=TRUE`, `PERSIST_DIRECTORY=/data`, `ANONYMIZED_TELEMETRY=FALSE`. Redis env: `REDIS_ARGS="--appendonly yes"` (same persistence mode as architecture 4.5).
- `dev-services` is idempotent: it removes a stale container of the same name first, then starts, then waits (max 30 s) for Chroma `GET /api/v2/heartbeat` and Redis `PING` and prints the export line `CHROMA_HOST=localhost CHROMA_PORT=8100 REDIS_HOST=localhost REDIS_PORT=6379`.
- Dev containers run with Docker defaults (not hardened); the hardened run is only the verify script (D-041).
- Image tags are Makefile variables for the two images, nowhere else. No `:latest`.

### 4.2 `scripts/verify_services.py`

```
python scripts/verify_services.py [--chroma-port 8100] [--redis-port 6379] [--skip-docker]
```

Environment fallbacks: `CHROMA_HOST`, `CHROMA_PORT`, `REDIS_HOST`, `REDIS_PORT`. Uses only `chromadb.HttpClient`, `redis`, stdlib `subprocess`/`argparse`. Prints one line per check (`PASS`, `FAIL`, `SKIP`) with a short detail, then a summary; exit 0 if no FAIL, else 1. A service that is unreachable prints a single FAIL line naming host and port (not a traceback). Imports nothing from `api/` or `indexer/`.

| Item | Checks (each is a separate PASS/FAIL line) |
| --- | --- |
| 1 Chroma, needs the dev container | 1.1 `create_collection` with metadata `{hnsw:space: cosine, embed_model, index_id, doc_versions (JSON string)}`. 1.2 `get_max_batch_size()` printed (records A-3 headroom). 1.3 one `add` of **500** 768-dim records with metadata `{source, section, page, doc_version, superseded: bool}`, then `count()==500`. 1.4 `modify(name=...)` rename with no metadata argument: old name gone, new name present, `count()==500`, **metadata identical** to the original. 1.5 the swap sequence of architecture 5.4.4 on real names: stage `x_next`, delete `x` (existing), rename `x_next` to `x`; collection `x` has the new `index_id`. 1.6 `query(where={"superseded": False})` and `where={"doc_version": {"$in": [...]}}` return only matching records (AD-11 filters work on a bool and on `$in`). 1.7 `delete_collection`, `list_collections` no longer shows it. All names are `verify_*` throwaways, cleaned up in `finally`. |
| 2 Redis Stack, needs the dev container | 2.1 `FT.CREATE idx:cache:verify ON HASH PREFIX 1 cache:verify: SCHEMA scope TAG embedding VECTOR HNSW 6 TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE` (exact form of 5.9.1). 2.2 `HSET` two entries with different `scope` tags and float32 bytes (`array('f')`). 2.3 `FT.SEARCH ... "(@scope:{a})=>[KNN 1 @embedding $vec AS dist]" PARAMS 2 vec <bytes> DIALECT 2` returns the entry of scope `a`, `1 - dist` at least 0.999 for the identical vector, and the entry of scope `b` only when asked for `b` (the tag filter works). 2.4 `EXPIRE` sets a TTL (`TTL` above 0). 2.5 `FT._LIST` contains the index, `FT.DROPINDEX idx:cache:verify DD` removes the index **and** its keys (`EXISTS` is 0). |
| 3 Redis Stack hardened (R-02), needs docker | 3.1 `docker image inspect` prints the image's default `User`. 3.2 **Discovery**: start the image as the candidate UID (default `10001`, overridable) **without** `--read-only`, on a fresh volume made writable for that UID (an `alpine chown` helper run, which stands in for `fsGroup`), run item 2 against it on port 6380, then `docker diff` and report every path written outside `/data`. 3.3 **Confirmation**: restart with `--read-only --cap-drop ALL --security-opt no-new-privileges --tmpfs /tmp` plus one `--tmpfs` per path found in 3.2, `/data` volume, run item 2 again. PASS prints the UID, the volume and tmpfs paths Ahmad must mount. If 3.3 fails, print the stderr tail and which path was missing; try UIDs `999`, `1001`; if none works the line is FAIL and the fallback to D-001 option B is named. |
| 4 Chroma hardened (R-01), needs docker | Same method as item 3 for `chromadb/chroma:1.0.12` on port 8101, UID `10001`, with checks 1.1 to 1.5 as the functional test. Also report the image default `User` and whether `/data` ownership mattered. |

Items 3 and 4 are SKIP (with the reason) when `--skip-docker` is given or `docker info` fails. The script cleans up its own throwaway containers and volumes (`rahbar-verify-*`) in `finally`, including on Ctrl-C.

### 4.3 `scripts/verify_ollama.py`

```
python scripts/verify_ollama.py [--url http://localhost:11434] [--llm llama3.2:3b] [--embed nomic-embed-text]
```

Stdlib plus `httpx` (already in `.venv`). Imports `Answer` from `api/app/schemas.py` by adding `api/` to `sys.path` (read-only use of the schema, the same object phase 10 sends as `format`). Prints PASS/FAIL per line, exit 1 on any FAIL.

| Check | Detail |
| --- | --- |
| 5.1 models present | `GET /api/tags` lists both models. |
| 5.2 embed | `POST /api/embed` `{"model", "input": [32 short texts]}` returns 32 vectors of length 768 (a batch of 32 works, `EMBED_BATCH_SIZE`); one input with prefix `search_query: ` is accepted. |
| 5.3 `format` honoured | `POST /api/chat` with `stream=false`, `format=Answer.model_json_schema()`, `options={temperature:0.2, num_ctx:8192, num_predict:512}` on three prompts (answerable from a given evidence block, unanswerable, one containing an injected "ignore all previous instructions" line). Every reply parses as JSON and passes `Answer.model_validate`; `prompt_eval_count` and `eval_count` are present. Prints latency per call. |
| 5.4 `num_ctx` honoured | One prompt of about 6000 tokens (filler paragraphs, a code word in the first paragraph, a question asking for it). PASS if `prompt_eval_count` is at least 5500 (a default 2048 or 4096 window would truncate it) and the reply contains the code word. Reports `GET /api/ps` `size` and `size_vram` and the host `free -m` delta as memory evidence for the model at 8192. |

It never starts or stops Ollama. At the end of the phase the developer session runs `pkill ollama` (Zain's rule).

## 5. Behaviour and design details

- **Pin the Redis Stack tag** `redis/redis-stack-server:7.4.0-v8` (D-038). Pull and run it first; if 3.3 fails on 7.4.0-v8 for a reason a different tag fixes, retry once with `7.2.0-v20`, record both results, and pin the one that passes. The shipped tag is written to `architecture.md` section 3 in a separate commit and is the `REDIS_IMAGE` default.
- **Throwaway data**: all verification keys, collections and indexes are prefixed `verify`; the script deletes them even when a check fails, so it can run repeatedly and never touches `rahbar` or `rahbar_next`.
- **No silent workaround.** If any check FAILs: stop the step, write a `DEV-NNN` entry (severity per `deviations.md`; weakening a securityContext for R-01 or R-02 is S1; a changed swap procedure is S2), tell Zain in one line, and for S1 or S2 pause for his answer (WORKFLOW 3 and 9). Watch-list fallbacks: R-02 to D-001 option B; A-2 or A-3 to a different swap procedure or smaller batch.
- **A-6 failure policy**: if `format` is not honoured, the fallback is the Pydantic validation plus one retry already in the design (5.7.3); log a deviation and carry the finding into phase 10. If `num_ctx` 8192 does not fit in memory, report the largest `num_ctx` that does and what that does to `TOP_K` and chunk size; that is a question for Zain, not a quiet change.
- **A-1, A-4, A-5** are cluster assumptions (Ahmad's lane) and are not tested here.
- Check 1.6 is the early warning that the `where` filter shapes phase 8 relies on (AD-11) work over HTTP.
- **Security**: scripts take host and port only from flags and environment; no secret is read or printed; all containers bind `127.0.0.1` only. Data returned by services is never `eval`ed.

## 6. Acceptance criteria

- [ ] **AC-1**: `sg docker -c "make dev-services"` starts `rahbar-dev-chroma` and `rahbar-dev-redis` on `127.0.0.1:8100` and `:6379`, prints the export line, and returns only after both answer (heartbeat 200, `PING` PONG). Running it twice in a row leaves one of each container.
- [ ] **AC-2**: `make dev-services-stop` removes both containers and keeps the two volumes; `make dev-services-reset` removes the containers and both volumes.
- [ ] **AC-3**: `python scripts/verify_services.py --skip-docker` prints PASS for checks 1.1 to 1.7 and 2.1 to 2.5, exits 0, and a second run is also green (cleanup works). Evidence of A-2 (rename keeps metadata) and A-3 (500 per add, the `get_max_batch_size` value) is in its output.
- [ ] **AC-4**: With services stopped the script prints one clear FAIL naming the host and port, exits 1, no traceback.
- [ ] **AC-5**: Item 3 (Redis Stack hardened) has an explicit result: PASS with image default user, UID, volume path and every tmpfs path, **or** FAIL with the stderr tail and the named fallback. Recorded in the progress log and in `architecture.md` section 9 (R-02).
- [ ] **AC-6**: Item 4 (Chroma hardened) has the same explicit result for R-01.
- [ ] **AC-7**: `python scripts/verify_ollama.py` prints PASS for 5.1 to 5.4 (or FAIL with the finding), with the memory and latency numbers; results recorded in the log and in `architecture.md` section 9 (A-6). `pkill ollama` has been run at the end.
- [ ] **AC-8**: Architecture section 9 shows the verified result for A-2, A-3, A-6, R-01, R-02; every FAIL has a `deviations.md` entry (if nothing differs, the log says so).
- [ ] **AC-9**: The Redis Stack tag replaces "pinned at implementation" in `architecture.md` section 3 in its own commit; `REDIS_IMAGE` in the Makefile equals it; no `:latest` anywhere (`grep -rn ':latest' Makefile scripts` is empty).
- [ ] **AC-10**: H-2 and H-3 are written in the progress log as ready-to-send messages (tag, UID, writable paths, `fsGroup` need, probe path) and ticked in section 3 of the plan.
- [ ] **AC-11**: `make test && make lint` stay green (`scripts/verify_*.py` are added to the ruff line of `lint`, a shared-file commit); no file under `k8s/`, `ui/`, `.github/`, `api/` or `indexer/` changed.
- [ ] **AC-12**: `python3 scripts/check_submission.py` shows no new failure compared with the baseline taken at the start of the phase.

## 7. Test strategy and traceability

These are integration tools, not application code, so the scripts are themselves the checks; the independent tester runs them, tries to break them, and may add negative cases in a small test file only if it needs no services.

| AC | Level | Test or command | Needs |
| --- | --- | --- | --- |
| AC-1 | integration | `sg docker -c "make dev-services"` twice; `docker ps --filter name=rahbar-dev`; `curl -s localhost:8100/api/v2/heartbeat` | docker |
| AC-2 | integration | `make dev-services-stop` then `docker ps -a` and `docker volume ls`; `make dev-services-reset` then `docker volume ls` | docker |
| AC-3 | integration | `.venv/bin/python scripts/verify_services.py --skip-docker` (twice) | dev containers |
| AC-4 | integration | stop services, run the script, check exit code 1 and the message | none |
| AC-5 | integration | `sg docker -c ".venv/bin/python scripts/verify_services.py"`, item 3 output | docker |
| AC-6 | integration | same, item 4 output | docker |
| AC-7 | integration, manual | `.venv/bin/python scripts/verify_ollama.py`; `pgrep ollama` empty afterwards | host Ollama |
| AC-8, AC-10 | review | `git diff dev -- docs/architecture` and the progress log | none |
| AC-9 | command | `grep -rn ':latest' Makefile scripts`; `grep -n 'redis-stack-server' docs/architecture/architecture.md Makefile` | none |
| AC-11 | command | `make test && make lint`; `git diff --stat dev -- k8s ui .github api indexer` is empty | none |
| AC-12 | command | `python3 scripts/check_submission.py` before and after, diff | none |

Spec-implied cases the tester should try: a leftover `rahbar-dev-*` container from a crash; port 6379 or 8100 already in use (clear error, not a hang); a verify run interrupted halfway (next run still green); a pre-existing collection named like a throwaway one; Redis running **without** the search module (plain `redis:7-alpine` on the port: 2.1 FAILs with a clear message, not a stack trace); `--skip-docker` really skips items 3 and 4.

## 8. Open questions

All asked in one batch on 2026-11-04 and answered with the recommendation.

| # | Question | Options and recommendation | Decision entry | Answer |
| --- | --- | --- | --- | --- |
| Q1 | Which Redis Stack tag to pin | 7.4.0-v8 (rec) / 7.2.0-v20 | D-038 | 7.4.0-v8 |
| Q2 | Where the A-6 Ollama check lives | separate `verify_ollama.py` (rec) / flag / manual curl | D-039 | separate script |
| Q3 | Dev data persistence | named volumes kept, stop removes containers only, plus `dev-services-reset` (rec) / ephemeral | D-040 | volumes kept |
| Q4 | Where the non-root read-only checks live | inside `verify_services.py` as items 3, 4 (rec) / manual only | D-041 | in the script |

## 9. Risks and assumptions

- **R-02 is the real risk.** Redis Stack may default to root and need `/opt/redis-stack` or `/var` writable. The two-step method (discover with `docker diff`, confirm with `--read-only`) finds the minimal writable set; if the vector module refuses to load as non-root, that is a deviation and D-001 B is the fallback (a rewrite of phase 11's plan; Zain decides).
- A named volume is root-owned on first mount; local `--user` runs need the `chown` helper, which stands in for Kubernetes `fsGroup`. The result tells Ahmad whether `fsGroup` is required.
- Pulling the two images is roughly 1 GB; slow network slows the phase. Pull is step 0 so a delay shows early.
- Memory: 15 GB host with about 7 GB available; Chroma, Redis, Ollama with both models and minikube is tight (R-04). `verify_ollama.py` reports the real number.
- Docker group workaround: `sg docker -c` must wrap the Python script for items 3 and 4; documented in the Makefile comment and the script's `--help`.
- Ports 8101 and 6380 (hardened runs) are assumed free; the script reports a clear error otherwise.

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit message |
| --- | --- | --- | --- | --- |
| 0 | Baseline: save `check_submission.py` output; pull both images | none | `sg docker -c "docker pull ..."` | (none) |
| 1 | Makefile targets `dev-services`, `dev-services-stop`, `dev-services-reset`, image variables; add the two scripts to the ruff line of `lint`; `.PHONY` | `Makefile` | AC-1, AC-2 commands; `make lint` | `build(make): dev-services targets for Chroma and Redis Stack` |
| 2 | `verify_services.py` items 1 and 2 (functional, no docker), cleanup in `finally`, clear unreachable-service message | `scripts/verify_services.py` | AC-3, AC-4; second run green | `feat(scripts): verify Chroma and Redis Stack behaviour (A-2, A-3)` |
| 3 | `verify_services.py` items 3 and 4 (hardened non-root, read-only, discovery then confirmation) | `scripts/verify_services.py` | AC-5, AC-6 | `feat(scripts): verify non-root read-only Chroma and Redis Stack (R-01, R-02)` |
| 4 | `verify_ollama.py` (A-6, embed contract) | `scripts/verify_ollama.py` | AC-7; then `pkill ollama` | `feat(scripts): verify Ollama format, num_ctx and embed (A-6)` |
| 5 | Run everything for real, paste outputs in section 11; any FAIL triggers its `deviations.md` entry and a question to Zain before continuing | `docs/architecture/deviations.md` (only if needed) | outputs in section 11 | `docs(deviations): DEV-001 ...` (only if needed) |
| 6 | Record results in architecture section 9 (a "Verified" note per row) | `docs/architecture/architecture.md` | AC-8 | `docs(architecture): record phase 2 assumption results` |
| 7 | Redis Stack tag into architecture section 3 (own commit) | `docs/architecture/architecture.md` | AC-9 | `docs(architecture): pin Redis Stack tag` |
| 8 | Progress files: plan dashboard and log, H-2 and H-3 text, `OPEN_DECISIONS` entries closed, `AI-USAGE.md`, one line in `SETUP.md` | `docs/IMPLEMENTATION_PLAN.md`, `docs/OPEN_DECISIONS.md`, `docs/AI-USAGE.md`, `docs/SETUP.md` | AC-10, AC-11, AC-12 | `docs(progress): phase 02 implemented` |

No file under `api/` or `indexer/` changes, so the existing 7 + 4 tests stay as they are and `make test && make lint` is green after every step.

### 10.2 Test plan

- Each script step starts with the **failing** case (unreachable service, plain Redis without the module), watched to fail with a clear message, then the passing path.
- Testing subagent runs: `make test && make lint`; the AC-1 to AC-12 commands under `sg docker`; the spec-implied cases in section 7; confirms cleanup (`docker ps -a`, `docker volume ls`, `FT._LIST`, `list_collections` show nothing named `verify*`); confirms `git diff --stat dev -- api indexer k8s ui .github` is empty; runs `pkill ollama` afterwards.

### 10.3 Rollback and risks

- Every step is one commit; revert the commit. The Makefile commit adds targets and one lint path only.
- If a hardened check cannot pass, do not give Ahmad weaker settings silently: stop at step 5, deviation entry, ask Zain (S1).
- If linting `scripts/` surfaces findings in the existing `check_submission.py`, the ruff line lists only the two new files.

### 10.4 Estimate

| Step | Hours |
| --- | --- |
| 0, 1 | 0.25 |
| 2 | 0.4 |
| 3 | 0.5 |
| 4 | 0.3 |
| 5 to 8 | 0.4 |
| Test rounds (tester) | 0.3 |
| Total | about 2.1 h against 1.5 h in the work plan |

That is 40% over the work plan; the excess is the Ollama script and the hardened discovery step. Proposed cut if time is short: drop the host `free -m` delta in check 5.4 and keep `/api/ps`. Say if you want the cut now.

## 11. Implementation notes

<!-- Filled during IMPLEMENT. -->

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |

Coverage of `app`: not applicable (no application code changes).

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | | | |
| Tester verdict PASS | | | rounds: |
| Merged | | | PR # |
