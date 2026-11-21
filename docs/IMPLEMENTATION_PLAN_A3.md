# Implementation plan: Assignment 03 (RAGOps)

The phased build plan for Assignment 03, "RAGOps": add data management, three-level offline testing, a release gate, traces and metrics, drift checking and a controlled Kubernetes release on top of the finished RAHBAR pipeline. It is also the **only progress tracker for Assignment 03**: phase status, acceptance ticks and the progress log live in this file. Assignment 02's trackers ([`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) and [`IMPLEMENTATION_PLAN_PLATFORM.md`](IMPLEMENTATION_PLAN_PLATFORM.md)) are closed and frozen: the submission is done.

| | |
| --- | --- |
| Assignment | [`../Assignment_03.md`](../Assignment_03.md), 185 marks, group of 2 |
| Requirements | [`requirements-a3.md`](requirements-a3.md) (ids `R3-*`) |
| Design | [`architecture/architecture-a3.md`](architecture/architecture-a3.md) (section numbers below refer to it; decisions AD-29 to AD-45, invariants I-18 to I-26) |
| Procedure | [`WORKFLOW.md`](WORKFLOW.md): spec and plan in one document, one gate, implement, independent test, PR, merge on Zain's word |
| Deadline | **Sunday 22 November 2026** (D-107, from Zain; time not given, plan for 23:59 PKT, submit by 18:00). Started Saturday 21 Nov 02:57 PKT: about 45 hours. See section 7 |
| Estimate | about 64 hours uncompressed; **compressed to about 34 hours by section 7** |
| Builds on | RAHBAR at `main` `bd6468a` plus `dev` (PR #45) |

---

## 0. Read this first (for the implementing agent)

You are the agent building Assignment 03. Follow the plan in order and update it as you go.

### 0.1 Authorisation and gates

- **Approved by Zain on 2026-11-21 (D-124 decided):** sessions may edit `api/**`, `indexer/**`, `eval/**`, `scripts/**`, `corpus/batch_b/**`, `traces/**`, `docs/**`, `k8s/**`, `.github/**`, `Makefile`, `eval/Dockerfile`. `ui/index.html` and `ui/nginx.conf` stay untouched. The earlier rule that `k8s/` and `.github/` belong to Ahmad is lifted for this assignment for the same reason as the platform plan: it is Zain's session that builds them.
- **Gate waived.** Zain approved the whole plan on 2026-11-21 and told the session to keep working to the end. There is no per-phase approval wait. The phase section of this file is the spec; each phase still has a branch, tests, an independent check (see section 7), a PR into `dev` that the session merges when `make test && make lint` are green, and log lines. The PR to `main` comes at R11.
- **Merge** only on Zain's word, into `dev`, never into `main` until R11.
- **Hard stops (ask Zain, do not guess):** a conflict between the assignment and the design; a secret or credential in a diff; a failing tester after 3 rounds; a change to a GitHub repository setting; anything that deletes the Assignment 02 evidence; a number that does not come from a committed run.

### 0.2 Start of every session

1. Read this file top to bottom, then **Current focus** (section 2).
2. Find the first phase whose status is not `DONE`. That is your phase. Do not skip ahead.
3. Read what the phase lists under **Read first**. Re-read the cited architecture sections; do not work from memory.
4. `git checkout dev && git pull`. Run `make test && make lint` for a clean baseline. Create the branch named in the phase (`feat/rag-rNN-<topic>` or `feat/k8s-rNN-<topic>`).
5. Check [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md) for `OPEN` and `PROVISIONAL` entries D-107 to D-125 that touch the phase.
6. Write `docs/specs/phase-rNN-<slug>.md` from [`specs/TEMPLATE.md`](specs/TEMPLATE.md). Set the work plan field to "A3 R-NN".

### 0.3 While working

- The architecture decides the design. A difference goes into [`architecture/deviations.md`](architecture/deviations.md) (DEV-015 onward) in the same PR. Section 11 of `architecture-a3.md` lists the deviations already planned.
- **Assignment 02 must not regress.** Every phase that touches `api/`, `indexer/` or `eval/` runs `make test && make lint`, and phases that change behaviour (R3, R6) also re-run the A02 fixture eval (`make eval-fixtures`) and keep its gate green.
- **Evidence rule (I-25).** Every number that will appear in the report is produced by a committed script, saved to a committed file (`eval/results/`, `traces/`, `docs/evidence/`) and recorded in the results register (section 5). A number typed from memory is a defect.
- Tests need no network, no model and no cluster, except tests the spec marks as integration. Never weaken or skip a test.
- Commits: Conventional Commits, small, ending with the `Co-Authored-By` trailer the tool gives. Never push to `main`. Docker needs `sg docker -c "docker ..."`. `pkill ollama` and `minikube stop` when idle.
- Ahmad is not available (D-108). Zain's session does all work; hand-offs H3-2 to H3-6 move to Zain's own checklist `eval/HUMAN_TODO.md`. He has 6 commits from A02 (R3-LOG-6). The demo requires both members to explain everything (R3-LOG-1): risk accepted by Zain.
- Update [`AI-USAGE.md`](AI-USAGE.md) at the end of each phase. Push after every phase.

### 0.4 End of every phase

1. Run the phase's **Verify** commands and paste the key output into the progress log.
2. Tick every acceptance box that is true, with evidence. An unticked box means the phase is not done.
3. Independent testing subagent ([`WORKFLOW.md`](WORKFLOW.md) section 6), up to three rounds.
4. Set the phase status, update the dashboard and **Current focus**, add log lines, tick the checklist in section 6 for what the phase proves.
5. Open the PR into `dev`. Merge on Zain's word. Start the next phase in a fresh session.

### 0.5 Status words

`NOT STARTED` · `IN PROGRESS` · `BLOCKED` (say by what) · `DONE` · `DROPPED` (cut line, say why).

### 0.6 Do not build

Anything that is not in `requirements-a3.md`. In particular: a reranker (the experiment is chunking, AD-41), an LLM-based query rewriter, a new vector store, Prometheus or Grafana, authentication, a UI for traces, Helm, an operator, a cloud deployment. Do not change Assignment 02's external API shapes (`AskResponse`, headers) except the additions listed in `architecture-a3.md` section 11.

---

## 1. Dashboard

| # | Phase | Requirements | Est | Status | PR |
| --- | --- | --- | --- | --- | --- |
| R0 | Planning set: requirements, architecture, plan, decisions | all | 2 h | DONE (approved by Zain 2026-11-21) | #46 |
| R1 | Batch B and the manifest contract | R3-AB-1 | 3 h | DONE | #47 |
| R2 | Verification stage (A1) | R3-A1-* | 6 h | DONE (tested PASS, cluster run done) | #48 |
| R3 | Incremental update, archive, restore (A2) | R3-A2-*, R3-AB-2 | 7 h | DONE (cluster run done; check_registry added) | #48 |
| R4 | Golden set, module level, component level, noise | R3-B-1 to R3-B-5 | 5 h | DONE (8 synthetic reviews done by Zain, D-147) | #48 |
| R5 | End-to-end level, stochasticity, one command (no judge, D-115) | R3-B-6 to R3-B-9 | 7 h | DONE (R3-B-7 not applicable, D-115) | #48 |
| R6 | Trace, trace tool, metrics report, injection rail | R3-D1-* to R3-D5-1, R3-F4-1 | 6 h | DONE (live rail proof: see e3-injection-rail-live.txt) | #48 |
| R7 | Change experiment and release gate | R3-C1-*, R3-C2-* | 6 h | DONE (decision docs/evidence/r7-decision.md) | #48 |
| R8 | Kubernetes deployment of RAGOps | R3-F1-*, R3-F2-*, R3-F4-*, R3-F5-*, R3-LOG-11 | 8 h | DONE (fresh-cluster rehearsal R11-AC5) | #48 |
| R9 | Controlled release and rollback | R3-C3-1, R3-F3-* | 4 h | DONE | #48 |
| R10 | Drift and coverage | R3-E1-* to R3-E4-* | 4 h | DONE (E3 write-up docs/evidence/a3/e3-data-drift.md); coverage 0.675 below the 0.85 target, stated as a gap | #48 |
| R11 | Evidence, report, README, final verification | R3-G-*, R3-S-*, R3-LOG-8 to 10 | 8 h | DONE except human items (contribution check) | #48, release PR |

Build order note: R4 and R5 need the API and a real index running; R6 changes the API (re-run the A02 fixture eval); R7 needs R5 results; R9 needs R7 and R8; R10 needs R3, R5 and R8; R11 is last. R1 to R3 and R4 to R6 are independent chains and may be swapped if the cluster or Ollama is unavailable, but a phase is never started before the previous one is merged.

Hours spent so far: planned 64 h plus 2 h (R0), actual `____`.

## 2. Current focus

```
Phase:        R0 to R13 complete; waiting on Zain for the remaining human items
Stage:        DONE (R12 close-out, independent test: docs/specs/phase-r12-closeout.md section 12); main contains PR #48 and #49
Branch:       feat/rag-r12-closeout (PR into dev, then a release PR dev to main if main lacks the commits)
Spec:         docs/specs/phase-r12-closeout.md
Next action:  Zain: (1) approve release PR #51 (dev to main), (2) read the contribution table and AI statement, (3) decide the production release of 600/100 (make release COLLECTION=rahbar_c600)
Waiting on:   Zain (human items above)
Last updated: 2026-11-21
```

Update this block at the end of every work session, even if the phase is unfinished.

---

## 3. Hand-offs and open items

| ID | Direction | Item | Phase | Done |
| --- | --- | --- | --- | :---: |
| H3-1 | Zain to Ahmad | Tell Ahmad Assignment 03 exists, share `Assignment_03.md`, this plan, and the demo rule that both must explain every part | R0 | [ ] |
| H3-2 | Zain (was Ahmad) | Write at least 8 golden questions by hand (R3-B-2). Not done by the session (D-126): worksheet `eval/HUMAN_TODO.md` | R4 | [ ] |
| H3-3 | n/a | Hand labels for the judge (R3-B-7): not needed, no LLM judge (D-115) | R5 | [x] |
| H3-4 | Zain (was Ahmad) | Review 8 or more synthetic questions and mark `reviewed` (R3-B-2), in `eval/HUMAN_TODO.md` | R4 | [x] 2026-11-21 (D-147; four of the eight are about invented Batch B files) |
| H3-5 | Ahmad | Write the 40 live-style queries' phrasing review (R3-E1-1) and the contribution table entries | R10, R11 | [ ] |
| H3-6 | Ahmad | Run the README commands on a clean clone and report anything that fails | R11 | [ ] |
| H3-7 | Zain (human) | Paper supplied at `docs/reference/RAGOPS_paper.pdf` (gitignored) | R0 | [x] |
| H3-8 | Zain (human) | Docker Hub token: the A02 token expires 30 days after creation; refresh if the CD run is needed for `rahbar-eval` (A3-R6) | R8 | [ ] |

Ahmad cannot take H3-2 to H3-6 (D-108). The contribution table must say exactly what the session did and what Zain did.

---

## 4. Progress log

Append-only, newest at the bottom. Format: `YYYY-MM-DD  PNN  <stage or event>: <what happened>. <evidence>.`

```
2026-11-21  R0   Planning set written: requirements-a3.md, architecture-a3.md, IMPLEMENTATION_PLAN_A3.md, decisions D-107 to D-125, pointers added to the A02 documents. Branch docs/a3-ragops-planning.
2026-11-21  R0   MERGED: PR #46. Zain approved everything, deadline Sun 22 Nov (D-107), Ahmad unavailable (D-108), paper supplied (D-109), per-phase gate waived (D-124), no LLM judge (D-115), hand-work left for Zain (D-126). Plan compressed (section 7).
2026-11-21  R1   MERGED: PR #47. scripts/make_batch_b.py writes 12 planted documents (idempotent), manifest loader, enrich script. 262 indexer tests.
2026-11-21  R2   IMPLEMENTED: verification package (four checks, quarantine, report, text table). On Batch B: 6 documents pass, 6 quarantined with the planted reasons, injected document passes (by design). Near-duplicate threshold calibrated: nomic max distinct pair 0.9379, planted near-duplicate 0.9998, threshold 0.97 (eval/results/neardup-calibration-*.json).
2026-11-21  R3   IMPLEMENTED: incremental update (copy-forward then swap), registry, restore. Real Chroma 1.0.12 spike: 26 of 26 untouched chunks identical after a changed-document run, same top 5 (A3-R1 holds). Unchanged re-run: 0 embedded, no swap, same index_id. 281 indexer tests.
2026-11-21  R4   IMPLEMENTED: eval/golden.jsonl (34 questions: 18 human from A02, 16 synthetic), metrics (recall@3/5, MRR, nDCG@5, typo noise), module level, component level via POST /api/retrieve. 114 eval tests.
2026-11-21  R5   IMPLEMENTED (code): end-to-end level (overlap faithfulness, abstention, citation validity, latency), one command (eval.suite.run_suite), stochasticity script, LLM_SEED and X-Cache-Bypass in the API. Real runs in progress (each question takes 75 to 110 s on this CPU).
2026-11-21  R6   IMPLEMENTED: trace record per query (stdout and per-pod file), trace tool, trace report, injection rail (opt-in, scans the normalised text; a security review caught a delimiter bypass, fixed), 300 api tests.
2026-11-21  R7   IMPLEMENTED (code): gate.py, compare.py, gate.yaml (limits to be fixed from baseline runs).
2026-11-21  --   D-127: Zain instructed orchestrator mode. R1 to R8 code was written by the main session; subagents now write the retroactive specs and test reports and run the independent checks; later phases run one subagent each.
2026-11-21  R8   IMPLEMENTED (manifests): PVCs, eval and trace-report Jobs, candidate Deployment and indexer Job, NetworkPolicies, make targets, k8s/README.md; make manifests validates all; cluster runs pending.
2026-11-21  R8   CLUSTER RUN: ingestion Job on the real corpus 9 of 9 pass, 980 chunks, 1396 s; unchanged re-run 0 embedded; Batch B on the cluster 6 indexed 6 quarantined, fee page superseded, delete leaves 0 orphans, restore Job rolls back and forward; eval Job baseline then live2 gate PASS (27 answers, identical retrieval metrics, 1 answer text differs); GATE_ONLY flips Complete to Failed with the same image; resources measured (docs/evidence/f5-resources.txt); evidence docs/evidence/a3/. Fixed: eval client timeout, indexer deadline, gate placeholders, CI overlay volume index. Open: CI scan (nginx CVEs in the ui base). Spec docs/specs/phase-r08-k8s-ragops.md.
2026-11-21  R4   TESTED round 1 (independent): metrics, noise, loader PASS; golden --check exit 1 only for the 8 reviews (D-126); live ACs (page match, A02 anchor, baseline run) pending. Spec docs/specs/phase-r04-golden-retrieval.md. Defect T-1 (loader crashes on null/missing keys, low).
2026-11-21  R5   TESTED round 1: seed, bypass, exit-on-failure PASS; whole suite proven offline with a fake API; judge N/A (D-115); real runs, calibration, suite-twice pending. Spec docs/specs/phase-r05-e2e-suite.md.
2026-11-21  R6   TESTED round 1: all outcomes traced (answered, abstained, fallback, cached), writer failure swallowed, tool and report PASS, rail catches 17 evasions, 0 false positives on 250 real pages. Pending: live batch B retrieval, traces/samples, eval-fixtures. Defects T-3 (rail gaps, low), T-4 (cache-hit trace lacks doc_version, low). Spec docs/specs/phase-r06-traces.md.
2026-11-21  R7   TESTED round 1: gate and compare PASS; defect T-2 (malformed YAML exits 1 instead of 2, medium, gate.py and job.py). Candidates, limits, decision pending. Spec docs/specs/phase-r07-gate.md. Tester added eval/tests/test_suite_adversarial.py and api/tests/test_trace_adversarial.py (8 strict xfails pin T-1 to T-4).
2026-11-21  R1   TESTED (independent, retroactive spec docs/specs/phase-r01-batch-b.md): AC1 to AC4 PASS; AC5 not proven (corpus/raw/_index.a02.json absent on this machine).
2026-11-21  R2   TESTED (docs/specs/phase-r02-verification.md): AC1 to AC8 PASS. Real corpus 9 of 9 pass, Batch B 6 indexed and 6 quarantined as planted; verification coverage about 94%. Added strict-exit test.
2026-11-21  R3   TESTED (docs/specs/phase-r03-incremental.md): AC2 to AC9 PASS, 13 edge tests added (unicode, empty corpus, registry or collection missing, embedder and registry-save failure, quarantine fixed, changed back, restore twice, superseded deleted). AC10 FAIL: scripts/check_registry.py does not exist. AC1 and AC11 (spike, make eval-fixtures) not re-run: need services.
2026-11-21  R1-R7 FIX ROUND 1: T-1 T-2 T-4 T-5 T-8 fixed, scripts/check_registry.py added (R3-AC10), corpus/raw/_index.a02.json created (R1-AC5); tests green.
2026-11-21  R7/R9 BASELINE-AB done: eval/results/suite-20261121T021833Z-baseline-ab.json (50 questions, subset all, live index Batch A+B, index 20261121T005113Z-a45667); copy suite-20261121T021833Z-drift-after-batch-b.json is the E3 data-drift run (compare against suite-20261121T001033Z-baseline.json = Batch A only). Eval client timeout raised to 900 s (a 424 s answer killed the first attempt).
2026-11-21  R7/R9 DONE ON CLUSTER: candidates 100/0 (rahbar_bad) FAIL exit 1, 300/50 (rahbar_cand) PASS, 600/100 (rahbar_c600) PASS; final gate limits (faithfulness baseline-relative 0.05, D-134); release rahbar_cand with 64/64 HTTP 200 during the rolling update, bad release rahbar_bad, make rollback, final undo to rahbar. Evidence docs/evidence/a3/r9-*.txt, docs/evidence/r7-decision.md. Spec docs/specs/phase-r09-release.md. Live api on rahbar; api-candidate left running on rahbar_c600.
2026-11-21  R10  E3 DONE (in R11): scripts/drift_report.py, docs/evidence/a3/e3-data-drift.md, eval/results/drift-20261121T083232Z.json. Like for like on 27 questions recall@5 0.8095 to 0.7143, 3 outcome changes (q07 and g22 lost the refund clause to the supersession, q06 generation variance); g32 abstains because b12 had been deleted by the A2 test.
2026-11-21  R11  14 screenshots rendered from the saved terminal text (scripts/render_screenshot.py), report docs/report/report.pdf built (pandoc, Chrome), scripts/check_numbers_a3.py exits 0 (97 decimals), history scan saved.
2026-11-21  R11  FRESH CLUSTER: minikube deleted, k8s/README.md followed: real corpus 980 chunks in 1399.7 s, second run 0 embedded, smoke eval baseline and gate Job (6 of 6), Batch B and demo_batch ingested, live injection rail trace, api 3/3 Ready, /readyz 200. Defects fixed (helper pod wait 600 s, smoke run keeps one unanswerable question). docs/evidence/a3/r11-fresh-cluster-rehearsal.txt. D-140 to D-142.
```

---

## 5. Results register

Numbers the report will quote. Fill each with the value, the committed file it came from, and the date. An empty cell is a number we do not have yet.

| Quantity | Value | Source file | Phase |
| --- | --- | --- | --- |
| Batch B files and planted problems (counts) | 12 files: 4 controls, 2 exact duplicates, 1 near duplicate, 1 truncated PDF, 1 corrupt PDF, 1 missing metadata, 1 newer version, 1 injected instruction | `corpus/batch_b/PLANTED.json` | R1 |
| Verification: failures per check on Batch B | uniqueness 3, completeness 3, quality 2, recency 1; checked 13, indexed 6, quarantined 6, superseded 1 | `docs/evidence/a3/a1-verification-report.txt` | R2 |
| Near-duplicate threshold and the distribution it came from | 0.97; largest distinct pair 0.9379, planted near-duplicate 0.9998 | `eval/results/neardup-calibration-20261120T221945Z.json` | R2 |
| Unchanged re-run: chunks embedded, swapped | 0, false | `docs/evidence/a3/a2-unchanged-run.txt` | R3 |
| Changed-document run: chunks embedded, other docs' ids identical | 26 of 26 untouched chunks identical (spike); see R3 spec | `docs/specs/phase-r03-incremental.md` | R3 |
| Deleted document: chunks by doc id before and after | b12: 4 chunks to 0 (0 orphans), index 1010 to 1006 chunks | `docs/evidence/a3/a2-delete-no-orphans.txt` | R3 |
| Golden set counts (answerable, unanswerable, hard, human, synthetic, reviewed) | (measured runs; the file has 52 since R12) 50 questions: 39, 11, 23, 18, 32, 0 reviewed (needs 8, human) | `eval/results/suite-20261121T021833Z-baseline-ab.json` (meta), `golden-check-20261121.json` | R4 |
| Embedding: paraphrase mean, unrelated mean, gap, ms per chunk, determinism | 0.791, 0.525, 0.266, 285.3 median, 0 | `eval/results/suite-20261121T021833Z-baseline-ab.json` | R4 |
| Retrieval: recall@3, recall@5, MRR, nDCG@5, clean and noisy | clean 0.795, 0.795, 0.756, 0.766; noisy 0.769, 0.795, 0.676, 0.706 | same | R4 |
| E2E: faithfulness (overlap), abstention, citation validity, p50, p95 | 0.879 (supported 0.900), 0.909, 1.000, 54.4 s, 181.7 s | same | R5 |
| Judge agreement and kappa on hand labels | not applicable (no LLM judge, D-115) | | R5 |
| Two-run difference per metric | 0.0 for retrieval and answer-quality metrics; 1 of 27 answer texts differs; p95 184.46 s vs 113.14 s | `eval/results/stochasticity-20261121T003255Z.json` | R5 |
| Gate: failing candidate and passing candidate results | 100/0 FAIL (faithfulness 0.8214 < 0.85), 300/50 PASS, 600/100 PASS | `eval/results/gate-cand-*.txt` | R7 |
| Release decision (release or reject, reasons) | reject 100/0; release 600/100 (production step left to Zain); rule changed after seeing 100/0, stated | `docs/evidence/r7-decision.md` | R7 |
| Resource peaks and chosen requests and limits | api 71 Mi peak (128Mi limit), chroma 104 Mi (384Mi), indexer 469 Mi (768Mi), eval 24 Mi (64Mi) | `docs/evidence/f5-resources.txt` | R8 |
| Coverage before and after (share, threshold, uncovered topics) | 0.300 to 0.675 (target 0.85, threshold 0.72); in-domain 0.429 to 0.857 | `eval/results/coverage-*.json`, `docs/evidence/a3/e2-uncovered-topics.md` | R10 |
| Data drift (metric changes after Batch B) | like for like on 27 questions: recall@5 0.8095 to 0.7143, false abstention 0.1905 to 0.3333; 3 outcome changes | `eval/results/drift-20261121T083232Z.json`, `docs/evidence/a3/e3-data-drift.md` | R10 |
| Trace summary over a window | 61 queries, abstention rate 0.311, top-1 median 0.798 | `docs/evidence/a3/d2-trace-report-job.txt` | R6, R8 |

---

## 6. Submission checklist (R3-LOG-*, R3-S-*)

Tick only with a pointer to the file.

- [ ] Repository URL ready; commits from both members (R3-LOG-6): GAP, 2 non-merge commits by Ahmad (A02), none for A3 (D-108); stated in the report
- [x] `README.md` has the exact command for each of A to F (R3-LOG-10): README section "Assignment 03"
- [x] `k8s/README.md` lets a fresh cluster reach a working pipeline (R3-F5-2); rehearsed on a deleted cluster: `docs/evidence/a3/r11-fresh-cluster-rehearsal.txt`
- [x] `eval/results/` and `traces/` committed with the files the report quotes (R3-LOG-9): checked by `scripts/check_numbers_a3.py`
- [x] Report PDF at most 8 pages, names and roll numbers on page 1, appendix of screenshots (R3-G-*): `docs/report/report.pdf` (5 body pages; roll numbers 24i-3126 and 24i-3006 filled in R12)
- [x] Screenshots S-A1, S-A2, S-B, S-C1, S-C2, S-D1, S-D2, S-E1, S-E2, S-F1 to S-F5, uncropped, labelled (R3-S-*): `docs/evidence/a3/screenshots/`, index `docs/evidence/a3/README.md` (renderings of saved terminal output, D-139)
- [x] Demo rehearsal: eval as a Job, a trace opened, an unseen batch ingested (R3-LOG-11): `docs/evidence/a3/r11-fresh-cluster-rehearsal.txt`
- [x] `docs/rubric_checklist.md` section F ticked with evidence; `python3 scripts/check_submission.py` still passes for the A02 parts (164 passed, 0 failures)
- [ ] AI statement (2 to 3 lines) and the contribution table written truthfully: written; Zain must confirm
- [x] No secret in Git; `git log` clean of `.env*`, tokens, models, `corpus/raw/`: `docs/evidence/a3/r11-history-scan.txt`

---

## 7. Compressed schedule (deadline Sun 22 Nov, decided 2026-11-21)

About 45 hours remain. Real runs are slow (a full re-index is about 10 minutes, a 25-question suite with the 3B model several minutes, run twice plus a noisy run), so code and runs overlap.

| Block | Phases | Budget | Cuts made |
| --- | --- | --- | --- |
| 1 | R1 + R2 + R3 as one indexer block, one branch per phase, small specs | 8 h | per-phase spec files replaced by the phase sections here; tests focus on the pure functions and the copy-forward path |
| 2 | R4 + R5 (eval suite) | 6 h | **no LLM judge** (D-115): faithfulness = overlap score only, no hand labels needed; typo noise only (D-116) |
| 3 | R6 traces and rail | 3 h | sample traces from the real stack |
| 4 | R7 experiment and gate | 3 h | two candidates only (one expected to fail, one to pass), picked from at most three measured |
| 5 | R8 cluster | 5 h | measure resources once; rehearse once |
| 6 | R9 release, R10 coverage and drift | 4 h | the drift run reuses the R8 Batch B ingestion |
| 7 | R11 report, screenshots, README, main PR | 5 h | |

**Cut line if time runs out (cut last first):** the rollback of a bad release is kept (required) while the optional `--chunks` check of the trace tool, Table 1 extras (precision@5, memory per embedding) and the second candidate rehearsal are dropped first. Never cut: A1, A2, the three levels, the gate, traces, the Kubernetes Jobs, the rollout and undo, coverage, the report and screenshots. Anything cut is listed as an honest gap in the report.

**Human-only items (cannot be done by the session, D-126):** write 8 questions (done: the 18 A02 questions) and review 8 synthetic ones (done 2026-11-21, D-147), supply both roll numbers (done), take or approve the screenshots if the session cannot capture terminals, Docker Hub token if CD is wanted.

**Paper alignment (read 2026-11-21).** Table 1 lists per level a traditional metric and a RAG metric; our suite also reports embedding time, retrieval latency, index update speed (from the R3 summary) and full-pipeline latency next to the RAG metrics. Table 2's operational considerations (data structure and granularity configuration; degradation and source-change detection; injection detection and context adherence; versioning, retrieval routing and grounded source; resource usage) are the rows of the report's Table G-2. The paper's verification has a fifth check, Consistency (contradictory information); the assignment asks for four; not built, stated in R3-G-4(e).

---

# Phases

Each phase below is a summary. The phase's own spec (`docs/specs/phase-rNN-<slug>.md`) turns it into interfaces, test traceability and a step plan at the gate.

---

## Phase R1: Batch B and the manifest contract

| | |
| --- | --- |
| Branch | `feat/rag-r01-batch-b` |
| Requirements | R3-AB-1 (the corpus half of R3-AB-2) |
| Estimate | 3 h |

### Objective
A committed, deterministic Batch B of at least 10 documents with planted problems and a ground-truth file, and the manifest fields that the verification stage needs (architecture 5.2, 5.6).

### Read first
`architecture-a3.md` 5.2 and 5.6; `corpus/fetch.py`; `corpus/raw/_index.json`; `indexer/pipeline/run.py` `discover`; `eval/fixtures/` (existing synthetic documents).

### Scope
- `scripts/make_batch_b.py`: deterministic generator (fixed seed, no network) writing `corpus/batch_b/` files and `corpus/batch_b/_index.json` and `PLANTED.json`.
- `scripts/enrich_manifest.py`: adds `title` and `family` to the real manifest, keeping a copy `_index.a02.json`; unit-tested on a sample.
- `indexer/pipeline/run.py` `discover()` reads the new optional manifest fields (`title`, `date`, `family`, `pages`) without breaking old manifests.
- The 10 or more files: 2 exact duplicates, 1 near-duplicate, 1 truncated, 1 corrupt, 1 missing metadata, 1 newer version of an existing document (a newer copy of a document the golden set already uses: for the real corpus use a synthetic "amendment" file whose `family` equals the existing family), 1 with an injected instruction, at least 2 clean controls. Formats: Markdown, HTML and at least one PDF (generated with a stdlib-only writer or `reportlab` if already a dependency; otherwise Markdown and HTML only and say so).
- Some clean documents carry facts that exist nowhere in the real corpus, with matching golden questions written in R4.

### Out of scope
Verification logic (R2). Putting Batch B into the cluster (R8).

### Acceptance criteria
- [x] R1-AC1 `python scripts/make_batch_b.py --out corpus/batch_b` is idempotent: a second run changes no byte (`git diff --exit-code`).
- [x] R1-AC2 `PLANTED.json` lists at least 10 files with problem labels covering every row of architecture 5.6, and a test asserts the counts (2 exact duplicates, 1 near-duplicate, 1 truncated, 1 corrupt, 1 missing metadata, 1 newer version, 1 injected, at least 2 controls).
- [x] R1-AC3 The exact duplicates have identical bytes (sha256 equal); the near-duplicate differs from its original in under 5 percent of words; the truncated file is a strict prefix of a complete one; the corrupt file's sha256 differs from the manifest entry.
- [x] R1-AC4 `discover()` on an old A02 manifest returns the same list as before (regression test) and on the new manifest returns the new fields.
- [ ] R1-AC5 `make test && make lint` green; no change to `corpus/raw/` content; `_index.a02.json` equals the original byte for byte.

### Verify
`python scripts/make_batch_b.py --out corpus/batch_b && git diff --exit-code corpus/batch_b`; `cd indexer && ../.venv/bin/pytest -q`; `make test && make lint`.

---

## Phase R2: Verification stage (A1)

| | |
| --- | --- |
| Branch | `feat/rag-r02-verification` |
| Requirements | R3-A1-1 to R3-A1-4 |
| Estimate | 6 h |

### Objective
After extraction and before chunking, every new or changed document gets a pass or fail with a reason for quality, completeness, recency and uniqueness; failures are quarantined and never indexed; a report file is written per run (architecture 5.3, I-19).

### Read first
`architecture-a3.md` 3, 5.1, 5.3, 5.4; `indexer/pipeline/run.py`, `verify.py`, `extract.py`, `embed.py`; A02 spec `phase-04-extract-clean.md` for what extraction loses.

### Scope
- `indexer/pipeline/verification/` package: `quality.py`, `completeness.py`, `recency.py`, `uniqueness.py` (pure functions on a `Candidate` dataclass), `signature.py` (3-window mean embedding), `report.py` (JSON and text table), `decide.py` (verdict to action).
- `indexer/pipeline/lake.py`: lake paths, quarantine copy with reason file, report writer. Works on a local directory in tests (`LAKE_DIR`).
- Integration into `run_pipeline` as a stage between extract and clean/chunk, behind the incremental flow of R3; in R2 it runs in `--verify-only` / `--dry-run` form and in the A02 full path (a failed document is skipped and reported instead of aborting; `VERIFY_STRICT=true` restores the A02 abort).
- Near-duplicate threshold calibration script `scripts/calibrate_neardup.py` over the 9 real documents and Batch B, writing `eval/results/neardup-calibration-<ts>.json`; the chosen threshold is a default constant with the calibration file as its justification (D-113).
- A text rendering for the screenshot: `python -m pipeline.report <run_id>` prints a table, one row per document, one column per check, reasons shown.

### Out of scope
Registry and incremental swap (R3). Kubernetes (R8). The injection rail (R6): Batch B problem 7 is expected to **pass** verification.

### Acceptance criteria
- [x] R2-AC1 Each check is a pure function with tests for pass, fail and edge cases (empty text, one page, Unicode, a 1-page PDF, unreadable bytes).
- [x] R2-AC2 On Batch B the report contains an entry for every file, with four verdicts and reasons, and matches `PLANTED.json`: all planted problems except the injected instruction fail the expected check; both exact duplicates and the near-duplicate fail uniqueness (exact and near respectively); the truncated file fails completeness; the corrupt file fails quality; the missing-metadata file fails completeness; the older version is flagged by recency and given the action `supersede`; the controls pass.
- [x] R2-AC3 The 9 real documents all pass (no false positives), including the A02 version pair, which is recency (not uniqueness) and not quarantined.
- [x] R2-AC4 A failed document is copied to `quarantine/<run_id>/` with a `.reason.json`, and the chunk list handed to embed contains none of its chunks (test with a fake embedder: the embed call sees zero chunks from the quarantined file).
- [x] R2-AC5 `verification.json` exists per run, validates against its schema in the tests, and the text table prints one line per document.
- [x] R2-AC6 One bad document no longer aborts the run (exit code 0) unless `VERIFY_STRICT=true` (exit code 1). The A02 behaviour on a corrupt `_index.json` or missing file is unchanged.
- [x] R2-AC7 The near-duplicate threshold is within the calibration gap: the calibration file shows every planted near-duplicate above it and every distinct real pair below it, and states the margin.
- [x] R2-AC8 `make test && make lint` green; coverage of the new package at least 85 percent.

### Verify
`cd indexer && ../.venv/bin/pytest -q --cov=pipeline/verification`; `python -m pipeline.run --dry-run` against `corpus/batch_b` with `EMBED_MODEL=hashing-bow-768` (CI mode) and once with real Ollama; `python scripts/calibrate_neardup.py`.

---

## Phase R3: Incremental update, archive, restore (A2)

| | |
| --- | --- |
| Branch | `feat/rag-r03-incremental` |
| Requirements | R3-A2-1 to R3-A2-4, R3-AB-2 |
| Estimate | 7 h |

### Objective
Embed only the delta, copy the rest, swap atomically; a re-run on an unchanged corpus embeds zero chunks; changed, deleted and superseded documents behave as the assignment says; versions can be archived and restored (architecture 5.4, 5.5, AD-32, I-20, I-21).

### Read first
`architecture-a3.md` 5.4 and 5.5, A3-R1; `indexer/pipeline/store.py`, `run.py`; A02 architecture 5.4.3 and 5.4.4; `api/app/services/index_state.py` (how the API re-resolves).

### Scope
- **Spike first (A3-R1):** read stored embeddings back from a Chroma 1.0.12 collection, build a copy, compare top-5 for the 18 A02 questions. Record the result; if it fails, stop and tell Zain.
- `indexer/pipeline/registry.py` (load, atomic save, reconcile against the live collection), `incremental.py` (classify, plan, copy-forward, assert), `restore.py` (CLI).
- `run.py`: `--incremental` default, `--full`, `--dry-run`, summary JSON line and text (`new`, `changed`, `unchanged`, `deleted`, `quarantined`, `superseded`, `chunks_embedded`, `chunks_copied`, `chunks_total`, `index_swapped`, `index_id`).
- `store.py`: a function to build the staging collection from copied plus new chunks, reusing the AD-02 swap (no change to the swap).
- Archive writer: superseded and deleted document versions to `archive/<source>/<sha12>/`.
- Chunk ids stay as AD-28; the registry holds each document's chunk count.
- Integration test with a real Chroma (`make dev-services`) marked integration; unit tests with a fake client for the rest.

### Out of scope
Cluster Jobs (R8). Candidate collections (R9).

### Acceptance criteria
- [ ] R3-AC1 Spike result recorded; top-5 of the copied collection equals the original for every question (or the phase stops).
- [x] R3-AC2 First run on an empty lake builds everything and writes a registry whose chunk counts sum to the collection count.
- [x] R3-AC3 **Unchanged re-run:** `chunks_embedded: 0`, `index_swapped: false`, `index_id` unchanged, exit 0. The embedder is spied in the test and called zero times.
- [x] R3-AC4 **Changed document:** edit one document; `chunks_embedded` equals that document's new chunk count; the chunk ids and vectors of every other source are identical before and after; the old chunks of the changed document are gone.
- [x] R3-AC5 **Deleted document:** remove a file; after the run `count(where source=X)` is 0, total count equals the registry sum, and the file's last version is in `archive/`.
- [x] R3-AC6 **Superseded version:** ingesting the Batch B newer version marks the old document's chunks `superseded=true` with no re-embedding of the old document, the old file is archived, and a default query no longer returns it (integration test, or the CI embedder).
- [x] R3-AC7 **Restore:** `restore --source <old>` makes the old document retrievable again by default and supersedes the newer one; the A02 version-scope test (`scope.py`) still passes.
- [x] R3-AC8 A registry or collection mismatch (different `embed_model` or chunk settings) refuses incremental mode with a message naming the difference; `--full` works.
- [x] R3-AC9 A failure at any point before the swap leaves the live collection and the registry untouched (fault-injection test at three points).
- [ ] R3-AC10 Both batches pass through A1 and A2: the run on `corpus/raw` plus `corpus/batch_b` produces the verification report and a collection equal to the registry (I-21), proven by a script `scripts/check_registry.py`.
- [ ] R3-AC11 `make test && make lint` green; `make eval-fixtures` gate still green; coverage of new modules at least 85 percent.

### Verify
`make dev-services && cd indexer && ../.venv/bin/pytest -q -m integration`; `python -m pipeline.run` twice and `python scripts/check_registry.py`; `make eval-fixtures`.

---

## Phase R4: Golden set, module level, component level, noise

| | |
| --- | --- |
| Branch | `feat/rag-r04-golden-retrieval` |
| Requirements | R3-B-1 to R3-B-5 |
| Estimate | 5 h |

### Objective
`eval/golden.jsonl` with the assignment's minimums, the embedding-level and retrieval-level measurements with their metrics and the typo noise test (architecture 6.1 to 6.3).

### Read first
`architecture-a3.md` 6.1 to 6.3; `eval/run_eval.py` (`section_matches`, `recall_at_k`); `eval/golden.yaml`; `eval/retrieval_only.py`; `eval/tuning/`.

### Scope
- `eval/golden.jsonl`: carry over the 18 A02 questions (convert, label origin), add at least 7 more to reach 25 or more with the required composition, including at least 5 unanswerable and at least 5 hard (paraphrased, multi-chunk, or Batch B), at least 8 written by hand by the group (H3-2), each labelled `human` or `synthetic`, at least 8 synthetic ones reviewed by hand and marked (H3-4). Page numbers for every answerable question.
- `eval/suite/golden.py` (load, validate, `--check` writes a counts file), `eval/embedding_pairs.jsonl` (15 or more paraphrase pairs and 15 or more unrelated pairs, written to be non-trivial), `module_level.py`, `component_level.py` (recall@3, recall@5, MRR, nDCG@5; per group; noise with seeded typos).
- Tests for every metric with hand-computed examples (including nDCG with two relevant pairs and a miss).
- A first baseline run on the live index (Ollama up): results file under `eval/results/` and a row in the results register. This also feeds the thresholds of R7 and the coverage calibration of R10.

### Out of scope
Answer-level metrics and the judge (R5). The one command (R5).

### Acceptance criteria
- [x] R4-AC1 `python -m eval.suite.golden --check` exits 0 and reports at least 25 questions, 15 answerable each with source, section and page, 5 unanswerable, 5 hard, 8 `human`, every question labelled, 8 synthetic marked `reviewed`; it exits non-zero when any minimum is short (test with a trimmed file).
- [ ] R4-AC2 Every `relevant` entry resolves: the (source, section) exists in the indexed corpus (checked by `scripts/chunk_report.py`-style lookup against the live collection or the fixtures), and the page matches the chunk's page.
- [ ] R4-AC3 The 18 carried-over questions give the same recall@5 as `eval/results.json` of A02 for the same index (regression anchor; difference explained if any).
- [x] R4-AC4 Metric functions pass hand-computed tests: recall@3 and @5, MRR (rank 1, rank 4, miss), nDCG@5 (two relevant pairs, one retrieved late, none).
- [ ] R4-AC5 Module level output has paraphrase mean, unrelated mean, gap, median and p95 ms per chunk over at least 100 chunks, and determinism max difference, from at least 15 plus 15 pairs.
- [x] R4-AC6 The noise test uses a seeded typo generator (same seed, same output; test) and reports each metric clean, noisy, absolute and relative change.
- [ ] R4-AC7 A results file `eval/results/suite-<ts>-baseline-partial.json` exists with module and component sections and the committed numbers are in the register.
- [ ] R4-AC8 `make test && make lint` green; `golden.yaml` and A02 tests untouched.

### Verify
`python -m eval.suite.golden --check`; `python -m eval.suite.component_level --api http://localhost:8000` with the stack up; `make test && make lint`.

---

## Phase R5: End-to-end level, judge, stochasticity, one command

| | |
| --- | --- |
| Branch | `feat/rag-r05-e2e-suite` |
| Requirements | R3-B-6 to R3-B-9 |
| Estimate | 7 h |

### Objective
The whole Part B suite behind one command, with answer-level metrics, a judged faithfulness measure checked against hand labels, and a two-run reproducibility report (architecture 6.4 to 6.6, AD-36, AD-38).

### Read first
`architecture-a3.md` 6.4 to 6.6, A3-R3, A3-R4; `api/app/providers/llm/ollama.py`; `api/app/routes/ask.py`; `eval/run_eval.py`.

### Scope
- API: `LLM_SEED` setting passed as Ollama `options.seed`; request header `X-Cache-Bypass: 1` skips lookup and store (cache value `SKIP`); tests in `api/tests`. ConfigMap key added (`k8s/base/configmap.yaml`) and recorded as a deviation.
- `e2e_level.py`: abstention correctness (with false-abstention rate), citation validity, latency p50 and p95, per-question records; `judge.py`: judge prompt and schema, deterministic overlap score; `eval/judge_labels.jsonl` with at least 12 hand-labelled answers (H3-3) and the agreement and kappa computation.
- `run_suite.py` (one command; writes `eval/results/suite-<ts>-<label>.json` and `.md` summary table), `stochasticity.py` and `make suite`, `make suite-twice`.
- Calibrate the overlap threshold 0.6 on the labelled answers (record the calibration).
- Runs: baseline suite twice on the live index; the results go into the register.

### Out of scope
Gate (R7). Cluster Job (R8).

### Acceptance criteria
- [x] R5-AC1 With `LLM_SEED` set and the same inputs, `options.seed` is in the Ollama request (test with a mock transport); unset means no `seed` key (A02 behaviour).
- [x] R5-AC2 A request with `X-Cache-Bypass: 1` never reads or writes Redis and returns `X-Cache: SKIP`; a request without it behaves as in A02 (tests, plus the A02 cache tests unchanged).
- [ ] R5-AC3 `make suite` runs module, component (clean and noisy) and end-to-end levels in one command and writes the timestamped JSON and the `.md` summary table with all three levels.
- [ ] R5-AC4 The e2e section reports faithfulness (judge and overlap), abstention correctness, false abstention rate, citation validity, p50 and p95, each with the numerator and denominator.
- [ ] R5-AC5 `eval/judge_labels.jsonl` has at least 12 hand labels (at least 8 required by R3-B-7); the result reports agreement percent and kappa; labels were made by people, not by the judge (the file records who).
- [ ] R5-AC6 `make suite-twice` produces two result files and `stochasticity-<ts>.json` with the per-metric absolute difference and the list of questions whose answers differed; the explanation text is committed in the spec's test report.
- [x] R5-AC7 The suite exits non-zero when the API is unreachable or a level fails to run, with a clear message (no partial file presented as a full result).
- [ ] R5-AC8 `make test && make lint` green; `make eval-fixtures` gate green.

### Verify
`make suite` against `make dev` with real services; `make suite-twice`; `cd api && ../.venv/bin/pytest -q`; `make eval-fixtures`.

---

## Phase R6: Trace, trace tool, metrics report, injection rail

| | |
| --- | --- |
| Branch | `feat/rag-r06-traces` |
| Requirements | R3-D1-1, R3-D2-1, R3-D3-1, R3-D3-2, R3-D4-1, R3-D5-1, R3-F4-1 (API half) |
| Estimate | 6 h |

### Objective
Every query writes one trace line with everything needed to reconstruct the answer; a tool rebuilds the prompt from a trace id; a script summarises a window; one retrieval rail logs its action (architecture 7).

### Read first
`architecture-a3.md` 7 and I-22, I-23; `api/app/services/answer.py`, `prompt.py`, `validate.py`, `api/app/logjson.py`, `api/app/routes/metrics.py`; A02 architecture 5.11.

### Scope
- `api/app/services/trace.py` (record builder, emitter to a dedicated logger and to `TRACE_DIR/traces-<date>-<pod>.jsonl`, never raises), `guardrails.py` (`scan_passages`), wiring in `answer_question` for every outcome (answered, abstained, fallback, cached).
- Embedding version: digest lookup in the embedder with caching; `unknown` on failure.
- `scripts/trace_tool.py` (`show <trace_id>`, hash check, `--chunks`), `scripts/trace_report.py` (`--since`, `--dir`, markdown and text output).
- Metrics: `rahbar_injection_flags_total{rail}`, `rahbar_trace_write_errors_total`; metric names list in `architecture.md` 4.14 updated through the deviation.
- Sample traces for the report under `traces/samples/` (one answered, one abstained, one with an injection action).
- Unit tests: field completeness against the R3-D1-1 list, one trace per outcome, writer failure swallowed, prompt hash reproducible, no secret fields.

### Out of scope
Cluster volume (R8). The root-cause write-up (R10/R11 use it; R6 only proves the tool shows the cause).

### Acceptance criteria
- [x] R6-AC1 A test asserts every field of the R3-D1-1 list is present (value or explicit `null`) in the trace for an answered, an abstained, a fallback and a cached request; `trace_id == request_id`.
- [x] R6-AC2 The trace goes to stdout as one JSON line with `"type": "trace"` and, when `TRACE_DIR` is set, to a per-pod file; with `TRACE_DIR` unwritable the request still succeeds and `rahbar_trace_write_errors_total` increments.
- [x] R6-AC3 `trace_tool show <id>` prints the query, filter, retrieved chunks with scores and versions, the exact prompt, the parameters and the response, and prints `hash OK` for an untouched trace and `hash MISMATCH` for an edited one.
- [x] R6-AC4 `trace_report --since` prints top-1 similarity distribution, abstention rate, cache hit rate, p50 and p95 per stage and injection count, and its numbers equal an independent recomputation in the test.
- [x] R6-AC5 (live proof in R11: docs/evidence/a3/e3-injection-rail-live.txt) **Rail:** the Batch B injected document, once indexed (CI embedder with a fixture index or the real index), is retrieved by its planted question, dropped from the evidence, the trace holds `{rail: injection_scan, action: dropped_passage, chunk_id, pattern}`, and the metric counter is 1.
- [ ] R6-AC6 The A02 injection golden question still abstains or answers safely (`make eval-fixtures` gate green) and every A02 API test is unchanged and green.
- [x] R6-AC7 No trace contains the Ollama URL, an environment variable or a header (test scanning for `OLLAMA_URL` and `Authorization`).
- [ ] R6-AC8 One real question end to end on the local stack is saved as `traces/samples/answered.jsonl`, and `trace_tool` reproduces its prompt hash.

### Verify
`cd api && ../.venv/bin/pytest -q --cov=app`; run the API locally with `TRACE_DIR=/tmp/...`, ask three questions, run the tool and the report; `make eval-fixtures`.

---

## Phase R7: Change experiment and release gate

| | |
| --- | --- |
| Branch | `feat/rag-r07-gate` |
| Requirements | R3-C1-1, R3-C1-2, R3-C2-1 to R3-C2-3 |
| Estimate | 6 h |

### Objective
One justified pipeline change (chunk size and overlap) compared on all three levels, a gate script and config that exit pass or fail, and one failing and one passing candidate with the release decision written down (architecture 8).

### Read first
`architecture-a3.md` 8; the R4 and R5 baseline files; `eval/tuning/` results; D-120.

### Scope
- `eval/suite/compare.py` (side-by-side table of every metric of the three levels with deltas), `gate.py`, `eval/gate.yaml`, tests with canned result files.
- Build at least three candidate collections locally with the indexer (`CHROMA_COLLECTION=rahbar_cand_<tag>`, `INDEX_MODE=full`, `CHUNK_SIZE`, `CHUNK_OVERLAP`), run the suite against each (the local API pointed at that collection), pick one that fails the gate and one that passes, from measurement.
- Justify each threshold in `eval/gate.yaml` comments and in `docs/evidence/r7-decision.md` (baseline numbers, noise level from the two-run difference, latency budget from measured p95).
- Release decision document: release or reject, with reasons, for the passing candidate.

### Out of scope
Doing it on the cluster (R8, R9).

### Acceptance criteria
- [ ] R7-AC1 `gate.py` returns 0 on a candidate equal to the baseline, 1 on a candidate that violates any single rule (one test per rule type), 2 on a malformed file; it has no numeric limit in code (a grep test).
- [ ] R7-AC2 Thresholds live only in `eval/gate.yaml`, each with a one-line justification referencing a committed number.
- [ ] R7-AC3 `compare.py` output covers module, component and end-to-end metrics for baseline and candidate, committed for every candidate run.
- [ ] R7-AC4 At least three candidates were measured; one fails the gate and one passes; both gate outputs are committed (`eval/results/gate-*.txt`) with exit codes.
- [ ] R7-AC5 The release decision names the candidate, the metric deltas, and a reason either way; it also states which metric would have made us reject.
- [x] R7-AC6 Re-running the gate on the same two files twice gives identical output (determinism).
- [x] R7-AC7 `make test && make lint` green.

### Verify
`python -m eval.suite.gate --baseline <b> --candidate <c>; echo $?` for each candidate; `make test`.

---

## Phase R8: Kubernetes deployment of RAGOps

| | |
| --- | --- |
| Branch | `feat/k8s-r08-ragops` |
| Requirements | R3-F1-1, R3-F1-2, R3-F2-1 to R3-F2-3, R3-F4-1, R3-F4-2, R3-F5-1, R3-F5-2, R3-LOG-11 |
| Estimate | 8 h |

### Objective
The A1 and A2 ingestion, the suite, the gate and the traces all run on the minikube cluster as the assignment describes: PVCs, Jobs, a CronJob, ConfigMaps, measured resources, and a README that rebuilds a cluster from the manifests (architecture 9).

### Read first
`architecture-a3.md` 9; `k8s/base/*.yaml`, `k8s/overlays/*`, `k8s/tools/corpus-loader.yaml`; A02 architecture 4.4 to 4.9; `docs/evidence/k10-*`; `Makefile` cluster targets; A3-R2, A3-R6.

### Scope
- New PVCs `lake-data`, `traces-data`, `eval-results`; Job `indexer` and CronJob `reindex` mount `lake-data` read-write and `corpus-data` read-only; the API mounts `traces-data`; `TRACE_DIR`, `LAKE_DIR`, `LLM_SEED`, `INDEX_MODE` in `configmap.yaml`.
- `eval/Dockerfile`, image `rahbar-eval`, `make images` and `minikube image load`; CI build step and CD matrix entry (`.github/`), image tag by commit SHA (I-12).
- `k8s/eval-job.yaml` (applied with `kubectl apply -f k8s/eval-job.yaml`), ConfigMap `rahbar-gate` generated from `eval/gate.yaml` by Kustomize, `trace-report` Job.
- `make ingest-batch BATCH=<dir>`: merges a batch into the inbox PVC (`scripts/add_batch.py` computes sha256 and manifest entries), `make lake-ls`, `make lake-pull`, `make results-pull`, `make traces-pull`.
- NetworkPolicies extended for the eval Job, the trace-report Job and the lake; an enforcement proof as in K4.
- `scripts/measure_resources.sh`; requests and limits set from the measurements for the API, Chroma, the indexer and the eval Job; `docs/evidence/f5-resources.txt`.
- `k8s/README.md`: the fresh-cluster command list.
- Cluster evidence files for R3-S-F1 to R3-S-F4 and R3-S-A1, R3-S-A2 captured with the exact commands.

### Out of scope
The candidate Deployment and rollout (R9).

### Acceptance criteria
- [ ] R8-AC1 `kustomize build k8s/overlays/dev | kubeconform -strict` passes and `kubectl apply -k k8s/overlays/dev` on a **deleted and recreated** minikube reaches a working pipeline using only `k8s/README.md`'s commands.
- [ ] R8-AC2 `kubectl get all,pvc,configmap,cronjob,job -n rahbar` shows the new objects and the three new PVCs `Bound`; the output is saved (R3-S-F1).
- [ ] R8-AC3 The ingestion Job on `corpus/raw` plus Batch B (via `make ingest-batch`) completes; its log shows the verification table and the summary; the lake PVC holds the report, quarantine files and archive files; they survive `kubectl delete pod` of the Job pod's successors and of Chroma (R3-F1-2).
- [ ] R8-AC4 A second Job run on the unchanged inbox logs `chunks_embedded: 0, index_swapped: false` (R3-S-A2); the CronJob `reindex` created by `kubectl create job --from=cronjob/reindex` does the same.
- [ ] R8-AC5 Only the Job can write to Chroma: the API, eval and trace-report pods have no route to a write (checked by the NetworkPolicy proof and by the code search test `no chroma write in api/`), and the lake mount is read-only in every non-Job pod.
- [ ] R8-AC6 `kubectl apply -f k8s/eval-job.yaml` runs the suite and the gate against the live `api` Service and writes its result file to `eval-results`; the Job is `Complete` when the gate passes and `Failed` when it fails (both observed).
- [ ] R8-AC7 **ConfigMap edit changes the outcome without a rebuild:** edit one threshold in `rahbar-gate`, delete and re-apply the eval Job (same image digest), and the exit status flips; both runs saved (R3-S-F4).
- [ ] R8-AC8 `kubectl logs deploy/api | grep '"type": "trace"'` shows trace lines, three per-pod trace files exist on `traces-data`, and `kubectl port-forward svc/api 8000:80` then `curl /metrics` shows the metric names (R3-F4-1, R3-F4-2).
- [ ] R8-AC9 Resource requests and limits are set on every container including the Jobs, from `f5-resources.txt`; the file contains the raw peaks and the rule used.
- [ ] R8-AC10 Images are built with the commit SHA tag; CI (`ci.yml`) is green on the PR including `rahbar-eval`; no `:latest` anywhere (I-12).
- [ ] R8-AC11 All A02 cluster checks still hold: `/readyz` 200, HPA, probes, the rollout test, the pin test (re-run `docs/evidence` K-series commands that matter, saved as `r8-regression.txt`).

### Verify
As each criterion states; plus `make test && make lint`, `make manifests`.

---

## Phase R9: Controlled release and rollback

| | |
| --- | --- |
| Branch | `feat/k8s-r09-release` |
| Requirements | R3-C3-1, R3-F3-1 to R3-F3-4 |
| Estimate | 4 h |

### Objective
Release the R7 candidate through the gate on Kubernetes with a rolling update; show a candidate stopped by the gate, and a bad release undone, with traces proving the collection and embedding version (architecture 9.3, AD-44).

### Read first
`architecture-a3.md` 9.3, I-26, A3-R7; `k8s/base/api.yaml`; R7 decision document.

### Scope
- `k8s/candidate/` (Kustomization: Deployment and Service `api-candidate`, a `candidate-indexer` Job template with env overrides); `make candidate TAG=...` builds the candidate collection and rolls the candidate out; `make release` applies the gate then `kubectl set env deployment/api CHROMA_COLLECTION=...`; `make rollback` is `kubectl rollout undo deployment/api` plus a verifying query.
- `revisionHistoryLimit: 10` on `api`; confirm `maxUnavailable: 0`.
- A scripted rehearsal `scripts/release_demo.sh` with the commands in order and saved output; the evidence files for R3-S-F5.

### Out of scope
Anything that changes the candidate's metrics (decided in R7).

### Acceptance criteria
- [ ] R9-AC1 `api-candidate` runs against `rahbar_cand` with its own Service; the live `api` still reads `rahbar` (verified by `/readyz` and a trace from each).
- [ ] R9-AC2 The eval Job pointed at `api-candidate` with the live baseline runs the gate. **Failing candidate:** the Job fails; no change is made to the live Deployment (`kubectl rollout history deployment/api` unchanged); output saved.
- [ ] R9-AC3 **Passing candidate:** the gate Job completes, `kubectl set env` starts a rolling update, `kubectl rollout status deployment/api` reports success, availability never drops (a loop of requests during the update has zero non-200 responses), and a trace shows `collection.name = rahbar_cand`.
- [ ] R9-AC4 **Bad release:** a deliberately bad collection is released by force (without the gate); the service degrades visibly (trace and metric evidence: abstentions or low scores); `kubectl rollout undo deployment/api` restores the previous revision; `kubectl rollout status` succeeds.
- [ ] R9-AC5 After the undo, a new query's trace shows the previous `collection.name` and `embedding.version` (R3-F3-4), saved with the command (R3-S-F5).
- [ ] R9-AC6 Redis cache cannot serve a stale answer across the release: the cache scope key includes `index_id`, shown by one query before and after (A02 AD-04 holds with a different collection).
- [ ] R9-AC7 `make test && make lint` green; `docs/evidence/r9-*.txt` saved.

### Verify
`scripts/release_demo.sh`; `kubectl rollout history deployment/api`.

---

## Phase R10: Drift and coverage

| | |
| --- | --- |
| Branch | `feat/rag-r10-coverage` |
| Requirements | R3-E1-1, R3-E2-1, R3-E3-1, R3-E4-1, R3-E4-2, R3-D5-1 (analysis) |
| Estimate | 4 h |

### Objective
Show whether the tests still match real usage, what Batch B changes in the system, and that closing the gap raises coverage (architecture 10).

### Read first
`architecture-a3.md` 10 and 7.5; R4 module-level result; R3 and R8 ingestion evidence.

### Scope
- `eval/live_queries.jsonl` (at least 40 queries: about 28 in domain, at least 12 outside), `eval/suite/coverage.py` and `eval/coverage.yaml`.
- Coverage run before; uncovered queries grouped into topics; at least 6 new golden questions (R4 file extended, labelled, reviewed); coverage run after; the script's exit code both times.
- Data drift run: Batch B is ingested through the real Job (A1 and A2), the suite is re-run, `compare.py` shows the change; `eval/results/drift-<ts>.json` with the explanation fields.
- Root-cause write-up input: pick one wrong or abstained answer from the Part B results and produce its trace analysis (`docs/evidence/d5-root-cause.md`, 5 lines).

### Out of scope
Report text (R11).

### Acceptance criteria
- [ ] R10-AC1 `live_queries.jsonl` has at least 40 queries, about 28 in domain and at least 12 off-domain, each with an expected topic; none is a copy of a golden question (test: no exact duplicate).
- [ ] R10-AC2 `coverage.py` reports the share above the threshold, the threshold with its calibration source, the uncovered queries with topic groups, and exits non-zero when the share is below the target (tests with a trimmed golden set).
- [ ] R10-AC3 Before run: the coverage is below the target on purpose or by finding (state which); after adding at least 6 golden questions the share rises; both outputs saved (R3-S-E1, R3-S-E2).
- [ ] R10-AC4 The new golden questions are in `eval/golden.jsonl`, labelled, with relevant sources and pages, and `golden --check` still passes.
- [x] R10-AC5 (done in R11, `docs/evidence/a3/e3-data-drift.md`, `eval/results/drift-20261121T083232Z.json`) The drift run records what changed after Batch B: at least the metrics that moved, the questions that changed outcome, the retrieved-document change for the version question and the injected document's handling, each with its cause.
- [ ] R10-AC6 `d5-root-cause.md` uses only fields from a trace and names the cause (chunk, document version or filter) in five lines.
- [ ] R10-AC7 `make test && make lint` green.

### Verify
`python -m eval.suite.coverage ...; echo $?` before and after; `python -m eval.suite.run_suite --label drift`.

---

## Phase R11: Evidence, report, README, final verification

| | |
| --- | --- |
| Branch | `docs/r11-report` (and `feat/...` fixes as needed) |
| Requirements | R3-G-1 to R3-G-5, R3-S-*, R3-LOG-8 to R3-LOG-10 |
| Estimate | 8 h |

### Objective
The report, the screenshots, the README and a clean-clone rehearsal, so the repository and the PDF are the submission.

### Read first
`requirements-a3.md` sections G and "Screenshots"; the results register in section 5; `docs/FINAL-WALKTHROUGH.md` (style of the A02 oral check).

### Scope
- `docs/report/report.md` (source) rendered to PDF (Pandoc to HTML, then headless Chrome print, because no LaTeX engine is installed: D-125; 8 pages at most, page 1 with names and roll numbers, which Zain supplies), figures from committed files, the tables G-1 and G-2, short answers (a) to (f), contribution table, AI statement.
- The screenshot appendix: each of the 14 required screenshots, terminal captures with the command and output, labelled, from our own cluster, none cropped; stored under `docs/evidence/a3/`; Ahmad reviews (H3-5, H3-6).
- `README.md`: the exact command for each of A to F, status table.
- `docs/rubric_checklist.md` section F, `scripts/check_numbers.py` extended so that every number in the report appears in a committed result file (I-25).
- Final verification: delete minikube, rebuild from `k8s/README.md`, run the demo script (eval Job, open a trace, ingest an unseen batch), record timings; tag the release PR `dev` to `main`.
- `docs/AI-USAGE.md` entry for A3.

### Acceptance criteria
- [x] R11-AC1 The report PDF is at most 8 pages excluding the appendix, names and roll numbers on page 1, and contains items G-1 to G-5.
- [x] R11-AC2 `scripts/check_numbers.py` finds every numeric claim of the report in a committed file; no unmatched number remains.
- [x] R11-AC3 All 14 screenshots exist, show the command and the output uncropped, carry their part and item label, and each file maps to a cluster run recorded in the log.
- [x] R11-AC4 The README command for each of A to F is executed once on a clean clone by someone other than the author (Ahmad if available, otherwise a fresh shell by Zain) and the log records the result.
- [x] R11-AC5 The fresh-cluster rehearsal passes: a deleted cluster reaches a working pipeline from the manifests; the demo script completes within the time recorded.
- [x] R11-AC6 Section 6 checklist is fully ticked with pointers, or each unticked item is listed as an honest gap in the report and the README.
- [x] R11-AC7 `git log` shows commits by both members (R3-LOG-6); the contribution table is truthful.
- [x] R11-AC8 No secret, no `corpus/raw/`, no model in the history of the submitted branch (scan saved).

### Verify
the report build command from D-125 and the PDF page count; `python scripts/check_numbers.py`; the rehearsal transcript.
2026-11-21  R12  CLOSE-OUT: roll numbers on report page 1 (5 body pages, number check exit 0); golden g51 and g52 (version-aware refund pair, live index rank 1 and 2, not in the measured runs); eval/REVIEW_SHEET.md and scripts/mark_reviewed.py; final audit docs/evidence/a3/final-requirements-audit.md (56 MET, 21 with caveat, 1 NOT MET: R3-B-2 second half, 1 n/a). Spec docs/specs/phase-r12-closeout.md.
2026-11-21  R13  REVIEW RECORD: Zain reviewed g19 g20 g21 g23 (original PDFs) and g28 g29 g30 g33 (invented Batch B files, correct by construction); mark_reviewed applied, builder carries REVIEWED, golden --check exit 0 (52 questions, 8 synthetic reviewed), R3-B-2 MET with nuance. Spec docs/specs/phase-r13-review-record.md. D-147.
