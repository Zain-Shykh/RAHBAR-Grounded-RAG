# E2: uncovered live queries grouped by topic

Source: `docs/evidence/a3/e1-coverage-before.txt` (`eval/results/coverage-before-20261121T010202Z.json`), threshold 0.72 (`e2-coverage-calibration.txt`), 34 golden questions, 40 live queries.

Before: 12 of 40 covered (share 0.300, exit code 1); in-domain share 0.429 (12 of 28); no off-domain query was covered.
The golden set was built from the Assignment 02 questions and the Batch A paraphrases. It missed whole areas that students ask about.

| Group | Live ids | Topics (expected_topic) | Corpus has an answer? | Action (E4) |
| --- | --- | --- | --- | --- |
| Academic rules | l03, l15, l16, l17, l18, l26, l27, l28, l08 | withdrawal and refund, repeating courses, academic warning, plagiarism, leave of absence, scholarships, degree requirements, rechecking, generative AI policy | yes (academic rules handbook, student handbook, Batch B exam guidelines) | g35 repeating, g36 warning, g37 freeze, g42 rechecking, g43 generative AI, g45 unfair means |
| Batch B services | l19, l20, l21, l22, l23, l25 | library fines, lab emergency, fee instalments, late fee, transcripts, transport | yes for l19, l20, l21, l22, l25 (b01, b02, b10, b06); transcripts: no | g38, g39, g40, g41, g44 answerable; g48 transcripts unanswerable |
| Campus life, no corpus support | l24, l37, l36, l38, l39, l34 | sports teams, parking, wifi, internships, student societies, careers | no (best retrieval is unrelated text, checked with POST /api/retrieve) | g46 parking, g47 cricket team, unanswerable by design |
| Off-domain | l29, l30, l31, l32, l33, l35, l40 | weather, cricket score, bitcoin, food, entertainment, programming, general knowledge | not a university topic | g49 weather, g50 programming, unanswerable |

Reading: the gap is real, not forced. 16 in-domain queries had no close golden question; the largest cause is Batch B topics (library, lab, fees, exams, transport) that have only one or two golden questions each, and the A02 rules areas with one question each. The topic labels (`expected_topic`) were taken as the grouping; the nearest golden id in the output shows the uncovered queries sit at 0.46 to 0.71 from their nearest question, below T = 0.72.

After (`e1-coverage-after.txt`, `eval/results/coverage-after-20261121T011214Z.json`): 16 new golden questions g35 to g50, 27 of 40 covered, share 0.675 (in-domain share 0.857, 24 of 28). Still below the 0.85 target (exit code 1): 13 uncovered remain, 9 off-domain or without corpus support (l30, l31, l32, l33, l34, l36, l38, l39, l40) plus l03 (0.707), l22 (0.699), l26 (0.719), l27 (0.707) that sit just under T. Not forced further: more unanswerable questions would raise the share without testing the system more.
