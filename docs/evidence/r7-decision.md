# R7 release decision: chunk size and overlap (D-120)

Baseline: live index `rahbar`, 400/50, Batch A and B, 50 questions, `eval/results/suite-20261121T021833Z-baseline-ab.json`.
Candidates are full re-indexes into their own collections, served by `api-candidate`, scored by the same Job and the gate in `eval/gate.yaml` (limits and their reasons are in that file). All tables: `eval/results/compare-cand-*.txt`; gate outputs: `eval/results/gate-cand-*.txt`.

| Candidate (chunk/overlap, collection, chunks) | recall@5 | MRR | faithfulness (supported) | abstention | citation validity | p95 s | Gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline 400/50 (`rahbar`, 1006) | 0.7949 | 0.7564 | 0.9000 | 0.9091 | 1.000 | 181.7 | |
| 100/0 (`rahbar_bad`, 1428) | 0.7949 | 0.7308 | 0.8214 | 1.0000 | 1.000 | 128.7 | FAIL, exit 1 (faithfulness -0.079, limit -0.05) |
| 300/50 (`rahbar_cand`, 1041) | 0.7949 | 0.7436 | 0.8966 | 1.0000 | 1.000 | 188.6 | PASS, exit 0 |
| 600/100 (`rahbar_c600`, 977) | 0.7949 | 0.7564 | 0.9310 | 0.9091 | 1.000 | 179.8 | PASS, exit 0 |

## What the gate said, and an honest note on the limits

- The first gate run used the placeholder limits (faithfulness at least 0.70, an absolute floor chosen from the 0.833 Batch-A-only baseline). With them candidate 100/0 passed 6 of 6 rules (`eval/results/gate-cand-100-0-initial-limits.txt`, exit 0): 0.821 is above 0.70 although it is 7.9 points below the new baseline of 0.900.
- The faithfulness rule was then changed to `not_below_baseline_by 0.05`. The reason is measured noise, not the candidate: two identical runs differ by one answer in 27 (0.033 to 0.037, `docs/evidence/a3/f3-stochasticity.txt`), so 0.05 allows about 1.5 answers of noise, while an absolute floor ignores the baseline moving (D-134). The limit was set after the 100/0 result was seen, so the 100/0 failure is a consequence of a justified limit, not an independent blind test. Both outputs are committed. No other limit was changed (only the justification text).
- Retrieval is deterministic (two-run difference 0.0), so any recall or MRR change is real. The three candidates keep recall@5 unchanged; only 100/0 and 300/50 lose a little MRR (-0.026, -0.013), inside the 0.03 limit.
- Latency p95 is noisy on this CPU (184.5 s vs 113.1 s on identical runs), so p95 has only the absolute 300 s limit.

## Decision

- **Reject 100/0.** Faithfulness fell from 0.900 to 0.821 (below the limit 0.850), expected-text hit 0.714 to 0.667, recall@5 with typos 0.795 to 0.744, and live probes on `rahbar_bad` showed one question answered wrongly (41 instead of 19) and one abstained (`docs/evidence/a3/r9-bad-release.txt`). The metric that rejected it is `e2e.faithfulness_supported_rate`. Tiny chunks lose the sentence context the answer needs.
- **Release 600/100 (`rahbar_c600`).** It passes every rule and is the best measured: faithfulness +0.031 (0.931), expected-text hit +0.027, MRR and recall unchanged, citations valid, p95 179.8 s against 181.7 s. The gain is small: it is about one answer in 30, within the measured noise of two answers, so the honest statement is "no regression, a possible small gain", not a proven improvement. 977 chunks is also fewer vectors than the baseline's 1006.
- **300/50 (`rahbar_cand`) also passes** (faithfulness -0.003, abstention +0.09 on 11 questions, which is one question). It was the first passing candidate, so the R9 release rehearsal (rolling update, bad release, undo) was recorded on it before 600/100 had been measured. The mechanics are identical for any collection; `make release COLLECTION=rahbar_c600` is the production step.
- **Which metric would have made us reject a candidate:** `e2e.faithfulness_supported_rate` below baseline minus 0.05 (the one that fired), then `component.clean.recall_at_5` below baseline minus 0.02 (a re-chunking that splits the answer sentence would hit retrieval first), then `e2e.citation_validity` below 0.95 (a hard invariant).
- The live Deployment was returned to the original collection `rahbar` at the end of the rehearsal (`docs/evidence/a3/r9-rollout-undo.txt`); the production release of 600/100 is left to Zain.
