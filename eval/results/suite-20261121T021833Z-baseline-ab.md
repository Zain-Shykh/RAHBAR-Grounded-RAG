# Suite result baseline-ab (20261121T021833Z)

index `20261121T005113Z-a45667`, embed `nomic-embed-text@0a109f422b47`, questions 50, subset `all`, git `unknown`

## Module level (embedding)

| metric | value |
| --- | --- |
| paraphrase mean cosine (15 pairs) | 0.791 |
| unrelated mean cosine (15 pairs) | 0.525 |
| gap | 0.266 |
| embed time per chunk, median / p95 ms (100 chunks) | 285.3 / 1100.7 |
| memory per embedding (float32 bytes) | 3072 |
| determinism, largest abs difference | 0.00e+00 |

## Component level (retrieval, answerable questions)

| metric | clean | with typos | change |
| --- | --- | --- | --- |
| recall@3 (n=39) | 0.795 | 0.769 | -0.026 |
| recall@5 (n=39) | 0.795 | 0.795 | +0.000 |
| MRR (n=39) | 0.756 | 0.676 | -0.080 |
| nDCG@5 (n=39) | 0.766 | 0.706 | -0.060 |
| retrieval latency median / p95 ms | 205.8 / 350.7 | | |

## End-to-end level (answers)

| metric | value |
| --- | --- |
| faithfulness, support overlap mean (answered n=30) | 0.879 |
| faithfulness, share supported at 0.6 | 0.900 |
| abstention correctness (n=11) | 0.909 |
| false abstention rate (answerable) | 0.256 |
| citation validity (39 citations) | 1.000 |
| expected-text hit rate | 0.714 |
| fallback rate | 0.020 |
| latency p50 / p95 seconds | 54.4 / 181.7 |
