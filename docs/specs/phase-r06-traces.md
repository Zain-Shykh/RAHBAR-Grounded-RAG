# Phase R6 spec and plan: trace, trace tool, report, injection rail

| | |
| --- | --- |
| Phase | R6, from `docs/IMPLEMENTATION_PLAN_A3.md` |
| Work plan task | none (A3 plan; Ahmad out, D-108) |
| Branch | `feat/rag-r04-eval-suite` (planned name `feat/rag-r06-traces`) |
| Stage | IMPLEMENTED BEFORE SPEC (retroactive, D-127). Tested round 1; real sample traces pending |
| Started | 2026-11-21 |
| Approved (spec and plan) | gate waived (D-124); everything approved as recommended |
| Depends on | A02 answer pipeline, R1 batch B (injected document), R5 (`X-Cache-Bypass`) |

## 1. Objective

Every query writes one JSON trace line with everything needed to reconstruct the answer; a tool rebuilds the prompt from a trace id and checks its hash; a script summarises a time window; one retrieval rail drops instruction-like passages and logs the action.

## 2. Context

- Architecture: `architecture-a3.md` 7, AD-39, AD-40, invariants I-22 (a trace never fails a request), I-23 (a trace holds no secret).
- Requirements: R3-D1-1, R3-D2-1, R3-D3-1, R3-D3-2, R3-D4-1, R3-D5-1 (R10/R11), R3-F4-1 (API half).
- Decisions: D-118 (storage, prompt stored, trace id equals request id), D-119 (the rail is opt-in).
- Code: `api/app/services/trace.py`, `guardrails.py`, `answer.py`, `config.py` (`TRACE_DIR`, `TRACE_PROMPT`, `INJECTION_RAIL`), `routes/metrics.py`; `scripts/trace_tool.py`, `scripts/trace_report.py`.

## 3. Scope

**In scope**: trace record for answered, abstained, fallback and cached outcomes; stdout logger `rahbar.trace` and per-pod file; embedding version lookup; trace tool; trace report; rail with five pattern families and text normalisation; metrics `rahbar_injection_flags_total{rail}`, `rahbar_trace_write_errors_total`.

**Out of scope**: the cluster volume (R8); the 5-line root-cause write-up (R10/R11); sample traces from a real question (pending).

## 4. Interfaces and contracts

- Record keys: `type, trace_id, request_id, ts, query, rewritten_query, embedding{model,version,dimension}, collection{name,index_id,chunk_count,embed_model}, scope, retrieved[{rank,chunk_id,doc_id,section,page,doc_version,superseded,score}], reranked_order, floor, prompt, prompt_sha256, model{provider,name,attempts,params}, response{answer,citations,confidence,answered_from_context,outcome}, guardrails[], cache (hit|miss|skipped|bypassed), latency_ms{scope,embed,cache,retrieve,guardrails,generate,total}, tokens, fallback_reason, abstain_reason`.
- `Trace(trace_id, query, settings).emit()` never raises; failures increment `rahbar_trace_write_errors_total`.
- `guardrails.scan_text(text) -> list[pattern names]`, `scan_passages(passages) -> (kept, actions)`; action `{rail:"injection_scan", action:"dropped_passage", chunk_id, source, section, pattern[]}`. If the rail drops everything the answer is an abstention with `abstain_reason: guardrail` and no model call.
- CLI `python scripts/trace_tool.py show <id> [--dir D | --kubectl deploy/api] [--namespace N]`: exit 0 and prints the record, 1 when not found. CLI `python scripts/trace_report.py [--dir D] [--since 24h] [--out F] [--json]`.
- Env: `TRACE_DIR` (empty means stdout only), `TRACE_PROMPT` (false stores the hash only), `INJECTION_RAIL` (default false).

## 5. Behaviour and design details

- File name `traces-<UTC yyyymmdd>-<HOSTNAME>.jsonl`, one writer per file, append, one line per record.
- Prompt hash: SHA-256 of `json.dumps(messages, sort_keys=True, ensure_ascii=False)`; the tool recomputes it and prints `hash OK` or `hash MISMATCH`. The hash covers the prompt only: editing other fields (response, scores) is not detected.
- Rail normalises text before matching: NFKC, zero-width and soft-hyphen removal, `[<>]{2,}` runs removed (as `prompt.strip_delimiters`), whitespace collapsed. It is a pattern rail, not a classifier (AD-40); paraphrased injections pass and the A02 defences still apply.
- A cache hit records `retrieved` from the cached response (no `doc_version`), `prompt` null, `model` null.
- Secrets: the record has no headers, environment variables or URLs.

## 6. Acceptance criteria

- [x] **R6-AC1** Every R3-D1-1 field is present (value or explicit null) in the trace for an answered, an abstained, a fallback and a cached request; `trace_id == request_id`.
- [x] **R6-AC2** The trace goes to stdout as one JSON line with `"type": "trace"` and, when `TRACE_DIR` is set, to a per-pod file; with `TRACE_DIR` unwritable the request still succeeds and `rahbar_trace_write_errors_total` increments.
- [x] **R6-AC3** `trace_tool show <id>` prints query, filter, retrieved chunks with scores and versions, exact prompt, parameters, response; `hash OK` for an untouched trace, `hash MISMATCH` for an edited prompt.
- [x] **R6-AC4** `trace_report` prints top-1 similarity distribution, abstention rate, cache hit rate, p50 and p95 per stage, injection count; numbers equal an independent recomputation.
- [ ] **R6-AC5** Rail: the Batch B injected document is retrieved, dropped from the evidence, the trace holds `{rail: injection_scan, action: dropped_passage, chunk_id, pattern}`, the counter is 1. (Code and the planted paragraph proven offline; retrieval of the indexed document by its planted question pending the live index.)
- [ ] **R6-AC6** The A02 injection golden question still abstains or answers safely (`make eval-fixtures`, pending) and every A02 API test is unchanged and green.
- [x] **R6-AC7** No trace contains the Ollama URL, an environment variable or a header.
- [ ] **R6-AC8** One real question end to end saved as `traces/samples/answered.jsonl` and the tool reproduces its prompt hash (pending real run; `traces/samples/` holds no trace yet).

## 7. Test strategy and traceability

| AC | Level | Test file and name, or command | Needs |
| --- | --- | --- | --- |
| AC1 | unit | `api/tests/test_trace.py::test_answered_trace_has_every_field`, `::test_abstained_below_floor_has_no_prompt`, `::test_fallback_trace`; `api/tests/test_trace_adversarial.py::test_cache_hit_trace_is_complete_and_has_no_prompt`, `::test_embed_failure_trace_is_a_fallback_with_a_reason`, `::test_abstained_trace_by_model_keeps_prompt_and_reason` | nothing |
| AC2 | unit | `test_trace.py::test_file_writer_one_line_per_trace_and_stdout_logger`, `::test_writer_failure_is_counted_and_swallowed`; `test_trace_adversarial.py::test_read_only_trace_dir_is_swallowed_and_counted`, `::test_unserialisable_value_is_swallowed_or_stringified`, `::test_trace_with_unicode_query_round_trips` | nothing |
| AC3 | unit | `eval/tests/test_trace_scripts.py::test_tool_finds_trace_and_checks_hash`; `eval/tests/test_suite_adversarial.py::test_tool_detects_every_prompt_edit_and_shows_none_for_abstained`, `::test_tool_ignores_other_ids_substring_hits_and_non_trace_lines` | nothing |
| AC4 | unit | `test_trace_scripts.py::test_report_numbers_match_independent_computation`; `test_suite_adversarial.py::test_report_on_empty_dir_and_old_records_and_missing_retrieved` | nothing |
| AC5 | unit / integration | `test_trace.py::test_rail_off_by_default_and_on_drops_injected_passage`, `::test_rail_dropping_everything_abstains_without_a_model_call`; `test_trace_adversarial.py::test_batch_b_injected_paragraph_is_dropped_traced_and_counted`, `::test_rail_blocks_the_injection_before_prompt_and_hash_excludes_it`; live: ask the planted question on a batch B index | live index |
| AC6 | unit / cmd | `cd api && pytest -q`; `make eval-fixtures` | local API |
| AC7 | unit | `test_trace.py::test_trace_holds_no_secret` | nothing |
| AC8 | manual | run the API with `TRACE_DIR`, ask one question, `trace_tool show` | Ollama, stack |

Rail quality: `test_trace_adversarial.py::test_rail_catches_evasion` (17 variants), `::test_rail_known_gaps` (strict xfail), `::test_no_false_positive_on_normal_rule_sentences`, `::test_only_the_planted_injections_are_flagged_in_repo_text`.

## 8. Open questions

| # | Question | Options and recommendation | Decision entry | Answer |
| --- | --- | --- | --- | --- |
| Q1 | Store the full prompt? | yes, `TRACE_PROMPT` switch | D-118 | PROVISIONAL, accepted |
| Q2 | Rail on by default? | opt-in, default off keeps A02 behaviour | D-119 | PROVISIONAL, opt-in |

## 9. Risks and assumptions

- The rail is a pattern list: homoglyphs, spaced-out letters, underscore joins and novel phrasings pass (defect T-3, accepted limit of AD-40). A02 defences remain.
- Hash covers only the prompt, so a trace edited elsewhere is not flagged.
- `embed_version` queries Ollama `/api/tags` once per (model, URL) with a 3 s timeout; offline it yields `<model>@unknown` and may add up to 3 s to the first request of a process.
- Sample traces need a real answered question (pending).

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit message |
| --- | --- | --- | --- | --- |
| 1 | Trace builder and emitter | `services/trace.py`, `answer.py` | `test_trace.py` | `feat(api): trace record` |
| 2 | Rail | `services/guardrails.py` | tests | `feat(api): injection rail` |
| 3 | Metrics | `routes/metrics.py` | tests | `feat(api): trace and rail metrics` |
| 4 | Tool and report | `scripts/trace_tool.py`, `trace_report.py` | `eval/tests/test_trace_scripts.py` | `feat(scripts): trace tool and report` |
| 5 | Sample traces | `traces/samples/` | tool reproduces hash | (pending) |

### 10.2 Test plan
Unit tests per outcome; independent tester adds cache hit, bypass, embed failure, read-only dir, evasions and false-positive scans over real rule text.

### 10.3 Rollback and risks
`INJECTION_RAIL=false` is the default; the trace writer cannot fail a request.

### 10.4 Estimate
Plan estimate 6 h.

## 11. Implementation notes

- Implemented by the orchestrator session before this spec (D-127). A security review during implementation found a delimiter bypass (`ign<<<ore`); the fix is the normalisation step. DEV-017 records the API additions.

## 12. Test report

Round 1, 2026-11-21, branch `feat/rag-r04-eval-suite`, base 64464d3. No Ollama, docker, network (the trace tests stub `embed_version`).

| AC | Result | Evidence |
| --- | --- | --- |
| R6-AC1 | PASS with a note | answered, abstained (floor and model), fallback (provider error and embed failure) and cached traces contain all keys of `REQUIRED`; `trace_id == request_id` ("req-2" on the hit). Note T-4: on a cache hit `retrieved` has no `doc_version` (R3-D1-1 asks for versions); pinned by a strict xfail |
| R6-AC2 | PASS | one line per trace in `traces-*.jsonl`, logger record with `"type": "trace"`; unwritable parent (file in the way) and read-only directory (0o500) both swallowed, counter +1; a set value is stringified, not fatal; Unicode query round-trips |
| R6-AC3 | PASS | `hash OK` for untouched; `hash MISMATCH` for an edited system message, an appended message and a wrong `prompt_sha256`; `PROMPT: none` for an abstained trace; id `t1` does not match `t12` or a non-trace line; exit 1 when not found. Limit: editing the response or scores leaves `hash OK` (by design) |
| R6-AC4 | PASS | `test_report_numbers_match_independent_computation` (queries, abstention 0.25, cache 0.25, injection 2, p50/p95, histogram sum); empty directory gives `queries: 0` and `None` rates; `--since` drops old records; bad window raises SystemExit |
| R6-AC5 | PARTIAL | the exact paragraph of `corpus/batch_b/b11-examination-guidelines-2026.md` (2.2 "Note to the assistant ...") is dropped, one `injection_scan` action with `chunk_id`, `INJECTION_FLAGS{rail=injection_scan}` +1. Retrieval of the indexed document by its planted question: pending live index |
| R6-AC6 | PARTIAL | A02 API tests unchanged and green (api 330 passed, 19 skipped, 5 xfailed); `make eval-fixtures` not run (needs own API) |
| R6-AC7 | PASS | `test_trace_holds_no_secret` (URL, API key, `Authorization` absent) |
| R6-AC8 | PENDING | `traces/samples/` has no `answered.jsonl`; needs a real question |

Rail probes (`app.services.guardrails.scan_text`): caught: upper case, newline and tab separation, zero-width and soft hyphen inside words, no-break and ideographic space, `<>` and `<<<>>>` runs inside a word, markdown emphasis, fullwidth letters, "disregard prior rules", "forget your instructions", "pretend to be", "reveal ... hidden system prompt", "do not cite", "a note for the AI". Not caught (known limit, T-3): `i g n o r e ...`, `ignore_all_previous_instructions`, Cyrillic `і` in "previous", "ignore everything above".

False positives: all paragraphs of `eval/fixtures/*.md`, `corpus/MANIFEST.md`, `corpus/batch_b/*.md` scanned: only the two planted injections flag (`academic-rules-2026.md` 3.2 and `b11` 2.2). 250 pages (the first 60 pages of each PDF) of the real corpus in `corpus/raw` (pdfplumber, one-off script): 0 flags. Seven normal rule sentences with near-miss wording: 0 flags.

Extra tests: `api/tests/test_trace_adversarial.py` (30 passed, 5 xfailed) and the trace tool and report cases in `eval/tests/test_suite_adversarial.py`.

Defects found:

- **T-3 (low)** rail evasions above; accepted limit of a pattern rail (AD-40). Four strict xfail cases document it.
- **T-4 (low)** cache-hit trace omits `doc_version` and `superseded` in `retrieved`; the cached response does not store them. One strict xfail.
- **T-7 (info)** the first request of a process can block up to 3 s in `embed_version` when Ollama is unreachable (`lru_cache` then keeps `@unknown`).

Coverage: `app/services/trace.py` 95%, `guardrails.py` 100%, `app` total 98%.

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-21 | `make test`; `pytest --cov=app`; probes | PASS with pending items | pending: AC5 live, AC6 fixtures, AC8 samples |

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | 2026-11-21 | waived (D-124, D-127) | retroactive |
| Tester verdict PASS | | | round 1: PASS for code ACs; AC5 live, AC8 pending |
| Merged | | | |
