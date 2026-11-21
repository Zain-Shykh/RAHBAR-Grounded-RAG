# RAHBAR rubric checklist

Working checklist for **Assignment 02** (closed). **Assignment 03 (RAGOps) has its own checklist in section F at the end of this file** and its requirements in `docs/requirements-a3.md`. Source of detail: `docs/requirements.md` (IDs in brackets). Tick a box only with evidence (file path, command output or screenshot in `docs/evidence/`). Re-run the whole list before submitting, plus `make check`.

Legend: `[x]` done and evidenced, `[ ]` not done. Point weights for graded lines are not published in the assignment; deductions are.

---

## A. Things to AVOID (automatic deductions)

**Final verification, 2026-11-07 (phase 15).** Every row above is ticked on this evidence:

| Violation | Evidence |
| --- | --- |
| R-DED-1 secret in history | `git log -p --all` scanned for `dckr_pat_`, `gsk_`, `AIza`, `sk-`, `ghp_`, private-key blocks: no hit. Word-level scan (`api_key`, `token`, `password`, `secret`) reviewed: only code identifiers, docs and the placeholder template. `docs/evidence/final-history-scan.txt` |
| R-DED-2 Secret with a value | only `k8s/base/secret.placeholder.yaml` (`REPLACE_ME`), not in `kustomization.yaml`; `kubectl kustomize` output has no `Secret` (`docs/evidence/k05-manifests.txt`) |
| R-DED-3 index at startup | indexer is a Job (ADR 0001); `grep -rn 'upsert\|\.add(' api/app` is empty |
| R-DED-4 / R-DED-5 | `eval/results.json`: citation validity 1.0 (16 of 16), abstention 1.0 (2 of 2); through the Ingress `docs/evidence/k10-eval-gate.txt` |
| R-DED-6 | chroma StatefulSet with `volumeClaimTemplates`, redis Deployment + PVC, four ClusterIP Services (`k8s/base/`) |
| R-DED-7 | `docs/evidence/k10-embed-pin-mismatch.txt` (`0/1`, 503 `embed_pin`, log line) |
| R-DED-8 | `docs/evidence/resources.md`, `k10-hpa.txt` (real percentage) |
| R-DED-9 | `.github/workflows/cd.yml`: `needs:` on `build-push` and `deploy`, tags are the commit SHA, no `:latest` (the workflow checks the rendered manifests too); `k08-cd-run.txt` |
| R-DED-10 | namespace `rahbar` via kustomize `namespace:`; `k01-images-and-manifests.txt` |
| R-DED-11 | `docs/evidence/k11-clean-clone.txt` (README followed line by line from a fresh clone) |
| R-DED-12 | only the initial commit (`53bd1b9`) was made on `main` before protection; every other change reached `main` through PR #1 and #2 and the release PR. Protection: `k09-branch-protection.txt` |


Check every one before each merge to `main` and again at submission. Total possible loss if all hit: −111.

| Done right? | Pts | Violation | How we stay clear | Verify with |
| :---: | ---: | --- | --- | --- |
| [x] | −20 | Secret, key or password anywhere in Git history [R-DED-1] | `.gitignore` covers `.env*`, `*secret*.yaml`, keys. Secrets only via `make secret`. Never paste a key into a file, even briefly. If one leaks: rotate and write a two-line incident note. | `git log -p \| grep -iE 'api[_-]?key\|token\|password\|secret'`; look for the Docker Hub token |
| [x] | −15 | Base64 Secret with a real value in a committed manifest [R-DED-2] | Only `k8s/base/secret.placeholder.yaml` with `REPLACE_ME`, and not listed in `kustomization.yaml` | `grep -rn 'kind: Secret' k8s/`; inspect values |
| [x] | −10 | Indexing at API startup [R-DED-3] | Indexer is a Job; API has no write path to Chroma | `grep -rn 'add\|upsert' api/app` finds no writes; ADR 0001 exists |
| [x] | −10 | A returned citation not matching a retrieved chunk [R-DED-4] | Post-generation citation check against `retrieved`; drop or fall back on mismatch | `citation_validity` = 100% in `eval/results.json`; unit test |
| [x] | −10 | Must-abstain golden question answered from context [R-DED-5] | Relevance floor + prompt + validation | Abstention correctness 100% in `eval/results.json` |
| [x] | −8 | Chroma or Redis as Deployment with no PVC, or NodePort/LoadBalancer [R-DED-6] | Chroma = StatefulSet + `volumeClaimTemplates`; Redis = Deployment + PVC; all Services ClusterIP | `kubectl get svc,pvc -n rahbar` |
| [x] | −8 | Embedding model not pinned, or indexer and API can disagree silently [R-DED-7] | One ConfigMap key; collection metadata check in `/readyz` | Demo: change `EMBED_MODEL`, API sits at `0/1` with a log line |
| [x] | −6 | A container with no requests, or HPA reading `<unknown>` [R-DED-8] | Requests and limits on every container including Job and CronJob; metrics-server on | `kubectl get hpa -n rahbar` shows a number; grep manifests for `resources:` |
| [x] | −6 | Publish/deploy job without `needs:`, or `:latest` [R-DED-9] | `cd.yml`: `build-push needs: test`, `deploy needs: build-push`; tag `${{ github.sha }}` | `grep -n 'latest\|needs' .github/workflows/*.yml` |
| [x] | −5 | Manifests in `default` namespace [R-DED-10] | Namespace `rahbar` in every object (kustomize `namespace:`) | `kubectl get all -n default` is empty; `grep -L 'namespace' k8s/base/*.yaml` |
| [x] | −5 | README apply order fails from a clean clone [R-DED-11] | Test the README steps on a fresh clone and fresh minikube | Dry run on clean clone (or Ahmad's machine) |
| [x] partly | −4 | Commits pushed directly to `main` [R-DED-12] | Branch protection on. All work via `dev` + PR. (Initial commit went to `main` before protection: unavoidable now.) | `git log main --first-parent`; protection screenshot |

Extra "don't" items from the text (not listed as deductions but explicitly forbidden or scored):

- [x] Do not use lecture slides, an LLM-generated corpus, or paywalled/private documents [R-COR-10].
- [x] Do not commit the downloaded PDFs (`corpus/raw/` stays ignored) [R-COR-12].
- [x] Do not log to a file; stdout JSON only [R-OBS-1].
- [x] Do not let `/healthz` touch Chroma, Redis or the LLM [R-PRB-1].
- [x] Do not make `ui` able to reach `chroma` [R-SEC-4].
- [x] Do not cache follow-ups, abstentions, out-of-scope answers or failed validations [R-CAC-4].
- [x] Do not forget cache invalidation on re-index [R-CAC-5].
- [x] Do not let a user see a 500 from malformed model output [R-GEN-2].
- [x] Do not pass model or retrieved text to `eval`, or build SQL from it [R-SEC-5].
- [x] Do not assert on model wording in CI; assert on metrics [R-EVA-8].
- [x] Do not write a golden set from chunks already retrieved [§5.1].
- [x] Do not ship chunk settings without three measured configs [R-IDX-7] (scores zero).
- [x] Do not write generic engineering-note answers (scores zero) [R-ENG-*].
- [x] Do not remove the pause between fetch requests [R-COR-11].
- [x] Do not list the placeholder Secret in `kustomization.yaml` [§4.7].
- [x] Do not present AI output as our own; disclose in `AI-USAGE.md` [R-AI-1].
- [x] Do not leave any starter-kit placeholder marker or `raise NotImplementedError` in the repo [R-SUB-5].
- [x] Do not start minikube without `--cni=calico` [§9].

---

## B. Things to DO

### B1. Setup and process

- [x] Public repo, `.gitignore`, `dev` branch, `main` protected [R-DEV-1, R-DEV-2] — six required checks, strict, one approval recorded in `docs/evidence/k09-branch-protection.txt`; admin enforcement OFF by D-014.
- [x] Collaborator (Ahmad) added.
- [x] PR #1 (corpus) approved and merged; corpus named in first PR [R-LOG-3].
- [x] Dependencies documented in root `requirements.txt`.
- [x] minikube up with Calico, metrics-server, ingress.
- [x] Docker Hub account + access token; token stored only in GitHub Secrets [R-CD-4].
- [x] README replaced with our own [R-LOG-6].

### B2. Corpus [R-COR-1..13]

- [x] 6+ documents, 40+ pages (9 docs, 279 PDF pages).
- [x] Version pair (Aug 2023 rules, `superseded: true`; Jun 2026 handbook).
- [x] Scanned PDF (entrepreneurship policy; 2023 rules body).
- [x] Table with real information (fee, grading, annual reports).
- [x] Long definitions (Student Handbook GenAI policy).
- [x] Deliberately absent topic (hostel rules).
- [x] Exact-term content (clause numbers, CGPA 2.00, 130 credit hours, fees).
- [x] `docs/CORPUS.md` filled with all seven.
- [x] `corpus/MANIFEST.md` (URL + SHA-256) and `corpus/sources.yaml` committed, fetch script used.
- [x] README states documents are fetched, not committed.

### B3. Indexing pipeline [R-IDX-*]

- [x] Extract: detect no-text pages, OCR them, strip repeating headers/footers, keep headings.
- [x] Extract: HTML tables handled; PDF tables kept row-wise (`pdftotext -layout` or pdfplumber).
- [x] Clean: documented rules + one thing deliberately not stripped.
- [x] Chunk: sections, then paragraphs, then sentences; overlap; target size; unit stated.
- [x] Embed: pinned model, dimension recorded (768 for nomic-embed-text).
- [x] Store: id, text, vector, metadata. Metadata has `source`, `section`, `page`, `doc_version`, `superseded` on every chunk.
- [x] Collection metadata records embed model name + dimension [R-PIN-2].
- [x] Cache expired when the Job runs [R-CAC-5].
- [x] Three (size, overlap) configs measured on recall@5; table in `docs/PIPELINE.md`; shipped one justified.
- [x] `docs/PIPELINE.md` contains: OCR list, before/after table example, unrecovered loss, cleaning rules, storage amplification, model/dim/pin location, chunk count, metadata schema, how docs reach the Job.

### B4. Query pipeline and generation [R-QRY-*, R-GEN-*, R-LLM-*]

- [x] Validate 3 to 500 chars (422 otherwise; kit does this).
- [x] Semantic cache lookup (skipped for follow-ups); threshold from ConfigMap.
- [x] Embed with pinned model.
- [x] `ChromaRetriever` top-k with `superseded=false` filter unless user asks about older version.
- [x] Prompt: instructions, numbered delimited evidence, question.
- [x] LLM at configured low temperature; Ollama `format=` schema enforcement.
- [x] Pydantic validation; retry once; canned fallback.
- [x] Relevance floor, abstention with `answered_from_context: false`.
- [x] Citation check against retrieved chunks.
- [x] Poisoned-chunk injection test passes [R-GEN-6].
- [x] `reasoning` stripped from output.
- [x] Provider interface with `LLM_PROVIDER`; `ollama-host` fully working; swap = one file.
- [x] Temperature in ConfigMap with one-line justification.
- [x] ADR: cache choice (Redis vs second Chroma collection) [R-CAC-1].
- [x] Cache threshold chosen with data: 2 or 3 tried, false hit that ruled one out recorded [R-CAC-3].

### B5. Kubernetes [R-K8S-*]

- [x] Dockerfiles + `.dockerignore` for api, indexer; Dockerfile for ui (non-root, `/tmp` emptyDir).
- [x] Pinned image tags (`chromadb/chroma:1.0.12`, redis, nginx).
- [x] Namespace `rahbar`.
- [x] api Deployment: 3 replicas, 3 probes with the exact values, requests/limits, `maxSurge: 1`, `maxUnavailable: 0`, `terminationGracePeriodSeconds`, `preStop` sleep.
- [x] ui Deployment (1+ replicas).
- [x] chroma StatefulSet, 1 replica, `volumeClaimTemplates`.
- [x] redis Deployment + PVC.
- [x] indexer Job: `restartPolicy: OnFailure`, `backoffLimit` set, requests/limits.
- [x] reindex CronJob weekly, same image/args as Job.
- [x] 4 ClusterIP Services.
- [x] Ingress: `/` to ui, `/api` to api, one host.
- [x] ConfigMap: chunk size, overlap, top_k, relevance floor, cache threshold, temperature, EMBED_MODEL, LLM_PROVIDER, CHROMA_HOST.
- [x] Secret placeholder only; real Secret created via command line.
- [x] NetworkPolicies: default deny + DNS egress + Ollama host `ipBlock` + allow paths (ui from Ingress; api from ui and Ingress; chroma from api and indexer; redis from api).
- [x] Prove ui cannot reach chroma (exec test), api can.
- [x] HPA on api, 3 to 8, shows a real percentage.
- [x] One ServiceAccount per workload; `automountServiceAccountToken: false` where unused.
- [x] `runAsNonRoot`, `readOnlyRootFilesystem`, drop ALL capabilities on every container.
- [x] kustomize base + overlays `dev` and `prod`.
- [x] `readyz`: Chroma reachable, collection non-empty, Redis reachable, embed pin matches; 503 names failing dependency.
- [x] `healthz` touches nothing external.
- [x] `docs/ARCHITECTURE.md` explains why Chroma is a StatefulSet.
- [x] `make cluster && make images && make apply` order documented and works from clean clone.

### B6. Observability [R-OBS-*]

- [x] JSON logs to stdout.
- [x] `request_id` on every line (header or generated; echoed back).
- [x] Metrics: request count, request latency, retrieval latency, generation latency, cache hit ratio, abstention count, fallback count, tokens in/out.
- [x] Per-request log line: `top_k`, retrieved chunk ids, scores, abstention flag.

### B7. Evaluation [R-GOL-*, R-EVA-*]

- [x] `eval/golden.yaml` written before tuning: at least 15 questions: 8 ordinary, 2 version-sensitive, 2 exact-term, 2 must-abstain, 1 injection; relevant chunk ids or doc+section listed.
- [x] `recall_at_k`, `citation_validity`, `summarise`, `gate` implemented.
- [x] recall@3 and recall@5 overall and by question type, committed.
- [x] Exact-term recall vs definitional recall noticed and explained.
- [x] Citation validity reported (target 100%, gate 95%).
- [x] Abstention correctness 100%.
- [x] `eval/results.json` and `eval/baseline.json` committed.
- [x] Gate fails on: recall@5 drop > 5 points, any must-abstain answered, citation validity < 95%.

### B8. Failure analysis [R-FAI-*]

At least four of six, each with symptom, diagnosis, stage, remedy, and "how I'd have found it" with the metric or log number. All six are done (phase 16 added B and D, `docs/specs/phase-16-failure-experiments-bd.md`).

- [x] A · Extraction (index scanned PDF without OCR)
- [x] B · Chunking (100-word chunks, no overlap, 981 to 1 402 chunks; recall unchanged, expect-text in top 5 14/16 to 13/16; `docs/evidence/k16-b-*.txt`)
- [x] C · Retrieval (`top_k: 1` or API-only `EMBED_MODEL` change)
- [x] D · Prompt ("use only the evidence" removed in memory; 12 questions, intact vs D1 vs D2; D2 answers "120" credit hours from outside the cited chunk; `docs/evidence/k16-d-*.txt`)
- [x] E · Source (remove superseded filter, ask version question)
- [x] F · Generation (temperature 1.2)

### B9. CI/CD [R-CI-*, R-CD-*]

- [x] `ci.yml` triggers: PR to `main`, push to `dev`.
- [x] Jobs: lint (ruff + mypy), test (pytest, coverage ≥ 60% on app package, stub provider), manifests (`kustomize build k8s/overlays/prod | kubeconform -strict`), build (no push on PR), scan (Trivy HIGH/CRITICAL with fix), e2e-eval (kind/k3d, fixture corpus, run_eval gate).
- [x] `cd.yml` on push to `main`: `test` → `build-push` (needs test, Docker Hub, `${{ github.sha }}`) → `deploy` (needs build-push, ephemeral cluster, rollout status, Ingress smoke test).
- [x] `permissions:` least-privilege in every workflow.
- [x] Secrets only from GitHub Secrets (Docker Hub token).
- [x] CI job names added as required status checks on `main`.
- [x] Gate demo screenshots: failing eval gate with greyed-out Merge button, then the same PR fixed and green [R-CD-6]: [red](evidence/screenshots/k09-rcd6-eval-gate-red.jpg) and [green](evidence/screenshots/k09-rcd6-eval-gate-green.jpg), PR #39, log in `k09-rcd6-demo.txt`. Earlier partial captures: PR #30 and PR #37 (`k09-failing-gate.png`, `k09-passing-gate.png`).
- [x] Successful main `cd.yml` run 42297154091 linked in `docs/evidence/README.md` (all three jobs verified).
- [x] Docker Hub images visible with SHA tags.

### B10. Docs [§10, R-AI-1, R-ENG-*]

- [x] `docs/adr/0001-indexer-as-job.md` (own words; the first file the marker reads).
- [x] `docs/adr/0002-*.md`, `0003-*.md` (cache choice; embedding pin / chunking or similar).
- [x] `docs/adr/0004-llm-provider-and-data-governance.md`.
- [x] ADR for any contract change from the kit.
- [x] `docs/PIPELINE.md`
- [x] `docs/FAILURE-ANALYSIS.md`
- [x] `docs/ENGINEERING-NOTES.md` — 7 answers, each citing our own files and line numbers.
  - [x] 1 indexing at startup breaks what; object; manifest line
  - [x] 2 swapped probes + Chroma slow 90 s
  - [x] 3 CPU HPA while LLM generates; better signal
  - [x] 4 indexer memory limit, margin, exit 137
  - [x] 5 recall@5 by type; worst type; hybrid retrieval
  - [x] 6 `EMBED_MODEL` changed on API only
  - [x] 7 the >1 hour failure
- [x] `docs/AI-USAGE.md`: tools, what they wrote, what we changed and why.
- [x] README: what it is, apply order, secret create line, corpus fetch note, Ollama-host embedding note, how to re-index, how to run eval.
- [ ] LICENSE present.

### B11. Evidence screenshots/outputs in `docs/evidence/`

- [x] UI cited answer about academic warning and hostel-curfew abstention: [answer](evidence/screenshots/k10-ui-cited-answer.png), [abstention](evidence/screenshots/k10-ui-abstention.png); supporting K10 text evidence indexed in [evidence README](evidence/README.md).
- [x] Branch protection settings.
- [x] Text output of a blocked merge and the fixed PR with green checks (`k09-blocked-merge.txt`, `k09-green-pr.txt`); the PR was closed unmerged. Button screenshots: see B9 [R-CD-6] (PR #39).
- [x] `kubectl top pods` (api, chroma, redis, ui, indexer peak) justifying requests/limits.
- [x] `kubectl get endpoints` with 3+ IPs.
- [x] `kubectl get hpa` with real percentage.
- [x] `kubectl rollout status` then `rollout undo` showing the old version.
- [x] Pod deleted, service stays up.
- [x] `EMBED_MODEL` mismatch: `0/1 READY` + log line.
- [x] Manual re-index: `kubectl create job --from=cronjob/reindex manual-reindex-1 -n rahbar`.
- [x] NetworkPolicy proof (ui→chroma blocked).

### B12. Final submission gate

- [x] `python scripts/check_submission.py` (`make check`) clean.
- [x] the placeholder-marker grep printed by `make check` returns nothing.
- [x] `make test && make lint` green.
- [x] Fresh clone + README steps works end to end (cited answer, abstention, pod delete survives).
- [x] Git history scanned for secrets.
- [x] Repo public (or both instructors added).
- [ ] Google Classroom entry: repo URL, successful `cd.yml` run link, Docker Hub images link with SHA tags, `eval/results.json` + `eval/baseline.json` committed.
- [ ] Submitted before Sun 8 Nov 2026, 23:59 PKT. Late = not accepted.

---

## C. BONUS and optional

- [ ] `ollama-incluster` provider: Deployment + PVC for weights, `startupProbe` `failureThreshold: 30`, minikube 8 GB [R-BON-1].
- [ ] Hybrid retrieval (BM25/keyword + vector) to fix exact-term recall; show before/after recall by type [R-BON-2].
- [x] A better HPA signal than CPU (in-flight requests or queue depth); describe or build [R-BON-3].
- [ ] `hosted` provider implemented alongside `ollama-host` (Secret handling exercised).
- [ ] Extra version pairs in the corpus (Annual Reports, EE PLOs 12 vs 11, calendar) used in golden questions.
- [x] Admin enforcement on `main` is OFF by decision D-014 (no second approver available); say so in the submission notes.
- [x] Extra golden questions beyond 15 for a tighter metric.

---

## D. Evidence pointers for sections B1 to B12 (final verification, 2026-11-07)

Every ticked box in section B rests on one of these. Nothing is ticked on memory.

| Section | Evidence |
| --- | --- |
| B1 setup | `gh repo view` = PUBLIC; `k09-branch-protection.txt` (six required checks, strict, one approval); PR #1 and #2 merge commits on `origin/main`; Docker Hub images pushed by `cd.yml` (`k08-cd-run.txt`); README is ours |
| B2 corpus | `docs/CORPUS.md`, `corpus/MANIFEST.md`, `corpus/sources.yaml`; README "corpus is fetched, not committed"; `git log --all --stat -- corpus/raw` is empty (`final-history-scan.txt`) |
| B3 indexing | `docs/PIPELINE.md` (tables, 3 configs at 200/25, 400/50, 600/100 in `eval/tuning/`), `docs/examples/` before/after, `indexer/tests/` |
| B4 query and generation | `api/tests/` (the checker counts 481 test functions across `api/tests/`, `indexer/tests/` and root `tests/`, not API alone; `test_safety.py` injection, `test_answer.py` abstain and fallback, `test_cache*.py`), `docs/adr/0003-cache-store.md`, `docs/adr/0004-llm-provider-and-data-governance.md`; ConfigMap comments give the one-line justifications (TEMPERATURE, CACHE_THRESHOLD, RELEVANCE_FLOOR) |
| B5 Kubernetes | `k8s/base/*`, `docs/evidence/k01` to `k05`, `k10-*`; ADR 0001; `docs/architecture/architecture.md` 4.2 and 4.7 (why Chroma is a StatefulSet) |
| B6 observability | `api/app/logjson.py`, `api/app/routes/metrics.py`, `api/tests/test_metrics.py`; the `answered` line is in `k02-first-answer.txt` |
| B7 evaluation | `eval/golden.yaml` (18 questions), `eval/results.json` = `eval/baseline.json`, `final-numbers-check.txt`, `eval/tests/` |
| B8 failure analysis | `docs/FAILURE-ANALYSIS.md` (all six: A, C, E, F from D-015; B and D from phase 16, D-105, D-106) |
| B9 CI/CD | `.github/workflows/ci.yml` (six jobs), `cd.yml`; `k06`, `k07`, `k08`, `k09-*` evidence; final main CD 42297154091 linked in `docs/evidence/README.md`. PR #30 failed manifests and separate PR #37 six-job success screenshots indexed in `docs/evidence/README.md`; disabled Merge button and same-PR recovery screenshots remain missing |
| B10 docs | `docs/adr/0001` to `0004`, `PIPELINE.md`, `FAILURE-ANALYSIS.md`, `ENGINEERING-NOTES.md` (7 answers, `k11-reference-check.txt` resolves every path:line), `AI-USAGE.md`, `README.md` |
| B11 evidence | `docs/evidence/README.md` indexes every file |
| B12 gate | `make test && make lint && make manifests` green; `make check`: 164 passed, 5 warnings, 0 failures (explained below); `final-history-scan.txt`; `k11-clean-clone.txt` |

## E. Known gaps (honest list)

- **UI polish (A-12) and Ahmad's onboarding (A-00) were not done.** Ahmad was unavailable for the whole window; the platform lane was built by Zain's session (platform plan K1 to K11). `ui/index.html` and `ui/nginx.conf` are the starter's.
- **R-CD-6:** closed by the PR #39 demo (red then green on the same PR, greyed-out Merge button). UI cited-answer and abstention screenshots are now indexed in `docs/evidence/README.md`.
- **One commit author.** Both partners were meant to commit under their own identity; every work commit is under Zain's identity (the only other author is Ahmad on the GitHub merge commits of PR #1 and #2). `make check` warns about it.
- **Release and main CD complete:** [PR #36](https://github.com/Zain-Shykh/RAHBAR-Grounded-RAG/pull/36) merged; [run 42297154091](https://github.com/Zain-Shykh/RAHBAR-Grounded-RAG/actions/runs/42297154091) passed `test`, `build-push`, `deploy`. The older `k08-cd-run.txt` is a rehearsal from `ci/k08-cd` using a temporary push trigger, not the final main run. See `docs/evidence/README.md` for final links.
- **Admin enforcement on `main` is OFF** (D-014): Ahmad, the only second approver, is unavailable. The release PR has merged. The reconciliation does not infer an approval or override event from merge success alone.
- **No LICENSE file** (decision of 2026-11-04: none for now).
- **Not built, by design (non-goals):** `ollama-incluster`, `hosted`, hybrid retrieval (the fix for the `exact` recall of 0.5 is described in `ENGINEERING-NOTES.md` section 5), extra version pairs.
- **Ahmad has not reviewed** ADR 0001 or the Kubernetes answers in `ENGINEERING-NOTES.md` (Q1 to Q4, Q6); they are flagged as written without him. Both people's ability to explain every module remains unconfirmed; reading `docs/FINAL-WALKTHROUGH.md` alone is not proof of understanding.
- **Submission to Google Classroom** and the 23:59 PKT deadline are Zain's to do.
- **Chunk count:** 981 (host build, all measurements) vs 980 (cluster build, Tesseract difference): DEV-010.

### `make check` warnings, explained

1. *secret-shaped files in history*: `k8s/base/secret.placeholder.yaml`, a template with `REPLACE_ME`, deliberately committed and not in any kustomization.
2. *only one commit author*: see above.
3. *readiness does not look like it checks for a NON-EMPTY collection*: **false positive.** `readyz` calls `IndexState.get()`, which raises `IndexUnavailable("collection")` when `col.count() == 0` (`api/app/services/index_state.py:72-79`), and `/readyz` turns that into 503 naming `collection`. Tested in `api/tests/test_index_state.py` and `test_health.py`. The checker only reads the `readyz` function body and ignores comments, so it cannot see the delegation. Not changed to satisfy a regex (D-104).
4. *no never-cache rule found*: **false positive.** The rule is `cacheable()` (`api/app/services/cache.py:35`): only a validated, answered, from-context, non-follow-up response with valid citations is stored; tested in `api/tests/test_cache_answer.py`. The code names it `follow_up`/`cacheable`, not `is_followup`/`never_cache`, which is all the regex looks for (D-104).
5. *time.sleep() in tests*: five deliberate delays, with some residual timing sensitivity. `test_health.py` (3) simulates slow dependencies for timeout/probe tests; `test_ollama_provider.py` (1) holds concurrent calls open to exercise the semaphore; `test_cache_redis_adversarial.py` waits 2.2 s for a real Redis TTL of 1 s to expire (the TTL is Redis's clock, not patchable from the test). Removing them would remove the behaviour under test.

---

## F. Assignment 03 (RAGOps): things to avoid and things to do

Source of detail: `docs/requirements-a3.md` (ids `R3-*`). Plan: `docs/IMPLEMENTATION_PLAN_A3.md`. Tick only with a file pointer. The assignment publishes no point weights; the zero-mark conditions come from its own instructions.

### F.1 Things to AVOID (zero or loss of credit)

State at final verification, 2026-11-21 (R11). `[x]` = clear of the violation, with the pointer.

- [x] The demo runs on Docker or Compose only: **0 for the demo** [R3-LOG-5]. Everything ran on minikube: `docs/evidence/a3/f1-get-all-final.txt`, `r11-fresh-cluster-rehearsal.txt`.
- [ ] Late submission: **zero** [R3-LOG-2]. Deadline Sunday 22 November (D-107); submission is Zain's act.
- [x] A requirement changed or renamed: **no credit** [R3-LOG-3]. Names kept: `eval/golden.jsonl`, `eval/results/`, `traces/`, `k8s/eval-job.yaml`; 50 golden questions (minimum 25), 40 live queries (minimum 40).
- [x] A number in the report that is not from our own committed run [R3-LOG-4, I-25]. `python scripts/check_numbers_a3.py` exits 0 (`docs/specs/phase-r11-report.md` section 12).
- [ ] Commits from one member only [R3-LOG-6]. **Not clear in substance:** `git log` has 2 non-merge commits by Ahmad Jamal against 283 by Muhammad Zain, all Assignment 02; Ahmad did no work on Assignment 03 (D-108). The report says so.
- [ ] A member who cannot explain a part at the demo [R3-LOG-1]. Risk accepted by Zain (D-108); Ahmad has not seen Assignment 03.
- [x] Report over 8 pages (appendix excluded), or names and roll numbers missing on page 1 [R3-G]. `docs/report/report.pdf`: body pages as printed by `scripts/build_report.sh`; **roll numbers are a placeholder** that Zain fills (human item).
- [x] A screenshot cropped, unlabelled, or from somewhere other than our cluster [R3-S-*]. 14 PNGs in `docs/evidence/a3/screenshots/`, each ends with an end marker; they are renderings of the terminal output saved from the cluster runs (D-139), index in `docs/evidence/a3/README.md`.
- [x] A secret, `corpus/raw/`, a model or `.env*` in Git (A02 rule I-13 still applies). `docs/evidence/a3/r11-history-scan.txt`.
- [x] Anything that breaks Assignment 02: I-1 to I-17, the A02 CI gate, `/readyz` pin check. `make test && make lint` green, `python3 scripts/check_submission.py` 164 passed, 0 failures (5 pre-existing warnings), CI on PR #48.

### F.2 Things to DO

| Part | Items | Evidence |
| --- | --- | --- |
| A | [x] A1 four checks with reasons [R3-A1-2]; [x] quarantine [R3-A1-3]; [x] report per run [R3-A1-4]; [x] unchanged run embeds 0 [R3-A2-1]; [x] changed replaces only its chunks [R3-A2-2] (spike on real Chroma, `docs/specs/phase-r03-incremental.md`); [x] delete leaves no orphans, counted by id [R3-A2-3]; [x] supersede, archive, restore [R3-A2-4]; [x] Batch B of 12 with planted problems [R3-AB-1] | `docs/evidence/a3/a1-verification-report.txt`, `a2-unchanged-run.txt`, `a2-delete-no-orphans.txt`, `a2-restore.txt`, `a2-batch-b-ingest.txt`, `corpus/batch_b/PLANTED.json` |
| B | [x] 25+ golden questions (50) [R3-B-1]; [ ] 8 human and 8 reviewed synthetic [R3-B-2]: 18 human, **0 of 32 synthetic reviewed** (human, `eval/HUMAN_TODO.md`); [x] module level [R3-B-3]; [x] recall@3, recall@5, MRR, nDCG@5 [R3-B-4]; [x] noise test [R3-B-5]; [x] e2e metrics [R3-B-6]; [x] judge agreement [R3-B-7]: not applicable, no LLM judge (D-115); [x] two seeded runs and the difference [R3-B-8]; [x] one command, timestamped result [R3-B-9] | `eval/results/suite-20261121T021833Z-baseline-ab.json`, `stochasticity-20261121T003255Z.json`, `golden-check-20261121.json` |
| C | [x] one change, three levels compared [R3-C1]; [x] thresholds in a config file, gate script exits [R3-C2-1, R3-C2-2]; [x] one failing and one passing candidate [R3-C2-3]; [x] release decision [R3-G-3] (rule changed after seeing 100/0: stated) | `eval/gate.yaml`, `eval/results/gate-cand-*.txt`, `compare-cand-*.txt`, `docs/evidence/r7-decision.md` |
| D | [x] trace fields complete [R3-D1-1]; [x] trace tool [R3-D2-1]; [x] metrics and window script [R3-D3-*]; [x] guardrail in the trace [R3-D4-1] (offline test on the Batch B paragraph; live proof in `docs/evidence/a3/e3-injection-rail-live.txt`); [x] root cause in 5 lines [R3-D5-1] | `docs/evidence/a3/d1-trace-record.txt`, `d2-trace-tool.txt`, `d2-trace-report-job.txt`, `d5-root-cause.md` |
| E | [x] 40 live queries [R3-E1-1]; [x] coverage with justified threshold and topics [R3-E2-1]; [x] data drift [R3-E3-1]; [x] 16 new golden questions, coverage rises 0.300 to 0.675 [R3-E4-1] (**below the 0.85 target: honest gap**); [x] non-zero exit below threshold [R3-E4-2] | `eval/results/coverage-*.json`, `docs/evidence/a3/e1-*`, `e2-*`, `e3-data-drift.md` |
| F | [x] Deployment, StatefulSet, Service, lake on a PVC [R3-F1-*]; [x] ingestion Job and CronJob, only writer [R3-F2-1]; [x] eval Job via `kubectl apply -f k8s/eval-job.yaml`, fails when the gate fails [R3-F2-2]; [x] gate ConfigMap edit flips the outcome [R3-F2-3]; [x] candidate Deployment and Service, own collection [R3-F3-1]; [x] rolling update with `maxUnavailable: 0` [R3-F3-2]; [x] blocked candidate and rollout undo [R3-F3-3]; [x] trace after undo shows the previous collection and embedding [R3-F3-4]; [x] traces on stdout and a volume, metrics by port-forward [R3-F4-*]; [x] measured requests and limits [R3-F5-1]; [x] fresh cluster from `k8s/README.md` [R3-F5-2] | `docs/evidence/a3/f1-*`, `f2-*`, `f3-*`, `f4-*`, `r8-*`, `r9-*`, `f-metrics.txt`, `docs/evidence/f5-resources.txt`, `r11-fresh-cluster-rehearsal.txt` |
| G | [x] Figure 3 table [R3-G-1]; [x] Table 2 qualities table [R3-G-2]; [x] results and release decision [R3-G-3]; [x] short answers (a) to (f) [R3-G-4]; [ ] contribution table and AI statement [R3-G-5]: written truthfully, Zain must check; [x] 14 screenshots [R3-S-*] | `docs/report/report.pdf`, `docs/report/report.md` |
