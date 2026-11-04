# Phase 01 spec and plan: Container images

| | |
| --- | --- |
| Phase | 01, from `docs/IMPLEMENTATION_PLAN.md` |
| Work plan task | Z-01 |
| Branch | `feat/rag-z01-dockerfiles` |
| Stage | READY FOR PR |
| Started | 2026-11-04 |
| Approved (spec and plan) | 2026-11-04, Zain |
| Depends on | nothing. Unblocks Ahmad's A-02 and A-04 (hand-off H-1). |

## 1. Objective

`rahbar-api` and `rahbar-indexer` build and run as non-root containers with a read-only root filesystem, so Ahmad can deploy real containers instead of stubs.

## 2. Context

- Architecture: 4.12 (image rules), 4.7 (root containers row: UID 10001, `readOnlyRootFilesystem`, `/tmp` only writable), 4.8 (api listens on 8000, probes on `/healthz`), 5.2 (code map: api has no OCR or PDF libs, indexer has no web framework), I-12 (no `:latest`), I-13 (no secret).
- `STARTER.md` "Images and ports": api port 8000, build context `api/`; indexer no port, build context `indexer/`, exits.
- Requirements and rubric: checker `check_dockerfiles` in `scripts/check_submission.py` (pinned `FROM`, non-root `USER`, exec-form `CMD`, no hard-coded credential, `.dockerignore` excludes `.git` and `__pycache__`, soft check for `corpus`/venv).
- Open decisions: D-003 (documents reach the Job through a PVC, so the image holds no corpus). D-035 to D-037 below.
- Existing code: `api/requirements.txt` (runtime only: fastapi, uvicorn, pydantic, httpx, prometheus-client, chromadb-client, posthog, redis), `indexer/requirements.txt` (adds pyyaml, pdfplumber, pypdf, pytesseract, pdf2image), `api/app/`, `indexer/pipeline/` (`python -m pipeline.run [--dummy]`). No Dockerfile exists. `python:3.12-slim-bookworm` pulls (verified 2026-11-04).

## 3. Scope

**In scope**

- `api/Dockerfile`, `api/.dockerignore`, `indexer/Dockerfile`, `indexer/.dockerignore`.
- `docs/OPEN_DECISIONS.md` entries, and `docs/AI-USAGE.md` plus progress files at stage 4.

**Out of scope**

- ui Dockerfile (Ahmad, A-01). Compose file. Image publishing (CD, Ahmad). Makefile changes (D-037: leave `make images` as is). HEALTHCHECK (D-036). Application code changes.

## 4. Interfaces and contracts

| Item | api | indexer |
| --- | --- | --- |
| Image name and tag | `rahbar-api:dev` | `rahbar-indexer:dev` (from `make images`, `TAG ?= dev`, unchanged) |
| Build context | `api/` | `indexer/` |
| Port | 8000 | none |
| User | `10001:10001` | `10001:10001` |
| `CMD` | `["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--timeout-graceful-shutdown","20"]` | `["python","-m","pipeline.run"]` |
| Writable paths | `/tmp` only (emptyDir) | `/tmp` only (emptyDir); corpus read from a mounted path |
| Config | environment only (ConfigMap contract C-2); no config key baked in with `ENV` | same |

No frozen contract (C-1 to C-8) changes.

## 5. Behaviour and design details

Both images:

- `FROM python:3.12-slim-bookworm` (tag pin, never `latest`).
- `ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1`, `WORKDIR /app`.
- Non-root: create user and group id 10001 (`groupadd -g 10001 app && useradd -u 10001 -g 10001 -M -s /usr/sbin/nologin app`), then `USER 10001:10001`. Code in `/app` is root-owned and read-only to the user.
- Read-only root: `ENV HOME=/tmp` so libraries that want a home or cache write under `/tmp`. No `ARG` secrets, no credentials, no `COPY . .`.
- Exec-form `CMD`. One uvicorn worker, no `--reload`.

**api** (D-035: virtualenv). Stage `build` creates `/opt/venv` and runs `pip install --no-cache-dir -r requirements.txt` (runtime file, not `-dev`). The final stage copies `/opt/venv` and `app/` only, with `ENV PATH=/opt/venv/bin:$PATH`. No apt packages, no tesseract, no pdfplumber, no pdf2image.

**indexer**. One stage. `apt-get install -y --no-install-recommends tesseract-ocr poppler-utils`, `rm -rf /var/lib/apt/lists/*`, then `pip install --no-cache-dir -r requirements.txt`, then `COPY pipeline/ pipeline/`. No web framework.

**.dockerignore** (both): `.git`, `__pycache__`, `*.pyc`, `.venv`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache`, `tests`, `corpus`, `*.md`, `requirements-dev.txt`. Each Dockerfile also copies only named paths.

## 6. Acceptance criteria

- [ ] **AC-1**: `docker build -t rahbar-api:dev api` and `docker build -t rahbar-indexer:dev indexer` exit 0.
- [ ] **AC-2**: `docker run --rm -d --read-only --tmpfs /tmp --user 10001 -p 8000:8000 rahbar-api:dev` answers `GET /healthz` with HTTP 200 and `{"status":"alive",...}`; the container keeps running; `docker exec <c> id -u` prints `10001`.
- [ ] **AC-3**: in the api image `tesseract` is absent, and `import pdfplumber`, `import pdf2image`, `import pytesseract` each raise `ModuleNotFoundError`.
- [ ] **AC-4**: in the indexer image `tesseract --version` and `python -c "import pytesseract, pdf2image, pdfplumber"` exit 0, and `import fastapi` fails.
- [ ] **AC-5**: `docker run --rm --read-only --tmpfs /tmp rahbar-indexer:dev python -m pipeline.run --dummy` runs as UID 10001 and fails only because Chroma is unreachable (a connection error, not a permission or import error).
- [ ] **AC-6**: neither Dockerfile has `:latest` in a `FROM`, an `ARG`/`ENV` secret or a `COPY . .`; `docker history --no-trunc` shows no credential.
- [ ] **AC-7**: `python3 scripts/check_submission.py` section "I · api image / indexer image / .dockerignore" has no FAIL for api and indexer.
- [ ] **AC-8**: H-1 delivered: PR merged into `dev`, Ahmad told the image names, tags, UID and `CMD`.

## 7. Test strategy and traceability

No unit tests: there is no Python logic. Evidence is commands. `make test && make lint` must stay green (nothing in `api/app` or `indexer/pipeline` changes).

| AC | Level | Command | Needs |
| --- | --- | --- | --- |
| AC-1 | manual | `sg docker -c "docker build -t rahbar-api:dev api"`, same for indexer | docker |
| AC-2 | manual | Verify block of phase 1 in `IMPLEMENTATION_PLAN.md`, plus `docker exec t-api id -u` | docker |
| AC-3 | manual | `docker run --rm --entrypoint sh rahbar-api:dev -c 'command -v tesseract; python -c "import pdfplumber"'`, same for the other two modules | docker |
| AC-4 | manual | the two commands from the plan; `python -c "import fastapi"` must fail | docker |
| AC-5 | manual | `docker run ... python -m pipeline.run --dummy`, read the log tail | docker |
| AC-6 | manual | `grep -nE "latest\|COPY \. \.\|PASSWORD\|SECRET\|TOKEN\|API_?KEY" api/Dockerfile indexer/Dockerfile`; `docker history --no-trunc` | docker |
| AC-7 | command | `python3 scripts/check_submission.py \| sed -n '/I · api image/,/I · tests/p'` | nothing |
| AC-8 | manual | PR merged, hand-off message in the log | Zain's "Merge it" |

## 8. Open questions

| # | Question | Options and recommendation | Decision entry | Answer |
| --- | --- | --- | --- | --- |
| Q1 | How the api build stage hands over dependencies | virtualenv at `/opt/venv` (recommended) or wheel directory | D-035 | virtualenv |
| Q2 | HEALTHCHECK instruction | none (recommended) or api only | D-036 | none |
| Q3 | Touch the Makefile `images` target | no, leave it (recommended) or add `images-rag` | D-037 | no |

## 9. Risks and assumptions

- **Read-only root.** A library may write outside `/tmp` (for example the Chroma client or posthog telemetry). AC-2 and AC-5 find it; the fix is an env var such as `HOME=/tmp`, not a code change.
- **apt drift.** Debian package versions (tesseract, poppler) are not pinned. Accepted: the base tag is pinned and CI rebuilds. Mention in the engineering notes.
- **Wheels on slim.** Assumed `chromadb-client==1.0.12` and `posthog==5.4.0` install without a compiler. If one needs it, `build-essential` goes in the discarded build stage only.
- **`--dummy` failure mode.** Assumed the first failure is the Chroma connection. Confirmed or corrected at step 2 by reading `run.py`.
- **Image size** is not a requirement; recorded in section 11 for information.

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit message |
| --- | --- | --- | --- | --- |
| 1 | api `.dockerignore` and multi-stage Dockerfile | `api/Dockerfile`, `api/.dockerignore` | AC-1 (api), AC-2, AC-3 | `feat(api): add multi-stage non-root Dockerfile` |
| 2 | indexer `.dockerignore` and Dockerfile with OCR tools | `indexer/Dockerfile`, `indexer/.dockerignore` | AC-1 (indexer), AC-4, AC-5 | `feat(indexer): add Dockerfile with tesseract and poppler` |
| 3 | Checker and hygiene pass; fix any finding | the four files if needed | AC-6, AC-7, `make test && make lint` | `fix(images): <what>` (only if needed) |

### 10.2 Test plan

The commands in section 7 are the tests; nothing is written before the code. The testing subagent runs every command in the table, plus: the container exits within the 20 s graceful window on `SIGTERM` (exec-form PID 1), runs with `--cap-drop ALL --security-opt no-new-privileges`, and `docker image inspect` shows `User=10001:10001`. It reports both image sizes.

### 10.3 Rollback and risks

Each step adds new files only; rollback is `git revert`. Nothing existing changes, so `make test` cannot regress.

### 10.4 Estimate

Step 1: 0.5 h. Step 2: 0.5 h. Step 3, test rounds, PR and hand-off: 0.5 h. Total 1.5 h, equal to the work plan.

## 11. Implementation notes

- Built as planned, no deviation. Step 3 needed no fix.
- Sizes: `rahbar-api:dev` 388 MB, `rahbar-indexer:dev` 592 MB.
- `HOME=/tmp` is set in both images; read-only runs (`--read-only --tmpfs /tmp`) worked with no other writable path.
- api `/healthz` returns `{"status":"alive"}` (no `version` yet; phase 10 adds it per architecture 4.8).
- `--dummy` fails at `chromadb.HttpClient` with `Could not connect to a Chroma server` (DNS for `chroma`), no permission or import error.
- Checker section I: api, indexer and both `.dockerignore` files all `ok`. Remaining FAILs are `ui/Dockerfile` and `.github/workflows/` (Ahmad's).
- Developer-side evidence: AC-1 to AC-7 pass. Awaiting independent tester.

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-04 | full AC run at c564c17 | FAIL | AC-1..7 pass. D-1 (low): nested `__pycache__`/`.pyc` leaked into images, `.dockerignore` patterns anchored at root. Fixed in 6bde1f6. |
| 2 | 2026-11-04 | full AC run at 6bde1f6 | FAIL | D-1 closed. D-2 (medium): `**/__pycache__` alone broke the checker (AC-7), my regression. D-3 (low, latent): nested `tests`, `corpus`, `*.md` not excluded. Fixed in 56bd1cf (root and `**/` forms both kept). |
| 3 | 2026-11-04 | full AC run at 56bd1cf | PASS | AC-1..7 PASS, AC-8 pending merge. `make test` 7 api + 4 indexer pass, `make lint` clean. D-1..D-3 closed. |

Round 3 evidence: healthz 200 as UID 10001 with `--read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges`; api has no tesseract/pdfplumber/pdf2image/pytesseract; indexer has all, no fastapi; `--dummy` ends `Could not connect to a Chroma server`; only `/tmp` writable as UID 10001; indexer OCRs a PNG and a PDF page under read-only root; SIGTERM clean; nested-leak test (planted `NOTE.md`, `tests/`, `corpus/`, `__pycache__`) leaves `/app` clean; checker section I only FAIL is `ui/Dockerfile` (Ahmad). Sizes: api 388 MB, indexer 592 MB.

Coverage of `app`: not relevant (no Python change).

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | 2026-11-04 | Zain | "Approved" |
| Tester verdict PASS | 2026-11-04 | independent subagent | rounds: 3 |
| Merged | | | PR # |
