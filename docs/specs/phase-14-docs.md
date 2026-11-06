# Phase 14 spec and plan: Documents and ADRs

| | |
| --- | --- |
| Phase | 14, from `docs/IMPLEMENTATION_PLAN.md` |
| Work plan task | Z-15 |
| Branch | `feat/rag-z15-docs` |
| Stage | READY FOR PR |
| Started | 2026-11-05 |
| Approved (spec and plan) | 2026-11-05, pre-approved by Zain (no gate) |
| Depends on | phases 1 to 13 DONE on `dev`; H-13, H-14 open on Ahmad's side |

## 1. Objective

Write the RAG-lane documents from the measurements already in the results register: four ADRs, a finished `docs/PIPELINE.md`, the RAG-lane answers in `docs/ENGINEERING-NOTES.md`, the README API table, a complete `docs/AI-USAGE.md`, and no starter placeholder left in files this lane owns.

## 2. Context

- Requirements: R-IDX-1..9 (report items), R-CAC-1 (ADR for the cache store), R-LLM-1..6, R-ENG-1..7, R-AI-1, R-SUB-5, R-JOB-4 (ADR 0001 is the first file the marker reads).
- Architecture: AD-01, AD-03..AD-06, AD-09, AD-10, AD-12, AD-14, AD-22, AD-23, 5.3, 5.4, 5.9, 5.12.3, 5.14.
- Rubric: zero score for generic engineering notes and for unmeasured chunk settings; starter placeholders and `NotImplementedError` are deductions.
- Existing text: `docs/PIPELINE.md` already has extraction, cleaning, chunking, floor, cache, evaluation and embed-and-store sections; the `Embedding` section is a one-line stub and R-IDX-9 (how documents reach the Job) is missing. `docs/FAILURE-ANALYSIS.md` is complete (phase 13).
- Checker today (`python3 scripts/check_submission.py`): 11 failures. Lane-owned: starter placeholders, `NotImplementedError` in `api/app/providers/llm/hosted.py`, ADRs (0 of 4), API table, `ENGINEERING-NOTES.md` too short. Not this lane: `ui/Dockerfile`, `.github/workflows/`, `docs/evidence/`, `k8s/` manifests (Ahmad).

## 3. Scope

**In scope**

- `docs/adr/0001-indexer-as-job.md` (written here because it blocks the checker; header says authored by Zain's session, Ahmad to review and rewrite in his words), `0002-chunking.md`, `0003-cache-store.md`, `0004-llm-provider-and-data-governance.md`.
- `docs/PIPELINE.md`: finish `Embedding`, add how documents reach the Job, remove the placeholder comment.
- `docs/ENGINEERING-NOTES.md`: Q5, Q6, Q7 in full; Q1 to Q4 get the RAG-lane facts and a clearly marked section for Ahmad.
- `README.md` (shared, small separate commit): API table with endpoints, headers, status codes; fix stale statements (provider value, project status).
- `api/app/providers/llm/hosted.py`: remove the stub (D-87); `get_provider` raises a clear `ValueError` for `hosted`.
- `docs/AI-USAGE.md`: phase 14 entry, remove the placeholder comment, check every phase's entry.
- Reword prose mentions of the starter placeholder in lane-owned docs (plan, specs).

**Out of scope**

- `k8s/`, `ui/`, `.github/`, `docs/evidence/` (Ahmad). Ahmad's answers to Q1 to Q4 and his half of Q6. README apply order.
- Shared files that mention the placeholder in prose (`docs/requirements.md`, `docs/rubric_checklist.md`, `docs/WORKPLAN.md`, `docs/WORKFLOW.md`): listed for Zain, not edited.
- New code beyond the `hosted.py` removal. The recommendations in `FAILURE-ANALYSIS.md` (fail the Job on zero chunks) stay recommendations.

## 4. Interfaces and contracts

- `get_provider(settings)` for `LLM_PROVIDER=hosted` raises `ValueError("LLM_PROVIDER 'hosted' is not implemented in this build ...")` instead of importing a stub. Values `stub`, `extractive`, `ollama-host`, `ollama-incluster` unchanged. No HTTP shape changes. `api/app/main.py` builds the provider at start-up, so a bad value stops the pod before it is ready (visible, not silent).
- No config key added.

## 5. Behaviour and design details

- Every number comes from the results register (`docs/IMPLEMENTATION_PLAN.md` section 5), `eval/baseline.json`, `eval/tuning/*.json` or a command run in this phase. No new measurement is invented.
- ADR shape: the repo template (`docs/adr/0000-template.md`): Status, Context, Decision, Options considered, Consequences. About a page each, own words, file references with real names.
- ADR 0004 records: provider interface and its optional parameters (AD-14, `GenerationResult`), embedder duplication with the parity test (AD-09), no hosted provider built and why, what would leave the pod in a hosted mode, Ollama bound to `0.0.0.0`, no authentication on Chroma and Redis (NetworkPolicy is the only guard), PII (questions are logged at INFO; the Redis cache entry stores the question text).
- Q7: the failure told is the one the repo's logs actually record: the 398 s prompt and the timeout it forced (DEV-007), with what we believed first, taken from the progress log and the phase 10 and 12 specs. No invented timeline.

## 6. Acceptance criteria

- [ ] **AC-1**: four ADR files exist, names contain `indexer-as-job`, `chunking`, `cache-store`, `llm-provider-and-data-governance`; each has Status, Context, Decision, Options considered, Consequences, and at least one number from the register (0002, 0003, 0004).
- [ ] **AC-2**: `docs/PIPELINE.md` has every item of R-IDX-1..9 (OCR list, before and after, what could not be recovered, rules, one thing not stripped, size and overlap, amplification, three-row measured table, model, dimension, pin and its check, chunk count, metadata schema, how documents reach the Job), at least 1200 characters, a table, no placeholder.
- [ ] **AC-3**: `docs/ENGINEERING-NOTES.md` answers Q5, Q6, Q7 with real file and line references; Q1 to Q4 hold lane facts and an explicit "Ahmad" section; no invented Kubernetes answer.
- [ ] **AC-4**: README has an API table with `POST /api/ask`, `GET /healthz`, `GET /readyz`, `GET /metrics`, headers `X-Cache`, `X-Outcome`, `X-Request-ID` and their values, and status codes 200, 422, 503; every statement matches the code.
- [ ] **AC-5**: the starter placeholder is absent from `api`, `indexer`, `eval` (except `golden.example.yaml`, a kit example the checker skips), `docs/PIPELINE.md`, `docs/FAILURE-ANALYSIS.md`, `docs/ENGINEERING-NOTES.md`, `docs/AI-USAGE.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/specs/`; remaining files are listed in the PR.
- [ ] **AC-6**: no `raise NotImplementedError` in `api/app` or `indexer/`; `get_provider` has a test for `hosted`; `make test && make lint` green.
- [ ] **AC-7**: `python3 scripts/check_submission.py` has no failure attributable to this lane; remaining failures are named with owners.
- [ ] **AC-8**: an independent tester checks every number and file name in the new documents against the repo and the register.

## 7. Test strategy and traceability

| AC | Level | Command | Needs |
| --- | --- | --- | --- |
| AC-1 | manual | `ls docs/adr`; `grep -c "^## " docs/adr/000*.md` | nothing |
| AC-2 | checker | `python3 scripts/check_submission.py` sections A, H | nothing |
| AC-3 | checker, tester | checker section J; tester reads the cited lines | nothing |
| AC-4 | checker, tester | checker section J; tester compares to `api/app/` | nothing |
| AC-5 | manual | `grep -rn` for the placeholder over the repo | nothing |
| AC-6 | unit | `api/tests/test_ollama_provider.py::test_hosted_is_a_clear_config_error` | nothing |
| AC-7 | checker | `python3 scripts/check_submission.py` | nothing |
| AC-8 | tester | brief in `docs/WORKFLOW.md` section 6, adapted to documents | nothing |

## 8. Open questions

None blocking. Decisions D-86 to D-89 in `docs/OPEN_DECISIONS.md` (Claude, pre-approved by Zain).

## 9. Risks and assumptions

- A line number in a document goes stale if code changes before submission; the tester checks each reference, and phase 15 re-checks.
- Ahmad owns ADR 0001 by plan. The file is written now and marked for his rewrite; if he disagrees on a fact it is his to change.
- The checker counts the placeholder even in prose. Rewording prose in lane-owned docs is a text change, not a weakening of anything.

## 10. Plan

| Step | What | Files | Verify | Commit |
| --- | --- | --- | --- | --- |
| 1 | Spec, decisions | this file, `OPEN_DECISIONS.md` | read | `docs(spec): phase 14 spec and plan` |
| 2 | Remove hosted stub, add test | `hosted.py`, `providers/llm/__init__.py`, test | `make test && make lint` | `refactor(api): remove the hosted provider stub` |
| 3 | ADR 0001 | `docs/adr/0001-indexer-as-job.md` | checker | `docs(adr): 0001 indexer as a Job` |
| 4 | ADR 0002 | `0002-chunking.md` | numbers vs register | `docs(adr): 0002 chunking` |
| 5 | ADR 0003 | `0003-cache-store.md` | same | `docs(adr): 0003 cache store` |
| 6 | ADR 0004 | `0004-llm-provider-and-data-governance.md` | same | `docs(adr): 0004 provider and data governance` |
| 7 | PIPELINE | `docs/PIPELINE.md` | checker | `docs(pipeline): embedding, document delivery` |
| 8 | Notes | `docs/ENGINEERING-NOTES.md` | tester | `docs(notes): RAG-lane engineering answers` |
| 9 | README | `README.md` | tester | `docs(readme): API table, status` |
| 10 | Placeholders, AI-USAGE | plan, specs, `AI-USAGE.md` | grep | `docs: remove starter placeholders, phase 14 AI usage` |
| 11 | Tester rounds (max 3), plan, PR, merge | spec 12, `IMPLEMENTATION_PLAN.md` | tester PASS | per fix |

### 10.3 Rollback

Documents only, plus one stub removal. Revert the commit.

### 10.4 Estimate

About 3 h (plan: 3 h).

## 11. Implementation notes

Hosted provider removed, not built (D-87). ADR 0001 written here (D-86). The results register's stage times (extract+clean+chunk 4 min 17 s, embed 422 s, store 1.3 s = 11 min 20 s) do not add up to its 9 min 39 s wall time; documents quote only the total and the 422 s embedding. Zain should re-check that register row. The checker's remaining failures are Ahmad's (evidence, workflows, k8s, ui image) and four shared docs that mention the starter placeholder in prose.

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-05 | tester brief (WORKFLOW 6, adapted) | FAIL | D1 OCR timing, D2 cluster policies stated as built, D3 provider default, D4 AD-26 cite, D5 readiness timeout, D6 README hosted step and median range; all fixed in the next commit |
| 2 | 2026-11-05 | same brief | PASS | five low defects N1 to N5 (median 23 to 117, amplification 1.02, make corpus not written, IP wording, design wording), fixed |

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan | 2026-11-05 | Zain (pre-approved, no gate) | |
| Tester verdict PASS | 2026-11-05 | independent subagent | rounds: 2 |
| Merged | | | PR # |
