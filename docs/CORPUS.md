# Corpus

Source: FAST-NUCES public website (nu.edu.pk) · Documents: 9 (7 PDF, 2 HTML) · Pages: 279 PDF pages, plus 2 HTML pages

Every document is public. Nothing is behind a login. The files are not committed: `corpus/sources.yaml` lists each URL with its `doc_version` and `superseded` flag, and `corpus/MANIFEST.md` records each file's size and SHA-256. Run `make fetch` to download them and `python corpus/fetch.py --verify` to check the hashes. Downloaded 2026-11-04.

| File | Pages | Version | Superseded |
| --- | ---: | --- | --- |
| Undergraduate Academic Rules (Aug 2023) | 26 | 2023-08 | yes |
| Academic Rules Handbook (Jun 2026) | 58 | 2026-06 | no |
| Prospectus 2026, Academic Rules and Regulations | 5 | 2026 | no |
| Student Handbook (Jun 2026) | 64 | 2026-06 | no |
| Annual Report 2019-20 | 33 | 2019-20 | no |
| Annual Report 2023-24 | 85 | 2023-24 | no |
| Faculty Entrepreneurship and Technical Start-ups Policy | 8 | 2022-05 | no |
| Fee Structure page (HTML) | n/a | 2026-27 | no |
| Grading page (HTML) | n/a | 2026 | no |

| # | Required property | Document(s) that provide it | Evidence or notes |
| --- | --- | --- | --- |
| 1 | At least 6 documents, 40 pages | All 9 documents | 7 PDFs total 279 pages (`pdfinfo`), plus 2 HTML pages |
| 2 | Two versions of one policy | Undergraduate Academic Rules Aug 2023 and Academic Rules Handbook Jun 2026 (also the Prospectus 2026 rules, and two Annual Reports) | The 2023 rules are `superseded: true` with `doc_version: 2023-08`. The 2026 Handbook is current, `doc_version: 2026-06`. The clause numbers differ: attendance is 1.22 in 2023 and 1.21 in 2026. The retriever filters on `superseded` so it quotes the current clause unless the user asks about an older version |
| 3 | Scanned, image-only PDF | Faculty Entrepreneurship and Technical Start-ups Policy (8 pages), and the body pages of the Aug 2023 rules | The policy has an empty `pdffonts` list and no extractable text on pages 1 to 5. The 2023 rules (made in CorelDRAW) have text only on page 1 and page 26; pages 2 to 25 return no text although the PDF lists 3 fonts, so the text was probably converted to outlines. Tesseract 5.3.4 at 200 dpi read both well (the 2023 rules page 8 came out clean, clause numbers included). On the policy, OCR misreads some clause numbers (for example 9.2 read as `92.`), which is a loss we must document |
| 4 | A table with real information | Fee Structure page and Grading page (HTML); Annual Reports (PDF) | Fee page has 3 tables (fee per program, refund timeline and percentage). Grading page has 5. The PDF tables in the Annual Reports are not yet checked |
| 5 | Long definitions | Student Handbook (Jun 2026), section XII "Policy on Generative AI Based Tools" | Starts at line 1730 of the `pdftotext -layout` output, with numbered sub-sections. A fixed-size chunker will cut these in half |
| 6 | A deliberately absent topic | Hostel rules | We did not download the Prospectus "Transport and Hostel Facilities" PDF. Students plausibly ask about hostel rules, fees and timings. The Student Handbook only mentions "In-Campus Hostel" in passing (line 1633), so golden questions must ask for specific hostel rules, not whether hostels exist |
| 7 | Exact-term content | Academic Rules Handbook 2026, Aug 2023 rules, fee page | Clause numbers (attendance 1.21 in 2026, 1.22 in 2023), minimum CGPA 2.00 for graduation, 130 credit hours for a Bachelor's degree, fees per program |

## Known risks

- The Aug 2023 rules depend on OCR for pages 2 to 25. The version pair is only as good as that OCR.
- The Annual Reports are only weakly useful as a version pair: the corpus has two editions (2019-20 and 2023-24), not the five on the site.
- The Prospectus 2026 rules overlap the 2026 Handbook with different clause numbers. This is good test material for exact-term retrieval, and a trap for duplicate answers.
