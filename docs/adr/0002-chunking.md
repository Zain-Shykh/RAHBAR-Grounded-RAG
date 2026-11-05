# ADR 0002: Structure-first chunking, 400 words with 50 overlap

## Status
Accepted · 2026-11-05 (phase 12 measurement, D-81)

## Context
Retrieval quality starts at the chunk. The nine documents are a mixed bag: numbered clauses (Academic Rules Handbook, Aug 2023 rules), roman-numbered parts (Student Handbook), a scanned policy whose OCR separates clause numbers from their text, a three-column prospectus, HTML fee and grading pages with tables, and two annual reports full of table rows. A fixed-size window would cut "clause 4.25" in half and put the withdrawal deadline and its neighbour into one vector. The golden set asks about single clauses (q12 withdrawal 4.25, q14 clause 1.21), so a chunk that is one clause is what we want to retrieve, and its `section` label is what the citation check compares against (`api/app/services/validate.py`, `citation_matches`).

The assignment requires three measured (size, overlap) configurations on the golden set and a justified choice; a number with no measurement scores zero (R-IDX-7).

## Decision
`indexer/pipeline/chunk.py` splits at **headings first**, then blank-line paragraphs, then sentences, then `CHUNK_SIZE`-word pieces for a sentence that is still too long. Units are packed greedily up to the size. A table row (` | `) is never split. Overlap is the last `CHUNK_OVERLAP` words of the previous chunk, only inside the same section and never after a table row. A short clause is never merged into its neighbour, so a chunk's `section` is always true. Size and overlap are counted in **words** (AD-10), not tokens. Ids are stable: `<source stem>-p<page:03d>-c<seq:03d>` (AD-28).

**Shipped: 400 words, 50 overlap.** Measured on the real corpus with the real `nomic-embed-text` and the 18-question golden set (`eval/retrieval_only.py recall`, raw output in `eval/tuning/`):

| Size / overlap | Chunks | Amplification | recall@3 | recall@5 | ordinary / version / exact / injection |
| --- | ---: | ---: | ---: | ---: | --- |
| 200 / 25 | 1103 | 1.06 | 0.875 | 0.875 | 0.909 / 1.0 / 0.5 / 1.0 |
| **400 / 50** | **981** | **1.04** | **0.875** | **0.875** | 0.909 / 1.0 / 0.5 / 1.0 |
| 600 / 100 | 952 | 1.03 | 0.875 | 0.875 | 0.909 / 1.0 / 0.5 / 1.0 |

All three miss the same two questions (q10, q14) and score every question within 0.011 of each other. I expected the size to matter; it does not, because the chunker splits at headings first, so most chunks are one clause (median 25 to 117 words) and the size only decides the few long sections: 600 words changes 3% of the chunks, 200 words 12%. With recall tied, the choice follows cost: 600/100 stores 3% fewer chunks but lengthens the worst-case prompt by half on a CPU model whose latency is prompt-bound (36 to 49 s per question already), and 200/25 stores 12% more chunks and more duplicated text for no gain. The architecture default stays.

## Options considered
- **Fixed-size sliding window (no structure).** Simple and the lecture default, but it ignores clause boundaries and would make the `section` label false for half the chunks. Not measured here, because it cannot satisfy the citation rule; rejected on design.
- **Tokens instead of words.** More exact against the model's context, but needs a tokenizer in the indexer image and ties the unit to one model; words are enough on this corpus (amplification measured the same way). Rejected for dependency cost.
- **Merge short clauses into their neighbours.** Fewer, larger chunks, but one vector then answers two clauses and the label is wrong for one of them. Rejected.
- **Larger overlap or a parent-document retriever** to fix q10 and q14. These two are not size problems (see below), so more overlap would only add duplicated text.

## Consequences
- Storage amplification is 1.04 (75 644 stored words over 73 051 source words, `scripts/chunk_report.py`): overlap costs 4%, not the 25% a blind 50-word overlap on 200-word windows would.
- The chunk count is 981; the indexer embeds at 422 s for all of them; a change of size needs a full re-index (stage-and-swap, ADR 0001).
- The recall plateau at 0.875 is not a chunking limit. q14 ("clause 1.21") is a retrieval miss because the embedding gives the number almost no weight (1.21 and 1.22 sit at cosine 0.927), and q10 is a scanned policy whose OCR named the section by title; both need hybrid (lexical plus vector) retrieval, not built here (architecture 1.2, D-006). More chunk tuning will not move them.
- The heading rules are heuristics with known losses (list items inside a roman section become their own sections; OCR clause numbers like `92.` for `9.2`; duplicated Student Handbook pages 30 and 31). They are listed in `docs/PIPELINE.md`. Watch: a new document type with no heading markers falls back to paragraphs and loses the `section` guarantee.
