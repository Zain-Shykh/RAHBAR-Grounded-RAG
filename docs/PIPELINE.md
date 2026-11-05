# Indexing and retrieval pipeline

<!-- STARTER-TODO(3.1, 3.3, 5.2): fill each section with your numbers, then delete this comment. -->

## Extraction
PDF text comes from `pdfplumber` (default mode: a table row stays on one line). A page with fewer than 30 non-space characters is OCR'd (`pdf2image` 200 dpi, one page at a time, `pytesseract` `eng`). HTML uses the stdlib parser, keeps only `div.main-content`, drops scripts, navigation, breadcrumb and footer, and writes each table row as one line with ` | ` between cells. Repeating headers and footers (a line in the top or bottom three lines of at least half the pages, compared with digits ignored) are removed; numbered clause lines never are.

**Which documents needed OCR** (measured by `scripts/check_golden_extract.py`, 41 pages, about 88 s on the host):

| Document | Pages | OCR'd |
| --- | ---: | ---: |
| Undergraduate Academic Rules (Aug 2023) | 26 | 24 (pages 2 to 25: text was converted to outlines) |
| Faculty Entrepreneurship and Start-ups Policy | 8 | 8 (scanned) |
| Academic Rules Handbook (Jun 2026) | 58 | 5 (cover and back pages) |
| Student Handbook (Jun 2026) | 64 | 4 (cover and back pages) |
| the other five documents | | 0 |

**Before and after (a table row).** Annual Report 2023-24, PDF page 13, "Faculty Summary". Plain `pdftotext` puts one value per line, so the columns are lost ([before](examples/annual-report-2023-24-p13-before.txt)); the extract stage keeps `Islamabad 19 14 46 16 83 50 8 236` on one line ([after](examples/annual-report-2023-24-p13-after.txt)).

**Multi-column page.** The Prospectus 2026 is three columns; read line by line, the sentence "Minimum attendance requirement for Graduate and Post Graduate degree programs are 75%" is cut by unrelated text. A per-file table of gutters (`COLUMN_SPLITS`, x = 220 and 397) reads each column in turn; the sentence is then contiguous (golden q11).

**What could not be recovered**
- OCR misreads some clause numbers (`6:1.` for `6.1`, `92.` for `9.2`) and the policy's numbering sits apart from its text (page 2 lists `6.` to `7.2.` before the paragraphs). Also `six. monthly` (golden q10). Not repaired: clause-number repair was out of scope; the loss is left visible.
- OCR of cover and back pages may give junk lines; no question depends on them.
- Prospectus: the page header is cut at the gutters (`Academic R`, `ules and Regulations`); words the PDF itself spaces badly (`pr ograms`, `Semesterstartsin`) stay; anything spanning a gutter is split.
- The Student Handbook PDF repeats some pages (PDF pages 30 and 31 are identical); both are indexed, so a passage may appear twice.
- Annual Report tables: rows stay on one line, but a header wrapped over three lines stays as three lines above the rows.

## Cleaning
Applied to each page, in order: Unicode NFKC and whitespace normalisation (zero-width characters, soft hyphens, form feeds, non-breaking spaces); repair of letter-spaced lines (a mostly single-character line with a run of five or more single characters is joined, so `7 5 %` becomes `75%`; word spaces inside the run are lost); joining of a word hyphenated across a line end when the next line starts lowercase; removal of lines that are only a page number (`12`, `Page 3 of 85`, `- 7 -`); collapse of three or more blank lines to one.

**Deliberately not stripped:** clause numbers and heading numbering, even when OCR mangled them (`92.` for `9.2`). Dropping them would hide the loss and break exact-term questions such as "clause 1.21". Table separators ` | ` and heading lines are also never touched.

## Chunking
Unit: **words** (whitespace split, AD-10). Defaults 400 words and 50 overlap; the shipped pair comes from the three runs below (phase 12). Code: `indexer/pipeline/chunk.py`; measured with `scripts/chunk_report.py`.

**Order:** headings first, then blank-line paragraphs, then sentences, then `size`-word pieces for a sentence that is still too long; units are packed greedily up to `size`. A table row (` | `) is one unit and is never split. Overlap is the last `overlap` words of the previous chunk, only inside the same section, and never after a table row. A short clause is never merged with its neighbour, so a chunk's `section` is always true and the median chunk is small (26 to 117 words).

**Headings** (first match wins, details and reasons in DEV-003): numbered clause `4.3 The ...` or `5. Title` (a capital next, line at most 150 characters; `1)` items and page headers like `16 Student Handbook 2026` do not count); roman `VI – SEMESTER RULES`; lettered `A. Eligibility`; all-caps line; an isolated short line (blank above, text below, no final punctuation), which finds the HTML headings `Fee Refund Policy`. `section` is the heading line, whitespace-normalised, cut at 80 characters. Before the first heading it is the file stem. A bare title with no body hands its line to the next section. A line is split before a dotted clause number with a capital word after it, because the two-column pages of the Academic Rules Handbook put two columns on one line.

**Chunk id:** `<stem>-p<page:03d>-c<seq:03d>`, `seq` from 1 over the document; `page` is the page of the first new (non-overlap) text.

**Known losses.** The Handbooks were two-page spreads read across the gutter; they are split per page now (D-052), so mid-line headings are recovered; numbered list items inside a roman section become their own sections (the chunk is labelled `7. Students who ...`, not `VI – SEMESTER RULES`); OCR text puts clause numbers on their own lines, so the policy sections are named by their title. Annual-report tables have no heading and are labelled with the chapter line above them. The Student Handbook PDF repeats some pages, so some chunks exist twice. Four golden section strings were changed to the real labels (q05, q06, q09, q10).

**Measured at 400 / 50 on the nine real documents** (`scripts/chunk_report.py`, 2026-11-05): 1044 chunks; stored words 85 094 over 82 099 source words, **storage amplification 1.04** (1.00 for the Aug 2023 rules, Prospectus, fee, grading and policy; 1.01 Academic Rules Handbook; 1.04 Student Handbook; 1.03 and 1.06 the Annual Reports). Median chunk size 25 words (Aug 2023 rules) to 117 (Annual Report 2023-24); the largest is 400.

**Chunking experiment (phase 12, 2026-11-05).** Same nine documents, same golden set (18 questions, 16 with relevant passages), real `nomic-embed-text`, scope `current`; recall from `eval/retrieval_only.py recall` (the `retrieved` list the API builds before the model is called, scored by the same `run_eval.summarise` as the gate; raw output in `eval/tuning/`). Size and overlap are in words (AD-10), not tokens.

| Size (words) | Overlap (words) | recall@3 | recall@5 | recall@5 by type (ordinary / version / exact / injection) | Chunks stored | Amplification |
| ---: | ---: | ---: | ---: | --- | ---: | ---: |
| 200 | 25 | 0.875 | 0.875 | 0.909 / 1.0 / 0.5 / 1.0 | 1103 | 1.06 |
| **400** | **50** | **0.875** | **0.875** | 0.909 / 1.0 / 0.5 / 1.0 | **981** | **1.04** |
| 600 | 100 | 0.875 | 0.875 | 0.909 / 1.0 / 0.5 / 1.0 | 952 | 1.03 |

**Shipped: 400 / 50.** The three configurations are indistinguishable on recall and on the score of every question to within 0.011 (q04 0.889 at 200/25, 0.878 at the others), and they miss the same two questions (q10 and q14, see the exact-term finding in the results register). The reason is the chunker, not luck: it splits at headings first, so most chunks are one clause (median 25 to 117 words) and the size limit only matters for the few long sections; a 600-word limit changes 3% of the chunks, a 200-word limit 12%. With recall tied, nothing measured justifies leaving the architecture default: 600/100 stores 3% fewer chunks but lengthens the worst-case prompt by half on a CPU model whose latency is prompt-bound, and 200/25 adds 12% more chunks and more duplicated text for no gain (D-81). The conclusion for the design is that on this corpus heading structure matters more than the size knob.

## Embedding
Model, vector dimension, where the pin lives, how the API checks it.

## Semantic cache
Thresholds you tried, the false hit that ruled one out, the one you shipped.

## Evaluation method
How recall@k matches retrieved passages to golden ones (by source and section? by chunk id?).

## Embed and store (phase 7)

**Pin.** `EMBED_MODEL` (ConfigMap, read by the indexer and the API) is `nomic-embed-text`, 768 dimensions, cosine. The indexer writes `embed_model` and `dimension` into the collection metadata; the API compares at `/readyz`. Embedded text is `search_document: <section>\n<text>`; the stored document is the chunk text only. CI uses `hashing-bow-768` (offline, same dimension).

**Store.** Stage-and-swap: build `rahbar_next`, check `count()`, delete `rahbar`, rename. A failure before the delete leaves the live index. Collection metadata: `hnsw:space`, `embed_model`, `dimension`, `index_id`, `built_at`, `chunk_count`, `chunk_size`, `chunk_overlap`, `doc_versions`. Record metadata: `source`, `section`, `page`, `doc_version`, `superseded`.

**Real corpus at 400/50.** 981 chunks: Academic Rules Handbook 238, Student Handbook 245, Aug 2023 rules 152, Annual Report 2023-24 182, Annual Report 2019-20 65, Prospectus 44, faculty policy 40, grading page 8, fee page 7. Amplification 1.04. Wall time 9 min 39 s (embedding 422 s), indexer peak memory 438 MB; Ollama runs on the host. Re-running replaces the collection and changes `index_id`.
