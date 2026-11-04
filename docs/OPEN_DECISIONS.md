# Open decisions

Running log of decisions for RAHBAR. Two jobs:

1. **Open**: things Claude is unsure about or that only the team can decide. Claude writes them here instead of guessing.
2. **Decided**: choices already made, with the reason, so nobody re-argues them later.

Requirement IDs (`R-...`) point to `docs/requirements.md`.

## How this file works

- Claude adds an entry as soon as it hits an unclear spec point, a trade-off, or a choice with real cost. It keeps working on anything not blocked by that entry, using its recommendation as a provisional default and marking the code or doc that depends on it.
- The owner (Zain, with Ahmad) fills in **Decision** and changes **Status**. Claude then moves on and, if the choice changes a contract, writes an ADR.
- Statuses: `OPEN` (waiting on a human), `PROVISIONAL` (Claude proceeded on its recommendation, please confirm), `DECIDED`, `SUPERSEDED` (replaced; link the new entry).
- Never delete entries. Mark them `SUPERSEDED`.
- IDs are `D-001`, `D-002`, ... in order of creation. Newest goes at the bottom of its section.

Entry template:

```
### D-NNN Short title
- Status: OPEN | PROVISIONAL | DECIDED | SUPERSEDED
- Raised: YYYY-MM-DD by Claude | Zain | Ahmad
- Area: corpus | indexer | api | k8s | ci-cd | eval | docs | process
- Related: R-..., files, ADR
- Question: what must be decided
- Options: A ... / B ... / C ...
- Claude recommends: option and why
- Blocks: what cannot be finished until this is settled (or "nothing")
- Decision: (owner fills in)
- Decided on: YYYY-MM-DD
```

## Summary table

| ID | Title | Area | Status | Blocks |
| --- | --- | --- | --- | --- |
| D-001 | Semantic cache backend | api | OPEN | ADR, Redis manifests, cache code |
| D-002 | Chunk size unit | indexer | OPEN | chunker, ConfigMap, PIPELINE.md |
| D-003 | How documents reach the indexer Job | indexer, k8s | OPEN | Job manifest, indexer Dockerfile |
| D-004 | Work split between Zain and Ahmad | process | OPEN | everything |
| D-005 | Embedding via Ollama host | indexer, api | OPEN | embed stage, NetworkPolicy |
| D-006 | Retrieval: vector only or hybrid | api, eval | OPEN | retriever, exact-term recall |
| D-007 | ADR 0002 and 0003 topics | docs | OPEN | ADR files, checker |
| D-008 | Where ARCHITECTURE.md lives | docs | OPEN | doc layout |
| D-009 | Ingress hostname | k8s | OPEN | Ingress, eval host header |
| D-010 | CI e2e cluster: kind or k3d | ci-cd | OPEN | ci.yml |
| D-011 | Handling of the "older version" question | api | OPEN | retriever filter logic |
| D-012 | Follow-up question detection | api | OPEN | cache, answer service |
| D-013 | Docker Hub account and repo names | ci-cd | OPEN | cd.yml |
| D-014 | Branch protection: required checks and admin enforcement | process | OPEN | merging |
| D-015 | Which four failure stages to break | docs | OPEN | FAILURE-ANALYSIS.md |
| D-016 | Duplicate content: Prospectus 2026 vs Handbook 2026 | corpus, indexer | OPEN | golden set, retrieval |
| D-017 | OCR settings and quality threshold | indexer | OPEN | extract stage |
| D-018 | LLM provider scope | api | OPEN | provider code |
| D-019 | Corpus choice | corpus | DECIDED | |
| D-020 | Absent topic is hostel rules | corpus | DECIDED | |
| D-021 | Default LLM mode and models | api | DECIDED | |
| D-022 | Cluster setup | k8s | DECIDED | |
| D-023 | Branching and PR flow | process | DECIDED | |
| D-024 | Dependency documentation | process | DECIDED | |
| D-025 | Docker access workaround | process | DECIDED | |

---

## Open

### D-001 Semantic cache backend
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: api
- Related: R-CAC-1..5, R-K8S-REDIS, R-PRB-2, future ADR
- Question: Redis or a second Chroma collection for the semantic cache? The assignment wants the choice defended in an ADR.
- Options:
  - A. Redis (plain `redis` image, keep question embedding + answer as a value, scan and compute cosine in Python). Fits the required Redis Deployment + PVC and the "Redis reachable" readiness check. Cost: no vector index, so lookup is O(n); fine for a few hundred entries.
  - B. Second Chroma collection (`cache`). Real vector search, TTL not built in, invalidation = delete collection. But then the required Redis object has no job, and `/readyz` has no reason to check Redis.
  - C. Redis Stack with vector search. Real index, but bigger image, more memory, not needed at our scale.
- Claude recommends: A. The assignment already requires Redis objects and a Redis readiness check; option B would leave Redis decorative. Invalidate by bumping a generation key or deleting the `cache:*` keys when the indexer starts.
- Blocks: ADR, Redis manifests, cache code.
- Decision:
- Decided on:

### D-002 Chunk size unit
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: indexer
- Related: R-IDX-3, R-IDX-7, R-IDX-8, `CHUNK_SIZE=400`, `CHUNK_OVERLAP=50`
- Question: Are `CHUNK_SIZE` and `CHUNK_OVERLAP` in tokens or characters? The report must state the unit and the storage amplification is "tokens stored / tokens original".
- Options: A. Tokens (use an approximate tokenizer or word count). B. Characters (simple, deterministic, no tokenizer dependency).
- Claude recommends: A with whitespace-word counts as a proxy (no extra dependency), stated plainly in PIPELINE.md. Amplification is then just words stored / words original. Three configs to measure, for example (200, 25), (400, 50), (600, 100).
- Blocks: chunker, ConfigMap, PIPELINE.md.
- Decision:
- Decided on:

### D-003 How documents reach the indexer Job
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: indexer, k8s
- Related: R-IDX-9, R-COR-12
- Question: The PDFs are not committed (only MANIFEST + fetch script). How do they get into the Job pod?
- Options:
  - A. Job downloads them at start with `corpus/fetch.py` (init container or first step) into an `emptyDir`. Reproducible from the manifest and checks SHA-256. Needs egress to nu.edu.pk and respects the pause; slower; NetworkPolicy must allow it.
  - B. Bake `corpus/raw/` into the indexer image. Fast and offline, but the image then contains university PDFs (not committed to Git, but pushed to Docker Hub publicly). Possibly a redistribution concern.
  - C. Mount a PVC filled by hand with `kubectl cp`. Simple but not reproducible from a clean clone, which breaks R-DED-11.
- Claude recommends: A for the real corpus (init container, verify hashes, egress allowed to the internet only for that pod). CI keeps using `eval/fixtures` baked or mounted, so CI stays offline and fast.
- Blocks: Job manifest, indexer Dockerfile, NetworkPolicy egress.
- Decision:
- Decided on:

### D-004 Work split between Zain and Ahmad
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: process
- Question: Who owns which stream? Two natural streams: (1) platform: Dockerfiles, k8s manifests, NetworkPolicy, CI/CD, evidence; (2) RAG: indexer stages, retriever, providers, cache, eval, golden set. Docs split along the same lines.
- Options: A. Zain platform, Ahmad RAG. B. Reverse. C. Pair on both, alternating.
- Claude recommends: A or B (pick by who is stronger at what), with the golden set written jointly and early, since both streams depend on it.
- Blocks: everything; also the AI-USAGE.md attribution.
- Decision:
- Decided on:

### D-005 Embedding via Ollama on the host
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: indexer, api
- Related: R-LLM-5, R-PIN-1..3, R-SEC-4
- Question: Embed with `nomic-embed-text` served by Ollama on the laptop (same host as generation)? The assignment allows it if the README says so.
- Options: A. Yes, host Ollama for both embedding and generation. B. Embed with a library in the image (sentence-transformers): heavier image, more RAM in the Job, no Ollama dependency for indexing.
- Claude recommends: A. Already installed and tested (768-dim). Consequence: the indexer Job and the API both need egress to the host, and the CI e2e job cannot reach Ollama, so CI needs a deterministic fake embedder or a stub path. See D-010.
- Blocks: embed stage, NetworkPolicy, CI design.
- Decision:
- Decided on:

### D-006 Retrieval: vector only or hybrid
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: api, eval
- Related: R-COR-7, R-ENG-5, R-BON-2
- Question: Build hybrid retrieval (keyword/BM25 plus vector) or stay vector-only and document the exact-term weakness?
- Options: A. Vector only, measure the weakness, explain it (ENG-5 only asks to name the technique). B. Add hybrid (BM25 over chunks in memory, rank fusion), show recall by type before and after.
- Claude recommends: A first. Add B only if time remains after the CI gate works; it is bonus-sized and risks the CI timeline.
- Blocks: retriever design only.
- Decision:
- Decided on:

### D-007 ADR 0002 and 0003 topics
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: docs
- Related: `docs/adr/`, `scripts/check_submission.py`
- Question: The assignment names ADR 0001 (indexer as Job) and 0004 (LLM provider and data governance). What are 0002 and 0003? Need to read what the checker expects.
- Claude recommends: 0002 semantic cache backend (D-001), 0003 embedding pin and metadata filtering for versions. Claude will read `scripts/check_submission.py` and adjust.
- Blocks: ADR files.
- Decision:
- Decided on:

### D-008 Where ARCHITECTURE.md lives
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: docs
- Related: R-K8S-CHROMA
- Question: The assignment requires the reason for StatefulSet to be documented "in your ARCHITECTURE.md", but the layout lists no such file.
- Claude recommends: `docs/ARCHITECTURE.md`, unless the checker looks for it at the root.
- Blocks: doc layout.
- Decision:
- Decided on:

### D-009 Ingress hostname
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: k8s
- Related: R-K8S-ING, `make ask`, `run_eval.py --host`
- Question: Which host name does the Ingress use? Starter `run_eval.py` examples use `--host rahbar.local`.
- Claude recommends: `rahbar.local`, with the `/etc/hosts` line (`$(minikube ip) rahbar.local`) in the README.
- Blocks: Ingress manifest, README.
- Decision:
- Decided on:

### D-010 CI e2e cluster: kind or k3d
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: ci-cd
- Related: R-CI-6
- Question: kind or k3d for the e2e-eval job? The CI runner has no Ollama. Which embedder and LLM does CI use?
- Options: A. kind or k3d plus the stub LLM and a deterministic fake embedder (hash-based) so recall on the 3 fixture docs is meaningful but cheap. B. Ollama in the runner (slow model pulls, flaky).
- Claude recommends: k3d (installed locally already) with option A. Needs an `EMBED_MODEL` value for the fake embedder and care so the pin check still runs. This also means the baseline in CI differs from the real-corpus baseline: keep two baselines or gate on fixtures only. Needs your decision.
- Blocks: ci.yml, eval baseline design.
- Decision:
- Decided on:

### D-011 Handling of the "older version" question
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: api
- Related: R-QRY-4, R-GOL-2
- Question: The filter must exclude superseded documents "unless the user explicitly asks about an older version". How do we detect that?
- Options: A. Keyword/regex on year or words like "2023", "old", "previous", "before", "superseded". B. Ask the LLM to extract an intent flag. C. Two-pass: retrieve current; if the question names a year matching a superseded `doc_version`, retrieve from it.
- Claude recommends: C using the year/version text (regex), no LLM call, easy to test. Answers must name which version they quote.
- Blocks: retriever filter logic, version-sensitive golden questions.
- Decision:
- Decided on:

### D-012 Follow-up question detection
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: api
- Related: R-QRY-2, R-CAC-4
- Question: The cache must skip follow-ups, but the API contract has only `{"question": "..."}`. How do we know a question is a follow-up?
- Options: A. Add an optional `history` or `conversation_id` field to the request (contract change, needs an ADR). B. Heuristic on the text (pronouns, "and what about", very short). C. Single-turn only: nothing is a follow-up, document it.
- Claude recommends: check what `ui/index.html` already sends. If it sends history, use it; otherwise C and say so.
- Blocks: cache, answer service.
- Decision:
- Decided on:

### D-013 Docker Hub account and repo names
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: ci-cd
- Related: R-CD-1, R-CD-4, R-SUB-3
- Question: Which Docker Hub account, and what repository names? Who creates the access token and stores it as a GitHub Secret? Images are public.
- Claude recommends: one namespace, three repos `rahbar-api`, `rahbar-indexer`, `rahbar-ui`. Token created by the account owner and added under repo Secrets: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`. Claude never sees the token.
- Blocks: cd.yml.
- Decision:
- Decided on:

### D-014 Branch protection: required checks and admin enforcement
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: process
- Related: R-DEV-2, R-DED-12
- Question: Once ci.yml exists, add its job names as required status checks. Enforce on admins now or only before submission? (Enforcement now stops accidental direct pushes by the owner too.)
- Claude recommends: enforce on admins as soon as CI exists; it removes the risk of another −4.
- Blocks: merging.
- Decision:
- Decided on:

### D-015 Which four failure stages to break
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: docs
- Related: R-FAI-A..F
- Question: Four of A to F are required. Which four?
- Claude recommends: A (scanned PDF without OCR), C (change `EMBED_MODEL` on the API only, which doubles as the pin demo), E (remove the superseded filter, version question), F (temperature 1.2). Chosen because each has a clear metric. B and D are cheap extras if time remains.
- Blocks: FAILURE-ANALYSIS.md.
- Decision:
- Decided on:

### D-016 Duplicate content: Prospectus 2026 vs Handbook 2026
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: corpus, indexer
- Related: R-COR-7, `docs/CORPUS.md` Known risks
- Question: The 5-page Prospectus rules overlap the 58-page Handbook with different clause numbers. Two current documents give the same rule with different numbering. Which one counts as "relevant" in the golden set? Which one should the answer cite?
- Claude recommends: golden questions list the Handbook as the primary relevant passage and accept the Prospectus as an alternate; do not dedupe at index time, and note the trap in PIPELINE.md.
- Blocks: golden set.
- Decision:
- Decided on:

### D-017 OCR settings and quality threshold
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: indexer
- Related: R-IDX-1, R-COR-3
- Question: When is a page "no text layer"? Which dpi and language? What is the accepted loss (for example clause numbers like 9.2 read as `92.`)?
- Claude recommends: a page counts as scanned when it has fewer than ~30 extractable characters; OCR at 200 dpi, `eng`, via `pytesseract` + `pdf2image` (what we tested). Add a light fix-up for clause numbers only if measured as worth it; otherwise document the loss.
- Blocks: extract stage.
- Decision:
- Decided on:

### D-018 LLM provider scope
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: api
- Related: R-LLM-1..4
- Question: Implement only `ollama-host` fully (the minimum), or also `hosted`? `hosted` needs a free-tier key and Secret handling and may be used in CI-less demos.
- Claude recommends: `ollama-host` full; `hosted` as a thin second file if time remains. Stub stays for tests.
- Blocks: provider code, ADR 0004.
- Decision:
- Decided on:

---

## Decided

### D-019 Corpus choice
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: corpus
- Decision: 9 FAST-NUCES documents (7 PDF, 2 HTML, 279 PDF pages): Rules Handbook 2026, Undergraduate Rules Aug 2023 (superseded), Prospectus 2026 rules, Student Handbook 2026, Annual Reports 2019-20 and 2023-24, Entrepreneurship policy (scanned), Fee page, Grading page. All seven properties covered. See `docs/CORPUS.md`.
- Decided on: 2026-11-04

### D-020 Absent topic is hostel rules
- Status: DECIDED
- Area: corpus
- Decision: Hostel PDF deliberately not downloaded. Golden must-abstain questions ask for specific hostel rules, not whether hostels exist (the Student Handbook mentions "In-Campus Hostel" in passing).
- Decided on: 2026-11-04

### D-021 Default LLM mode and models
- Status: DECIDED
- Area: api
- Decision: `ollama-host` default, `llama3.2:3b` for generation, `nomic-embed-text` (768-dim) for embeddings. Ollama runs on the laptop, listening on `0.0.0.0` (stop with `pkill ollama` when idle).
- Decided on: 2026-11-04

### D-022 Cluster setup
- Status: DECIDED
- Area: k8s
- Decision: minikube v1.39.0, docker driver, Calico CNI, 6 GB RAM, 4 CPUs, metrics-server and ingress addons, via `make cluster`. Docker commands go through `sg docker -c "..."` until the desktop session is re-logged.
- Decided on: 2026-11-04

### D-023 Branching and PR flow
- Status: DECIDED
- Area: process
- Decision: Work on `dev`, merge to `main` by PR with CI and one approval. The first starter commit went to `main` before protection (accepted). Commit trailer: `Co-Authored-By: Claude`.
- Decided on: 2026-11-04

### D-024 Dependency documentation
- Status: DECIDED
- Area: process
- Decision: Root `requirements.txt` includes the api and indexer dev requirements and lists system tools with versions in comments.
- Decided on: 2026-11-04

### D-025 Docker access workaround
- Status: DECIDED
- Area: process
- Decision: Use `sg docker -c "<cmd>"` until the user logs out and in so the `docker` group applies.
- Decided on: 2026-11-04

---

## Change log

- 2026-11-04: file created with D-001 to D-025.
