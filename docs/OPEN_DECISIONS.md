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
| D-001 | Semantic cache backend | api | DECIDED | ADR, Redis manifests, cache code |
| D-002 | Chunk size unit | indexer | PROVISIONAL | chunker, ConfigMap, PIPELINE.md |
| D-003 | How documents reach the indexer Job | indexer, k8s | PROVISIONAL | Job manifest, indexer Dockerfile |
| D-004 | Work split between Zain and Ahmad | process | DECIDED | everything |
| D-005 | Embedding via Ollama host | indexer, api | DECIDED | embed stage, NetworkPolicy |
| D-006 | Retrieval: vector only or hybrid | api, eval | PROVISIONAL | retriever, exact-term recall |
| D-007 | ADR 0002 and 0003 topics | docs | DECIDED | ADR files, checker |
| D-008 | Where ARCHITECTURE.md lives | docs | PROVISIONAL | doc layout |
| D-009 | Ingress hostname | k8s | PROVISIONAL | Ingress, eval host header |
| D-010 | CI e2e cluster: kind or k3d | ci-cd | DECIDED | ci.yml |
| D-011 | Handling of the "older version" question | api | PROVISIONAL | retriever filter logic |
| D-012 | Follow-up question detection | api | PROVISIONAL | cache, answer service |
| D-013 | Docker Hub account and repo names | ci-cd | OPEN | cd.yml |
| D-014 | Branch protection: required checks and admin enforcement | process | OPEN | merging |
| D-015 | Which four failure stages to break | docs | OPEN | FAILURE-ANALYSIS.md |
| D-016 | Duplicate content: Prospectus 2026 vs Handbook 2026 | corpus, indexer | DECIDED | golden set, retrieval |
| D-017 | OCR settings and quality threshold | indexer | PROVISIONAL | extract stage |
| D-018 | LLM provider scope | api | PROVISIONAL | provider code |
| D-019 | Corpus choice | corpus | DECIDED | |
| D-020 | Absent topic is hostel rules | corpus | DECIDED | |
| D-021 | Default LLM mode and models | api | DECIDED | |
| D-022 | Cluster setup | k8s | DECIDED | |
| D-023 | Branching and PR flow | process | DECIDED | |
| D-024 | Dependency documentation | process | DECIDED | |
| D-025 | Docker access workaround | process | DECIDED | |
| D-026 | Re-index swap strategy | indexer | DECIDED |  |
| D-027 | Cache invalidation without indexer in Redis | api, indexer | PROVISIONAL | cache code |
| D-028 | Third overlay `ci` | k8s, ci-cd | PROVISIONAL | kustomize layout |
| D-029 | Kit interface extensions | api | PROVISIONAL | provider, retriever code |
| D-030 | Embedding code duplicated in api and indexer | api, indexer | PROVISIONAL | embedder code |
| D-031 | Two eval baselines | eval, ci-cd | PROVISIONAL | CI gate |
| D-032 | Pull request flow inside the team | process | PROVISIONAL | merging |
| D-033 | License | docs | DECIDED | |
| D-034 | Load balance between lanes | process | OPEN | work plan |
| D-035 | api image: how the build stage hands over dependencies | api | DECIDED | api/Dockerfile |
| D-036 | HEALTHCHECK in the Dockerfiles | api, indexer | DECIDED | Dockerfiles |
| D-037 | Makefile `images` target during phase 1 | process | DECIDED | make images |
| D-038 | Redis Stack server image tag | api, k8s | DECIDED | Makefile, Redis manifest |
| D-039 | Where the Ollama assumption check lives | process | DECIDED | verify_ollama.py |
| D-040 | Dev services data persistence | process | DECIDED | make dev-services |
| D-041 | Where the non-root read-only checks live | process | DECIDED | verify_services.py |
| D-042 | Version pair for the golden set (attendance premise is wrong) | corpus, eval | DECIDED | golden set, CORPUS.md |
| D-043 | Injection golden question: `relevant` item or empty | eval | DECIDED | golden set |
| D-044 | Multi-column Prospectus: how extract orders the text | indexer | DECIDED | extract |
| D-045 | Where the golden-versus-cleaned-text check lives | indexer, eval | DECIDED | phase 4 test plan |
| D-046 | Eval section match folds dashes | eval | DECIDED | run_eval.py recall_at_k, DEV-002 |
| D-047 | Eval behaviour when an /api/ask call fails | eval | DECIDED | run_eval.py main |
| D-048 | Guard --update-baseline against a failed gate | eval | DECIDED | run_eval.py main |

---

## Open

### D-001 Semantic cache backend
- Status: DECIDED
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
- Decision: Redis Stack with a real vector index (HNSW, cosine). Chosen by Zain on 2026-11-04. See architecture AD-03. Risk: image must run non-root (architecture R-02); fallback is plain Redis with app-side cosine.
- Decided on: 2026-11-04

### D-002 Chunk size unit
- Status: PROVISIONAL
- Raised: 2026-11-04 by Claude
- Area: indexer
- Related: R-IDX-3, R-IDX-7, R-IDX-8, `CHUNK_SIZE=400`, `CHUNK_OVERLAP=50`
- Question: Are `CHUNK_SIZE` and `CHUNK_OVERLAP` in tokens or characters? The report must state the unit and the storage amplification is "tokens stored / tokens original".
- Options: A. Tokens (use an approximate tokenizer or word count). B. Characters (simple, deterministic, no tokenizer dependency).
- Claude recommends: A with whitespace-word counts as a proxy (no extra dependency), stated plainly in PIPELINE.md. Amplification is then just words stored / words original. Three configs to measure, for example (200, 25), (400, 50), (600, 100).
- Blocks: chunker, ConfigMap, PIPELINE.md.
- Decision: Words (whitespace-separated), AD-10 in architecture. Confirm.
- Decided on: (pending confirmation)

### D-003 How documents reach the indexer Job
- Status: PROVISIONAL
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
- Decision: PVC corpus-data filled by `make corpus` from local corpus/raw (AD-08); the Job re-hashes files against _index.json before indexing. Zain asked for the drawbacks of this option; Claude proceeded provisionally. Confirm or switch to the init-container fetch.
- Decided on: (pending confirmation)

### D-004 Work split between Zain and Ahmad
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: process
- Question: Who owns which stream? Two natural streams: (1) platform: Dockerfiles, k8s manifests, NetworkPolicy, CI/CD, evidence; (2) RAG: indexer stages, retriever, providers, cache, eval, golden set. Docs split along the same lines.
- Options: A. Zain platform, Ahmad RAG. B. Reverse. C. Pair on both, alternating.
- Claude recommends: A or B (pick by who is stronger at what), with the golden set written jointly and early, since both streams depend on it.
- Blocks: everything; also the AI-USAGE.md attribution.
- Decision: Zain: RAG, API, indexer, eval, api and indexer Dockerfiles. Ahmad: Kubernetes, UI, CI/CD, evidence. Details in docs/WORKPLAN.md.
- Decided on: 2026-11-04

### D-005 Embedding via Ollama on the host
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: indexer, api
- Related: R-LLM-5, R-PIN-1..3, R-SEC-4
- Question: Embed with `nomic-embed-text` served by Ollama on the laptop (same host as generation)? The assignment allows it if the README says so.
- Options: A. Yes, host Ollama for both embedding and generation. B. Embed with a library in the image (sentence-transformers): heavier image, more RAM in the Job, no Ollama dependency for indexing.
- Claude recommends: A. Already installed and tested (768-dim). Consequence: the indexer Job and the API both need egress to the host, and the CI e2e job cannot reach Ollama, so CI needs a deterministic fake embedder or a stub path. See D-010.
- Blocks: embed stage, NetworkPolicy, CI design.
- Decision: Yes: Ollama on the host embeds for both indexer and API (AD-06). CI uses the deterministic hashing embedder `hashing-bow-768` instead (AD-07).
- Decided on: 2026-11-04

### D-006 Retrieval: vector only or hybrid
- Status: PROVISIONAL
- Raised: 2026-11-04 by Claude
- Area: api, eval
- Related: R-COR-7, R-ENG-5, R-BON-2
- Question: Build hybrid retrieval (keyword/BM25 plus vector) or stay vector-only and document the exact-term weakness?
- Options: A. Vector only, measure the weakness, explain it (ENG-5 only asks to name the technique). B. Add hybrid (BM25 over chunks in memory, rank fusion), show recall by type before and after.
- Claude recommends: A first. Add B only if time remains after the CI gate works; it is bonus-sized and risks the CI timeline.
- Blocks: retriever design only.
- Decision: Vector only in the baseline (architecture 1.2). Hybrid stays optional bonus.
- Decided on: (pending confirmation)

### D-007 ADR 0002 and 0003 topics
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: docs
- Related: `docs/adr/`, `scripts/check_submission.py`
- Question: The assignment names ADR 0001 (indexer as Job) and 0004 (LLM provider and data governance). What are 0002 and 0003? Need to read what the checker expects.
- Claude recommends: 0002 semantic cache backend (D-001), 0003 embedding pin and metadata filtering for versions. Claude will read `scripts/check_submission.py` and adjust.
- Blocks: ADR files.
- Decision: Read from scripts/check_submission.py: 0001 indexer-as-Job, 0002 chunking, 0003 cache store, 0004 LLM provider and data governance (PII). Filenames should contain these words.
- Decided on: 2026-11-04

### D-008 Where ARCHITECTURE.md lives
- Status: PROVISIONAL
- Raised: 2026-11-04 by Claude
- Area: docs
- Related: R-K8S-CHROMA
- Question: The assignment requires the reason for StatefulSet to be documented "in your ARCHITECTURE.md", but the layout lists no such file.
- Claude recommends: `docs/ARCHITECTURE.md`, unless the checker looks for it at the root.
- Blocks: doc layout.
- Decision: The reason for the StatefulSet is written in docs/architecture/architecture.md section 4.10. Add a short docs/ARCHITECTURE.md pointer when the README is written, so the file name the assignment mentions exists. The checker does not look for it.
- Decided on: (pending confirmation)

### D-009 Ingress hostname
- Status: PROVISIONAL
- Raised: 2026-11-04 by Claude
- Area: k8s
- Related: R-K8S-ING, `make ask`, `run_eval.py --host`
- Question: Which host name does the Ingress use? Starter `run_eval.py` examples use `--host rahbar.local`.
- Claude recommends: `rahbar.local`, with the `/etc/hosts` line (`$(minikube ip) rahbar.local`) in the README.
- Blocks: Ingress manifest, README.
- Decision: rahbar.local, as in the Makefile and run_eval examples (architecture 4.3).
- Decided on: (pending confirmation)

### D-010 CI e2e cluster: kind or k3d
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: ci-cd
- Related: R-CI-6
- Question: kind or k3d for the e2e-eval job? The CI runner has no Ollama. Which embedder and LLM does CI use?
- Options: A. kind or k3d plus the stub LLM and a deterministic fake embedder (hash-based) so recall on the 3 fixture docs is meaningful but cheap. B. Ollama in the runner (slow model pulls, flaky).
- Claude recommends: k3d (installed locally already) with option A. Needs an `EMBED_MODEL` value for the fake embedder and care so the pin check still runs. This also means the baseline in CI differs from the real-corpus baseline: keep two baselines or gate on fixtures only. Needs your decision.
- Blocks: ci.yml, eval baseline design.
- Decision: Zain: no LLM in CI, a rule-based fallback instead. Implemented as the `extractive` provider plus the `hashing-bow-768` embedder (AD-07). Cluster: kind plus ingress-nginx (AD-19, provisional). Two baselines (AD-27).
- Decided on: 2026-11-04

### D-011 Handling of the "older version" question
- Status: PROVISIONAL
- Raised: 2026-11-04 by Claude
- Area: api
- Related: R-QRY-4, R-GOL-2
- Question: The filter must exclude superseded documents "unless the user explicitly asks about an older version". How do we detect that?
- Options: A. Keyword/regex on year or words like "2023", "old", "previous", "before", "superseded". B. Ask the LLM to extract an intent flag. C. Two-pass: retrieve current; if the question names a year matching a superseded `doc_version`, retrieve from it.
- Claude recommends: C using the year/version text (regex), no LLM call, easy to test. Answers must name which version they quote.
- Blocks: retriever filter logic, version-sensitive golden questions.
- Decision: Rule-based: year tokens matching known doc_versions, else older-version phrases, else current only (architecture 5.6.2).
- Decided on: (pending confirmation)

### D-012 Follow-up question detection
- Status: PROVISIONAL
- Raised: 2026-11-04 by Claude
- Area: api
- Related: R-QRY-2, R-CAC-4
- Question: The cache must skip follow-ups, but the API contract has only `{"question": "..."}`. How do we know a question is a follow-up?
- Options: A. Add an optional `history` or `conversation_id` field to the request (contract change, needs an ADR). B. Heuristic on the text (pronouns, "and what about", very short). C. Single-turn only: nothing is a follow-up, document it.
- Claude recommends: check what `ui/index.html` already sends. If it sends history, use it; otherwise C and say so.
- Blocks: cache, answer service.
- Decision: Single-turn API, no follow-ups. The UI sends only the question. A follow_up flag exists internally for the cache rule (architecture 5.5.4).
- Decided on: (pending confirmation)

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
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: corpus, indexer
- Related: R-COR-7, `docs/CORPUS.md` Known risks
- Question: The 5-page Prospectus rules overlap the 58-page Handbook with different clause numbers. Two current documents give the same rule with different numbering. Which one counts as "relevant" in the golden set? Which one should the answer cite?
- Claude recommends: golden questions list the Handbook as the primary relevant passage and accept the Prospectus as an alternate; do not dedupe at index time, and note the trap in PIPELINE.md.
- Blocks: golden set.
- Decision: A, one primary source in `relevant`, no new YAML keys. Questions about a rule that exists in more than one current document name the document or pick content only one document holds (phase 3 spec 5.1). Index-time dedupe stays off; the trap is noted for PIPELINE.md.
- Decided on: 2026-11-04

### D-017 OCR settings and quality threshold
- Status: PROVISIONAL
- Raised: 2026-11-04 by Claude
- Area: indexer
- Related: R-IDX-1, R-COR-3
- Question: When is a page "no text layer"? Which dpi and language? What is the accepted loss (for example clause numbers like 9.2 read as `92.`)?
- Claude recommends: a page counts as scanned when it has fewer than ~30 extractable characters; OCR at 200 dpi, `eng`, via `pytesseract` + `pdf2image` (what we tested). Add a light fix-up for clause numbers only if measured as worth it; otherwise document the loss.
- Blocks: extract stage.
- Decision: Page is scanned when it has fewer than 30 non-space characters; OCR at 200 dpi, language eng, pdf2image + pytesseract (architecture 5.4.2).
- Decided on: (pending confirmation)

### D-018 LLM provider scope
- Status: PROVISIONAL
- Raised: 2026-11-04 by Claude
- Area: api
- Related: R-LLM-1..4
- Question: Implement only `ollama-host` fully (the minimum), or also `hosted`? `hosted` needs a free-tier key and Secret handling and may be used in CI-less demos.
- Claude recommends: `ollama-host` full; `hosted` as a thin second file if time remains. Stub stays for tests.
- Blocks: provider code, ADR 0004.
- Decision: ollama-host full; `extractive` for CI and tests; `hosted` as a thin second file only if time allows (architecture 5.7.2).
- Decided on: (pending confirmation)

### D-026 Re-index swap strategy
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: indexer
- Related: AD-02, `indexer/pipeline/store.py`, ADR 0001
- Decision: Build `rahbar_next`, verify the count, delete `rahbar`, rename `rahbar_next` to `rahbar`. A failed Job never touches the live index. Chosen by Zain on 2026-11-04.
- Decided on: 2026-11-04

### D-027 Cache invalidation without the indexer touching Redis
- Status: PROVISIONAL
- Raised: 2026-11-04 by Claude
- Area: api, indexer
- Related: AD-04, AD-05, R-CAC-5, R-SEC-4
- Question: The assignment says "redis from api only" and also "expire the cache when the indexing Job runs". Both hold only if the indexer never reaches Redis.
- Claude recommends (and used): the indexer stamps a new `index_id` in the collection metadata; each API pod names its cache search index by it and drops older ones. A `scope` tag keeps version-intent questions apart.
- Decision: pending confirmation.

### D-028 Overlays: add `ci` next to `dev` and `prod`
- Status: PROVISIONAL
- Raised: 2026-11-04 by Claude
- Area: k8s, ci-cd
- Related: AD-18, requirements R-CI-6, R-CD-1
- Question: The assignment names two overlays. CI and the CD smoke test run on kind with no Ollama, so they need fixture corpus, hashing embedder and extractive provider. Three overlays keep that out of `dev` and `prod`.
- Decision: pending confirmation.

### D-029 Kit interface extensions
- Status: PROVISIONAL
- Raised: 2026-11-04 by Claude
- Area: api
- Related: AD-14, AD-15, STARTER.md ("If you change a contract, say why in an ADR")
- Question: Provider `generate` returns a `GenerationResult` (adds token counts) and accepts a retry `hint`; the retriever accepts an optional pre-computed `vector` and `where`; outcome travels in `X-Outcome` and `X-Cache` headers. The external JSON is unchanged. Needs a line in ADR 0004.
- Decision: pending confirmation.

### D-030 Embedding code duplicated in api and indexer
- Status: PROVISIONAL
- Raised: 2026-11-04 by Claude
- Area: api, indexer
- Related: AD-09
- Question: The two images have separate build contexts, so the Ollama client and the hashing embedder exist twice. A parity test with a fixed golden vector keeps them equal. Alternative: a shared package built into both images (more build plumbing).
- Decision: pending confirmation.

### D-031 Two eval baselines
- Status: PROVISIONAL
- Raised: 2026-11-04 by Claude
- Area: eval, ci-cd
- Related: AD-27
- Question: The CI gate runs on fixtures with a deterministic embedder, so its numbers differ from the real-corpus baseline. CI uses `eval/fixtures/baseline.fixture.json`; `eval/baseline.json` holds the shipped real numbers from a local run.
- Decision: pending confirmation.

### D-032 Pull request flow inside the team
- Status: PROVISIONAL
- Raised: 2026-11-04 by Claude
- Area: process
- Related: CONTRIBUTING.md section 2
- Question: Feature branches off `dev`, one PR per task. A change touching only your own lane's files may be merged into `dev` by its author after `make test && make lint`; changes in shared files or contracts need the other person's review. `dev` to `main` needs approval (protection).
- Claude recommends: as written, to keep a four-day schedule moving. Stricter option: every PR into `dev` needs the other person's approval.
- Decision: pending confirmation.

### D-033 License
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: docs
- Decision: No license for now (Zain, 2026-11-04). `scripts/check_submission.py` may warn about a missing LICENSE; revisit before submission.
- Decided on: 2026-11-04

### D-034 Load balance between lanes
- Status: OPEN
- Raised: 2026-11-04 by Claude
- Area: process
- Related: docs/WORKPLAN.md
- Question: Estimates are about 37.5 h (Zain) and 39 h (Ahmad) against roughly 40 h each. Zain's lane has the serial dependency chain. If Zain slips, candidates to move to Ahmad: the `hashing-bow-768` embedder and `extractive` provider (he needs them for CI e2e), unit tests for the pure modules, and running the four failure-analysis experiments.
- Decision: pending.

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

### D-035 api image: how the build stage hands over dependencies
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: api
- Related: architecture 4.12, phase 1 spec
- Question: Copy a virtualenv or a wheel directory from the build stage to the runtime stage?
- Options: A. Virtualenv at `/opt/venv`. B. Wheel directory, `pip install --no-index` in the final stage.
- Claude recommends: A. One COPY, no wheel-install step in the final image.
- Blocks: api/Dockerfile.
- Decision: A, virtualenv at `/opt/venv`.
- Decided on: 2026-11-04

### D-036 HEALTHCHECK in the Dockerfiles
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: api, indexer
- Related: architecture 4.8, R-PRB-1
- Question: Add a Docker `HEALTHCHECK`?
- Options: A. None. B. api only, python one-liner against `/healthz`.
- Claude recommends: A. Kubernetes ignores `HEALTHCHECK`; the probes in the manifests are fixed by the assignment; slim has no curl.
- Blocks: Dockerfiles.
- Decision: A, none.
- Decided on: 2026-11-04

### D-037 Makefile `images` target during phase 1
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: process
- Related: Makefile `images`, WORKPLAN A-01
- Question: `make images` also builds the ui image, which does not exist until Ahmad's A-01. Edit the shared Makefile now?
- Options: A. Leave it; Ahmad runs the two `docker build` lines until A-01 lands. B. Add an `images-rag` target.
- Claude recommends: A. Shared file, outside the phase scope.
- Blocks: nothing.
- Decision: A, leave the Makefile alone. Tell Ahmad in H-1.
- Decided on: 2026-11-04

### D-38 Redis Stack server image tag
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: api, k8s
- Related: architecture 3, 9.2 R-02, D-001, H-2
- Question: Which exact `redis/redis-stack-server` tag to pin (no `latest`)?
- Options: A. `7.4.0-v8` (newest 7.4, 2025-11-03). B. `7.2.0-v20` (newest 7.2).
- Claude recommends: A. Newest stable line; fall back to B in the same phase if the non-root check fails on A for a tag-specific reason.
- Blocks: Makefile `REDIS_IMAGE`, architecture section 3, Ahmad's Redis manifest.
- Decision: A, `redis/redis-stack-server:7.4.0-v8`.
- Decided on: 2026-11-04

### D-39 Where the Ollama assumption check lives
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: process
- Related: architecture 9.1 A-6, phase 10
- Question: Where does the A-6 check (`format`, `num_ctx` 8192, embed batch) live?
- Options: A. Separate `scripts/verify_ollama.py`. B. Flag on `verify_services.py`. C. Manual curl only.
- Claude recommends: A. `verify_services.py` then needs only the two containers; the Ollama script is re-runnable in phase 10.
- Blocks: verify_ollama.py.
- Decision: A, separate script.
- Decided on: 2026-11-04

### D-40 Dev services data persistence
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: process
- Related: phase 2, phase 7
- Question: Do `make dev-services` containers keep data between runs?
- Options: A. Named volumes kept; stop removes containers only; extra `dev-services-reset` removes volumes. B. Fully ephemeral.
- Claude recommends: A. Phase 7 indexing with OCR and embeddings is slow; no re-index per session.
- Blocks: Makefile targets.
- Decision: A, named volumes kept.
- Decided on: 2026-11-04

### D-41 Where the non-root read-only checks live
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: process
- Related: architecture 4.7, R-01, R-02
- Question: Where do the R-01 and R-02 `docker run --read-only --user` checks live?
- Options: A. Items 3 and 4 inside `verify_services.py` via subprocess docker. B. Manual commands recorded in the spec only.
- Claude recommends: A. Re-runnable evidence the tester can repeat; skipped cleanly without docker.
- Blocks: verify_services.py.
- Decision: A, inside the script.
- Decided on: 2026-11-04

### D-42 Version pair for the golden set (attendance premise is wrong)
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: corpus, eval
- Related: R-GOL-2, `docs/CORPUS.md` rows 2 and 7, `IMPLEMENTATION_PLAN.md` phase 3 design notes, phase 3 spec 2 and 5.1
- Question: `docs/CORPUS.md` and the plan say attendance is clause 1.22 in the Aug 2023 rules and 1.21 in the 2026 Handbook. OCR of the 2023 rules (PDF pages 7 and 8) shows attendance is 1.21 in both, identical wording; 1.22 is the F/A consequence in both. "130 credit hours" is clause 1.25 in 2023 only; the 2026 text has no such clause. Real differences found by a clause-level comparison: withdrawal deadline 4.25 (2023 last day of classes; 2026 last day of the makeup week), summer new courses (2023 allows exceptions; 2026 repeat only), summer length (8 to 9 weeks; 8 weeks).
- Options: A. Use withdrawal deadline 4.25 for the two version questions and correct CORPUS.md and the plan note in this PR. B. Same questions, leave the docs. C. Use summer new courses.
- Claude recommends: A. Clean, same clause number, different wording, short OCR text; wrong notes in the docs would mislead phases 6 and 13.
- Blocks: golden set; the wording of CORPUS.md.
- Decision: A.
- Decided on: 2026-11-04

### D-43 Injection golden question: `relevant` item or empty
- Status: DECIDED
- Raised: 2026-11-04 by Claude
- Area: eval
- Related: R-GOL-5, `eval/fixtures/golden.fixture.yaml` f06, `eval/golden.example.yaml` q15
- Question: The starter example gives the injection question an empty `relevant`; the CI fixture f06 gives it the attendance clause. Which one?
- Options: A. `relevant` = Handbook 1.21, `expect: 100%` (recall counted; tests that the system still answers from the document). B. Empty `relevant` (excluded from recall).
- Claude recommends: A. Matches the fixture and checks that resisting the injection does not turn into abstaining.
- Blocks: golden set q18.
- Decision: A.
- Decided on: 2026-11-04

### D-044 Multi-column Prospectus: how extract orders the text
- Status: DECIDED
- Raised: 2026-11-04 by Claude (phase 4)
- Area: indexer
- Related: architecture 5.4.2, 5.4.5; golden q11; phase 4 spec
- Question: The Prospectus 2026 PDF is 3 columns. pdfplumber reads it line by line across the columns, so the 75% attendance sentence is cut by unrelated text. Fix it, and how?
- Options:
  - A. Per-file column splits: a small table in `extract.py` maps the file name to its gutters (measured x about 220 and 397); each column is cropped and read in order.
  - B. Document the loss only.
  - C. Generic per-page gutter detector for every PDF (risk: splits tables in the handbooks).
- Claude recommends: A. Smallest change that fixes the one multi-column file, testable on a synthetic page.
- Blocks: extract.py design.
- Decision: A.
- Decided on: 2026-11-04

### D-045 Where the golden-versus-cleaned-text check lives
- Status: DECIDED
- Raised: 2026-11-04 by Claude (phase 4)
- Area: indexer, eval
- Related: eval/golden.yaml; phase 4 spec AC-9
- Question: Each golden `expect` string should be found in the cleaned text of its source page. The check needs `corpus/raw` and tesseract, which CI lacks. Script, pytest that skips when the corpus is absent, or both?
- Options: A. `scripts/check_golden_extract.py`, never skipped, run by developer and tester. B. pytest that skips without the corpus. C. Both.
- Claude recommends: A. `make test` stays offline and nothing is silently skipped.
- Blocks: phase 4 test plan.
- Decision: A.
- Decided on: 2026-11-04

### D-046 Eval section match folds dashes
- Status: DECIDED
- Raised: 2026-11-04 by Claude (phase 5)
- Area: eval
- Related: AD-22, architecture 5.13.2, R-EVA-1, eval/golden.yaml q05 and q06, DEV-002
- Question: AD-22 matches sections by trim, lower-case, whitespace collapse. The real Student Handbook heading is `VI – SEMESTER RULES` (en dash) while `V - EXAMINATION RULES` uses a hyphen, and the chunker may emit either. Fold dashes too?
- Options: A. NFKC plus en/em dash to hyphen before comparing (small deviation from AD-22). B. Strict AD-22.
- Claude recommends: A. A typographic dash must not score as a recall miss.
- Blocks: recall_at_k.
- Decision: A. Logged as DEV-002 (S3) with the code.
- Decided on: 2026-11-04

### D-047 Eval behaviour when an /api/ask call fails
- Status: DECIDED
- Raised: 2026-11-04 by Claude (phase 5)
- Area: eval
- Related: R-EVA-9, contract C-6 (exit codes 0, 1, 2)
- Question: A connection error or 5xx currently crashes the runner with a traceback (exit 1, same as gate failed). What should it do?
- Options: A. Catch, name the question and the error, write no results, exit 1. B. New exit code 3 (changes C-6). C. Record an error row and continue.
- Claude recommends: A. CI is red either way, contract unchanged, a half run is never scored.
- Blocks: main().
- Decision: A.
- Decided on: 2026-11-04

### D-048 Guard --update-baseline against a failed gate
- Status: DECIDED
- Raised: 2026-11-04 by Claude (phase 5)
- Area: eval
- Related: R-EVA-9, R-EVA-7
- Question: main() writes baseline.json with --update-baseline even if the gate failed. Guard it?
- Options: A. Refuse (print why, exit 1) when the abstention or citation gate fails; a recall drop alone may still be saved as a deliberate choice. B. Leave main() as given.
- Claude recommends: A. A baseline with a leaked abstention or invalid citations must never be committed.
- Blocks: main().
- Decision: A.
- Decided on: 2026-11-04

---

## Change log

- 2026-11-04: file created with D-001 to D-025.
- 2026-11-04: architecture v1.0 written. D-001, D-005, D-007, D-010 decided; D-002, D-003, D-006, D-008, D-009, D-011, D-012, D-017, D-018 made provisional; D-026 to D-031 added.
- 2026-11-04: work plan written. D-004 decided; D-032 to D-034 added.
- 2026-11-04: phase 1 questions answered. D-035 to D-037 added, all DECIDED.
- 2026-11-04: phase 2 questions answered. D-038 to D-041 added, all DECIDED.
- 2026-11-04: phase 3 questions answered. D-016 decided; D-042, D-043 added, all DECIDED.
- 2026-11-04: phase 4 questions answered. D-044, D-045 added, both DECIDED.
- 2026-11-04: phase 5 questions answered. D-046 to D-048 added, all DECIDED.
