# Phase 16 spec and plan: Failure experiments B and D

| | |
| --- | --- |
| Phase | 16 (extra RAG-lane phase, `docs/IMPLEMENTATION_PLAN.md`) |
| Work plan task | Z-14 extended (R-FAI-B, R-FAI-D) |
| Branch | `feat/rag-z16-failure-bd` |
| Stage | IMPLEMENTING |
| Started | 2026-11-07 |
| Approved (spec and plan) | 2026-11-07, pre-approved by Zain (no gate for this run) |
| Depends on | phase 13 (`docs/FAILURE-ANALYSIS.md`, method D-83 to D-85) |

## 1. Objective

Run the two missing experiments of `docs/requirements.md` 5.5, B (chunking) and D (prompt), on the real stack with the method and rigour of A, C, E, F, so that all six stages are measured and documented. No default, corpus or baseline changes.

## 2. Context

- Architecture 5.14 (map of breaks), 5.4.2 (chunking, AD-10: unit is words), 5.7.1 (prompt), 5.7.3 (validation), 5.6.3 (floor).
- Requirements R-FAI-B, R-FAI-D, R-FAI-0. Rubric: each stage needs a measured number or a quoted log line.
- Decisions: D-015, D-83 (no experiment flag in the repo), D-84 (separate collection), D-85 (flush the cache), D-105 and D-106 (this phase).
- Code: `indexer/pipeline/chunk.py` (`CHUNK_SIZE`, `CHUNK_OVERLAP` env already exist), `api/app/services/prompt.py` (`SYSTEM`, `build_messages`), `eval/retrieval_only.py`, `eval/run_eval.py`.

## 3. Scope

**In scope**

1. B: real indexer, full corpus, `CHUNK_SIZE=100 CHUNK_OVERLAP=0 CHROMA_COLLECTION=rahbar_exp_b` (env only). Compare with the live 400/50 index.
2. D: throw-away script that patches `app.services.prompt.SYSTEM` in memory (removes the "use only the evidence" instruction), runs the real `answer_question` pipeline; compare with the intact prompt on the same questions.
3. Docs: `FAILURE-ANALYSIS.md` (B and D, six of six), `rubric_checklist.md`, `PIPELINE.md`, `ENGINEERING-NOTES.md`, `FINAL-WALKTHROUGH.md`, `AI-USAGE.md`, plans; raw captures `docs/evidence/k16-*.txt`.

**Out of scope**

Any fix (recommendations only), any change to defaults, `eval/baseline.json`, `eval/results.json`, corpus, `k8s/`, `ui/`, `.github/`, the cluster workloads.

## 4. Interfaces and contracts

No new code in the repo, no new config key. Experiment tooling is throw-away scripts in the tmp directory (D-83); the raw outputs are saved as evidence. Env used: `CHUNK_SIZE`, `CHUNK_OVERLAP`, `CHROMA_COLLECTION`, `EMBED_MODEL`, `TOP_K`, `RELEVANCE_FLOOR`, `LLM_PROVIDER`, `LLM_TIMEOUT_SECONDS`.

## 5. Behaviour and design details

| Stage | Break | Measures |
| --- | --- | --- |
| B | indexer with 100-word chunks, no overlap, into `rahbar_exp_b`, full corpus (the 13-minute class job; the whole corpus is used so counts compare 1:1) | chunk count and size histogram against 981 at 400/50 (indexer `chunked total` line, collection metadata, `rahbar_index_info`-equivalent `chunk_count`); `eval/retrieval_only.py recall` against both collections (recall@3, @5, by type); at least 3 questions whose answer spans a sentence or clause boundary: the retrieved chunk text, whether the answer chunk holds the whole answer, the answer and citation through the real pipeline |
| D | in-memory removal of the instruction lines from `SYSTEM`; `answer_question` real pipeline, `llama3.2:3b`, cache flushed | in-corpus questions; out-of-corpus questions whose retrieval passes the floor (searched with `retrieval_only ask`); questions from training knowledge; `answered_from_context`, citation validity, `bad_citation`/`invalid_output` fallbacks, whether the answer uses outside knowledge; same questions with the intact prompt |

Rules: report what happened, including "no visible degradation" (as with F). Unit note: the chunk size unit is words (AD-10); "100-token" in R-FAI-B is 100 words here, stated in the write-up. Diagnosis written as if not caused on purpose. Remedy is a recommendation only.

## 6. Acceptance criteria

- [ ] **AC-1**: `docs/FAILURE-ANALYSIS.md` has B and D in the template (what we broke, symptom, diagnosis as if not caused, stage, remedy, the number), from real runs; intro says six of six; restore check updated.
- [ ] **AC-2**: B has chunk counts, recall@3/@5 against the experiment collection and the baseline, and at least 3 boundary-spanning questions with the retrieved text shown.
- [ ] **AC-3**: D has the comparison with the intact prompt on the same questions, with in-corpus, out-of-corpus and training-knowledge questions.
- [ ] **AC-4**: After the last step, `eval/retrieval_only.py recall` on the live collection equals `eval/baseline.json`; `git diff dev -- api indexer eval` is empty.
- [ ] **AC-5**: `python scripts/check_submission.py` and `scripts/check_numbers.py` stay green; `make test && make lint` green; `rahbar_exp_b` deleted, containers and Ollama stopped.

## 7. Test strategy and traceability

| AC | Level | Command |
| --- | --- | --- |
| AC-1..3 | manual, tester reads the docs against `docs/evidence/k16-*.txt` | |
| AC-4 | integration | `python eval/retrieval_only.py recall`; `git diff dev --stat -- api indexer eval` |
| AC-5 | script | `python scripts/check_submission.py`, `make test && make lint` |

## 8. Open questions

None blocking. Decisions D-105 (B on the full corpus; 100 words = "100 tokens"), D-106 (D by in-memory patch of `SYSTEM`).

## 9. Risks and assumptions

- Disk 1.6 GB free at start (5.1 GB after builder prune): the experiment collection is a few tens of MB; deleted at the end.
- Model calls take 15 to 150 s; `LLM_TIMEOUT_SECONDS=300`; one Ollama job at a time (the embedding job runs first).
- 3B model with schema-constrained output may keep citing correctly without the instruction; reported as measured.

## 10. Plan

| Step | What | Verify |
| --- | --- | --- |
| 1 | This spec, decisions | read |
| 2 | B: index, recall, boundary questions | `docs/evidence/k16-b-*.txt` |
| 3 | D: patched prompt vs intact | `docs/evidence/k16-d-*.txt` |
| 4 | Restore check, cleanup | recall equals baseline, `git diff` empty |
| 5 | Docs | `check_submission.py`, `check_numbers.py` |
| 6 | Tester, PR, merge | |

## 11. Implementation notes

(filled during implementation)

## 12. Test report

(filled by the tester)

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan | 2026-11-07 | Zain (pre-approved) | |
