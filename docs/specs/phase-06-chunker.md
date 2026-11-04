# Phase 06 spec and plan: Chunker

| | |
| --- | --- |
| Phase | 6, from `docs/IMPLEMENTATION_PLAN.md` |
| Work plan task | Z-05 |
| Branch | `feat/rag-z05-chunker` |
| Stage | MERGED |
| Started | 2026-11-05 |
| Approved (spec and plan) | 2026-11-05, Zain (pre-approved: no gate this session) |
| Depends on | phase 4 (extract, clean, merged), phase 5 (`section_matches`, merged) |

## 1. Objective

`indexer/pipeline/chunk.py::chunk(doc, size, overlap)` turns a cleaned `Document` into `Chunk`s: split on headings, then paragraphs, then sentences, packed to `size` words, with `overlap` words shared between neighbours of the same section, and the five metadata fields plus a stable id on every chunk. `scripts/chunk_report.py` measures it on the real corpus (storage amplification). The golden-set section strings are reconciled with the headings the chunker really produces.

## 2. Context

- Architecture: 5.4.2 (chunk row, id rule, amplification), 5.4.3 (record), AD-10 (words), AD-22 (section text and matching), AD-28 (id). Invariant: every chunk has the five fields (I-5 style rule in CLAUDE.md).
- Requirements: R-IDX-3, R-IDX-6, R-IDX-8. Rubric: metadata fields present, unit stated, amplification reported.
- Decisions made in this phase: D-049, D-050, D-051 (all "Claude, pre-approved by Zain"). Deviation: DEV-003.
- Existing code: `indexer/pipeline/models.py` (`Document`, `Page`, `Chunk`, `Chunk.metadata()`); `chunk.py` is the STARTER-TODO(3.1) stub; `run.py` and `dummy.py` do not call `chunk` yet (phase 7 wires it). `eval/run_eval.py::section_matches` is the matcher the golden strings must satisfy.
- Real text (cleaned, inspected with a throwaway script, nothing committed):
  - Clause documents (Academic Rules Handbook, Aug 2023 rules): every clause starts `4.3 The normal ...` on one line, so one clause is one section.
  - Student Handbook: Roman sections (`V - EXAMINATION RULES`), lone-integer headings (`5. Unacceptable Uses of ...`), but two-column pages are interleaved (`7. Students who ... VII - LIBRARY SERVICES AND RULES` on one line). Headings found mid-line are not recoverable; recorded as a known loss.
  - HTML pages (fee, grading): headings are plain short lines between blank lines (`Fee Refund Policy`), no marker. The architecture's three heading rules do not find them. DEV-003 adds a fourth rule.
  - Annual Reports: no blank lines, table rows without ` | `; numbered rows like `19 14 46` are table data.

## 3. Scope

**In scope**

- `chunk()` in `indexer/pipeline/chunk.py` and its helpers.
- `scripts/chunk_report.py` (not in the image): per document chunk count, words per chunk min/median/max, stored words, source words, amplification, distinct sections (`--sections`), `--golden` check that lists golden items with no matching chunk.
- Tests in `indexer/tests/test_chunk.py`.
- Reconcile `eval/golden.yaml` section strings with real headings (small commit; count logged).
- Docs: `deviations.md` DEV-003, `OPEN_DECISIONS.md` D-049..D-051, `PIPELINE.md` chunking rules paragraph, plan, `AI-USAGE.md`.

**Out of scope**

- Embedding, section-title prefix of embedded text (phase 7). Choosing the shipped size and overlap (phase 12; defaults 400 and 50 are used). Wiring `chunk` into `run.py` (phase 7). Fixing column interleaving (phase 4 territory; documented).

## 4. Interfaces and contracts

```python
def chunk(doc: Document, size: int, overlap: int) -> list[Chunk]
```

- Raises `ValueError` if `size < 1`, `overlap < 0` or `overlap >= size`.
- Returns `[]` for a document with no text. Pure function: no I/O, no logging, deterministic.
- Internal helpers (private): `_heading(line, prev_blank, next_blank) -> str | None`, `_units(lines, size)`, `_pack(...)`.
- No config keys added; `CHUNK_SIZE` and `CHUNK_OVERLAP` stay in `IndexerSettings` (already there) and are passed by the caller.
- `scripts/chunk_report.py [--corpus DIR] [--size 400] [--overlap 50] [--only SUBSTR] [--sections] [--golden FILE]`; exit 1 if `--golden` finds an item with no matching chunk. Needs `corpus/raw` and Tesseract.
- No frozen contract (C-1..C-8) changes; no hand-off to Ahmad.

## 5. Behaviour and design details

**Headings** (a line, stripped, not containing ` | `; first match wins):

1. Numbered clause: `N.` or `N.N...` (1 or 2 digits and a dot), then a capital or `(`, line at most 150 characters (architecture regex tightened: years, table data, page headers such as `16 Student Handbook 2026`, `1)` list items and one-line numbered lists do not match). DEV-003.
2. Roman: `^[IVXLC]{1,6}\s*[-–—.]\s*[A-Z][A-Z &/,'-]{3,}$` (`V - EXAMINATION RULES`, `VI – SEMESTER RULES`).
3. Lettered: `^[A-Z][.)]\s+[A-Z]` with at most 10 words and no final `.`.
4. All caps: at least 4 letters, 1 to 10 words, no lower case letter, no final `.`.
5. Isolated short line (DEV-003): the previous line is blank or absent (page start) and the next line is non-blank, 1 to 10 words, at least 4 letters, starts with a capital, does not end in `. : ; , ! ?`. Finds `Fee Refund Policy`.

`section` = the heading line, whitespace-normalised, cut at 80 characters on a word boundary (D-049). Before the first heading: the document title = file stem. A heading starts a new section; the section continues across pages until the next heading.

**Units.** Inside a section, lines are grouped into paragraphs (a blank line or a page change ends one; the page of a paragraph is the page of its first line). A line containing ` | ` is a table row and is its own unit, never split. A paragraph of at most `size` words is one unit; a longer one is split into sentences (`(?<=[.!?])\s+`); a sentence still longer than `size` is cut into `size`-word pieces (D-050). Lines inside a paragraph keep their newlines.

**Packing.** Units are added in order while the chunk stays within `size` words; the next unit that does not fit starts a new chunk. A chunk ends at a section end. The new chunk in the same section starts with the last `overlap` words of the previous chunk, reduced so that prefix plus the first unit still fits in `size` (never negative). No overlap after a chunk whose last unit is a table row (the prefix would start mid-row), and none across sections. A section whose whole text fits is one chunk, so a short clause is never merged with its neighbours (D-050).

**Id and page** (D-051): `<stem>-p<page:03d>-c<seq:03d>`; `stem` is `source` without extension; `page` is the page of the first unit that is not overlap; `seq` counts chunks in the document from 1. `Chunk.text` has no heading removal: the heading line stays in the text of the first chunk of its section.

**Words**: `len(text.split())` (AD-10). Chunk text never exceeds `size` words except a single table row longer than `size` (documented, tested).

**Known losses (go to `PIPELINE.md`):** headings embedded mid-line in interleaved two-column pages are missed; numbered list items inside a Roman section become their own sections (`7. Students who have ...`), so a chunk carries the item, not `VI – SEMESTER RULES`; annual-report tables have no headings, so their section is the nearest numbered or capitalised line before them.

## 6. Acceptance criteria

- [ ] **AC-1** Every chunk has non-empty `source`, `section`, `doc_version`, an int `page >= 1`, bool `superseded` copied from the document, and `Chunk.metadata()` returns exactly those five keys; ids match `^[a-z0-9._-]+-p\d{3}-c\d{3}$` and are unique within a document; two runs give identical ids and texts.
- [ ] **AC-2** No chunk mixes two documents (one `chunk` call, one document: `source` equal for all). No chunk exceeds `size` words, except a single table row longer than `size`.
- [ ] **AC-3** Neighbours in the same section share an overlap of up to `overlap` words (the start of chunk n+1 equals the tail of chunk n); the first chunk of a section starts with its heading and shares nothing with the previous section.
- [ ] **AC-4** A numbered sub-section of at most `size` words (the Generative AI policy shape: `5. Unacceptable Uses ...` with list items) is inside one chunk. Unit test on synthetic text; real Student Handbook check printed by `chunk_report.py`.
- [ ] **AC-5** Heading rules: each of the five rules has a positive and a negative test (years, table rows, `a)` list items, sentences ending in a period are not headings). A section name is at most 80 characters.
- [ ] **AC-6** Table rows (` | `) are never split; a long paragraph is split on sentences, an over-long sentence on `size` words. Empty or whitespace-only pages give no chunk; a document with no text gives `[]`. Invalid `size`/`overlap` raise `ValueError`.
- [ ] **AC-7** `scripts/chunk_report.py --size 400 --overlap 50` runs on all nine real documents (exit 0) and prints chunk count, words min/median/max, stored words, source words, amplification per document and overall; numbers recorded in the results register.
- [ ] **AC-8** `scripts/chunk_report.py --golden eval/golden.yaml` reports every golden `(source, section)` item matched by at least one chunk (using `section_matches`); the number of golden strings changed is logged.
- [ ] **AC-9** `make test && make lint` green; DEV-003 and D-049..D-051 recorded.

## 7. Test strategy and traceability

| AC | Level | Test or command | Needs |
| --- | --- | --- | --- |
| AC-1 | unit | `indexer/tests/test_chunk.py::test_metadata_and_ids`, `::test_ids_stable_across_runs` | nothing |
| AC-2 | unit | `::test_size_cap`, `::test_single_long_row_allowed`, `::test_source_constant` | nothing |
| AC-3 | unit | `::test_overlap_within_section`, `::test_no_overlap_across_sections`, `::test_no_overlap_after_table_row` | nothing |
| AC-4 | unit + manual | `::test_numbered_subsection_in_one_chunk`; `chunk_report.py --only student --sections` | real corpus for the manual part |
| AC-5 | unit | `::test_heading_rules` (parametrised positive and negative), `::test_section_truncated` | nothing |
| AC-6 | unit | `::test_table_rows_whole`, `::test_sentence_split`, `::test_hard_split`, `::test_empty_document`, `::test_bad_params` | nothing |
| AC-7 | manual | `.venv/bin/python scripts/chunk_report.py --size 400 --overlap 50` | `corpus/raw`, Tesseract |
| AC-8 | manual + unit | `chunk_report.py --golden eval/golden.yaml`; `indexer/tests/test_golden_set.py` keeps passing | `corpus/raw` |
| AC-9 | command | `make test && make lint` | nothing |

CI never needs the real corpus: unit tests use synthetic documents; AC-7 and AC-8 are measured locally and recorded in the results register and the test report.

## 8. Open questions

No question needs Zain: all three are answered with the recommended option (pre-approved). A conflict between the assignment and the architecture would stop the phase; none exists (DEV-003 extends the heading rules, it contradicts nothing in the assignment).

| # | Question | Options and recommendation | Decision entry | Answer |
| --- | --- | --- | --- | --- |
| Q1 | How are headings found, since the HTML pages have none of the three kinds in the architecture, and how long may a section string be? | A (rec.): add the isolated-short-line rule, tighten the numbered rule, cut at 80 chars. B: only the architecture rules (HTML sections become the page title, q07 and q15 cannot match). C: change `extract` to emit heading markers. | D-049 | A |
| Q2 | Do tiny adjacent sections merge, and how are over-long units, overlap and tables handled? | A (rec.): never merge sections; hard-split an over-long sentence; drop overlap after a table row. B: merge small neighbours (breaks one-section-per-chunk and AD-22 labelling). | D-050 | A |
| Q3 | Id and page details the architecture leaves open. | A (rec.): `seq` from 1; `page` = page of the first non-overlap unit. B: `seq` from 0; page of the overlap start. | D-051 | A |

## 9. Risks and assumptions

- Heading detection on messy text will misfire in places (two-column interleaving, OCR). Mitigation: rules are strict, errors only add or lose a section boundary, never lose text; the golden reconciliation and the report expose the result.
- Many tiny chunks (one per clause) lower storage amplification overhead but raise chunk count; measured in AC-7. If the count is too high for Chroma's 500 per add, `store` already batches (A-3).
- Isolated-line rule may promote a short sentence-fragment line in OCR text to a heading; accepted, harmless to recall.
- The golden `relevant` strings were provisional; reconciling changes the golden file (allowed by the plan). Questions keep their meaning; only the `section` strings and page comments change.

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit message |
| --- | --- | --- | --- | --- |
| 0 | (done) reject non-finite baseline | `eval/run_eval.py`, test | `make test` | `fix(runner): reject non-finite baseline recall_at_5` |
| 1 | Spec, plan, D-049..D-051 | this file, `OPEN_DECISIONS.md` | read | `docs(spec): phase 06 chunker spec and plan` |
| 2 | Tests first: heading rules, units, packing, ids, edges (red) | `indexer/tests/test_chunk.py` | tests fail with NotImplementedError | (with step 3) |
| 3 | `chunk()` | `indexer/pipeline/chunk.py` | `make test && make lint` | `feat(indexer): structure-aware chunker` |
| 4 | DEV-003 | `docs/architecture/deviations.md` | read | `docs(deviations): DEV-003 heading rules` |
| 5 | `chunk_report.py`, run on the real corpus | `scripts/chunk_report.py`, `Makefile` lint list if needed | AC-7 command | `feat(scripts): chunk_report with amplification` |
| 6 | Reconcile golden sections | `eval/golden.yaml` | `--golden` exit 0; `make test` | `fix(golden): section strings match real headings` |
| 7 | `PIPELINE.md` chunking rules, results register | docs | read | `docs(pipeline): chunking rules and measurements` |
| 8 | Tester rounds, report in section 12 | this file, tests | tester PASS | `test: phase 06 chunker report` |
| 9 | Plan, AI-USAGE, rubric ticks; PR | docs | `make test && make lint` | `docs(progress): phase 06 done` |

### 10.2 Test plan

Step 2 writes all unit tests before the code (synthetic `Document`s built in the test file). The tester runs `make test`, `make lint`, coverage for `pipeline/chunk.py`, the `chunk_report.py` commands (AC-7, AC-8), and tries to break it: empty pages, a heading as the last line, `overlap = size - 1`, a 5000-word line, tab and NBSP, Unicode headings, a page with only a table.

### 10.3 Rollback and risks

Each step is its own commit; revert the step. If heading rules over-fire on the real corpus, tighten rule 5 (drop it) and report q07 and q15 as lost; do not hide it.

### 10.4 Estimate

Spec 0.5 h, tests 0.75 h, code 0.75 h, report and corpus run 0.5 h, golden reconcile 0.5 h, tester and docs 1 h: about 4 h against 3 h in the work plan (+33%). The excess is the golden reconciliation and the isolated-line rule that the architecture did not foresee. No cut proposed.

## 11. Implementation notes

- Rules changed while measuring on the real corpus (all in DEV-003, none touch an acceptance criterion): a bare number needs a dot (page headers `16 Student Handbook 2026` were becoming sections); lines over 150 characters are never headings (an HTML list on one line); a heading may have one blank line below it (grading tables); a body-less short title hands its line to the next heading, which names the section (so `Attendance Requirements` above `1.21 ...` keeps the clause number in `section`); a line is split before a dotted clause number followed by a capital word (two-column Handbook text: `Freezing of Semester 4.25 The deadline`), excluding grades such as `4.00`. A roman-heading split was tried and dropped (it moved the answer of q05 under the wrong heading).
- The spec said the heading line stays in the first chunk of its section: true, including a carried title.
- `chunk_report.py --golden` is stricter than the spec asked: the chunk that holds the question's `expect` text must carry the golden section, not just any chunk of that section.
- Real corpus run, 400/50 (AC-7): 1044 chunks, amplification 1.04, per-document numbers in `docs/PIPELINE.md`. AC-8: 18 of 18 golden items matched; four section strings changed (q05 `7. Students who have missed classes due to any`, q06 `1. Mobile Phones, Smart Watches and all electronic`, q09 `Chapter-2 Faculty and Staff`, q10 `Mandatory periodic (six. monthly) deliverables of the start-up`).
- AC-4 on the real Student Handbook: GenAI sub-sections 1 to 7, 9, 10, 12 are each in one chunk (largest 392 words); 8 and 11 are not found as headings (mid-line in two-column text; known loss).
- Remaining real defect found, outside this phase: the Student Handbook and Academic Rules Handbook PDFs interleave two columns in `extract` (phase 4 handled only the Prospectus, D-044). Chunk labels are wrong where that happens. Suggested follow-up: column splits for the Handbook files, a small `COLUMN_SPLITS` entry plus a golden re-check.

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-05 | `make test`, `make lint`, `scripts/chunk_report.py --size 400 --overlap 50 --golden eval/golden.yaml`, 40-seed fuzz | FAIL | AC-1..9 pass; defect T-1 (medium): the mid-line clause splitter cut a table row (`Course \| 3.5 Credit hours \| x`), breaking "table rows never split". Fixed in 188d572 (lines with ` \| ` skip the split). Tester added `indexer/tests/test_chunk_edges.py`. |
| 2 | 2026-11-05 | same, plus 5 more break attempts on rows and clause splits | PASS | AC-1..AC-9 PASS; 183 indexer tests, 90 eval, 7 api; chunk_report exit 0, 0 golden misses, TOTAL 1044 chunks, 85 094 stored, 82 099 source words, amplification 1.04. `pipeline/chunk.py` 100% line coverage (round 1, `coverage` outside the repo; pytest-cov is not installed). |

Observations from the tester, no action: a one-line numbered clause with no final period and no body is carried into the next section by the DEV-003 title rule (pinned by a test); GenAI sub-sections 8 and 11 and some Student Handbook labels are lost to two-column interleaving (known loss, section 11).

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | 2026-11-05 | Zain (pre-approved) | no gate in this session |
| Tester verdict PASS | 2026-11-05 | independent subagent | rounds: 2 |
| Merged | 2026-11-05 | Claude (pre-approved by Zain) | PR #10 |
