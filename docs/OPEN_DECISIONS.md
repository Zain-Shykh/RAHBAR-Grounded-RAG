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
| D-015 | Which four failure stages to break | docs | DECIDED | FAILURE-ANALYSIS.md |
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
| D-052 | Handbook PDFs are two-page spreads: split by file like D-044 | indexer | DECIDED | extract |
| D-053 | Embedding package layout and parity with the api | indexer | DECIDED | embed, AD-09 |
| D-054 | What store validates before touching Chroma | indexer | DECIDED | store |
| D-055 | How the live indexer run is proven | indexer, process | DECIDED | phase 7 test plan |
| D-056 | Wait timeouts and batch size as config | indexer | DECIDED | config.py |

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
- Decision: A, C, E and F as recommended (A: scanned policy without OCR; C: `EMBED_MODEL` on the API only, which doubles as the pin demonstration; E: superseded filter removed; F: `TEMPERATURE=1.2`). B and D are not run. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

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

### D-049 How the chunker finds headings, and how long a section string may be
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 6)
- Area: indexer
- Related: architecture 5.4.2, AD-22; golden q07, q15; DEV-003
- Question: The architecture names three heading kinds (numbered clause, roman or lettered line, all caps). The HTML pages have plain short heading lines (`Fee Refund Policy`) that none of them find, and the numbered regex also matches years and table data (`2023 ...`, `19 14 46`). A clause line can also be long.
- Options:
  - A. Add a fourth rule (isolated short line: blank line before, text after, at most 10 words, no final punctuation); tighten the numbered rule to at most 2 leading digits and a capital or `(` next; cut `section` at 80 characters on a word boundary.
  - B. Architecture rules only; HTML sections fall back to the page title.
  - C. Change `extract` so HTML headings carry a marker.
- Claude recommends: A. Smallest change that makes the HTML golden items matchable; B loses q07 and q15; C reopens a merged phase.
- Blocks: chunk.py heading detection.
- Decision: A. Logged as DEV-003 (S3).
- Decided by: Claude, pre-approved by Zain
- Decided on: 2026-11-05

### D-050 Packing details: tiny sections, over-long units, overlap and tables
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 6)
- Area: indexer
- Related: architecture 5.4.2, AD-10, AD-22
- Question: What happens with clauses far shorter than `CHUNK_SIZE`, with a sentence longer than `CHUNK_SIZE`, and with overlap after a table row?
- Options:
  - A. Never merge sections (one clause is one chunk, so `section` stays exact); cut an over-long sentence into `size`-word pieces; no overlap after a chunk that ends in a table row.
  - B. Merge small neighbouring sections up to `size` (fewer chunks, but the chunk label is wrong for the second clause and recall by section drops).
  - C. Let an over-long sentence stay whole (violates the size cap).
- Claude recommends: A. Keeps AD-22 labels true, the size cap simple (only one table row may exceed it), and overlap never starts mid-row.
- Blocks: chunk.py packing.
- Decision: A.
- Decided by: Claude, pre-approved by Zain
- Decided on: 2026-11-05

### D-051 Chunk id sequence start and the page of a chunk
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 6)
- Area: indexer
- Related: architecture 5.4.2 (id rule, page rule), AD-28
- Question: Does `seq` start at 0 or 1, and is `page` the page of the overlap text or of the first new text?
- Options: A. `seq` from 1; page of the first non-overlap unit. B. `seq` from 0; page of the overlap start.
- Claude recommends: A. Overlap text is a copy; the new content defines where the chunk is cited from. 1-based matches the 1-based page.
- Blocks: chunk ids.
- Decision: A.
- Decided by: Claude, pre-approved by Zain
- Decided on: 2026-11-05

---

### D-90 ui base image tag
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase K1)
- Area: platform
- Question: Which pinned nginx-unprivileged tag for the ui image?
- Decision: `nginxinc/nginx-unprivileged:1.27-alpine` (nginx 1.27.5, 73.7 MB image). Non-root user 101, listens on 8080, pulls cleanly. Decided by: Claude, pre-approved by Zain
- Decided on: 2026-11-05

### D-91 Redis probes are exec `redis-cli ping`
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase K1)
- Area: platform
- Question: Probe form for Redis (H-2 allows `redis-cli ping` or tcpSocket)?
- Decision: Exec `redis-cli ping` for startup, liveness and readiness: it proves the server answers, not only that the port is open. Decided by: Claude, pre-approved by Zain
- Decided on: 2026-11-05

### D-92 Pods disable Service links
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase K1)
- Area: platform
- Question: Chroma crash-loops because Service `chroma` injects `CHROMA_PORT=tcp://...`. How to avoid?
- Decision: `enableServiceLinks: false` on every pod (api, ui, chroma, redis). Also stops Service variables from shadowing ConfigMap keys such as `REDIS_PORT`. Logged as DEV-008. Decided by: Claude, pre-approved by Zain
- Decided on: 2026-11-05

## Change log

- 2026-11-04: file created with D-001 to D-025.
- 2026-11-04: architecture v1.0 written. D-001, D-005, D-007, D-010 decided; D-002, D-003, D-006, D-008, D-009, D-011, D-012, D-017, D-018 made provisional; D-026 to D-031 added.
- 2026-11-04: work plan written. D-004 decided; D-032 to D-034 added.
- 2026-11-04: phase 1 questions answered. D-035 to D-037 added, all DECIDED.
- 2026-11-04: phase 2 questions answered. D-038 to D-041 added, all DECIDED.
- 2026-11-04: phase 3 questions answered. D-016 decided; D-042, D-043 added, all DECIDED.
- 2026-11-04: phase 4 questions answered. D-044, D-045 added, both DECIDED.
- 2026-11-04: phase 5 questions answered. D-046 to D-048 added, all DECIDED.
- 2026-11-05: phase 6 decisions. D-049 to D-051 added, all DECIDED (Claude, pre-approved by Zain).

### D-052 Handbook PDFs are two-page spreads: split by file like D-044
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 7, Zain's phase 6 review)
- Area: indexer
- Related: D-044, DEV-003, phase 6 spec known losses
- Finding: the Student Handbook (even pages) and the Academic Rules Handbook (pages 4, 6, 8, 54) hold two printed pages on one clipped MediaBox (width 410 and 420; content to x 756 and 796). pdfplumber read both halves line by line. Measured: left page ends x 363 / 377, right page starts x 445 / 462.
- Options: A. Add both files to `COLUMN_SPLITS` (gutter x 404 and 400); the last crop runs to the farthest word, not the page width. B. Generic detector. C. Leave it.
- Claude recommends: A (as D-044). Odd pages are unchanged (the right crop is empty).
- Decision: A. Decided by: Claude, pre-approved by Zain (phase 6 review).
- Result: `chunk_report.py --golden` still 0 missing. Golden section strings of q05, q06 not restored: numbered items inside a Roman section still become their own sections (DEV-003). q09, q10 are not Handbook items.
- Decided on: 2026-11-05

### D-53 Embedding package layout and parity with the api
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 7)
- Area: indexer
- Related: phase 7 spec
- Question: Where do the two embedders live, and how is parity with the api kept (AD-09)?
- Options: A. `indexer/pipeline/embedding/{ollama,hashing}.py` plus `embed.py` dispatcher, golden-vector test; the api copies the files in phase 8. B. One module. C. Shared package (breaks the two build contexts, AD-09).
- Claude recommends: A. Matches the plan and AD-09; a golden vector of eight numbers is the parity check.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-54 What store validates before touching Chroma
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 7)
- Area: indexer
- Related: phase 7 spec
- Question: Chroma silently upserts duplicate ids in some versions and accepts ragged vectors until query time. What does store check?
- Options: A. Fail fast (`StoreError`, exit 1) on length mismatch, duplicate ids, empty text, vectors not all the model dimension. B. Trust the pipeline. C. Drop bad chunks with a warning.
- Claude recommends: A. A partial index is the worst result (5.4.5, store row); failing before any write is free.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-55 How the live indexer run is proven
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 7)
- Area: indexer
- Related: phase 7 spec
- Question: Real-run checks need Chroma, Ollama and the corpus, which CI lacks. Pytest that skips, or a script?
- Options: A. `scripts/check_index.py` run by developer and tester, never skipped (as D-045). B. Pytest that skips without services. C. Both.
- Claude recommends: A. `make test` stays offline and nothing is silently skipped.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-56 Wait timeouts and batch size as config
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 7)
- Area: indexer
- Related: phase 7 spec
- Question: The plan wants Chroma and Ollama waits (120 s, 60 s) and `EMBED_BATCH_SIZE`. Which become ConfigMap keys?
- Options: A. `EMBED_BATCH_SIZE` is already in architecture 4.4; the two waits are env defaults only, no new ConfigMap key. B. Add both to the ConfigMap (a change for Ahmad, C-2).
- Claude recommends: A. Fewer contract changes; defaults are the architecture's numbers.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-57 Retriever pass-through of `vector` and `where`
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 8)
- Area: api
- Related: phase 8 spec
- Question: The orchestrator (phase 10) embeds once for the cache and the retrieval. How does the retriever take the vector and scope?
- Options: A. `retrieve(question, k, *, vector=None, where=None)`; embeds itself when `vector` is None; stub ignores both. B. The retriever always embeds. C. Separate `retrieve_by_vector`.
- Claude recommends: A. One embed per request, and the protocol stays one method.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-58 What an embedding-pin or dimension conflict does to retrieval
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 8)
- Area: api
- Related: phase 8 spec, architecture 5.3, R-PIN-3
- Question: On a pin mismatch, log only, or refuse to query?
- Options: A. Log the exact 5.3 line once per `index_id` and raise `IndexUnavailable("embed_pin")` on retrieve. B. Log only, query anyway.
- Claude recommends: A. Querying with the wrong model returns plausible but wrong passages, the worst failure.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-59 Index-state refresh failure with a previous snapshot
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 8)
- Area: api
- Related: phase 8 spec, AD-20
- Question: When the periodic refresh cannot reach Chroma, drop the snapshot or keep the old one?
- Options: A. Keep serving the old snapshot, log a warning; raise only when none exists. B. Raise at once.
- Claude recommends: A. A one-second Chroma blip should not break requests; the query itself still fails honestly if Chroma is down.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-60 Where the retrieval-only dev tool lives
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 8)
- Area: eval
- Related: phase 8 spec
- Question: Recall without the LLM, the loop test and manual asks need a script. Where?
- Options: A. `eval/retrieval_only.py` (own lane, covered by `ruff check eval`, reuses `run_eval.summarise`). B. `scripts/` (needs a Makefile lint-list edit, a shared file).
- Claude recommends: A. No shared file touched.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-61 Passage carries version and status
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 9)
- Area: api
- Related: phase 9 spec, architecture 5.7.1, DEV-004
- Question: The prompt header needs `version` and `status` but `Passage` has neither. How?
- Options: A. Optional `doc_version` and `superseded` on `Passage`, filled by `ChromaRetriever`. B. Omit them from the header (breaks 5.7.1). C. A second Chroma lookup per request.
- Claude recommends: A. Backward compatible, internal only, no extra call.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-62 Extractive sentence selection
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 9)
- Area: api
- Related: phase 9 spec, architecture 5.15, AD-07
- Question: Architecture 5.15 leaves sentence scoring open. Which rule?
- Options: A. Distinct question-word overlap per sentence; best passage by its best sentence; cite that one passage. B. Embedding similarity (needs a model, breaks CI mode). C. The whole top passage (long, cites more than it used).
- Claude recommends: A. Deterministic, no model, cites only what it used.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-63 `ollama-*` provider before phase 10
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 9)
- Area: api
- Related: phase 9 spec
- Question: What does `get_provider('ollama-host')` do before the HTTP client exists?
- Options: A. Raise `NotImplementedError` from `get_provider` naming phase 10. B. Return the kit class whose `generate` raises on the first request.
- Claude recommends: A. Fails at startup with a clear message, not on a user request.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-64 Abstention text has no topic phrase
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 9)
- Area: api
- Related: phase 9 spec, architecture 5.10
- Question: 5.10 says "plus, when possible, the topic phrase". Add it?
- Options: A. Fixed text only. B. Echo a phrase extracted from the question (puts untrusted text into the answer).
- Claude recommends: A. Deterministic, nothing echoed from the question.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-65 Orchestrator return shape
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 10)
- Area: api
- Related: phase 10 spec, architecture 5.5.3, AD-15
- Question: The route must set `X-Outcome` and `X-Cache`, but `answer_question` returns `AskResponse`, which has no such fields (JSON contract frozen). How does the route learn them?
- Options: A. `answer_question` returns `AskResult(response, outcome, cache)`; the route sets headers. B. A request-scoped context variable. C. Extra private fields on `AskResponse`.
- Claude recommends: A. Explicit, testable, no change to the frozen contract.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-66 Two names for the request latency histogram
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 10)
- Area: api
- Related: architecture 4.14, AD-24, `routes/metrics.py`
- Question: The 4.14 table names `rahbar_request_duration_seconds` but says "existing kit metric names stay as they are in the code", and the kit names it `rahbar_request_seconds`. Which?
- Options: A. Keep only the kit name. B. Rename to the table name (a deviation). C. Expose both, same observation.
- Claude recommends: C. Satisfies both readings of an internal inconsistency at the cost of one extra histogram; logged in the spec, no behaviour change.
- Decision: C. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-67 Redis check in `/readyz` before the cache exists
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 10)
- Area: api
- Related: phase 10 plan, architecture 4.8, R-PRB-2
- Question: What does `/readyz` report for Redis until phase 11 builds the cache?
- Options: A. `redis: "skipped"`, never failing. B. Real PING now (a pod would be unready without a cache that is not used yet). C. Omit the key.
- Claude recommends: A. Honest about not checking, does not block bring-up; phase 11 replaces it with the real check.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-68 `X-Cache` value while no cache exists
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 10)
- Area: api
- Related: architecture 5.5.3, 5.5.4
- Question: `MISS` implies a lookup happened. What does the response say before phase 11?
- Options: A. `SKIP` (log `cache=skipped`). B. `MISS`.
- Claude recommends: A. No lookup is made; phase 11 produces `MISS` and `HIT`.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-69 Which passages a citation may name, and the provider name
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 10)
- Area: api
- Related: architecture 5.7.3, 5.8, 5.5.3, R-GEN-5
- Question: (a) Validate citations against all retrieved passages or only those shown to the model (at or above the floor)? (b) The response `provider` is the configured name: `ollama-host` or the class name `ollama`?
- Options: (a) A. shown only. B. all retrieved. (b) A. `settings.llm_provider`. B. class constant.
- Claude recommends: (a) A, a model cannot legitimately cite a block it never saw. (b) A, "the configured provider name" (5.5.3).
- Decision: (a) A, (b) A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-70 Retry policy details
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 10)
- Area: api
- Related: architecture 5.7.4, 5.12.4, AD-13, AD-21
- Question: Which provider failures are transient, and what happens when the semaphore wait expires?
- Options: A. Transient: timeout, connect, read and protocol errors. Not transient: HTTP status errors, a bad envelope, a semaphore wait timeout (fallback at once). Total attempts capped at 2. B. Retry HTTP 5xx too. C. Retry the busy case.
- Claude recommends: A. Matches "retry once only if transient (timeout, connection reset)"; retrying a busy host would double the wait.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-71 Where cache maintenance runs
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 11)
- Area: api
- Related: architecture 5.9.4, D-27
- Question: When does the pod create `idx:cache:{index_id}` and drop the older ones?
- Options: A. From `answer_question` and `/readyz`, on each snapshot, cheap no-op when the `index_id` is unchanged. B. Inside `IndexState.get`.
- Claude recommends: A. Keeps `IndexState` a Chroma-only reader and makes `/readyz` repair a missing index; the readiness probe runs every few seconds so the effect is the same as a refresh hook (5.9.4 item 3).
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-72 `X-Cache` when Redis is down
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 11)
- Area: api
- Related: architecture 5.5.2, 5.5.3, AD-15
- Question: What does the response header say when Redis fails?
- Options: A. `MISS` (architecture 5.5.2 step 4: treat as a miss, count a miss, log a warning). B. A new value `BYPASS`.
- Claude recommends: A. The architecture already names the behaviour and the UI knows three values; the warning log carries the cause.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-73 Cache threshold calibration moves from phase 12 to phase 11
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 11)
- Area: api
- Related: architecture 5.9.3, R-CAC-3
- Question: Who measures `CACHE_THRESHOLD`?
- Options: A. Phase 11, with real nomic embeddings and Redis Stack, as Zain instructed for this run. B. Phase 12 as the plan says.
- Claude recommends: A. The cache needs a defended number to ship; phase 12 keeps floor, chunking and baselines and only re-checks the value.
- Decision: A. Plan phase 12 item 3 is done in phase 11. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-74 Backoff after a Redis failure
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 11)
- Area: api
- Related: architecture 5.9.2, I-16
- Question: Should every request retry a dead Redis?
- Options: A. After a failure skip Redis for 5 s (one client timeout of 1 s per 5 s, not per request). B. Retry every request.
- Claude recommends: A. Keeps the p95 of a degraded system close to the no-cache latency.
- Decision: A. `backoff_seconds=5.0`. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-75 Store gate re-checks citations
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 11)
- Area: api
- Related: architecture 5.9.2, I-9, I-10
- Question: Does the cache trust `validate` or check citations again before storing?
- Options: A. Check again (every citation names a retrieved `source` and `section`). B. Trust `validate`.
- Claude recommends: A. Cheap, and a cached bad answer is served many times.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-76 How the three chunking configurations are scored
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 12)
- Area: eval
- Related: phase 12 spec, architecture 5.13.5, R-IDX-7
- Question: Each of three configurations needs recall@3 and @5. A full `run_eval.py` run with the real model takes 10 to 30 minutes (18 questions at 30 to 90 s).
- Options: A. Score each configuration with `eval/retrieval_only.py recall` (same `summarise`, same retriever, no model call), then do the full real-model run once on the chosen configuration. B. Full `run_eval.py` run with the model for each of the three.
- Claude recommends: A. Recall is computed from the `retrieved` list that exists before any model call, so the numbers are identical; B adds about 1 to 1.5 hours of CPU for no extra information about the choice. Zain's brief named B; this differs in method, not in result, and is reported as such.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-77 How the chunking configuration is chosen
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 12)
- Area: indexer
- Related: phase 12 spec, R-IDX-7
- Question: What rule picks the shipped (size, overlap)?
- Options: A. Highest recall@5, then recall@3, then fewer chunks, then lower amplification. B. Highest recall@3. C. Fewest chunks within one point of the best recall@5.
- Claude recommends: A. recall@5 is the gated metric (5.13.3); the tie-breaks are cost.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-78 How the relevance floor is chosen
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 12)
- Area: api
- Related: phase 12 spec, architecture 5.6.3, AD-12
- Question: Where between the must-abstain maximum and the lowest answerable score does the floor sit?
- Options: A. The midpoint of the gap, rounded to 0.01, when the ranges do not overlap; if they overlap, keep abstention at 100% and list the answerable questions lost. B. Just above the abstain maximum (0.01 margin). C. Just below the answerable minimum.
- Claude recommends: A. With 18 questions, a margin on both sides is the least over-fitted choice.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-79 Prompt wording when answers are terse
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 12)
- Area: api
- Related: phase 12 spec, phase 10 results ("No", "60%")
- Question: The 3B model answers with one or two words. Change the prompt?
- Options: A. Only if the real run shows it hurts a metric or the demo; then change the wording and re-run the golden set to prove recall, citation validity and abstention did not get worse. B. Never. C. Always.
- Claude recommends: A. The prompt is also part of the measured system; every change needs a re-run.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-80 The cache threshold is not re-measured
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 12)
- Area: api
- Related: D-73, architecture 5.9.3, R-CAC-3
- Question: The plan lists the cache threshold in phase 12, but D-73 moved it to phase 11 (0.96, three thresholds, the false hit recorded).
- Options: A. Keep 0.96, record only real paraphrase pairs for the demo. B. Re-run the three thresholds against the final chunking.
- Claude recommends: A. The cache works on question embeddings, which chunking does not change; Zain's brief says not to redo it.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-81 Chunking result is a three-way tie: which pair ships
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 12)
- Area: indexer
- Related: D-77, phase 12 spec, `eval/tuning/`
- Question: 200/25, 400/50 and 600/100 give identical recall@3 and @5 (0.875 both) and identical score ranges. D-77's literal tie-break (fewer chunks) would pick 600/100 (952 chunks against 981, 3% fewer).
- Options: A. Keep 400/50 (the architecture default, 981 chunks, the index every earlier measurement used). B. 600/100 by D-77's tie-break. C. 200/25 (smallest worst-case chunk, 1103 chunks, amplification 1.06).
- Claude recommends: A. Nothing measured favours a change: 3% fewer chunks buys nothing, while a 600-word chunk lengthens the worst-case prompt by half on a CPU model whose latency is prompt-bound; 200/25 stores 12% more chunks and more overlap for no recall. When the numbers tie, the default stays. D-77 is amended: on a recall tie, keep the architecture default unless another pair is better by a measured quantity beyond the noise (more than 5% fewer chunks or better recall).
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-82 Markdown headings in the extractor, and the CI floor
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 12)
- Area: indexer, eval
- Related: phase 12 spec, `eval/fixtures`, architecture 5.4.2
- Question: The fixture run had recall 0: the Markdown extractor kept the `##` marks, so the chunker never saw `## 1. Attendance` as a heading and every fixture section label differed from the golden label. Also the 0.70 floor suits `nomic-embed-text`, not the lexical hashing embedder (fixture scores 0.28 to 0.43).
- Options: A. Drop the leading `#` marks of Markdown headings in the extractor, keep `golden.fixture.yaml` as it is; set the CI overlay `RELEVANCE_FLOOR` to 0.20 (above the fixture abstain score 0.00, below the lowest answerable top 0.316). B. Rewrite the fixture golden labels to what the chunker produced. C. Floor 0.70 in CI (every fixture question abstains).
- Claude recommends: A. The golden file stays as written; the bug is the extractor's. A real Markdown source with `##` headings is also affected.
- Decision: A. Decided by: Claude, pre-approved by Zain. H-8 tells Ahmad to set `RELEVANCE_FLOOR=0.20` in the `ci` overlay.
- Decided on: 2026-11-05

### D-83 How each failure experiment is applied without touching shipped code
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 13)
- Area: eval, docs
- Related: D-015, architecture 5.14, plan phase 13 ("no experiment flag changes default behaviour")
- Question: How is each break applied so that no default changes and nothing is merged?
- Options: A. No flag in the repo at all: A is a script in the job's tmp directory that patches `pipeline.extract._ocr_page` in memory and runs the real pipeline on a corpus copy into a separate collection `rahbar_exp_a`; C is an environment variable on the API process; E is an uncommitted one-line edit of `scope.py` reverted with `git checkout` straight after; F is an environment variable. B. A default-off `EXPERIMENT_NO_OCR` flag in `extract.py`. C. Temporary branch per experiment.
- Claude recommends: A. Nothing to review, nothing to leave behind, `git diff` is the proof. B adds a code path that can be switched on by mistake in the cluster.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-84 Experiment A uses a reduced corpus and a separate collection
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 13)
- Area: indexer, eval
- Related: D-83, results register ("Indexer wall time" 9 min 39 s)
- Question: Re-indexing the whole corpus without OCR takes about 7 minutes of embedding and would overwrite the live index. What do we index?
- Options: A. The policy PDF plus the fee page (no OCR) copied to a temporary directory, into collection `rahbar_exp_a`, with the same chunk settings; the live collection `rahbar` is untouched. B. The full corpus into the live collection, then rebuild it afterwards (about 20 minutes, and a window with a broken index). 
- Claude recommends: A. The symptom (zero chunks for the source, indexer log) does not depend on the other documents; the baseline index stays intact so the restore check is trivial.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-85 The semantic cache must be flushed before experiments C, E and F
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 13)
- Area: api
- Related: architecture 5.9, D-83
- Question: The cache key is the question embedding plus the scope tag, not `TEMPERATURE`, `TOP_K` or the retrieval code. A cached answer would hide the break. 
- Options: A. `FLUSHALL` on the dev Redis container before each run and ask questions not asked since. B. Use only never-asked questions.
- Claude recommends: A (dev container only, data volume is a local cache). The finding itself goes in FAILURE-ANALYSIS.md: a cache that outlives a bad setting can keep serving the old answers (or the bad ones) until the TTL or a re-index.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-86 ADR 0001 is written by this session, not Ahmad
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 14)
- Area: docs
- Related: WORKPLAN (ADR 0001 is Ahmad's), R-JOB-4, checker "ADR filename mentions the indexer Job"
- Question: The plan gives ADR 0001 to Ahmad, but the checker reads it first and he has not written it.
- Options: A. Write `docs/adr/0001-indexer-as-job.md` now from the architecture and the real code, header "authored by Zain's session, Ahmad to review and rewrite in his words". B. Leave it missing and report it. C. Empty placeholder.
- Claude recommends: A. It clears a checker failure and the R-DED-3 evidence line. It cites only code and architecture; Ahmad adds the manifest lines.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-87 The hosted provider stub is removed, not built
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 14)
- Area: api
- Related: IMPLEMENTATION_PLAN 0.5 (hosted is a non-goal), architecture 5.12, R-LLM-1 ("support at least one mode fully"), R-LLM-4
- Question: `api/app/providers/llm/hosted.py` raises `NotImplementedError`, which the checker counts as a stub.
- Options: A. Delete the file; `get_provider` raises a clear `ValueError` for `hosted`; ADR 0004 says hosted is not built and what it would cost. B. Write a minimal OpenAI-compatible provider (about 50 lines) with no live test (no key, no card). C. Keep the stub.
- Claude recommends: A. The assignment needs one mode fully (`ollama-host` is that); the plan forbids building hosted; an untested provider that sends corpus text off-site is a risk, not a feature.
- Decision: A. Decided by: Claude, pre-approved by Zain. Not an assignment conflict: R-LLM-1 asks for one mode; R-LLM-6 lists `hosted.py` in the kit layout only.
- Decided on: 2026-11-05

### D-88 Engineering notes: what this lane answers
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 14)
- Area: docs
- Related: WORKPLAN (Zain: Q5; Ahmad: Q1 to Q4, Q6), plan phase 14 (Q5, Q7), R-ENG-1..7
- Question: Which of the seven questions are written here?
- Options: A. Q5, Q6 (the guardrail is our code) and Q7 in full; Q1 to Q4 get the RAG-lane facts plus a marked "Ahmad" section. B. Only Q5 and Q7. C. All seven with guessed Kubernetes content.
- Claude recommends: A. C would invent Ahmad's manifests and fail the "own files" rule.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05

### D-89 Starter placeholder in prose: reword in lane-owned files, list the rest
- Status: DECIDED
- Raised: 2026-11-05 by Claude (phase 14)
- Area: docs
- Related: R-SUB-5, `scripts/check_submission.py` (counts the literal string in any text file except `STARTER.md`, the checker, `*.example.*` and `corpus/raw/`)
- Question: Prose that merely names the placeholder (plan, specs, requirements, rubric, workplan, workflow) trips the checker.
- Options: A. Reword to "the starter placeholder" in files this lane owns (plan, specs, PIPELINE, AI-USAGE); list `requirements.md`, `rubric_checklist.md`, `WORKPLAN.md`, `WORKFLOW.md` for Zain. B. Edit everything. C. Change the checker (not ours).
- Claude recommends: A.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-05
- 2026-11-05: phase K1 decisions. D-090 to D-092 added, all DECIDED (Claude, pre-approved by Zain).

### D-093 Job and CronJob share one pod spec via kustomize `replacements`
- Status: DECIDED
- Raised: 2026-11-06 by Claude (phase K2)
- Area: k8s
- Related: R-K8S-CRON ("same image and arguments"), architecture 4.2
- Question: How do the Job and the CronJob avoid drifting?
- Options: A. `replacements` copies the Job `spec` into the CronJob `jobTemplate.spec`. B. YAML anchors (do not cross documents). C. Duplicate and test equality.
- Claude recommends: A. One source, drift impossible.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-06

### D-094 `corpus-loader` helper pod uses pinned `busybox:1.37.0`, manifest in `k8s/tools/`
- Status: DECIDED
- Raised: 2026-11-06 by Claude (phase K2)
- Area: k8s
- Related: AD-08, assumption A-4
- Question: Which image has `tar` for `kubectl cp`, and where does the manifest live (not in the kustomization)?
- Options: A. busybox pinned, `k8s/tools/corpus-loader.yaml`. B. The indexer image (592 MB, has tar). C. alpine.
- Claude recommends: A. Smallest, pinned, has tar and a shell.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-06

### D-095 PodDisruptionBudget for the api: `minAvailable: 2`
- Status: DECIDED
- Raised: 2026-11-06 by Claude (phase K3)
- Area: k8s
- Related: architecture 4.9, R-RES-4
- Question: Ship a PDB, and with which value?
- Options: A. `minAvailable: 2` (one voluntary disruption at a time with 3 replicas). B. `maxUnavailable: 1`. C. No PDB.
- Claude recommends: A. Matches the plan; does not block rollouts (they are not evictions).
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-06

### D-096 `ci` overlay builds the fixtures ConfigMap with `--load-restrictor LoadRestrictionsNone`
- Status: DECIDED
- Raised: 2026-11-06 by Claude (phase K5)
- Area: k8s
- Related: architecture 4.5, 4.11, AD-18; `indexer/pipeline/run.py` `discover()`
- Question: How does the `ci` overlay get `eval/fixtures/*.md` into a ConfigMap, and does the Job need `_index.json`?
- Options: A. `configMapGenerator` pointing at `../../../eval/fixtures`, built with the load restrictor off. B. Copy the fixtures into `k8s/overlays/ci/` (two copies to drift). C. Symlinks (kustomize resolves and rejects them).
- Claude recommends: A. One copy of the fixtures. The cost is that this overlay needs `kustomize build --load-restrictor LoadRestrictionsNone ... | kubectl apply -f -` (not `kubectl apply -k`); `make manifests` and the workflows do that. `_index.json` is not needed: `discover()` falls back to the front matter and `verify` is skipped when it is absent, so no file is generated.
- Decision: A. Decided by: Claude, pre-approved by Zain.
- Decided on: 2026-11-06
