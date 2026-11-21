# D5: root cause of one abstained answer, from a trace only (R3-D5-1)

Question g19 "How many courses can a student enrol in during an ordinary semester?" (kind answerable, outcome abstained in `eval/results/suite-20261121T001033Z-baseline.json`). Trace `e994ef9c149940ac84e9cace96fb17cb` (`python scripts/trace_tool.py show e994ef9c149940ac84e9cace96fb17cb --dir traces/cluster`, file `traces-20261121-api-7966bb7df4-l7k72.jsonl`).

1. Floor and filter are not the cause: `floor.best_score` 0.8073 against `floor.value` 0.7 (`passed: true`), `scope.where` `{"superseded": false}` (key `current`), every retrieved chunk has `superseded=False`.
2. The rails did not drop evidence: `shown to the model` equals `retrieved` (5 of 5 chunks), `guardrails` citation_check `pass` on attempt 1.
3. The right evidence was in the prompt: chunks `student-handbook-jun-2026-p010-c037` (rank 3, 0.7993) and `-p011-c045` (rank 4) carry the text "recommended course load per semester (5 courses for BS and 3 courses for MS)" as EVIDENCE 3 and 4.
4. The model ignored it: response `answered_from_context: false`, `outcome: abstained`, answer "not explicitly stated in the provided evidence", `model.attempts` 1, `temperature` 0.2, llama3.2:3b (prompt hash verified OK).
5. Cause: the prompt carried the evidence and the model ignored it (`answered_from_context: false` with the text of EVIDENCE 3 and 4 in `prompt`). Not floor, not filter, not rail. Note: `retrieved` also repeats the summer-rule chunk at ranks 1 and 2; not the cause here. (`traces/cluster/` is a local `make traces-pull` copy, not committed.)
