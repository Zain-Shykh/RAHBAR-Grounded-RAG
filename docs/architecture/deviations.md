# Deviations from the architecture

Companion to [`architecture.md`](architecture.md) (version 1.0). Every place where the code, manifests or pipelines differ from what `architecture.md` says is recorded here, on the day it happens. Nothing is allowed to drift silently.

The log starts empty. An empty log means "built as designed". It is checked before every pull request to `main` and again before submission.

## 1. What counts as a deviation

Log an entry when any of these is true:

- A hard invariant (`architecture.md` section 0.2, I-1 to I-17) cannot be met as written.
- A class A or class B decision (section 0.1) is implemented differently from the document: a different component, port, probe value, NetworkPolicy path, ConfigMap key, metric name, metadata field, API shape, overlay layout or pipeline order.
- A security setting is relaxed (for example a container cannot run non-root, or a root filesystem has to be writable).
- A requirement in `docs/requirements.md` is met by a different mechanism than the architecture chose.
- An assumption or risk in section 9 of the architecture turns out to be false and the plan changes.
- A decision tagged `◇` is replaced after the user has seen the reason.

Not a deviation: choices in class C (private names, internal module splits, test layout, formatting), tuning a number that the architecture says is to be measured (chunk size, relevance floor, cache threshold, resource requests and limits), and filling in a value the architecture left as "pin at implementation" (image tags).

## 2. Rules

1. Log first or log in the same pull request as the change. Not later.
2. One entry per deviation. Keep it short and factual: what the document said, what was built, why.
3. A deviation ends in exactly one of two ways. **Reverted**: the code goes back to the architecture. **Absorbed**: `architecture.md` is amended in a pull request (new row in its version history) and the entry is marked `Absorbed in vX.Y`.
4. A class B or class A deviation needs a human decision before it is merged to `main`. An AI agent may implement it on `dev` and must say so in the pull request. Class A deviations (from the assignment) are almost never acceptable; if one is unavoidable, add a line to the matching ADR and tell the instructors in the README.
5. Never delete an entry. Change its status.
6. If the deviation changes a contract (request, response, metadata fields), also write or update an ADR, as `STARTER.md` requires.
7. If the deviation touches a deduction item in `docs/rubric_checklist.md` section A, say so in the entry and re-verify that item.

## 3. Severity

| Level | Meaning | Approval |
| --- | --- | --- |
| S1 | Breaks a hard invariant, an assignment requirement, or removes a security control | Human approval before merge to `main`; ADR or README note |
| S2 | Changes a class B decision or an externally visible contract without breaking an invariant | Human approval before merge to `main` |
| S3 | Local or temporary difference with no effect on behaviour or evidence (for example a workaround for a tool version) | Record only; absorb or revert before submission |

## 4. Statuses

`OPEN` (in effect, no decision), `ACCEPTED` (human agreed to keep it, not yet written into the architecture), `ABSORBED vX.Y` (architecture amended), `REVERTED` (code restored to the architecture), `SUPERSEDED BY DEV-NNN`.

Nothing may stay `OPEN` or `ACCEPTED` at submission unless the architecture is amended to match or the entry is explained in the README.

## 5. Entry template

Copy this block to the end of section 7, increment the number, and fill every line. Delete lines that truly do not apply.

```markdown
### DEV-NNN Short title

| | |
| --- | --- |
| Status | OPEN |
| Severity | S1 / S2 / S3 |
| Date | YYYY-MM-DD |
| Raised by | name or agent |
| Architecture reference | section and decision id, for example 4.6 (NetworkPolicy), AD-04, I-11 |
| Files changed | `path`, `path` |
| Related | PR #, issue, `docs/OPEN_DECISIONS.md` D-NNN, ADR number |

**The architecture says:** one or two sentences.

**What was built instead:** one or two sentences.

**Why:** the concrete obstacle (error message, version limit, measurement). Include the evidence.

**Impact:** what behaviour, security, requirement or deduction item changes. Say "none" if none.

**Plan:** revert by ..., or amend architecture section ... .

**Decision:** (human fills in) accepted / rejected / amend architecture, with date.
```

## 6. Index

| ID | Title | Severity | Status | Architecture reference | Date |
| --- | --- | --- | --- | --- | --- |
| DEV-001 | PDF extraction uses pdfplumber default text mode, not layout mode | S3 | ABSORBED | 5.4.2 (extract) | 2026-11-04 |
| DEV-002 | Eval section match also folds dashes and applies NFKC | S3 | ABSORBED | 5.13.2, AD-22 | 2026-11-04 |
| DEV-003 | Chunker heading rules: isolated short line added, numbered rule tightened, section cut at 80 characters | S3 | ABSORBED | 5.4.2 (chunk), AD-22 | 2026-11-05 |
| DEV-004 | `Passage` gains optional `doc_version` and `superseded` | S3 | ABSORBED | 5.7.2 | 2026-11-05 |
| DEV-005 | A citation may name a retrieved section by its leading clause number | S3 | ABSORBED | 5.7.3 rule 2 | 2026-11-05 |
| DEV-006 | Cache maintenance runs on the next request or readiness probe, not inside the index refresh | S3 | ABSORBED | 5.9.4 item 3 | 2026-11-05 |
| DEV-007 | The model timeout and the Ingress timeout must exceed 90 s and 120 s on the host CPU | S3 | ABSORBED | 4.4, 5.7.4 | 2026-11-05 |
| DEV-008 | Pods set `enableServiceLinks: false` (Service env vars break Chroma) | S3 | ABSORBED | 4.2, 4.4 | 2026-11-05 |
| DEV-009 | `fsGroup` is a no-op on minikube hostPath volumes; `/data` is writable because the provisioner makes it 0777 | S3 | OPEN, accepted | 4.7, R-01, R-02 | 2026-11-05 |
| DEV-010 | The in-cluster index has 980 chunks, not 981: Tesseract in the indexer image OCRs the 8-page faculty policy into 39 chunks (host run: 40) | S3 | OPEN, accepted | 5.4, AD-08 | 2026-11-06 |
| DEV-013 | Requests and limits in 4.2 replaced by the values measured in K10 (`docs/evidence/resources.md`) | S3 | CLOSED, absorbed | 4.2, R-RES-2 | 2026-11-07 |

## 7. Log

*(Entries start here. Newest last.)*

### DEV-001 PDF extraction uses pdfplumber default text mode, not layout mode

| | |
| --- | --- |
| Status | ABSORBED (2026-11-05, architecture 5.4.2 and AD-22) |
| Severity | S3 |
| Date | 2026-11-04 |
| Raised by | Claude (phase 5, found in phase 4 evidence) |
| Architecture reference | 5.4.2 (extract) |
| Files changed | `indexer/pipeline/extract.py` (phase 4, already merged) |
| Related | `docs/PIPELINE.md`, `docs/examples/annual-report-2023-24-p13-before.txt`, `docs/examples/annual-report-2023-24-p13-after.txt`, `docs/specs/phase-04-extract-clean.md` |

**The architecture says:** PDF extraction is "`pdfplumber` text per page, layout preserved so table rows stay on one line".

**What was built instead:** `page.extract_text()` in default text mode. `extract_text(layout=True)` is not used.

**Why:** default mode already keeps a table row on one line (Annual Report 2023-24 PDF page 13: `Islamabad 19 14 46 16 83 50 8 236`). Layout mode keeps rows too, but pads every line with spaces and adds blank lines that the cleaner would have to strip. Evidence: `docs/PIPELINE.md` and `docs/examples/annual-report-2023-24-p13-*.txt`.

**Impact:** none on behaviour. The goal of the sentence (table rows on one line) is met. No invariant, requirement or deduction item changes.

**Plan:** absorb: reword architecture 5.4.2 to "table rows stay on one line (pdfplumber default text mode)" in the next architecture version.

**Decision:** (human fills in)

---

## 8. Watch list

Places where the architecture has flagged a real chance of deviation (architecture section 9). If one of these happens, it is a deviation, and the entry should link to the risk number.

| Risk | If it happens, the likely deviation | Severity guess |
| --- | --- | --- |
| R-01 Chroma cannot run non-root with read-only root | Relaxed `securityContext` on `chroma` | S1 (security control) |
| R-02 Redis Stack cannot run non-root or needs a writable path | Relaxed `securityContext` on `redis`, or fall back to plain Redis with app-side cosine (D-001 option B) | S1, or S2 for the fallback |
| A-2 / A-3 Chroma rename or batch size not as assumed | Different swap procedure in the indexer `store` stage | S2 |
| A-4 `kubectl cp` into the PVC fails | Different corpus delivery (init container fetch, D-003) | S2 |
| A-5 native `preStop` sleep unavailable | `exec` sleep with an image that has `sleep` | S3 |
| R-07 NetworkPolicy unenforced on kind | CI cannot prove isolation; evidence comes only from minikube | S3 |
| Kit interface changes in `api/app` | Any change to `Retriever`, `LLMProvider`, `AskResponse` beyond architecture 5.7.2 | S2 |

### DEV-002 Eval section match also folds dashes and applies NFKC

| | |
| --- | --- |
| Status | ABSORBED (2026-11-05, architecture 5.4.2 and AD-22) |
| Severity | S3 |
| Date | 2026-11-04 |
| Raised by | Claude (phase 5) |
| Architecture reference | 5.13.2, AD-22 |
| Files changed | `eval/run_eval.py` (`_norm`, `section_matches`), `eval/tests/test_run_eval.py` |
| Related | `docs/OPEN_DECISIONS.md` D-046, `docs/specs/phase-05-eval-runner.md` |

**The architecture says:** a retrieved section matches a golden section when equal after trimming, lower-casing and collapsing whitespace, or when it starts with the golden section followed by a space, `.` or `:`.

**What was built instead:** the same rule, after also applying Unicode NFKC and mapping the dash variants U+2010 to U+2015 and U+2212 to `-`.

**Why:** the real Student Handbook heading is `VI – SEMESTER RULES` (en dash) while `V - EXAMINATION RULES` uses a hyphen, and the chunker may emit either. A typographic dash must not count as a recall miss. Zain chose this on 2026-11-04 (D-046).

**Impact:** recall can only rise, and only for headings that differ in dash or compatibility characters. No invariant, requirement or deduction item changes.

**Plan:** absorb: add "after NFKC and dash folding" to architecture 5.13.2 and AD-22 in the next version.

**Decision:** accepted by Zain 2026-11-04 (D-046); amend architecture later.

### DEV-003 Chunker heading rules: isolated short line added, numbered rule tightened, section cut at 80 characters

| | |
| --- | --- |
| Status | ABSORBED (2026-11-05, architecture 5.4.2 and AD-22) |
| Severity | S3 |
| Date | 2026-11-05 |
| Raised by | Claude (phase 6) |
| Architecture reference | 5.4.2 (chunk row), AD-22 |
| Files changed | `indexer/pipeline/chunk.py`, `indexer/tests/test_chunk.py` |
| Related | `docs/OPEN_DECISIONS.md` D-049, D-050, `docs/specs/phase-06-chunker.md` |

**The architecture says:** headings are numbered clauses (`^\d+(\.\d+)*[.)]?\s+\S`), roman or lettered section lines, and short all-caps lines; `section` is the heading text exactly as written, whitespace-normalised.

**What was built instead:** (1) a fourth rule: a short line (1 to 10 words, at least 4 letters, capital first, no final `. : ; , ! ?`, mostly not numbers) with a blank line above and text within two lines below is a heading; (2) the numbered rule needs `N.` or `N.N...` (1 or 2 digits, a dot, so `16 Student Handbook 2026` and `1)` list items are not headings), a capital or `(` next, and no line over 150 characters (a list squeezed on one line is not a heading); (3) `section` is cut at 80 characters on a word boundary; (4) a short title with no body is carried into the next section, whose heading names it (the title line stays in the text); (5) a line is split before a dotted clause number with a capital word after it (`... Semester 4.25 The deadline`), because the two-column pages of the Academic Rules Handbook run two columns into one line; grades such as `4.00` are excluded.

**Why:** the fee and grading HTML pages have plain heading lines (`Fee Refund Policy`, `Letter grades for MBA & MS programs`) that the three rules never find, so golden q07, q08 and q15 could not match. The original numbered regex matches page headers (`16 Student Handbook 2026`), years and table data, and the `1)` items inside one policy sub-section, which would split it. Full clause lines can be 100 characters or more.

**Impact:** a heading is found in more cases; `section` for a long clause is a prefix of the line, which `section_matches` (AD-22) already accepts. No invariant or requirement changes. Known loss: other headings inside interleaved two-column text (Student Handbook, and OCR text where clause numbers sit on their own lines) are not recovered; a chunk then carries the previous heading.

**Plan:** absorb: add the four rules and the 80-character cut to architecture 5.4.2 and AD-22 in the next version.

**Decision:** pre-approved by Zain 2026-11-05 (D-049); ACCEPTED by Zain 2026-11-05 after the phase 6 review; absorbed into architecture 5.4.2 and AD-22 the same day.

### DEV-004 `Passage` gains optional `doc_version` and `superseded`

| | |
| --- | --- |
| Status | ABSORBED (2026-11-05, architecture 5.7.2) |
| Severity | S3 |
| Date | 2026-11-05 |
| Raised by | Claude (phase 9) |
| Architecture reference | 5.7.1 (evidence header), AD-14 |
| Files changed | `api/app/schemas.py`, `api/app/retrieval/chroma.py` |
| Related | `docs/OPEN_DECISIONS.md` D-61, `docs/specs/phase-09-prompt-validate.md` |

**The architecture says:** the evidence header carries `version` and `status`; the kit `Passage` has no such fields.

**What was built instead:** `Passage.doc_version: str | None` and `Passage.superseded: bool | None`, both default `None`, filled by `ChromaRetriever` from chunk metadata. The prompt omits a header field when its value is `None`. `AskResponse`, `RetrievedRef` and every external JSON shape are unchanged.

**Why:** the prompt needs them (5.7.1) and a second Chroma lookup per request would add a call and a failure mode.

**Impact:** none on invariants or contracts C-1 to C-8; the stub retriever keeps working (fields stay `None`).

**Plan:** absorb: add the two optional fields to the `Passage` description in architecture 5.7.2.

**Decision:** pre-approved by Zain 2026-11-05 (D-61); ACCEPTED by Zain 2026-11-05 after the phase 9 review; absorbed into architecture 5.7.2 the same day.

### DEV-005 A citation may name a retrieved section by its leading clause number

| | |
| --- | --- |
| Status | ABSORBED |
| Severity | S3 |
| Date | 2026-11-05 |
| Raised by | Claude (phase 10) |
| Architecture reference | 5.7.3 (validate, rule 2), 5.8 |
| Files changed | `api/app/services/validate.py` (`citation_matches`), `api/app/services/prompt.py` (answer style line) |
| Related | `docs/specs/phase-10-generation.md` section 11, live run q01 |

**The architecture says:** every citation resolves to a retrieved passage matching `source` exactly and `section` exactly.

**What was built instead:** exact match first. Failing that, the cited `section` is accepted when it is a prefix of exactly one distinct retrieved `section` of the same `source`, ending at a space, dot or colon (`4.3` for `4.3 The normal course load is 5 courses.`). `validate` rewrites the citation to the passage's exact `source`, `section` and `page`, so the response only ever carries retrieved strings. An ambiguous prefix, a mid-word prefix or an empty section is still rejected.

**Why:** live llama3.2:3b on the real index (q01) copied the clause number and dropped the heading text although the prompt says to copy exactly; exact matching turned a correct, grounded answer into the canned fallback. The accepted forms are the same rule eval uses for golden sections (AD-22), and the output stays exact.

**Impact:** no invariant weakened: a citation to a chunk not retrieved for the request is still rejected (I-9 style check), citation validity in eval stays 100% by construction. No contract change.

**Plan:** absorb into 5.7.3 rule 2.

**Decision:** taken by Claude to fix a code defect found live; accepted by Zain 2026-11-05; absorbed into architecture 5.7.3 rule 2.

### DEV-006 Cache maintenance runs on the next request or readiness probe, not inside the index refresh

| | |
| --- | --- |
| Status | ABSORBED |
| Severity | S3 |
| Date | 2026-11-05 |
| Raised by | Claude (phase 11) |
| Architecture reference | 5.9.4 item 3, AD-04 |
| Files changed | `api/app/services/cache.py` (`maintain`), `api/app/services/answer.py`, `api/app/routes/health.py` |
| Related | `docs/OPEN_DECISIONS.md` D-71, `docs/specs/phase-11-semantic-cache.md` |

**The architecture says:** "When an API pod's refresh sees a new `index_id`, it creates `idx:cache:{new}`, then drops every other `idx:cache:*` index."

**What was built instead:** `IndexState` stays a Chroma-only reader. `SemanticCache.maintain(index_id, dimension)` is called with the request's snapshot in `answer_question` and with the probe's snapshot in `/readyz`, and does the create-then-drop the first time it sees a new `index_id`. It is a no-op while the `index_id` is unchanged.

**Why:** keeps Chroma and Redis concerns apart, lets `/readyz` heal a missing cache index, and needs no callback from `IndexState`. Readiness probes run every few seconds, so a pod that sees a new `index_id` in a refresh creates and cleans up the cache indexes within one probe period, or on its first question, whichever is first. Entries are keyed by `index_id`, so correctness never depends on the drop; the drop only frees memory.

**Impact:** none on invariants or contracts. Verified live: after a real re-index the earlier question was a `MISS` and `FT._LIST` showed only the new index.

**Plan:** absorbed into architecture 5.9.4 item 3.

**Decision:** taken by Claude, pre-approved by Zain (D-71).

### DEV-007 The model timeout and the Ingress timeout must exceed 90 s and 120 s on the host CPU

| | |
| --- | --- |
| Status | ABSORBED (Zain accepted option A, 2026-11-05; architecture 4.4, 5.7.4 and the Ingress section amended) |
| Severity | S3 |
| Date | 2026-11-05 |
| Raised by | Claude (phase 12) |
| Architecture reference | 4.4 (`LLM_TIMEOUT_SECONDS` 90, "below the Ingress timeout (120 s)"), 5.7.4 |
| Files changed | `api/app/config.py` (default 300 to match the amended architecture), ConfigMap and Ingress value for Ahmad (H-13) |
| Related | `docs/IMPLEMENTATION_PLAN.md` H-7, results register "Generation p50 / p95" |

**The architecture says:** the model call times out after 90 s, below a 120 s Ingress timeout.

**What was built instead:** nothing in code. The shipped baseline (`eval/results.json`) was measured with `LLM_TIMEOUT_SECONDS=300`, and the client in `eval/run_eval.py` now waits 300 s.

**Why:** on this CPU `llama3.2:3b` took 123 s (q04) and 139 s (q09) for two of 18 uncached golden questions on the first full run (p50 39.0 s, p95 138.6 s; a warm re-run of q04 took 41 s). With the 90 s default each of those would have ended as a `provider_error` fallback, and through an Ingress with a 120 s read timeout the client would have received a 504 first.

**Impact:** a cluster run with the architecture's values can show fallbacks and 504s on long prompts that the committed baseline does not have (fallback rate is gated only by reporting, citation validity and abstention are not affected). Cached answers (0.1 to 0.3 s) and floor abstentions are unaffected.

**Plan:** either (A) set `LLM_TIMEOUT_SECONDS=300` in the ConfigMap and the Ingress `proxy-read-timeout` to at least 310 s (what the baseline used; Ahmad, H-7), amending 4.4; or (B) keep 90 and accept fallbacks on the slowest questions, and say so in the engineering note. Recommended: A.

**Decision:** Zain accepted A: `LLM_TIMEOUT_SECONDS=300` in the ConfigMap and Ingress `proxy-read-timeout` of at least 310 s. Architecture amended.

### DEV-008 Pods set `enableServiceLinks: false`

| | |
| --- | --- |
| Status | ABSORBED (taken by Claude, pre-approved by Zain, D-092) |
| Severity | S3 |
| Date | 2026-11-05 |
| Raised by | Claude (phase K1) |
| Architecture reference | 4.2, 4.4 |
| Files changed | `k8s/base/api.yaml`, `ui.yaml`, `chroma-statefulset.yaml`, `redis.yaml` |

**The architecture says:** nothing about Service links.

**What was built instead:** every pod sets `enableServiceLinks: false`.

**Why:** the Service `chroma` makes Kubernetes inject `CHROMA_PORT=tcp://10.x.x.x:8000` into every pod in the namespace. The Chroma server reads `CHROMA_`-prefixed variables as its config, so it panicked (`invalid type: found string "tcp://...", expected u16 for key "PORT"`) and crash-looped. The same mechanism could shadow `REDIS_PORT` in the api. Seen on the first apply on minikube.

**Impact:** none on behaviour; DNS names (`chroma`, `redis`) still work. A future Service in the namespace cannot break a pod through env injection.

### DEV-009 `fsGroup` is a no-op on minikube hostPath volumes

| | |
| --- | --- |
| Status | OPEN, accepted (no action needed on minikube; real clusters honour `fsGroup`) |
| Severity | S3 |
| Date | 2026-11-05 |
| Raised by | Claude (phase K1) |
| Architecture reference | 4.7, R-01, R-02 (H-2, H-3 asked for the `fsGroup` mechanism to be confirmed) |
| Files changed | none (manifests keep `fsGroup: 10001`) |

**The architecture says:** the PVC pods set `fsGroup` so UID 10001 can write `/data`.

**What was observed:** in minikube (provisioner `k8s.io/minikube-hostpath`) `/data` inside both chroma-0 and redis is `drwxrwxrwx 0 0` (owner root, mode 0777). `fsGroup` does not change ownership on a hostPath volume, but the world-writable mode lets UID 10001 write anyway. Writes succeed, data survives pod deletion, the root filesystem stays read-only (`docs/evidence/k01-persistence-and-security.txt`).

**Why it matters:** the proof that `fsGroup` itself chowns the volume is not available here. On a cluster whose volume driver supports `fsGroup` the manifests rely on it, which is documented Kubernetes behaviour; it was not exercised here. The security settings are kept as designed.

**Impact:** none on the demo. Stated honestly in architecture 9.

### DEV-010 The in-cluster index has 980 chunks, not 981

| | |
| --- | --- |
| Status | OPEN, accepted |
| Severity | S3 |
| Date | 2026-11-06 |
| Raised by | Claude (phase K2) |
| Architecture reference | 5.4 (chunk counts), AD-08; platform plan K2 ("must equal 981") |
| Files changed | none |

**The plan says:** the collection holds 981 chunks (measured on the host in RAG phases 7 and 12).

**What was observed:** the indexer Job built 980 chunks twice (Job and `make index`), same `_index.json`, same SHA-256 verified files. Eight of nine documents match the host counts exactly (238, 65, 182, 7, 8, 44, 245, 152). The difference is `faculty-entrepreneurship-and-technical-start-ups-policy.pdf`: 8 pages, all 8 OCR'd, 39 chunks in the container, 40 on the host. OCR output depends on the Tesseract build and thread count, so one boundary moves.

**Why it matters:** none for correctness; eval baselines (`eval/baseline.json`) were measured on the 981 index, so a local `make eval` against the cluster may differ by a fraction of one chunk's effect. The count is recorded as 980 in the results register.

**Impact:** none. If an exact match is wanted later, pin the Tesseract version in `indexer/Dockerfile` and re-measure on the host with the same build (RAG lane).

### DEV-011 The `ci` overlay needs `--load-restrictor LoadRestrictionsNone`; rehearsal ran on minikube

| | |
| --- | --- |
| Status | OPEN, accepted |
| Severity | S3 |
| Date | 2026-11-06 |
| Raised by | Claude (phase K5) |
| Architecture reference | 4.11, 4.5, AD-18 |
| Files changed | `k8s/overlays/ci/kustomization.yaml`, `Makefile` (`manifests`) |

**The architecture says:** `kustomize build k8s/overlays/<x> | kubeconform -strict`, and the `ci` overlay carries a `corpus-fixtures` ConfigMap from `eval/fixtures`.

**What was built:** the ConfigMap generator reads `../../../eval/fixtures` (one copy of the fixtures), which kustomize refuses by default, so the `ci` overlay is built with `--load-restrictor LoadRestrictionsNone` and applied with `kustomize build ... | kubectl apply -f -` (not `kubectl apply -k`). `dev` and `prod` build with plain `kustomize build`. K6 to K8 must pass the flag (D-096). The end-to-end rehearsal ran on minikube in a throwaway namespace, not on kind, because the laptop disk filled while pulling the kind node image.

**Why it matters:** a workflow that forgets the flag fails at build time, loudly. The real kind run is the K7 job itself.

**Impact:** none on the demo. Absorbed in architecture 4.11 at K11.

### DEV-012 `cd.yml` also runs on `workflow_dispatch` and may push SHA tags from `dev`
| | |
| --- | --- |
| Status | OPEN, accepted |
| Severity | S3 |
| Date | 2026-11-06 |
| Raised by | Claude (phase K8) |
| Architecture reference | 4.15 (Triggers, CD) |
| Files changed | `.github/workflows/cd.yml` |

**The architecture says:** `cd.yml` runs on push to `main` only.

**What was built:** push to `main`, plus `workflow_dispatch`. The three `build-push-action` steps push only when the ref is `main` or `dev` (a dispatch from another branch builds and never publishes); the tag is always `${{ github.sha }}`. GitHub only offers `workflow_dispatch` for a workflow file that exists on the default branch, so until the `dev` to `main` merge the pipeline was rehearsed with a temporary `push` trigger on the working branch (removed before merge): run $R.

**Why it matters:** it lets CD be exercised from `dev` before the final merge; no `:latest`, no push from feature branches.

**Impact:** none on the submission; the run that counts for R-SUB-2 is the first push to `main` (Phase 15). Absorbed in architecture 4.15 at K11.

### DEV-013 Requests and limits in architecture 4.2 replaced by measured values

| | |
| --- | --- |
| Status | CLOSED, absorbed (architecture 4.2 table edited in the same PR) |
| Severity | S3 |
| Date | 2026-11-07 |
| Raised by | Claude (phase K10) |
| Architecture reference | 4.2 (workload table), R-RES-2 |
| Files changed | `k8s/base/api.yaml`, `ui.yaml`, `redis.yaml`, `chroma-statefulset.yaml`, `indexer-job.yaml` |

**The architecture says:** api 100m/256Mi to 500m/512Mi, ui 25m/32Mi to 100m/64Mi, chroma 100m/256Mi to 500m/1Gi, redis 100m/256Mi to 500m/512Mi, indexer 250m/512Mi to 1/2Gi.

**What was built:** api 100m/128Mi to 500m/256Mi, ui 10m/16Mi to 100m/32Mi, chroma 50m/192Mi to 500m/512Mi, redis 50m/64Mi to 250m/256Mi, indexer 250m/384Mi to 1/1Gi. Each number is justified by a measurement in `docs/evidence/resources.md`.

**Why it matters:** the plan (K10) asks that the requests follow what `kubectl top` showed; the design numbers were estimates.

**Impact:** none on behaviour; the HPA percentage is unchanged because the api CPU request stays 100m.

