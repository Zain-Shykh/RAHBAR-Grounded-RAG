# RAHBAR Assignment 03 requirements (RAGOps)

Extracted from [`../Assignment_03.md`](../Assignment_03.md). It extends [`requirements.md`](requirements.md) (Assignment 02) and does not replace it: every Assignment 02 requirement and every invariant I-1 to I-17 still holds unless [`architecture/architecture-a3.md`](architecture/architecture-a3.md) logs a deviation. If this file and the assignment disagree, the assignment wins: fix this file.

IDs are `R3-<area>-<n>`. The area letter is the assignment's part (A to G). Words such as "must", "at least" and "never" are the assignment's own. "Paper" means Xu, Weytjens, Zhang, Lu, Weber and Zhu, *RAGOps: Operating and Managing Retrieval-Augmented Generation Pipelines* (preprint, 2026). The paper is not in this repository (open decision D-109).

| | |
| --- | --- |
| Course | Software Construction and Development (CS4032), Fall 26 |
| Marks | 185, group of 2 |
| Deadline | **Not stated in the assignment text** (open decision D-107). Late submissions get zero |
| Builds on | RAHBAR (Assignment 02). A different working pipeline is allowed, but we use RAHBAR |

---

## 0. Logistics and rules (assignment "Instructions" and "Submission Guidelines")

| ID | Requirement |
| --- | --- |
| R3-LOG-1 | Group of two. Both members must be able to explain every part of the work at the demo. |
| R3-LOG-2 | Late submissions receive zero marks. Plagiarism may zero the whole assignments category. |
| R3-LOG-3 | There is no credit if the given requirements are changed. File names, the `kubectl apply -f k8s/eval-job.yaml` path, the 25-question minimum and every other number below are fixed. |
| R3-LOG-4 | AI tools and libraries are allowed. **Every number in the report must come from runs of our own pipeline, and the result files must be committed.** |
| R3-LOG-5 | The pipeline must be deployed on Kubernetes during the demo. Docker-only (plain `docker run` or Compose) gives **0 for the demo**. |
| R3-LOG-6 | Commits must come from both members (repository requirement). |
| R3-LOG-7 | Read the paper first. Sections 3.2, 4.2, Table 1, Table 2, 5.1 and 6.2 matter most. Figure 3 is the map of the assignment. |
| R3-LOG-8 | Deliverables are two things: the GitHub repository URL, and one report PDF with the screenshots as an appendix. |
| R3-LOG-9 | Results: every result file, trace sample and report produced by our scripts is committed under `eval/results/` and `traces/`. All Kubernetes manifests are committed under `k8s/`. |
| R3-LOG-10 | README: the repository `README.md` gives the exact command to run each part (A to F). |
| R3-LOG-11 | Demo: both members attend with a laptop running the pipeline on the local cluster. At the demo we (1) run our evaluation as a Kubernetes Job, (2) open a trace, (3) ingest a small batch of documents we have not seen, by running our ingestion Job. |

## A. Data management: verify and update (paper 4.2.1 to 4.2.4)

| ID | Requirement |
| --- | --- |
| R3-A1-1 | A verification step runs **after ingestion and before chunking**. |
| R3-A1-2 | For every document it records pass or fail, **with a reason**, for each of four checks: **quality** (empty, garbled or failed extraction), **completeness** (required metadata present: source, title, date or version, page count; text not truncated), **recency** (a newer version of the same document is detected), **uniqueness** (exact duplicates by hash, near-duplicates by embedding similarity). |
| R3-A1-3 | Documents that fail are moved to a quarantine folder and are not indexed. |
| R3-A1-4 | The output is a verification report file per run. |
| R3-A2-1 | Re-running ingestion on an unchanged corpus embeds **zero chunks**. The counts are shown. |
| R3-A2-2 | A changed document replaces only its own chunks. |
| R3-A2-3 | A deleted document leaves no orphan chunks in the vector store. Proved with a count by document id. |
| R3-A2-4 | A superseded version is archived and excluded from retrieval through metadata. It can be restored (rollback demo). |
| R3-AB-1 | Batch B: a second batch of **at least 10 documents** with planted problems: at least 2 exact duplicates, 1 near-duplicate, 1 truncated or corrupt file, 1 with missing metadata, 1 newer version of an existing document, 1 containing an injected instruction. |
| R3-AB-2 | Both batches run through A1 and A2. |

## B. Offline testing at three levels (paper 4.2.5, Table 1)

| ID | Requirement |
| --- | --- |
| R3-B-1 | Golden set in `eval/golden.jsonl`: at least **25** questions. At least 15 answerable (each with ground-truth document and page), at least 5 unanswerable (correct behaviour is to abstain), at least 5 hard (paraphrased, or needing more than one chunk, or from Batch B). |
| R3-B-2 | At least **8** questions are written by hand by the group. Every question is labelled `human` or `synthetic`. At least **8** synthetic questions are reviewed by hand. |
| R3-B-3 | **Module level (embedding):** mean cosine similarity of at least 15 paraphrase pairs against at least 15 unrelated pairs, and the gap between them. Embedding time per chunk. Determinism: embed the same text twice and report the largest difference. |
| R3-B-4 | **Component level (retrieval):** recall@3, recall@5, MRR and nDCG@5 on the golden set. |
| R3-B-5 | **Noise test:** add at least 3 irrelevant documents, **or** add typos to the queries, and report how each metric changes. |
| R3-B-6 | **End-to-end level (answers):** faithfulness (is the answer supported by the retrieved context), abstention correctness on the unanswerable questions, citation validity, latency p50 and p95. |
| R3-B-7 | If an LLM judges faithfulness: label **at least 8** answers by hand and report how often the judge agrees with us. |
| R3-B-8 | **Stochasticity:** fix random seeds, run the whole suite **twice**, report the difference for each metric, explain any remaining variation. |
| R3-B-9 | **One command** runs the whole suite and writes a **timestamped** result file to `eval/results/` with a summary table. |

## C. Change experiment and release gate (paper 4.1 (d), 4.2.5, 4.2.6)

| ID | Requirement |
| --- | --- |
| R3-C1-1 | Choose **one** pipeline change: chunk size or overlap, embedding model, reranker, top-k, or prompt template. |
| R3-C1-2 | Run the Part B suite on the baseline and on the candidate and compare **all three levels**. |
| R3-C2-1 | Thresholds are written in a config file, for example: recall@5 may not drop by more than 2 points against the baseline; faithfulness at least a value we justify; p95 latency at most a value we justify; abstention correctness not lower than the baseline. |
| R3-C2-2 | A script applies the gate and **exits with pass or fail**. |
| R3-C2-3 | Show one candidate that **fails** (a deliberately bad one is fine) and one that **passes**. |
| R3-C3-1 | The candidate is released and, if needed, rolled back on Kubernetes (see R3-F3-*). |

## D. Observability and traceability (paper 3.2.3, 5.1, Table 2)

| ID | Requirement |
| --- | --- |
| R3-D1-1 | **Trace record.** Every query writes one JSON line containing: trace id; timestamp; user query; any rewritten query; embedding model and version; collection name or version; retrieved chunk ids with document ids, document versions and scores; filters applied; reranked order; a prompt hash (or the full prompt); model and parameters; response; citations; guardrail actions; latency per stage; cache hit or miss. |
| R3-D2-1 | **Trace tool.** A command takes a trace id and prints the exact context and prompt that produced that answer. |
| R3-D3-1 | **Metrics.** Expose or report at least: top-1 retrieval similarity distribution, abstention rate, cache hit rate, p95 latency per stage, number of injection attempts flagged. |
| R3-D3-2 | A script summarises the trace log over a time window. |
| R3-D4-1 | **Guardrail logging.** The injection defence from Assignment 02 (or one simple retrieval rail) writes its action into the trace. Tested with the injected document from Batch B. |
| R3-D5-1 | **Root cause from the trace only.** Pick one wrong or abstained answer from Part B. Using only its trace, find the cause (which chunk, document version or filter), and write 5 lines in the report. |

## E. Drift and coverage checking (paper 4.2.7)

| ID | Requirement |
| --- | --- |
| R3-E1-1 | **Live query log:** at least **40** queries written as if from users: about 28 in the domain of the golden set and at least 12 from a topic the corpus or tests do not cover. |
| R3-E2-1 | **Query coverage:** for each live query find the most similar golden question. Report the share above a similarity threshold we choose and justify (the paper's example flags a gap when under 85 percent reach a score). List the uncovered queries and group them into topics. |
| R3-E3-1 | **Data drift:** ingest Batch B, re-run the Part B suite, report what changed and why. |
| R3-E4-1 | **Close the gap:** add at least **6** new golden questions from the uncovered topics, re-run, show that coverage rises. |
| R3-E4-2 | A script returns a **non-zero exit code** when coverage falls below our threshold. |

## F. Run it on Kubernetes (paper 4.1 (e) and (f), 5.1 reliability)

| ID | Requirement |
| --- | --- |
| R3-F1-1 | The API is a Deployment; the vector store is a StatefulSet (or a Deployment with a PVC); a Service exposes the API. |
| R3-F1-2 | The data lake, the quarantine folder and the archived document versions live on a **PersistentVolumeClaim**, so they survive pod restarts. |
| R3-F2-1 | Ingestion with verification (Part A) runs as a Kubernetes **Job**, and a **CronJob** re-runs it on a schedule. The only writer to the vector store is that Job. |
| R3-F2-2 | The Part B suite runs as a Job: `kubectl apply -f k8s/eval-job.yaml`. It writes its result file to a volume and **exits with a failing status when the release gate fails**. |
| R3-F2-3 | The gate thresholds are a **ConfigMap**. Show that changing a threshold changes the outcome **without rebuilding the image**. |
| R3-F3-1 | The candidate from Part C runs as a **second Deployment** with its own Service and its own collection name. The Part B suite Job is run against it. |
| R3-F3-2 | If the gate passes, release it to the live Deployment with a **rolling update (`maxUnavailable: 0`)**, watched with `kubectl rollout status`. |
| R3-F3-3 | Show a candidate that is **stopped by the gate and never rolled out**, and a **bad release reversed with `kubectl rollout undo`**. |
| R3-F3-4 | After the undo, a **new trace** must show the previous collection and embedding version. |
| R3-F4-1 | Trace records go to standard output as JSON lines (readable with `kubectl logs`). They are also written to a **volume** for the report scripts. |
| R3-F4-2 | The metrics endpoint is reachable with `kubectl port-forward`. |
| R3-F5-1 | Resource requests and limits for the API, the vector store and the Jobs, **from measurements we take** (the numbers are copied into the report). |
| R3-F5-2 | Every manifest is committed under `k8s/`. A **fresh cluster must reach a working pipeline by applying them**, with any extra commands listed in `k8s/README.md`. |

## G. Report (at most 8 pages)

The first page lists the names and roll numbers of both members. The screenshot appendix does not count towards the 8 pages.

| ID | Requirement |
| --- | --- |
| R3-G-1 | A table mapping each stage of **Figure 3** (ingest, verify, update data lake, update retrieval sources, offline testing, live testing, check coverage) to what the pipeline does, the file that does it, and what is missing. |
| R3-G-2 | A table for the five qualities of the paper's **Table 2** (adaptability, monitorability, observability, traceability, reliability): what we measure, our threshold, the evidence. |
| R3-G-3 | Results tables and figures from Parts A to F, and the **release decision** for Part C (release or reject, with reasons). |
| R3-G-4 | Short answers: (a) which verification check caught the most problems in Batch B, and which problem we did not catch, and what would catch it; (b) an example where a module-level metric looked fine but a component or end-to-end metric did not, or why we saw none; (c) did we archive or delete old versions, and what breaks if we delete; (d) which metric we trust least, and why; (e) which of the paper's ideas was hardest to apply, and what we changed from the paper; (f) which Kubernetes object carries which RAGOps responsibility (for example, which object ensures only one component writes to the vector store). |
| R3-G-5 | A contribution table (what each member did) and an AI statement of 2 to 3 lines. |

## Screenshots (appendix of the report)

Each screenshot shows the command we ran and its output, in the terminal, **with nothing cropped**. Each is labelled with part and item (for example "B3"). They must come from our own cluster and our own runs.

| ID | Required screenshot |
| --- | --- |
| R3-S-A1 | The verification report for Batch B (pass or fail per check, with reasons). |
| R3-S-A2 | A second ingestion run on an unchanged corpus showing 0 chunks embedded. |
| R3-S-B | The evaluation summary with all three levels. |
| R3-S-C1 | The release gate failing. |
| R3-S-C2 | The release gate passing. |
| R3-S-D1 | One full trace record. |
| R3-S-D2 | The trace tool rebuilding the prompt for a trace id. |
| R3-S-E1 | The coverage output before adding the new questions. |
| R3-S-E2 | The coverage output after adding the new questions. |
| R3-S-F1 | `kubectl get all,pvc,configmap,cronjob,job` for our namespace. |
| R3-S-F2 | The logs of a completed ingestion Job. |
| R3-S-F3 | The logs of a completed evaluation Job. |
| R3-S-F4 | The gate result changing after a ConfigMap edit. |
| R3-S-F5 | `kubectl rollout status` and `kubectl rollout undo`, with a trace afterwards showing the previous collection and embedding version. |

---

## Traceability: requirement to phase

Phases are in [`IMPLEMENTATION_PLAN_A3.md`](IMPLEMENTATION_PLAN_A3.md). Each phase's acceptance criteria cite these ids.

| Requirement ids | Phase |
| --- | --- |
| R3-AB-1, R3-AB-2 (corpus part) | R1 Batch B and the metadata contract |
| R3-A1-1 to R3-A1-4 | R2 Verification stage |
| R3-A2-1 to R3-A2-4, R3-AB-2 | R3 Incremental update |
| R3-B-1, R3-B-2, R3-B-3, R3-B-4, R3-B-5 | R4 Golden set and component levels |
| R3-B-6 to R3-B-9 | R5 End-to-end level, judge, stochasticity, one command |
| R3-D1-1 to R3-D5-1, R3-F4-1, R3-F4-2 (API half) | R6 Trace, trace tool, metrics, guardrail |
| R3-C1-*, R3-C2-* | R7 Change experiment and release gate |
| R3-F1-*, R3-F2-*, R3-F4-*, R3-F5-*, R3-LOG-11 | R8 Kubernetes deployment of RAGOps |
| R3-C3-1, R3-F3-* | R9 Controlled release |
| R3-E1-* to R3-E4-* | R10 Drift and coverage |
| R3-G-*, R3-S-*, R3-LOG-8 to R3-LOG-10 | R11 Report, evidence, README, final verification |
