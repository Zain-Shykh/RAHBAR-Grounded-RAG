# RAHBAR rubric checklist

Working checklist. Source of detail: `docs/requirements.md` (IDs in brackets). Tick a box only with evidence (file path, command output or screenshot in `docs/evidence/`). Re-run the whole list before submitting, plus `make check`.

Legend: `[x]` done and evidenced, `[ ]` not done. Point weights for graded lines are not published in the assignment; deductions are.

---

## A. Things to AVOID (automatic deductions)

Check every one before each merge to `main` and again at submission. Total possible loss if all hit: −111.

| Done right? | Pts | Violation | How we stay clear | Verify with |
| :---: | ---: | --- | --- | --- |
| [ ] | −20 | Secret, key or password anywhere in Git history [R-DED-1] | `.gitignore` covers `.env*`, `*secret*.yaml`, keys. Secrets only via `make secret`. Never paste a key into a file, even briefly. If one leaks: rotate and write a two-line incident note. | `git log -p \| grep -iE 'api[_-]?key\|token\|password\|secret'`; look for the Docker Hub token |
| [ ] | −15 | Base64 Secret with a real value in a committed manifest [R-DED-2] | Only `k8s/base/secret.placeholder.yaml` with `REPLACE_ME`, and not listed in `kustomization.yaml` | `grep -rn 'kind: Secret' k8s/`; inspect values |
| [ ] | −10 | Indexing at API startup [R-DED-3] | Indexer is a Job; API has no write path to Chroma | `grep -rn 'add\|upsert' api/app` finds no writes; ADR 0001 exists |
| [ ] | −10 | A returned citation not matching a retrieved chunk [R-DED-4] | Post-generation citation check against `retrieved`; drop or fall back on mismatch | `citation_validity` = 100% in `eval/results.json`; unit test |
| [ ] | −10 | Must-abstain golden question answered from context [R-DED-5] | Relevance floor + prompt + validation | Abstention correctness 100% in `eval/results.json` |
| [ ] | −8 | Chroma or Redis as Deployment with no PVC, or NodePort/LoadBalancer [R-DED-6] | Chroma = StatefulSet + `volumeClaimTemplates`; Redis = Deployment + PVC; all Services ClusterIP | `kubectl get svc,pvc -n rahbar` |
| [ ] | −8 | Embedding model not pinned, or indexer and API can disagree silently [R-DED-7] | One ConfigMap key; collection metadata check in `/readyz` | Demo: change `EMBED_MODEL`, API sits at `0/1` with a log line |
| [ ] | −6 | A container with no requests, or HPA reading `<unknown>` [R-DED-8] | Requests and limits on every container including Job and CronJob; metrics-server on | `kubectl get hpa -n rahbar` shows a number; grep manifests for `resources:` |
| [ ] | −6 | Publish/deploy job without `needs:`, or `:latest` [R-DED-9] | `cd.yml`: `build-push needs: test`, `deploy needs: build-push`; tag `${{ github.sha }}` | `grep -n 'latest\|needs' .github/workflows/*.yml` |
| [ ] | −5 | Manifests in `default` namespace [R-DED-10] | Namespace `rahbar` in every object (kustomize `namespace:`) | `kubectl get all -n default` is empty; `grep -L 'namespace' k8s/base/*.yaml` |
| [ ] | −5 | README apply order fails from a clean clone [R-DED-11] | Test the README steps on a fresh clone and fresh minikube | Dry run on clean clone (or Ahmad's machine) |
| [x] partly | −4 | Commits pushed directly to `main` [R-DED-12] | Branch protection on. All work via `dev` + PR. (Initial commit went to `main` before protection: unavoidable now.) | `git log main --first-parent`; protection screenshot |

Extra "don't" items from the text (not listed as deductions but explicitly forbidden or scored):

- [ ] Do not use lecture slides, an LLM-generated corpus, or paywalled/private documents [R-COR-10].
- [ ] Do not commit the downloaded PDFs (`corpus/raw/` stays ignored) [R-COR-12].
- [ ] Do not log to a file; stdout JSON only [R-OBS-1].
- [ ] Do not let `/healthz` touch Chroma, Redis or the LLM [R-PRB-1].
- [ ] Do not make `ui` able to reach `chroma` [R-SEC-4].
- [ ] Do not cache follow-ups, abstentions, out-of-scope answers or failed validations [R-CAC-4].
- [ ] Do not forget cache invalidation on re-index [R-CAC-5].
- [ ] Do not let a user see a 500 from malformed model output [R-GEN-2].
- [ ] Do not pass model or retrieved text to `eval`, or build SQL from it [R-SEC-5].
- [ ] Do not assert on model wording in CI; assert on metrics [R-EVA-8].
- [ ] Do not write a golden set from chunks already retrieved [§5.1].
- [ ] Do not ship chunk settings without three measured configs [R-IDX-7] (scores zero).
- [ ] Do not write generic engineering-note answers (scores zero) [R-ENG-*].
- [ ] Do not remove the pause between fetch requests [R-COR-11].
- [ ] Do not list the placeholder Secret in `kustomization.yaml` [§4.7].
- [ ] Do not present AI output as our own; disclose in `AI-USAGE.md` [R-AI-1].
- [ ] Do not leave any `STARTER-TODO` or `raise NotImplementedError` in the repo [R-SUB-5].
- [ ] Do not start minikube without `--cni=calico` [§9].

---

## B. Things to DO

### B1. Setup and process

- [x] Public repo, `.gitignore`, `dev` branch, `main` protected [R-DEV-1, R-DEV-2] — remaining: add CI job names as required status checks; keep "one approval".
- [x] Collaborator (Ahmad) added.
- [ ] PR #1 (corpus) approved and merged; corpus named in first PR [R-LOG-3].
- [x] Dependencies documented in root `requirements.txt`.
- [x] minikube up with Calico, metrics-server, ingress.
- [ ] Docker Hub account + access token; token stored only in GitHub Secrets [R-CD-4].
- [ ] README replaced with our own [R-LOG-6].

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
- [ ] README states documents are fetched, not committed.

### B3. Indexing pipeline [R-IDX-*]

- [x] Extract: detect no-text pages, OCR them, strip repeating headers/footers, keep headings.
- [x] Extract: HTML tables handled; PDF tables kept row-wise (`pdftotext -layout` or pdfplumber).
- [x] Clean: documented rules + one thing deliberately not stripped.
- [ ] Chunk: sections, then paragraphs, then sentences; overlap; target size; unit stated.
- [ ] Embed: pinned model, dimension recorded (768 for nomic-embed-text).
- [ ] Store: id, text, vector, metadata. Metadata has `source`, `section`, `page`, `doc_version`, `superseded` on every chunk.
- [ ] Collection metadata records embed model name + dimension [R-PIN-2].
- [ ] Cache expired when the Job runs [R-CAC-5].
- [ ] Three (size, overlap) configs measured on recall@5; table in `docs/PIPELINE.md`; shipped one justified.
- [ ] `docs/PIPELINE.md` contains: OCR list, before/after table example, unrecovered loss, cleaning rules, storage amplification, model/dim/pin location, chunk count, metadata schema, how docs reach the Job.

### B4. Query pipeline and generation [R-QRY-*, R-GEN-*, R-LLM-*]

- [ ] Validate 3 to 500 chars (422 otherwise; kit does this).
- [ ] Semantic cache lookup (skipped for follow-ups); threshold from ConfigMap.
- [ ] Embed with pinned model.
- [ ] `ChromaRetriever` top-k with `superseded=false` filter unless user asks about older version.
- [ ] Prompt: instructions, numbered delimited evidence, question.
- [ ] LLM at configured low temperature; Ollama `format=` schema enforcement.
- [ ] Pydantic validation; retry once; canned fallback.
- [ ] Relevance floor, abstention with `answered_from_context: false`.
- [ ] Citation check against retrieved chunks.
- [ ] Poisoned-chunk injection test passes [R-GEN-6].
- [ ] `reasoning` stripped from output.
- [ ] Provider interface with `LLM_PROVIDER`; `ollama-host` fully working; swap = one file.
- [ ] Temperature in ConfigMap with one-line justification.
- [ ] ADR: cache choice (Redis vs second Chroma collection) [R-CAC-1].
- [ ] Cache threshold chosen with data: 2 or 3 tried, false hit that ruled one out recorded [R-CAC-3].

### B5. Kubernetes [R-K8S-*]

- [ ] Dockerfiles + `.dockerignore` for api, indexer; Dockerfile for ui (non-root, `/tmp` emptyDir).
- [ ] Pinned image tags (`chromadb/chroma:1.0.12`, redis, nginx).
- [ ] Namespace `rahbar`.
- [ ] api Deployment: 3 replicas, 3 probes with the exact values, requests/limits, `maxSurge: 1`, `maxUnavailable: 0`, `terminationGracePeriodSeconds`, `preStop` sleep.
- [ ] ui Deployment (1+ replicas).
- [ ] chroma StatefulSet, 1 replica, `volumeClaimTemplates`.
- [ ] redis Deployment + PVC.
- [ ] indexer Job: `restartPolicy: OnFailure`, `backoffLimit` set, requests/limits.
- [ ] reindex CronJob weekly, same image/args as Job.
- [ ] 4 ClusterIP Services.
- [ ] Ingress: `/` to ui, `/api` to api, one host.
- [ ] ConfigMap: chunk size, overlap, top_k, relevance floor, cache threshold, temperature, EMBED_MODEL, LLM_PROVIDER, CHROMA_HOST.
- [ ] Secret placeholder only; real Secret created via command line.
- [ ] NetworkPolicies: default deny + DNS egress + Ollama host `ipBlock` + allow paths (ui from Ingress; api from ui and Ingress; chroma from api and indexer; redis from api).
- [ ] Prove ui cannot reach chroma (exec test), api can.
- [ ] HPA on api, 3 to 8, shows a real percentage.
- [ ] One ServiceAccount per workload; `automountServiceAccountToken: false` where unused.
- [ ] `runAsNonRoot`, `readOnlyRootFilesystem`, drop ALL capabilities on every container.
- [ ] kustomize base + overlays `dev` and `prod`.
- [ ] `readyz`: Chroma reachable, collection non-empty, Redis reachable, embed pin matches; 503 names failing dependency.
- [ ] `healthz` touches nothing external.
- [ ] `docs/ARCHITECTURE.md` explains why Chroma is a StatefulSet.
- [ ] `make cluster && make images && make apply` order documented and works from clean clone.

### B6. Observability [R-OBS-*]

- [ ] JSON logs to stdout.
- [ ] `request_id` on every line (header or generated; echoed back).
- [ ] Metrics: request count, request latency, retrieval latency, generation latency, cache hit ratio, abstention count, fallback count, tokens in/out.
- [ ] Per-request log line: `top_k`, retrieved chunk ids, scores, abstention flag.

### B7. Evaluation [R-GOL-*, R-EVA-*]

- [x] `eval/golden.yaml` written before tuning: at least 15 questions: 8 ordinary, 2 version-sensitive, 2 exact-term, 2 must-abstain, 1 injection; relevant chunk ids or doc+section listed.
- [x] `recall_at_k`, `citation_validity`, `summarise`, `gate` implemented.
- [ ] recall@3 and recall@5 overall and by question type, committed.
- [ ] Exact-term recall vs definitional recall noticed and explained.
- [ ] Citation validity reported (target 100%, gate 95%).
- [ ] Abstention correctness 100%.
- [ ] `eval/results.json` and `eval/baseline.json` committed.
- [x] Gate fails on: recall@5 drop > 5 points, any must-abstain answered, citation validity < 95%.

### B8. Failure analysis [R-FAI-*]

At least four of six, each with symptom, diagnosis, stage, remedy, and "how I'd have found it" with the metric or log number.

- [ ] A · Extraction (index scanned PDF without OCR)
- [ ] B · Chunking (100-token fixed, no overlap)
- [ ] C · Retrieval (`top_k: 1` or API-only `EMBED_MODEL` change)
- [ ] D · Prompt (remove "use supplied context")
- [ ] E · Source (remove superseded filter, ask version question)
- [ ] F · Generation (temperature 1.2)

### B9. CI/CD [R-CI-*, R-CD-*]

- [ ] `ci.yml` triggers: PR to `main`, push to `dev`.
- [ ] Jobs: lint (ruff + mypy), test (pytest, coverage ≥ 60% on app package, stub provider), manifests (`kustomize build k8s/overlays/prod | kubeconform -strict`), build (no push on PR), scan (Trivy HIGH/CRITICAL with fix), e2e-eval (kind/k3d, fixture corpus, run_eval gate).
- [ ] `cd.yml` on push to `main`: `test` → `build-push` (needs test, Docker Hub, `${{ github.sha }}`) → `deploy` (needs build-push, ephemeral cluster, rollout status, Ingress smoke test).
- [ ] `permissions:` least-privilege in every workflow.
- [ ] Secrets only from GitHub Secrets (Docker Hub token).
- [ ] CI job names added as required status checks on `main`.
- [ ] Gate demo: failing PR with greyed-out merge button, then green PR; both screenshots.
- [ ] Successful `cd.yml` run link saved.
- [ ] Docker Hub images visible with SHA tags.

### B10. Docs [§10, R-AI-1, R-ENG-*]

- [ ] `docs/adr/0001-indexer-as-job.md` (own words; the first file the marker reads).
- [ ] `docs/adr/0002-*.md`, `0003-*.md` (cache choice; embedding pin / chunking or similar).
- [ ] `docs/adr/0004-llm-provider-and-data-governance.md`.
- [ ] ADR for any contract change from the kit.
- [ ] `docs/PIPELINE.md`
- [ ] `docs/FAILURE-ANALYSIS.md`
- [ ] `docs/ENGINEERING-NOTES.md` — 7 answers, each citing our own files and line numbers.
  - [ ] 1 indexing at startup breaks what; object; manifest line
  - [ ] 2 swapped probes + Chroma slow 90 s
  - [ ] 3 CPU HPA while LLM generates; better signal
  - [ ] 4 indexer memory limit, margin, exit 137
  - [ ] 5 recall@5 by type; worst type; hybrid retrieval
  - [ ] 6 `EMBED_MODEL` changed on API only
  - [ ] 7 the >1 hour failure
- [ ] `docs/AI-USAGE.md`: tools, what they wrote, what we changed and why.
- [ ] README: what it is, apply order, secret create line, corpus fetch note, Ollama-host embedding note, how to re-index, how to run eval.
- [ ] LICENSE present.

### B11. Evidence screenshots/outputs in `docs/evidence/`

- [ ] Branch protection settings.
- [ ] Blocked merge (gate failing, greyed-out button) and green merge.
- [ ] `kubectl top pods` (api, chroma, redis, ui, indexer peak) justifying requests/limits.
- [ ] `kubectl get endpoints` with 3+ IPs.
- [ ] `kubectl get hpa` with real percentage.
- [ ] `kubectl rollout status` then `rollout undo` showing the old version.
- [ ] Pod deleted, service stays up.
- [ ] `EMBED_MODEL` mismatch: `0/1 READY` + log line.
- [ ] Manual re-index: `kubectl create job --from=cronjob/reindex manual-reindex-1 -n rahbar`.
- [ ] NetworkPolicy proof (ui→chroma blocked).

### B12. Final submission gate

- [ ] `python scripts/check_submission.py` (`make check`) clean.
- [ ] `grep -rn STARTER-TODO --exclude-dir=.venv .` returns nothing.
- [ ] `make test && make lint` green.
- [ ] Fresh clone + README steps works end to end (cited answer, abstention, pod delete survives).
- [ ] Git history scanned for secrets.
- [ ] Repo public (or both instructors added).
- [ ] Google Classroom entry: repo URL, successful `cd.yml` run link, Docker Hub images link with SHA tags, `eval/results.json` + `eval/baseline.json` committed.
- [ ] Submitted before Sun 8 Nov 2026, 23:59 PKT. Late = not accepted.

---

## C. BONUS and optional

- [ ] `ollama-incluster` provider: Deployment + PVC for weights, `startupProbe` `failureThreshold: 30`, minikube 8 GB [R-BON-1].
- [ ] Hybrid retrieval (BM25/keyword + vector) to fix exact-term recall; show before/after recall by type [R-BON-2].
- [ ] A better HPA signal than CPU (in-flight requests or queue depth); describe or build [R-BON-3].
- [ ] `hosted` provider implemented alongside `ollama-host` (Secret handling exercised).
- [ ] Extra version pairs in the corpus (Annual Reports, EE PLOs 12 vs 11, calendar) used in golden questions.
- [ ] Enable admin enforcement on `main` branch protection before submission.
- [ ] Extra golden questions beyond 15 for a tighter metric.
