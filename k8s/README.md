# Kubernetes: a fresh cluster to a working pipeline (R3-F5-2)

Everything runs in namespace `rahbar` on minikube (Calico). All manifests are under `k8s/`; the order below is the
whole procedure. Ollama runs on the host (`OLLAMA_HOST=0.0.0.0 ollama serve`; models `llama3.2:3b` and
`nomic-embed-text`). Docker needs `sg docker -c "..."` until the desktop is re-logged.

| Step | Command | What it does |
| --- | --- | --- |
| 1 | `make cluster` | minikube with Calico, metrics-server, ingress |
| 2 | `make images` | builds `rahbar-api`, `rahbar-indexer`, `rahbar-ui`, `rahbar-eval` and loads them into minikube |
| 3 | `kubectl apply -k k8s/overlays/dev` | namespace, ConfigMap, PVCs (`corpus-data`, `lake-data`, `traces-data`, `eval-results`), Chroma StatefulSet, Redis, api, ui, Ingress, HPA, NetworkPolicies, the indexer Job, the `reindex` CronJob |
| 4 | `make corpus` | copies `corpus/raw` into the `corpus-data` volume (the inbox) |
| 5 | `make gate-config` | creates ConfigMap `rahbar-gate` from `eval/gate.yaml` |
| 6 | `make index` | runs the ingestion Job from the CronJob template: verify, quarantine, embed the delta, swap |
| 7 | `make lake-ls` | lists registry, quarantine, archive and reports on the `lake-data` volume |
| 8 | `kubectl apply -f k8s/eval-job.yaml` | runs the suite and the gate as a Job; exit status = gate result |

## Part by part

| Part | Command |
| --- | --- |
| A, ingestion of a batch | `make ingest-batch BATCH=corpus/batch_b`, then `kubectl logs job/<ingest-...> -n rahbar` |
| A, second run, nothing changed | `make index` again; the log line `ingest summary` shows `chunks_embedded: 0, index_swapped: false` |
| A, verification report | `kubectl exec -n rahbar <viewer> -- cat /data/reports/<run>/verification.json` or `make lake-ls` |
| B, suite on the cluster | `kubectl apply -f k8s/eval-job.yaml` (first time with `SET_BASELINE=true`: see below) |
| C, gate | the eval Job: `kubectl get job eval -n rahbar` is `Complete` (gate passed) or `Failed` (gate failed) |
| C, change the outcome without a rebuild | edit `eval/gate.yaml`, `make gate-config`, delete and re-apply the Job |
| D, a trace | `kubectl logs deploy/api -n rahbar \| grep '"type": "trace"'`; `python scripts/trace_tool.py show <trace_id> --kubectl deploy/api` |
| D, metrics over a window | `kubectl apply -f k8s/trace-report-job.yaml`, then `kubectl logs job/trace-report -n rahbar` |
| F, metrics endpoint | `kubectl port-forward svc/api 8000:8000 -n rahbar`, then `curl localhost:8000/metrics` |
| F, candidate and release | `make candidate CHUNK=300 OVERLAP=50`, eval Job with `API_URL=http://api-candidate:8000`, `make release COLLECTION=rahbar_cand`, `make rollback` |

First baseline on the cluster: `make eval-job SET_BASELINE=true LABEL=baseline` (the result becomes
`/results/baseline.json`, no gate); afterwards `kubectl apply -f k8s/eval-job.yaml` (or `make eval-job`) gates against it.

## Volumes

| Claim | Size | Mounted by | Holds |
| --- | --- | --- | --- |
| `corpus-data` | 1 Gi | Job and CronJob (read-only) | the inbox: documents and `_index.json` |
| `lake-data` | 1 Gi | Job and CronJob (read-write) | `registry/`, `quarantine/<run>/`, `archive/<doc>/<sha>/`, `reports/<run>/` |
| `traces-data` | 500 Mi | api pods (read-write), `trace-report` Job (read-only) | `traces-<date>-<pod>.jsonl` |
| `eval-results` | 200 Mi | eval Job | `suite-*.json`, `baseline.json`, `gate-*.txt` |
| `chroma-data-chroma-0` | 2 Gi | Chroma | the vector index |
| `cache-data` | 1 Gi | Redis | the semantic cache |

## Which object carries which responsibility

| Object | Responsibility |
| --- | --- |
| Job `indexer`, CronJob `reindex` | the only writer to Chroma and to the lake; the CronJob re-runs the same spec weekly |
| NetworkPolicies `chroma-ingress`, `api-egress`, `eval-egress` | nothing but the indexer is meant to reach Chroma for writing: the api and the eval pods have no write code, and the lake is mounted by the Job only |
| PVC `lake-data` | quarantine, archive and registry survive pod restarts |
| ConfigMap `rahbar-gate` | the release thresholds; editing it changes the gate without an image rebuild |
| Job `eval` | runs the suite and the gate; its exit status is the release decision |
| Deployment `api-candidate` and Service | the candidate, own collection `rahbar_cand` |
| Deployment `api`, `rollingUpdate`, `maxUnavailable: 0`, `revisionHistoryLimit: 10` | the live release and its rollback (`kubectl rollout undo`) |
