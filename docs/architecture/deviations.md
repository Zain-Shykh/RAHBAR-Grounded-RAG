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
| Status | OPEN (absorb) |
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

**Decision:** pre-approved by Zain 2026-11-05 (D-61).

### DEV-005 A citation may name a retrieved section by its leading clause number

| | |
| --- | --- |
| Status | OPEN (absorb) |
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

**Decision:** taken by Claude to fix a code defect found live (pre-approved run); Zain to confirm in the PR.
