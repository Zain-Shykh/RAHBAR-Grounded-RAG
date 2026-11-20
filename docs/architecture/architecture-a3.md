# RAHBAR architecture, Assignment 03 (RAGOps layer)

Companion to [`architecture.md`](architecture.md) (version 1.0, Assignment 02). That file stays the source of truth for everything RAHBAR already is: topology, indexer, query pipeline, cache, invariants I-1 to I-17, decisions AD-01 to AD-28. **This file adds the RAGOps layer**: data management (verify, incremental update, archive), offline testing, release gate, traces and metrics, drift checks, and the Kubernetes objects that carry them. Requirements are in [`../requirements-a3.md`](../requirements-a3.md); the build order is in [`../IMPLEMENTATION_PLAN_A3.md`](../IMPLEMENTATION_PLAN_A3.md).

Rules of reading: where this file is silent, `architecture.md` applies. Where the two conflict, the assignment wins, then this file for RAGOps topics, then `architecture.md`. Every real difference from `architecture.md` is logged in [`deviations.md`](deviations.md) (entries DEV-015 onward) when the code is written, and listed in section 11 below as "planned deviations" so nobody is surprised.

Status: **design, not yet built.** Decisions tagged `◇` are the architect's defaults, listed in [`../OPEN_DECISIONS.md`](../OPEN_DECISIONS.md) (D-107 to D-125) and open to veto.

---

## 1. What we add, in one picture

```
            documents (inbox: PVC corpus-data, read-only to the Job; Batch A, Batch B, unseen batch)
                │
                ▼
  ┌──────────────────────── ingestion Job (indexer image, the ONLY writer to Chroma, I-1) ────────────────────────┐
  │ 0 integrity (sha256)  1 extract  2 VERIFY (new)  3 plan (new/changed/unchanged/deleted)  4 clean+chunk        │
  │ 5 embed ONLY the delta (new)  6 copy-forward unchanged chunks  7 stage-and-swap (AD-02)  8 registry + report   │
  └───────┬───────────────────────────────────────────────┬─────────────────────────────────────────────────────┘
          │ lake PVC (RW, Job only): registry, quarantine, archive, reports   │ Chroma collection (live, or candidate)
          ▼                                                                   ▼
  verification report per run                         API Deployment(s) ── read-only ──► Ollama (host)
                                                          │  one TRACE record per query (stdout + traces PVC)
                                                          ▼
   eval Job (suite + gate, ConfigMap thresholds) ◄── trace report scripts ── coverage script
          │ result files on eval-results PVC, committed copies under eval/results/ and traces/
          ▼
   release: candidate Deployment (own collection) ── gate pass ──► rolling update of live ── rollout undo
```

Everything runs on minikube in namespace `rahbar` (I-14). Nothing new is a stateful service: the additions are code in the existing images, one new image (`rahbar-eval`), three PVCs, Jobs, ConfigMaps and one extra Deployment.

## 2. Figure 3 map (initial; final version goes in the report, R3-G-1)

| Figure 3 stage | What RAHBAR does (target) | Where | Missing today (start of A3) |
| --- | --- | --- | --- |
| Ingest | Extract text page by page, OCR where needed, from the inbox PVC | `indexer/pipeline/extract.py` | batch delivery helper for unseen documents |
| Verify | Integrity (sha256) plus four checks per document with reasons, quarantine, per-run report | `indexer/pipeline/verification/` (new), `verify.py` (existing integrity) | everything beyond sha256 |
| Update data lake | Registry, quarantine and archive on the lake PVC; supersede, archive, restore | `indexer/pipeline/lake.py`, `registry.py` (new) | no archive, no registry, no restore |
| Update retrieval sources | Embed only the delta, copy unchanged chunks, swap | `indexer/pipeline/incremental.py` (new), `store.py` | A02 always re-embeds everything |
| Offline testing | Module, component, end-to-end levels, noise, stochasticity, one command | `eval/suite/` (new), `eval/golden.jsonl` | MRR, nDCG, faithfulness, embedding level, jsonl golden set |
| Live testing | Trace for every query, metrics, guardrail log, report scripts | `api/app/services/trace.py`, `guardrails.py`, `scripts/trace_*.py` (new) | no per-query trace |
| Check coverage | Live queries versus golden set, threshold, non-zero exit | `eval/suite/coverage.py` (new), `eval/live_queries.jsonl` | nothing |

## 3. Hard invariants added (continue the numbering of `architecture.md` 0.2)

| # | Invariant | Source |
| --- | --- | --- |
| I-18 | The ingestion Job is still the only writer to Chroma. Verification, quarantine, archive and registry are Job code and Job-writable volumes only. The API, eval Job and report Jobs mount the lake read-only or not at all. | A3 F2-1, I-1 |
| I-19 | A document that fails verification is never indexed. A failed *changed* document leaves its previous good version in place. | A3 A1-3 |
| I-20 | A run that changes nothing embeds **0 chunks**, does not swap, and does not change `index_id` (the cache survives). | A3 A2-1 |
| I-21 | After any run, the live collection holds exactly the chunks the registry lists as active or superseded: no orphans, no missing chunks. The Job asserts this before it exits 0. | A3 A2-3 |
| I-22 | Every query produces exactly one trace line. A trace write failure never fails the request (it is counted). | A3 D1-1, I-16 |
| I-23 | A trace never holds a secret. The prompt is stored; headers, environment variables and the Ollama URL are not. | I-13 |
| I-24 | The release gate decides from result files only. It reads thresholds from one config file (a ConfigMap on the cluster) and has no hard-coded limit. | A3 C2-1, F2-3 |
| I-25 | Every number in the report comes from a committed result file under `eval/results/`, `traces/` or `docs/evidence/`. | A3 LOG-4 |
| I-26 | A candidate never shares a collection with the live Deployment. Release changes which collection the live Deployment reads; it never writes into the live collection. | A3 F3-1 |

## 4. Decision register (continues AD-28)

| ID | Decision | Tag | Section |
| --- | --- | :---: | --- |
| AD-29 | A3 extends RAHBAR. Assignment 02 behaviour, `eval/golden.yaml`, `eval/baseline.json` and the CI gate are frozen and keep working. New code lives in new modules; edits to existing modules are additive. | ◇ | 1 |
| AD-30 | The **inbox** is the existing PVC `corpus-data` (read-only to the Job). A new PVC **`lake-data`** (1 Gi, read-write, Job only) holds registry, quarantine, archive and reports. | ◇ | 5.1 |
| AD-31 | A document id is its file name (`source`). A `family` groups versions of one document; it comes from the manifest `_index.json` (default: `source`). | ◇ | 5.2 |
| AD-32 | **Incremental update = embed only the delta, copy the rest, stage-and-swap.** Unchanged chunks are read back from the live collection with their stored vectors and written to the staging collection; new and changed documents are chunked and embedded; deleted documents are simply not copied. The swap of AD-02 is kept. No in-place mutation of the live collection, so no deviation from AD-02 and no half-updated state. | ◇ | 5.5 |
| AD-33 | Verification runs after extraction and before chunking, one verdict per document and check, written to a JSON report per run on the lake PVC. A failed document is copied to `quarantine/<run_id>/` with its reason and is not indexed. A failed integrity (sha256) check is a document-level failure in A3 and no longer aborts the run. | ◇ | 5.3 |
| AD-34 | Near-duplicate detection compares document signatures (mean of three window embeddings) by cosine, with a threshold calibrated on the real corpus and Batch B, never guessed. Same-family pairs with different versions are not near-duplicates (that is recency). | ◇ | 5.3 |
| AD-35 | The golden set for A3 is `eval/golden.jsonl`, a superset of `eval/golden.yaml` (the 18 existing questions are carried over and labelled). The YAML file stays for the A02 CI gate. | ◇ | 6.1 |
| AD-36 | Faithfulness is reported twice: an LLM judge (`llama3.2:3b` through Ollama, temperature 0, fixed seed), and a deterministic support-overlap score. Judge agreement with at least 12 hand labels is reported. The metric we trust least is named in the report. | ◇ | 6.4 |
| AD-37 | The noise test adds seeded typos to the queries. Added irrelevant documents are not used for B; data drift is shown by ingesting Batch B (E3). | ◇ | 6.5 |
| AD-38 | Reproducibility: `LLM_SEED` is a new ConfigMap key passed to Ollama as `options.seed`. Eval requests send `X-Cache-Bypass: 1` so cached answers cannot hide variation. | ◇ | 6.6 |
| AD-39 | The trace record is one JSON line per query: stdout (logger `rahbar.trace`) and one file per pod on PVC `traces-data`. `trace_id` equals `request_id`. The full prompt messages are stored with their SHA-256. | ◇ | 7.1 |
| AD-40 | One simple retrieval rail, `injection_scan`: instruction-like text in a retrieved passage is flagged, the passage is dropped from the evidence, the action is written into the trace, and `rahbar_injection_flags_total` counts it. The A02 defences (delimiter stripping, system prompt, citation validation) stay. | ◇ | 7.4 |
| AD-41 | The change experiment is a **chunk size and overlap** change (the candidate is a full re-index into its own collection). The two candidate configurations (one that fails the gate, one that passes) are chosen by measurement in R7 and recorded there. | ◇ | 8 |
| AD-42 | The gate is `eval/suite/gate.py` reading `eval/gate.yaml`. On the cluster the same file is mounted from ConfigMap `rahbar-gate`, generated from it by Kustomize so the two cannot drift. | ◇ | 8.2 |
| AD-43 | The suite runs in the new image `rahbar-eval` (`eval/Dockerfile`), as Job `eval` from `k8s/eval-job.yaml`. The CD matrix builds and pushes it like the other images. | ◇ | 9.2 |
| AD-44 | The candidate is Deployment and Service `api-candidate` reading collection `rahbar_cand`. Release is a change to the **live Deployment's own `env`** (`CHROMA_COLLECTION` and friends), which makes a new ReplicaSet and a rolling update. `kubectl rollout undo` therefore restores the previous collection. | ◇ | 9.3 |
| AD-45 | Coverage is the share of live queries whose best cosine similarity to a golden question is at least a threshold calibrated from the module-level paraphrase and unrelated means. The script exits non-zero below the coverage target. | ◇ | 10 |

## 5. Data management

### 5.1 Volumes and layout

```
corpus-data  (PVC, existing, 1 Gi, mounted READ-ONLY in the Job)   the INBOX
  _index.json                manifest: one entry per file (section 5.2)
  <files>                    PDF, HTML, Markdown, text

lake-data    (PVC, new, 1 Gi, READ-WRITE, mounted in the Job only)   the LAKE
  registry/<collection>.json          what is indexed, per collection (section 5.4)
  quarantine/<run_id>/<file>          copy of every failed document
  quarantine/<run_id>/<file>.reason.json
  archive/<source>/<sha12>/<file>     copy of every superseded or removed document version
  reports/<run_id>/verification.json  the per-run report (R3-A1-4)
  reports/<run_id>/summary.json       counts: new, changed, unchanged, deleted, embedded, copied
```

The inbox stays read-only so that nothing the Job does can damage the source documents. The lake is the Job's own state. Both survive pod restarts (R3-F1-2). `make lake-ls` and `make lake-pull` (copy reports out through a throw-away pod) are the human interface.

### 5.2 Document identity and the manifest

`_index.json` (written by `corpus/fetch.py` for Assignment 02) gains optional fields; every old entry stays valid.

| Field | Meaning | Default when absent |
| --- | --- | --- |
| `file` | file name inside the inbox; also the document id (`source`) | required |
| `sha256`, `bytes` | integrity | required (Assignment 02) |
| `doc_version`, `superseded` | as in A02 | `unknown`, `false` |
| `title` | human title | completeness check **fails** |
| `date` | ISO date of the document | completeness passes if `doc_version` is present |
| `family` | id shared by versions of one document, for example `academic-rules` | the file name |
| `pages` | declared page count (optional cross-check) | none |

Required for completeness: source (file name), title, **date or doc_version**, page count (measured during extraction, must be above zero). The real corpus manifest is extended with `title` (from `name`) and `family` once, by `scripts/enrich_manifest.py`; the original `_index.json` is kept as `_index.a02.json`.

### 5.3 The verification stage (R3-A1-*)

Runs for every **new or changed** document, after extraction (the checks need text) and before chunking. Unchanged documents are not re-extracted, so a clean re-run costs almost nothing; their earlier verdicts are in the registry.

| Check | Fails when | Reason strings (examples) |
| --- | --- | --- |
| quality | integrity sha256 does not match the manifest; extraction raised or returned zero pages; fewer than `VERIFY_MIN_CHARS` (default 200) non-space characters in total; garbled (alphabetic ratio below 0.60, or replacement characters above 1 percent) | `integrity: sha256 mismatch`, `empty text (37 chars)`, `garbled: alpha ratio 0.31` |
| completeness | a required field of 5.2 is missing; page count is zero; the text looks truncated: PDF without `%%EOF` in its last 1 KB, HTML without `</html>`, text or Markdown whose last sentence has no terminal punctuation; extracted pages fewer than the manifest's `pages` | `missing title`, `missing date or doc_version`, `truncated: no %%EOF`, `pages 3 < declared 12` |
| recency | a document of the same `family` with a newer `date` or `doc_version` is in the batch or the registry | `superseded by <source> (2026-06 > 2023-08)` |
| uniqueness | exact: file sha256 or normalised-text sha256 equals another document's; near: signature cosine at or above the calibrated threshold with a document of a different family, or the same family and the same version | `exact duplicate of <source>`, `near duplicate of <source> (cos 0.982)` |

Verdict handling:

| Outcome | Action | Indexed? |
| --- | --- | --- |
| All four pass | `index` (new) or `replace` (changed) | yes |
| quality, completeness or uniqueness fails | `quarantine`: copy to `quarantine/<run_id>/`, write the reason file, record the document and its sha in the registry's `quarantined` map so the next run does not retry or re-embed it | no (I-19) |
| recency fails for an older version | `supersede`: chunks stay in the index with `superseded=true` (A02 behaviour: old versions can still be asked about explicitly), the file is copied to `archive/` | yes, flagged |
| a *changed* document fails verification | `quarantine` the new file; the previous version stays indexed untouched | previous only |

Uniqueness decides which of two duplicates is kept by a fixed rule: the document already in the registry wins; inside one batch the alphabetically first file name wins, and the other is quarantined with a reference to it.

**Signature.** For each document, three windows of up to 300 words (head, middle, tail) are embedded with the `search_document: ` prefix and the vectors are averaged and normalised. The signature is stored in the registry (768 floats). The threshold is chosen in R2 from the distribution of pairwise similarities across the real corpus and Batch B (D-113); the plan forbids a guessed constant.

**Report (R3-A1-4).** `reports/<run_id>/verification.json`:

```json
{"run_id": "20261120T101500Z-a1b2c3", "corpus_dir": "/corpus", "embed_model": "nomic-embed-text",
 "documents": [
  {"source": "batch-b-dup-1.md", "action": "quarantine",
   "checks": {"quality": {"pass": true, "reason": "ok"},
              "completeness": {"pass": true, "reason": "ok"},
              "recency": {"pass": true, "reason": "ok"},
              "uniqueness": {"pass": false, "reason": "exact duplicate of batch-b-orig-1.md"}}}],
 "totals": {"checked": 12, "passed": 7, "quarantined": 4, "superseded": 1}}
```

The same table is printed to stdout as JSON lines and as a text table (`python -m pipeline.report <run_id>`) for the screenshot (R3-S-A1).

### 5.4 The registry

`registry/<collection>.json`, written atomically (write to `.tmp`, `fsync`, rename) and **only after the swap succeeded**.

```json
{"schema": 1, "collection": "rahbar", "embed_model": "nomic-embed-text", "dimension": 768,
 "chunk_size": 400, "chunk_overlap": 50, "updated_at": "...", "index_id": "...",
 "docs": {"<source>": {"sha256": "...", "text_sha256": "...", "signature": [..768..],
          "doc_version": "2026-06", "family": "academic-rules", "title": "...", "date": "...",
          "pages": 53, "status": "active|superseded", "pinned": false,
          "chunks": 112, "first_run": "...", "last_run": "...", "archive": null}},
 "quarantined": {"<source>": {"sha256": "...", "run_id": "...", "reasons": ["..."]}}}
```

If the registry is missing or does not match the live collection, the Job treats the run as a full build (it embeds everything) and says so in the summary. A registry whose `embed_model`, `dimension`, `chunk_size` or `chunk_overlap` differs from the current settings **refuses incremental mode** with a message that names the difference and tells the operator to run with `--full` (this is how the embedding pin and chunk settings stay consistent, I-3).

### 5.5 Incremental update: embed the delta, copy the rest (AD-32)

```
1  read inbox manifest; verify integrity per document (failure = document-level quality fail)
2  classify each inbox file against the registry by sha256:
     new | changed | unchanged | quarantined-before (same sha) ; registry docs missing from the inbox = deleted
3  extract + verify + decide for new and changed documents only (section 5.3)
4  nothing to add, replace, delete, supersede or restore?  ->  log "no changes", embed 0, DO NOT swap, exit 0   (I-20)
5  clean + chunk + embed the new and replaced documents only        (chunks_embedded = N)
6  stage: create rahbar_next with the same metadata as the live collection (new index_id)
   copy forward every chunk of every unchanged or flipped document: documents, metadatas, stored embeddings   (chunks_copied = M)
   flipped = metadata-only change (superseded true/false) applied while copying; no re-embedding
   add the new chunks; omit the chunks of changed (old version) and deleted documents
7  assert count(rahbar_next) == sum of registry chunk counts for the planned state   (I-21)
8  swap (delete live, rename staging), as AD-02; then write the registry; then copy archive files and the report
```

Why copy forward instead of mutating the live collection: the live collection stays valid until the instant of the swap, the whole update is all-or-nothing (AD-02), the API's re-resolution logic (AD-20) already handles the swap, and the exact "embedded 0 chunks on unchanged corpus" and "no orphans" claims are true by construction. The cost is reading about 1,000 stored vectors, which is seconds.

**Operations:**

| Operation | How | Proof (R3-A2-*) |
| --- | --- | --- |
| Unchanged re-run | step 4 | summary `chunks_embedded: 0`, `index_swapped: false`, same `index_id` |
| Changed document | classify as `changed`, replace only that source's chunks | `chunks_embedded` equals the new chunk count of that document; every other source's chunk ids are identical before and after |
| Deleted document | missing from inbox, registry entry removed, file copied to `archive/` first (the archive is kept) | `count where source=X` is `0` before and after the next run; total equals registry sum |
| Superseded version | recency fails for the older version | its chunks have `superseded=true`; default questions exclude them; it is in `archive/` |
| Restore (rollback) | `python -m pipeline.restore --source <older> [--supersede <newer>]` sets `pinned: true` on the older document and flips both documents' flags by the same copy-forward swap | the older document is retrievable again by default; trace shows the flag |
| Full rebuild | `--full` or `INDEX_MODE=full`: everything is re-extracted and re-embedded (the A02 behaviour) | required after a model or chunk-size change; also the way a candidate collection is built |

CLI: `python -m pipeline.run` (default `--incremental`), `--full`, `--dry-run` (print the plan and the verification report without writing), `python -m pipeline.restore ...`, `python -m pipeline.report <run_id>`.

**Deleted means archived, not erased.** The report answer to R3-G-4(c) is: we archive, never destroy; deleting an archived version would break rollback (R3-A2-4) and any answer that cites it.

### 5.6 Batch B (R3-AB-1)

`corpus/batch_b/` is committed (the files are synthetic and small; `corpus/raw/` stays gitignored). A deterministic generator `scripts/make_batch_b.py` writes the files from templates and records ground truth in `corpus/batch_b/PLANTED.json`, so the verification report can be scored against what we planted.

| # | Planted problem | Count | Expected check |
| --- | --- | --- | --- |
| 1 | Exact duplicate (same bytes, different name) | 2 | uniqueness (exact) |
| 2 | Near-duplicate (a few edited words) | 1 | uniqueness (near) |
| 3 | Truncated file | 1 | completeness (truncated) |
| 4 | Corrupt file (bytes do not match the manifest, or unreadable) | 1 | quality |
| 5 | Missing metadata (no title, no date or version) | 1 | completeness |
| 6 | Newer version of an existing document | 1 | recency (the **old** one is superseded) |
| 7 | Document containing an injected instruction | 1 | passes verification (we do not catch it here); caught by the retrieval rail (7.4) |
| 8 | Clean control documents that must pass | at least 2 | none |

At least 10 files in total. Some Batch B documents carry facts that exist nowhere in Assignment 02 (for example an invented but plausible policy clause), so that "hard" questions and the data-drift test (E3) have something new to find. Problem 7 is deliberately not a verification problem: it is the honest "which problem did you not catch" answer for R3-G-4(a), and it is what D4 exercises.

## 6. Offline testing (Part B)

### 6.1 Code layout and the golden set

```
eval/
  golden.jsonl               25+ questions, labelled (AD-35)           [new]
  golden.yaml                A02 golden set, frozen                     [existing]
  embedding_pairs.jsonl      >=15 paraphrase + >=15 unrelated pairs     [new]
  live_queries.jsonl         >=40 live-style queries (Part E)           [new]
  gate.yaml                  release-gate thresholds                    [new]
  suite/                                                                [new package]
    run_suite.py             the one command (R3-B-9)
    golden.py                load and validate golden.jsonl
    module_level.py          embedding level
    component_level.py       retrieval level and noise
    e2e_level.py             answer level
    judge.py                 LLM judge and deterministic support score
    stochasticity.py         two-run comparison
    compare.py               baseline versus candidate, all three levels
    gate.py                  apply gate.yaml, exit 0 or 1
    coverage.py              Part E
    report_md.py             summary tables (markdown)
  results/                   timestamped result files (committed)       [new]
  Dockerfile                 image rahbar-eval                          [new]
```

`golden.jsonl`, one JSON object per line:

```json
{"id": "g01", "question": "...", "kind": "answerable|unanswerable", "hard": false,
 "origin": "human|synthetic", "reviewed": true,
 "relevant": [{"source": "academic-rules-handbook-jun-2026.pdf", "section": "4.3", "page": 19}],
 "expect": "5 courses", "batch": "A|B", "tags": ["version","exact","injection","paraphrase","multi-chunk"],
 "must_abstain": false}
```

Minimums are fixed by the assignment (R3-B-1, R3-B-2) and checked by `golden.py --check`, which exits non-zero when any count is short. The 18 Assignment 02 questions are carried over (origin `human`); new questions cover Batch B and the multi-chunk and paraphrase cases.

### 6.2 Module level: embedding (R3-B-3)

`module_level.py` calls the embedder directly (no API). Output keys: `paraphrase_mean`, `unrelated_mean`, `gap`, `ms_per_chunk` (median and p95 over 100 real chunk texts), `determinism_max_abs_diff` (embed the same texts twice, largest absolute component difference), and the pair-level table. `paraphrase_mean` and `unrelated_mean` also calibrate the coverage threshold (section 10).

### 6.3 Component level: retrieval (R3-B-4, R3-B-5)

Computed from the `retrieved` list in the API response (top 5, in rank order), with A02's matching rule (`source` equal, `section` by normalised prefix equality, AD-22). For each answerable question with relevant set R:

- recall@k = (relevant pairs matched in the top k) / |R|, for k = 3 and 5.
- MRR = 1 / rank of the first matching passage in the top 5, or 0.
- nDCG@5 with binary gain: position i gains 1 if it matches a relevant pair not matched earlier; DCG = sum of gain / log2(i + 1); IDCG is the same with min(|R|, 5) gains at the top.

Means are over answerable questions, and also per `kind`/`tags` group. **Noise test:** every query is perturbed with seeded typos (about 1 character edit per 8 words: swap, drop, duplicate, replace; seed from `eval/gate.yaml`), the same four metrics are recomputed, and the report shows each metric's absolute and relative change.

### 6.4 End-to-end level (R3-B-6, R3-B-7)

| Metric | Definition |
| --- | --- |
| Faithfulness (judge) | share of answered responses that the judge marks `supported`, given only the passages the response cites. Judge: `llama3.2:3b`, temperature 0, `seed` fixed, JSON schema output. |
| Faithfulness (overlap) | deterministic: share of an answer's content words (lower-case, numbers kept, stop words dropped) found in the cited passages, averaged; a response counts as supported at or above 0.6 (calibrated in R5). |
| Judge agreement | on at least 12 answers labelled by hand (`eval/judge_labels.jsonl`, `supported` yes or no): percent agreement and Cohen's kappa. |
| Abstention correctness | on `unanswerable` and `must_abstain` questions: share with `answered_from_context=false`; also reported: false abstention rate on answerable questions. |
| Citation validity | A02 definition: share of citations that match a retrieved passage of that request. |
| Latency | client-side wall time per request, p50 and p95; per-stage p95 comes from the traces (section 7.3). |

### 6.5 Results file

`python -m eval.suite.run_suite --api URL --label baseline` writes `eval/results/suite-<UTC timestamp>-<label>.json` and a sibling `.md` summary table with the three levels. Schema keys: `meta` (timestamp, git SHA, label, seeds, `index_id`, collection, embed model and version, chunk settings, API image tag, golden-set hash), `module`, `component` (clean and noisy), `e2e`, `per_question`, `gate_inputs`. `make suite` is the one command; the same entry point is the Kubernetes Job.

### 6.6 Stochasticity (R3-B-8)

Seeds fixed: Python `random` and `PYTHONHASHSEED` in the suite; `LLM_SEED` for the generator and the judge; typo noise from the configured noise seed. `make suite-twice` runs the suite twice back to back, writes both files, and `stochasticity.py` writes `eval/results/stochasticity-<ts>.json` with the per-metric difference and a short list of the questions whose answers differed. The report explains what remains (for example, Ollama sampling on CPU is not bit-exact across runs even with a seed; answers that differ in wording but not in citations do not change retrieval metrics). Cache is bypassed with `X-Cache-Bypass: 1` (AD-38), otherwise the second run would return stored answers and prove nothing.

## 7. Observability and traceability (Part D)

### 7.1 The trace record (AD-39, R3-D1-1)

One JSON object per line, `"type": "trace"`. It is written by `api/app/services/trace.py`, filled by `answer_question` as each stage completes, and emitted once at the end (also on abstentions, fallbacks and cache hits).

| Field | Content |
| --- | --- |
| `trace_id` | equals `request_id` (header `X-Request-ID`, response body) |
| `ts` | ISO-8601 UTC |
| `query` | the question as received |
| `rewritten_query` | `null` (RAHBAR does not rewrite; recorded explicitly so the field is never silently absent) |
| `embedding` | `{model, version, dimension}`; version is the Ollama model digest (first 12 characters) read once and cached, `hashing-bow-768@1` for the CI embedder, `unknown` if unreadable |
| `collection` | `{name, index_id, chunk_count, embed_model}` as the pod sees the live index |
| `scope` | `{where, key, tag}`: the metadata filter applied and why (`current`, `all`, or specific versions) |
| `retrieved` | list in retrieval order: `{rank, chunk_id, doc_id (source), section, page, doc_version, superseded, score}` |
| `reranked_order` | chunk ids in the order shown to the model (the order after the floor filter and the injection rail; no reranker exists, so it is the same order minus dropped passages) |
| `floor` | `{value, best_score, passed}` |
| `prompt` / `prompt_sha256` | the exact chat messages sent to the model and their SHA-256 (null for abstentions and cache hits, which make no model call) |
| `model` | `{provider, name, params: {temperature, num_ctx, num_predict, seed, format: "json-schema"}, attempts}` |
| `response` | `{answer, citations, confidence, answered_from_context, outcome}` |
| `guardrails` | list of actions, each `{rail, action, detail}`: `injection_scan` (flagged or dropped, chunk id, matched pattern), `delimiter_strip` (count), `citation_check` (pass, rewrite, reject, retry), `floor` (abstain) |
| `cache` | `hit`, `miss`, `skipped`, or `bypassed` |
| `latency_ms` | `{scope, embed, cache, retrieve, guardrails, generate, total}` |
| `tokens` | `{in, out}` |
| `fallback_reason`, `abstain_reason` | as in the `answered` log line |

Sizes: a record with a prompt is about 6 to 10 KB. At the demo's volume this is negligible; the traces PVC is 500 Mi and the writer rotates a file per pod per UTC day.

**Writers.** (1) stdout through a dedicated logger so that `kubectl logs deploy/api | grep '"type": "trace"'` works (R3-F4-1), keeping the A02 rule that every log line is JSON with `request_id` (I-17). (2) When `TRACE_DIR` is set (the cluster sets `/traces`), one append-only file `traces-<UTC date>-<pod name>.jsonl` per pod, so there is a single writer per file and no locking. A write error is caught, counted in `rahbar_trace_write_errors_total`, and never reaches the user (I-22).

### 7.2 The trace tool (R3-D2-1)

`python -m scripts.trace_tool show <trace_id> [--dir traces/ | --pod deploy/api]` finds the record (a directory of `.jsonl` files, or `kubectl logs`), then prints in order: the query and scope filter, each retrieved chunk with score and version, the evidence blocks as the model saw them, the exact prompt messages, the model parameters and the response; and it recomputes the prompt SHA-256 and prints `hash OK` or `hash MISMATCH`. `--chunks` additionally fetches the current text of each cited chunk from Chroma and reports whether it still equals what was in the prompt (this exposes drift after a re-index). Sample traces for the report are committed under `traces/samples/`.

### 7.3 Metrics (R3-D3-*, R3-F4-2)

| Need | Live (`/metrics`, reachable with `kubectl port-forward`) | Over a window (`scripts/trace_report.py --since 24h`) |
| --- | --- | --- |
| Top-1 similarity distribution | existing `rahbar_top_score` histogram | histogram buckets plus min, p25, median, p75, max from `retrieved[0].score` |
| Abstention rate | existing `rahbar_abstentions_total` / requests | share of `outcome=abstained` |
| Cache hit rate | existing `rahbar_cache_hit_ratio` | share of `cache=hit` among non-skipped |
| p95 latency per stage | existing per-stage histograms | p50 and p95 of each `latency_ms` field |
| Injection attempts flagged | new `rahbar_injection_flags_total{rail}` | count of guardrail actions of rail `injection_scan` |

Metric names in `architecture.md` 4.14 (AD-24) are kept; the two added names are an additive extension logged as a deviation.

### 7.4 The retrieval rail (AD-40, R3-D4-1)

`api/app/services/guardrails.py::scan_passages(passages) -> (kept, actions)` runs after the relevance floor and before the prompt is built. It matches a short, reviewed list of instruction-override patterns (case-insensitive; for example "ignore (all|any|the) (previous|prior|above) instructions", "disregard (the )?(system|previous)", "you are now", "reveal (your|the) (system )?prompt", "do not cite", and model delimiter tokens) over the passage text. A matching passage is dropped from the evidence and recorded as `{rail: "injection_scan", action: "dropped_passage", chunk_id, pattern}`. If dropping lowers the best remaining score below the floor, the request abstains as usual. Limits, stated in the report: it is a pattern rail, not a classifier; paraphrased injections pass, and the model-side defences of A02 still apply. The Batch B injected document is the test (planted so that a golden question retrieves it).

### 7.5 Root cause from a trace (R3-D5-1)

Procedure the report follows: choose a Part B question whose answer was wrong or abstained, find its `trace_id` in the suite results, run the trace tool, and read off exactly one of: floor too high for the best chunk (`floor.best_score`), a superseded document hidden by `scope.where`, a right chunk missing from `retrieved`, a rail that dropped the right chunk, or a prompt that carried the evidence but a model answer that ignored it. Five lines in the report.

## 8. Change experiment and release gate (Part C)

### 8.1 The experiment (AD-41)

Baseline: `CHUNK_SIZE=400`, `CHUNK_OVERLAP=50` (live collection `rahbar`). A candidate is a full re-index with different values into its own collection by the same Job image (`CHROMA_COLLECTION=rahbar_cand`, `INDEX_MODE=full`), served by `api-candidate`. Assignment 02 already measured 200/25, 400/50 and 600/100 on 18 questions (`eval/tuning/`); R7 repeats them with the new suite on the 25+ question set and picks the two candidates from the measurements: one expected to fail the gate (for example 100/0 or 200/25) and one that may pass (for example 300/50 or 600/100). The release decision (release or reject, with reasons) is whatever the gate and the reasons say, not what we hoped.

### 8.2 The gate (AD-42, R3-C2-*)

`eval/gate.yaml`:

```yaml
baseline: eval/results/<baseline file>      # path or label; the Job takes it from an env var
rules:
  - {metric: component.recall_at_5,  op: not_below_baseline_by, value: 0.02}
  - {metric: component.mrr,          op: not_below_baseline_by, value: 0.03}
  - {metric: e2e.faithfulness_judge, op: at_least,              value: 0.80}   # justified in the report
  - {metric: e2e.abstention_correctness, op: not_below_baseline, value: 0}
  - {metric: e2e.citation_validity,  op: at_least,              value: 0.95}
  - {metric: e2e.latency_p95_ms,     op: at_most,               value: 90000}  # justified in the report
```

`gate.py --baseline B.json --candidate C.json [--config gate.yaml]` prints one line per rule (`PASS`/`FAIL`, observed, limit) and exits 0 only if all pass; exit 1 on any failure, 2 on a malformed input. Numbers above are placeholders to be justified in R7; the rule names are fixed by R3-C2-1.

## 9. Kubernetes

### 9.1 Object inventory (new or changed)

| Object | Kind | Responsibility (answers R3-G-4(f)) |
| --- | --- | --- |
| `corpus-data` | PVC (existing) | the inbox, read-only to the Job: documents cannot be altered by the pipeline |
| `lake-data` | PVC (new, 1 Gi) | registry, quarantine, archive, verification reports; survives pod restarts (R3-F1-2) |
| `traces-data` | PVC (new, 500 Mi) | per-pod trace files for the report scripts |
| `eval-results` | PVC (new, 200 Mi) | result files written by the eval Job |
| `indexer` | Job (existing, changed) | the only writer to Chroma and to the lake (I-1, I-18) |
| `reindex` | CronJob (existing, changed) | scheduled re-run of the same Job spec (incremental by default) |
| `chroma` | StatefulSet (existing) | vector store with its own PVC |
| `api` | Deployment (existing, changed) | the live pipeline; mounts `traces-data` read-write; rolling update `maxUnavailable: 0` |
| `api` | Service (existing) | live traffic |
| `api-candidate` | Deployment + Service (new) | the candidate, own collection, own Service (R3-F3-1) |
| `eval` | Job (new, `k8s/eval-job.yaml`) | runs the suite and the gate; exit code is the gate result (R3-F2-2) |
| `rahbar-gate` | ConfigMap (new, generated from `eval/gate.yaml`) | the thresholds; editing it changes the outcome without an image rebuild (R3-F2-3) |
| `rahbar-config` | ConfigMap (existing, new keys) | adds `LLM_SEED`, `TRACE_DIR`, `VERIFY_*`, `INDEX_MODE`, `LAKE_DIR` |
| `trace-report` | Job (new) | runs `trace_report.py` against `traces-data` (read-only mount) |
| NetworkPolicies | existing, extended | allow only the paths the new pods need (eval to API Service and Ollama host; api to nothing new) |

All new containers get requests and limits taken from measurement (R3-F5-1, I-15), recorded in `docs/evidence/f5-resources.txt` and in `k8s/README.md`.

### 9.2 The eval Job and its image (AD-43)

`k8s/eval-job.yaml` (applied with exactly `kubectl apply -f k8s/eval-job.yaml`): image `rahbar-eval:<tag>`, env `API_URL` (default `http://api`), `RUN_LABEL`, `GATE_CONFIG=/gate/gate.yaml` (ConfigMap mount), `BASELINE` path, `OLLAMA_URL`; volume `eval-results` mounted read-write at `/results`; non-root, read-only root filesystem, `backoffLimit: 0` so a failed gate is a failed Job and is not retried. The pod runs `run_suite` then `gate`; a non-zero gate exit makes the Job fail (`kubectl wait --for=condition=complete` versus `failed` shows the result). The result file is on the volume and is copied out with `make results-pull` into `eval/results/` for commit.

### 9.3 Controlled release (AD-44, R3-F3-*)

```
baseline live:   Deployment api   ── env CHROMA_COLLECTION=rahbar        ── Service api
candidate:       Deployment api-candidate ── env CHROMA_COLLECTION=rahbar_cand ── Service api-candidate
step 1  indexer Job (INDEX_MODE=full, CHUNK_*=candidate, CHROMA_COLLECTION=rahbar_cand)
step 2  api-candidate rolls out against rahbar_cand (readiness checks the pin and a non-empty collection)
step 3  eval Job with API_URL=http://api-candidate, BASELINE=<live baseline result>  ──► gate
step 4a gate FAIL  ──► stop. The candidate is never released. (evidence: failed Job, exit code)
step 4b gate PASS  ──► release: set the live Deployment's own env (CHROMA_COLLECTION, and CHUNK_* for the record)
                       kubectl set env deployment/api CHROMA_COLLECTION=rahbar_cand ...
                       rolling update, maxSurge 1, maxUnavailable 0; kubectl rollout status deployment/api
step 5  bad release: the same command with a collection that passed no gate (forced); watch traces and /metrics;
        kubectl rollout undo deployment/api  ──► previous ReplicaSet, previous CHROMA_COLLECTION
step 6  one new query: its trace shows collection.name and embedding version of the previous revision (R3-F3-4)
```

Why release by editing the Deployment's own `env`: it creates a new ReplicaSet revision, so `rollout status` and `rollout undo` have something real to track, and the live ConfigMap `rahbar-config` is not edited. An explicit `env` entry takes precedence over `envFrom`, so the live Deployment can point at another collection while the ConfigMap still names the original. The `deployment/api` revision history (`revisionHistoryLimit`) is set to at least 5. Because of AD-17 a ConfigMap-only change would not roll anything out, which is the reason for this design.

### 9.4 Resources and measurement (R3-F5-1)

`scripts/measure_resources.sh` samples `kubectl top pod` every 5 seconds during an eval Job run and an incremental ingestion run (metrics-server is already enabled for the HPA), and writes peaks to `docs/evidence/f5-resources.txt`. Requests are set at about the observed median and limits at about 1.5 times the observed peak, rounded; the numbers are copied into the report. This replaces the K10 values only where a new measurement disagrees (log in `deviations.md`).

### 9.5 A fresh cluster (R3-F5-2)

`k8s/README.md` lists the exact order: `make cluster`, `make images`, `kubectl apply -k k8s/overlays/dev`, `make corpus`, `make index`, `make lake-ls`, `kubectl apply -f k8s/eval-job.yaml`, plus the Ollama host step. A rehearsal on a deleted cluster is an acceptance criterion of R11.

## 10. Drift and coverage (Part E)

- `eval/live_queries.jsonl`: at least 40 lines `{id, query, expected_topic, in_domain}`; about 28 in domain and at least 12 about a topic the corpus does not cover (hostel life, transport routes, sports). Written to read like real student questions, not like the golden questions.
- `coverage.py --live eval/live_queries.jsonl --golden eval/golden.jsonl --threshold T --target P`: embeds both sets, for each live query takes the best cosine to any golden question, reports the share at or above T, lists the uncovered queries, groups them by `expected_topic` (verified by clustering the uncovered embeddings and printing both), and exits 1 if the share is below the target P (the paper's example: gap below 85 percent).
- Threshold T: calibrated from the module-level means: T is placed between `unrelated_mean` and `paraphrase_mean`, nearer the paraphrase side, and justified in the report with the pair table. The target P and T go in `eval/gate.yaml`-style config `eval/coverage.yaml`.
- E3: ingest Batch B (incremental Job), re-run the suite, compare with the pre-ingest result: what changed (new documents retrievable, the superseded document's questions now point at the new version, the injected document handled by the rail, scores of old questions changed or not) and why.
- E4: add at least 6 golden questions for the uncovered topics (they must have answers in the corpus or Batch B, or be unanswerable by design), re-run coverage, show the share rises, keep the before and after outputs.

## 11. Planned deviations from `architecture.md`

Logged for real in `deviations.md` when the code lands. None changes an external contract.

| Planned | Where | Why |
| --- | --- | --- |
| The integrity (sha256) failure becomes a per-document failure instead of aborting the run | indexer `run.py` | A1 needs a verdict per document; strict whole-corpus failure remains available with `VERIFY_STRICT=true` |
| The indexer gains a second mode (incremental) next to the A02 full rebuild; AD-02 is kept inside both | indexer | R3-A2 |
| New ConfigMap keys `LLM_SEED`, `TRACE_DIR`, `LAKE_DIR`, `INDEX_MODE`, `VERIFY_*` | `k8s/base/configmap.yaml` | contract C-2: told to the platform lane, which is us |
| New metric names `rahbar_injection_flags_total`, `rahbar_trace_write_errors_total` | `api/app/routes/metrics.py` | AD-24 names stay; these are additions |
| New request header `X-Cache-Bypass` | API route | reproducible evaluation (AD-38) |
| The `api` Deployment mounts a read-write volume (`traces-data`) and keeps `readOnlyRootFilesystem` | `k8s/base/api.yaml` | trace files; one file per pod |
| New image `rahbar-eval` and a CD matrix entry | `.github/workflows/cd.yml`, `ci.yml` | R3-F2-2 |
| Resource requests and limits revised where the new measurement differs | `k8s/base/*.yaml` | R3-F5-1 |

## 12. Risks and assumptions

| # | Assumption or risk | Check | Fallback |
| --- | --- | --- | --- |
| A3-R1 | Chroma 1.0.12 returns stored embeddings in `get(include=["embeddings"])` exactly as stored, and a staging collection built from them gives identical query results | R3 spike: copy a collection, compare top-5 for 18 questions | re-embed all (A02 behaviour) and report why |
| A3-R2 | RWO `traces-data` can be mounted read-write by three API pods on one node (minikube is single node) | R8: `kubectl get pods`, three pods running, three files written | an `emptyDir` plus a sidecar is not needed on a single node; document that multi-node needs RWX or a log collector |
| A3-R3 | A 3B judge is a noisy faithfulness judge | R5 reports agreement and kappa with at least 12 hand labels, plus the deterministic score | report both and name the weaker one as the metric we trust least (R3-G-4(d)) |
| A3-R4 | A full suite run is slow (the A02 eval of 18 questions took minutes; 25+ questions, twice, plus judge calls, plus noise run) | R5 measures; run twice in the background; judge calls batched | reduce the noise run to answerable questions only; keep the spec's minimums |
| A3-R5 | Near-duplicate threshold is data dependent | R2 calibration on 9 real documents + Batch B | choose the largest gap between distinct and planted-near-duplicate pairs and show the table |
| A3-R6 | The Docker Hub token expires (30 days) and CD must build `rahbar-eval` | R8: CD run on `dev` | build locally with `minikube image load`; images are local-only for the demo |
| A3-R7 | The `rollout undo` demo needs at least two ReplicaSet revisions of `api` | R9 | create the revisions in the rehearsal; revision history limit raised |
| A3-R8 | The paper's Table 1, Table 2 and Figure 3 are not available to us | D-109 | map from the assignment's own wording; the report states the assumption |
| A3-R9 | Ollama on the host must be running during every suite and demo run | `scripts/verify_ollama.py` first step of each run | none; stated in `k8s/README.md` |
