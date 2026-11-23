# Taking the 14 appendix screenshots from a real terminal

The assignment wants screenshots of a terminal that show the command and its output, uncropped, from the group's own cluster.
The 14 PNGs in `screenshots/` were made by `scripts/render_screenshot.py` from saved text, which is not a screenshot of a terminal.
A tool that runs in the background cannot press the screenshot key on the desktop (the screenshot portal refused it), so this part is done by a person at the keyboard, in about 30 minutes.

## Setup (once)

1. Cluster up: `sg docker -c "minikube start"`, Ollama (`OLLAMA_HOST=0.0.0.0 ollama serve`), `kubectl get pods -n rahbar` all Running.
2. A normal terminal, wide (at least 170 columns), dark or light, font small enough that the whole output fits on one screen. Nothing may be cropped; if the output is longer than the screen, shrink the font (Ctrl and minus) or use the `| tail -N` shown.
3. Change into the repository: `cd ~/Desktop/SCD_ASSIGNMENTS/assign_2`.
4. For every item: type `clear`, type the command (so the prompt and command are visible), wait for the output, press **PrtSc** and select the terminal window (or use the screenshot tool of the desktop). Save as the file name in the last column, in `docs/evidence/a3/screenshots/`, replacing the old PNG.
5. When all 14 are saved, rebuild the report: `bash scripts/build_report.sh` (it uses the files whose names start with the label). Then change the sentence in `docs/evidence/a3/README.md` and `scripts/build_report.sh` (appendix text) from "renderings" to "screenshots", and commit.

Run the items in this order. Items marked (LLM) call the model and take minutes; do not run two at once.

| Id | What to type (each line is typed and run in turn) | What the screen must show | Save as |
| --- | --- | --- | --- |
| A1 | `make lake-report RUN=20261121T082852Z-99934e` | the 13-document table with PASS/FAIL per check and the reasons (6 indexed, 6 quarantined, 1 superseded) | `A1-verification-report-batch-b.png` |
| A2 | `make index` then `JOB=$(kubectl get jobs -n rahbar --sort-by=.metadata.creationTimestamp -o name \| tail -1); kubectl wait --for=condition=complete $JOB -n rahbar --timeout=900s; kubectl logs $JOB -n rahbar \| tail -12` | `chunks_embedded: 0`, `index_swapped: false`, `unchanged` equal to the document count | `A2-second-run-unchanged.png` |
| B | `cat eval/results/suite-20261121T021833Z-baseline-ab.md` | the three levels: module, component, end-to-end (this file is the output of the eval Job on the real cluster; Job logs are in F3) | `B-evaluation-summary.png` |
| C1 | `bash scripts/release_demo.sh gate-fail` then `sleep 40; kubectl get job eval -n rahbar; kubectl logs job/eval -n rahbar \| tail -9` then `make release COLLECTION=rahbar_bad` | Job `Failed`, `GATE FAILED: 5 of 6 rules pass`, then `RELEASE REFUSED` | `C1-gate-fails.png` |
| C2 | `bash scripts/release_demo.sh gate-pass` then `sleep 40; kubectl get job eval -n rahbar; kubectl logs job/eval -n rahbar \| tail -9` | Job `Complete`, `GATE PASSED: 6 of 6 rules pass` | `C2-gate-passes.png` |
| D1 | `python scripts/trace_tool.py show 0a691237adee401f842e55aaa5efdc09 --dir traces/samples \| head -40` or, for a fresh one, ask a question (`make ask Q="What CGPA puts a student on academic warning?"`) and then `kubectl logs -l app.kubernetes.io/name=api -n rahbar --tail=-1 --prefix=false --max-log-requests=10 \| grep '"type": "trace"' \| tail -1 \| python3 -m json.tool` (LLM) | one full JSON trace record | `D1-trace-record.png` |
| D2 | `python scripts/trace_tool.py show <trace id from D1> --kubectl deploy/api \| head -60` (reads every api pod) | retrieved chunks with scores and versions, the exact prompt, the attempt line, `hash OK` | `D2-trace-tool-prompt.png` |
| E1 | `PYTHONPATH=. python -m eval.suite.coverage --golden eval/golden_before_e4.jsonl; echo "exit code $?"` | 12 of 40 covered, share 0.300, exit code 1 (the golden file before any coverage question was added) | `E1-coverage-before.png` |
| E2 | `PYTHONPATH=. python -m eval.suite.coverage --golden eval/golden_round1.jsonl \| head -3; PYTHONPATH=. python -m eval.suite.coverage \| head -3; PYTHONPATH=. python -m eval.suite.coverage --live eval/live_queries_fresh.jsonl \| head -3` | round 1 (16 questions): 27 of 40, 0.675; round 2 (13 more): 40 of 40; fresh queries never used to write questions: 4 of 12 | `E2-coverage-after.png` |
| F1 | `kubectl get all,pvc,configmap,cronjob,job -n rahbar` | Deployments, StatefulSet, Jobs, CronJob, PVCs, ConfigMap | `F1-kubectl-get-all.png` |
| F2 | `JOB=$(kubectl get jobs -n rahbar -o name \| grep indexer-candidate \| head -1); kubectl logs $JOB -n rahbar \| tail -25` | an ingestion Job log: extracted, verified, embedded, stored | `F2-ingestion-job-logs.png` |
| F3 | `make eval-job SET_BASELINE=false LABEL=live-smoke LIMIT=5` (LLM, about 6 minutes), then `kubectl wait --for=condition=complete job/eval -n rahbar --timeout=1800s; kubectl logs job/eval -n rahbar \| tail -12` | the eval Job log with the gate lines (a 5-question smoke run; the full run takes about 60 minutes) | `F3-eval-job-logs.png` |
| F4 | edit `eval/gate.yaml` (set the p95 limit to 0.001), then `make gate-config` then `make eval-job GATE_ONLY=/results/suite-20261121T072649Z-cand-600-100.json LABEL=cm-edit`, `sleep 40; kubectl get job eval -n rahbar; kubectl logs job/eval -n rahbar \| tail -4`, then `git checkout eval/gate.yaml && make gate-config` | the same image: Job `Failed` after the edit (was `Complete`) | `F4-gate-after-configmap-edit.png` |
| F5 | `kubectl rollout history deployment/api -n rahbar`, `make release COLLECTION=rahbar_drill FORCE=1`, `make rollback`, `kubectl rollout status deployment/api -n rahbar`, `make ask Q="What CGPA puts a student on academic warning?" > /dev/null` (LLM), then `python scripts/trace_tool.py show <its trace id> --kubectl deploy/api \| head -14` | `FORCED RELEASE`, `rollout undo`, `successfully rolled out`, and a trace whose collection is the previous one (`rahbar_c600`) with the embedding version | `F5-rollout-undo-trace.png` |

Notes for the report, if they differ from what the screen shows:

- The saved result files used by C1, C2 and F4 come from the full 50-question runs done earlier on this cluster setup (`eval/results/`); the gate is re-applied to them with `GATE_ONLY`, no model call.
- Item F5 uses the collection `rahbar_drill` (an oversized-chunk build, CHUNK=1500 OVERLAP=0) on purpose: it is a rollback drill that bypasses the gate and is separate from the gate-refused candidate `rahbar_bad`.
