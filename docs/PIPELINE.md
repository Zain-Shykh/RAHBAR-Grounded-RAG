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
Size and overlap you shipped, storage amplification (stored tokens / original tokens),
and the three configurations you measured:

| Size (tokens) | Overlap (tokens) | recall@5 | Chunks stored |
| --- | --- | --- | --- |

## Embedding
Model, vector dimension, where the pin lives, how the API checks it.

## Semantic cache
Thresholds you tried, the false hit that ruled one out, the one you shipped.

## Evaluation method
How recall@k matches retrieved passages to golden ones (by source and section? by chunk id?).
