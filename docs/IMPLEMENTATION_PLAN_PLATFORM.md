# Implementation plan: platform lane (Kubernetes, Docker, CI/CD, evidence)

The phased build plan for everything in the platform lane of RAHBAR except the chat UI: the `ui` image, the Kubernetes manifests, the overlays, the CI and CD workflows, branch protection, the cluster evidence and the platform documents. It is also the **only progress tracker for the platform lane**: phase status, acceptance ticks and the progress log all live in this file. The RAG lane has its own file, [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) (phases 0 to 14 are DONE there).

This file implements the WORK PLAN tasks A-01 to A-11, A-13 and A-14 from [`WORKPLAN.md`](WORKPLAN.md) section 5. They were Ahmad's. Ahmad is not available, so Zain's sessions build them. Two tasks stay with Ahmad, and nothing here blocks on them:

| Task | What | Owner |
| --- | --- | --- |
| A-00 | Onboarding on his own laptop (WSL setup, `SETUP.md` fixes) | Ahmad |
| A-12 | UI polish (states, mobile width, version label in the UI) | Ahmad, when he is back |

| | |
| --- | --- |
| Lane | Kubernetes, Docker (`ui` image), CI/CD, branch protection, cluster evidence, platform docs |
| Window | Thu 5 Nov evening to Sun 8 Nov 2026 (final freeze Sun 14:00, submit by 18:00, deadline 23:59 PKT) |
| Source of truth for design | [`architecture/architecture.md`](architecture/architecture.md) section 4 (section numbers below refer to it) |
| Built by | Zain's developer sessions, one phase per session |

---

## 0. Read this first (for the implementing agent)

You are the agent building the platform lane. Follow the plan, in order, and update it as you go.

### 0.1 Authorisation and autonomy (read twice)

- **Zain explicitly authorises you to edit `k8s/**`, `.github/**`, `ui/Dockerfile`, `ui/.dockerignore`, `docs/evidence/**` and the cluster targets of the `Makefile` for this plan.** This overrides the line in `CLAUDE.md` and `IMPLEMENTATION_PLAN.md` 0.2 that says those paths belong to Ahmad. Do not edit `ui/index.html` or `ui/nginx.conf` unless a phase says so.
- **There is no approval gate.** Zain has pre-approved the recommended options. Write the spec and plan, commit and push, then go straight on to implement, test (independent subagent), open the PR and **merge it yourself** when the tester has passed and `make test && make lint` are green. This is a deliberate change to the single gate in [`WORKFLOW.md`](WORKFLOW.md); every other part of that file still applies.
- **Merge rule.** Merging yourself is allowed even when the diff touches shared files (`Makefile`, `docs/architecture/*`, `docs/OPEN_DECISIONS.md`), provided every drift from the architecture is logged in [`architecture/deviations.md`](architecture/deviations.md) in the same PR and the shared files are listed in the PR description.
- **Hard stops (ask Zain, do not guess):** a conflict between the assignment and the architecture; a secret or credential (see 0.4); a failing tester after 3 rounds; Ahmad's work appearing on `origin` (`git ls-remote --heads origin` shows a branch that is not yours); changing GitHub repository settings (branch protection, secrets) without the explicit step in phase K9; a destructive action outside your own branch.

### 0.2 Start of every session

1. Read this file top to bottom, then **Current focus** (section 2).
2. Find the first phase whose status is not `DONE`. That is your phase. Do not skip ahead.
3. Read what that phase lists under **Read first**. Re-read the cited architecture sections; do not rely on memory.
4. `git checkout dev && git pull`. Run `make test && make lint` for a clean baseline. Check `git ls-remote --heads origin` for branches that are not yours. Create a branch `feat/k8s-<phase id>-<topic>` (for example `feat/k8s-k03-ingress-hpa`) or `ci/<topic>` for workflows.
5. Check [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md) for anything `OPEN` that touches your phase.
6. Write the spec and plan for the phase in `docs/specs/phase-<id>-<slug>.md` from [`specs/TEMPLATE.md`](specs/TEMPLATE.md) (for example `phase-k03-ingress-hpa.md`), and set the work plan field to the matching A-task.

### 0.3 While working

- The architecture decides the design. If the manifests must differ, add an entry to `deviations.md` in the same PR and mark the phase `DONE (with deviation DEV-NNN)`.
- If something is unclear and not decided anywhere, add an entry to `OPEN_DECISIONS.md` ("Decided by: Claude, pre-approved by Zain" when you pick the recommended option), use the most conservative default, and keep going.
- Commits: Conventional Commits, small, ending with the `Co-Authored-By` trailer the tool provides. Never push to `main`. Never push code straight to `dev`: always through a PR (the progress-log commit may ride in the same PR).
- Docker needs the group workaround until Zain re-logs in: `sg docker -c "docker ..."` (also for `minikube image load` and `make images`).
- **Prove it on the real cluster.** A manifest that passes `kubeconform` but was never applied is not done. Every phase that creates cluster objects has acceptance criteria that run on minikube, and the output is saved in `docs/evidence/` (plain text, the command first, then its output).
- Tools: `kubectl`, `kustomize` and `kubeconform` are installed. `kind` and `trivy` are not installed locally (CI only). A phase may install `kind` locally in `$HOME/.local/bin` to rehearse a CI job, but it must not be required by `make test` or `make lint`.
- Keep `docs/AI-USAGE.md` current at the end of each phase.

### 0.4 Secrets (a break costs 20 marks)

- Never write a token, a password, a kubeconfig or a `.env` into any file, commit, PR text or log you paste.
- Docker Hub: the **account and the access token are created by Zain**, and stored by Zain with `gh secret set DOCKERHUB_TOKEN` and `gh secret set DOCKERHUB_USERNAME` (the session tells Zain the exact commands; Zain runs them with the `!` prefix so the value never enters the chat). The workflows only reference `${{ secrets.NAME }}`.
- `k8s/base/secret.placeholder.yaml` holds `REPLACE_ME` only and is **not** listed in any `kustomization.yaml`.

### 0.5 End of every phase

1. Run the phase's **Verify** commands and paste the key output into the progress log.
2. Tick every acceptance box that is true, with evidence. An unticked box means the phase is not done.
3. Set the phase status, update the dashboard (section 1) and **Current focus** (section 2), add a **Progress log** line (section 4).
4. Update [`AI-USAGE.md`](AI-USAGE.md).
5. Independent testing subagent ([`WORKFLOW.md`](WORKFLOW.md) section 6): it re-runs the Verify commands and tries to break the acceptance criteria. Fix and recommit until it passes, up to 3 rounds.
6. Open the PR into `dev`, merge it (0.1), delete the branch, remove the worktree.
7. Leave minikube running with the application deployed unless the phase says otherwise: later phases and the evidence depend on it. Stop containers you started yourself.

### 0.6 Status words

`NOT STARTED` · `IN PROGRESS` · `BLOCKED` (say by what, in the log) · `DONE` · `DROPPED` (cut line, say why).

### 0.7 Do not build

Helm charts, a service mesh, an operator, an Ingress TLS setup, Prometheus or Grafana, an in-cluster Ollama, authentication, a second environment on a cloud provider. They are not required and each costs hours. Do not add ConfigMap keys that are not in architecture 4.4 without a `deviations.md` entry and a note to the RAG lane (contract C-2).

---

## 1. Dashboard

| # | Phase | Work plan task | Est | Status | PR |
| --- | --- | --- | --- | --- | --- |
| K1 | `ui` image and base workloads on minikube | A-01, A-02, A-03 | 5 h | DONE (with deviations DEV-008, DEV-009) | #20 |
| K2 | Indexer Job, CronJob, corpus delivery, real index in the cluster | A-04 (milestone I-2) | 3 h | DONE (with deviation DEV-010) | #21 |
| K3 | Ingress, HPA, rollout hardening | A-05 | 2 h | DONE | #22 |
| K4 | NetworkPolicies and proof | A-06 | 3 h | NOT STARTED | |
| K5 | Overlays `ci` and `prod`, manifest validation | A-07 | 2 h | NOT STARTED | |
| K6 | CI part 1: lint, test, manifests, build, scan | A-08 | 3 h | NOT STARTED | |
| K7 | CI part 2: e2e-eval on kind | A-09 | 4 h | NOT STARTED | |
| K8 | CD: Docker Hub, build-push, deploy | A-10 | 3 h | NOT STARTED | |
| K9 | Branch protection and the gate demonstration | A-11 | 1.5 h | NOT STARTED | |
| K10 | Cluster evidence | A-13 | 3 h | NOT STARTED | |
| K11 | Platform documents | A-14 | 3 h | NOT STARTED | |

After K11 comes **Phase 15** of the RAG plan (integration support and final verification, the joint phase). It is deliberately last, see section 6.

Hours spent so far (fill in at each phase end): planned 33.5 h, actual `____`.

## 2. Current focus

```
Phase:        K4  NetworkPolicies and proof
Stage:        not started   (SPEC DRAFT, IMPLEMENTING, TESTING, READY FOR PR, MERGED)
Branch:       (none yet)
Spec:         (none yet)
Next action:  fresh session: stage 0 then stage 1 for K4. K3 is merged: Ingress rahbar (192.168.49.2, host rahbar.local), HPA api 3-8 at 70%, PDB api minAvailable 2. On this laptop `minikube ip` needs `sg docker -c` (or INGRESS_IP=192.168.49.2); cached/cache-lookup questions need Ollama running (query embedding). K2 state: namespace rahbar runs api x3 (1/1), ui, chroma-0, redis, the real index (980 chunks, index_id changes on `make index`) and CronJob reindex; Ollama on the host is stopped (start it only when a cache-miss question must be answered: OLLAMA_HOST=0.0.0.0 ollama serve). Host gateway IP for K4: 192.168.49.1. `make apply` deletes and re-runs the indexer Job (13 min with Ollama running): use `kubectl apply -k k8s/overlays/dev` for manifest-only changes.
Waiting on:   Zain: Docker Hub account and token (needed from K8, create it early). Ahmad: nothing blocks.
Last updated: 2026-11-06
```

Update this block at the end of every work session, even if the phase is unfinished.

---

## 3. Hand-offs and open items

| ID | Direction | Item | Phase | Done |
| --- | --- | --- | --- | :---: |
| HP-1 | Zain (human) | Create the Docker Hub account and an access token (read, write, delete scope on the repos). Run `gh secret set DOCKERHUB_USERNAME` and `gh secret set DOCKERHUB_TOKEN` with the `!` prefix. Decide the Docker Hub namespace (decision D-013) | before K8 | [ ] |
| HP-2 | Zain (human) | Approve changing branch protection on `main` (required checks, admin enforcement) when K9 asks | K9 | [ ] |
| HP-3 | RAG lane to platform | H-7 to H-14 values: ConfigMap values, `ci` overlay floor 0.20, `LLM_TIMEOUT_SECONDS=300`, Ingress timeout at least 310 s, Redis settings, health and metrics paths. Texts are in the progress log of `IMPLEMENTATION_PLAN.md`. Already delivered, listed here so nothing is missed | K1 to K5 | [x] |
| HP-4 | Platform to RAG lane | Final status of H-9 (manifests running in minikube) and H-10 (real corpus on the PVC, Job runnable) recorded in `IMPLEMENTATION_PLAN.md` section 3 | K2 | [x] |
| HP-5 | Platform to Ahmad (when back) | `ui/Dockerfile` is done and merged; A-12 (UI polish and version label) and A-00 (onboarding) are his | K11 | [ ] |

---

## 4. Progress log

Append-only, newest at the bottom. One line per event: date, phase, what happened, evidence (command or file). Keep it factual.

```
2026-11-05  PLAN  Platform plan written. RAG lane phases 0 to 14 DONE; Ahmad's lane has no commits on origin (k8s/base empty, no workflows, no ui/Dockerfile, no evidence). Zain's sessions take over A-01 to A-11, A-13, A-14. A-00 and A-12 stay with Ahmad.
2026-11-05  K1  DONE (#20). k8s base running on minikube: api x3 0/1 (readyz 503 failed=[collection], healthz 200), ui, chroma-0, redis Ready, PVCs Bound; images api 388 MB, indexer 592 MB, ui 73.7 MB; kubeconform 16 resources valid, 0 Secret in build. Data survives pod deletion (Chroma collection, Redis key). A-5 verified (api pod deletion 11.4 s vs 0.9 s without preStop). Found: Service `chroma` injects CHROMA_PORT=tcp://... and crash-loops Chroma -> enableServiceLinks false (DEV-008). fsGroup is a no-op on minikube hostPath, /data is 0777 (DEV-009). Evidence docs/evidence/k01-*.txt. Note: api rollout stalls while no index exists (maxUnavailable 0, new pods never Ready): expected until K2.
2026-11-06  K2  DONE (#21). corpus-data PVC, Job `indexer`, CronJob `reindex` (spec copied from the Job by a kustomize replacement, D-093), make corpus/apply/down. A-1: host.minikube.internal = 192.168.49.1 from a pod, Ollama answered. A-4: kubectl cp into busybox helper OK (11 files). Job Complete 1/1 in 13 min, peak 483 Mi, 980 chunks (DEV-010). api 0/1 -> 1/1 by itself, no restart. Cited answer "80%" (prospectus, Attendance Requirement), repeat X-Cache HIT. `make index` 9 min 24 s, index_id changed, 90 requests during the swap all 200. Run 1 of the Job was marked DeadlineExceeded after the laptop slept ~15 h with the pod already finished; re-run clean (inhibit sleep for long waits). Evidence docs/evidence/k02-*.txt.
2026-11-06  K3  DONE (#22). k8s/base ingress.yaml, hpa.yaml, pdb.yaml (D-095). Ingress rahbar address 192.168.49.2; `/` returns the UI HTML; `make ask` through the Ingress returns a cited answer; /metrics and /api/healthz not routed to the api. HPA idle `cpu: 4%/70%`, 3-8. Forced test (target 5%, cached-question loop): 3 -> 6 -> 8 replicas in 30 s, back to 3 about 5 min after revert. `<unknown>` shows for about 1 min after pods restart (metrics lag), then a number. `rollout restart deploy/api` under a 0.5 s loop through the Ingress: 0 non-200 of 42. endpoints api = 3 IPs. kubeconform 22 resources valid. Evidence docs/evidence/k03-*.txt.
```

---

## 5. Results register

Numbers this lane must measure. Nothing here is a guess: leave `-` until measured.

| Quantity | Value | Phase | Measured with |
| --- | --- | --- | --- |
| `ui` image size | 73.7 MB (api 388 MB, indexer 592 MB) | K1 | `docker image ls` |
| Time from `make apply` to all pods Ready (no Job yet) | chroma, redis, ui Ready 3 s after pod creation with images cached (api stays 0/1 by design); first pull of chroma and redis images not timed | K1 | pod `Ready` transition minus creation time |
| Indexer Job wall time and peak memory in the cluster | 13 min 18 s Job (798 s in the pipeline: embed 414 s, OCR 76 s for the 8-page policy), `make index` 9 min 24 s; peak 483 Mi of 2 Gi (run 1: 484 Mi), CPU at the 1-core limit while chunking/OCR | K2 | `kubectl logs job/indexer`, `kubectl top pod` |
| Collection chunk count in the cluster (must equal 981) | 980 (DEV-010: OCR'd faculty policy 39 vs 40 chunks); `index_id` 20261106T103106Z-41fe5d, after `make index` 20261106T125625Z-ba262b | K2 | `scripts/check_index.py` or `/readyz`, `rahbar_index_info` |
| Api request and limit, actual `kubectl top` per pod, idle and under load | - | K10 | `kubectl top pods -n rahbar` |
| HPA reading (current/target) idle and under load | idle `cpu: 4%/70%` (3 replicas); cached-question loop with target forced to 5%: `32%/5%`, 3 to 6 to 8 replicas in 30 s; back to 3 about 5 min after the revert (K3; K10 repeats) | K3, K10 | `kubectl get hpa -n rahbar` |
| Failed requests during `rollout restart` of the api | 0 of 42 (cached question through the Ingress every 0.5 s) | K3 | request loop |
| `ci` e2e-eval wall time on kind | - | K7 | Actions run |
| Fixture eval result in CI (recall@5, citation validity, abstention) | - | K7 | `eval/fixtures/results.fixture.json` |
| Image sizes on Docker Hub (api, indexer, ui) and the SHA tag | - | K8 | Docker Hub page |
| Trivy findings (HIGH and CRITICAL with a fix) per image, and what was done | - | K6 | Actions log |
| Cold answer latency through the Ingress in the cluster (p50, p95) | - | K10 | `make eval` |

---

## Phase K1: `ui` image and base workloads on minikube (A-01, A-02, A-03)

**Status:** DONE · **Branch:** `feat/k8s-k01-base-workloads` · **Est:** 5 h · **Priority:** P0

### Objective
Everything except the indexer, the Ingress, the policies and the autoscaler runs in minikube from `kubectl apply -k k8s/overlays/dev`: the three images exist, and `api`, `ui`, `chroma` and `redis` are Ready with persistent storage.

### Read first
Architecture 4.1 (topology), 4.2 (workload inventory), 4.3 (Services), 4.4 (ConfigMap keys), 4.5 (storage), 4.7 (security posture), 4.8 (probes), 4.9 (rollouts), 4.10 (why StatefulSet), 4.11 (Kustomize layout), 4.12 (image rules); requirements R-K8S-*, R-IMG-*, R-SEC-1..3, R-RES-1, R-PRB-*; `ui/nginx.conf`, `ui/index.html`; `docs/IMPLEMENTATION_PLAN.md` section 4 for the texts of H-2 (Redis Stack: image `redis/redis-stack-server:7.4.0-v8`, runs as UID 10001, writes only `/data`, `fsGroup: 10001`, `REDIS_ARGS=--appendonly yes`), H-3 (Chroma `chromadb/chroma:1.0.12`, UID 10001, env `IS_PERSISTENT=TRUE PERSIST_DIRECTORY=/data ANONYMIZED_TELEMETRY=FALSE`, heartbeat `/api/v2/heartbeat`), H-7 (ConfigMap values), H-11 (health and readiness behaviour).

### Scope
- `ui/Dockerfile`, `ui/.dockerignore`: `nginxinc/nginx-unprivileged` with a pinned tag (confirm it pulls), copy `nginx.conf` to `/etc/nginx/nginx.conf` and `index.html` to the web root, port 8080, non-root. Check that `nginx.conf` serves `/healthz` for the probe; if it does not, report it (do not edit `nginx.conf` without a note).
- `make images`: make it work for all three images (the `ui` line was failing only because the Dockerfile was missing). Use `sg docker -c`.
- `k8s/base/`: `namespace.yaml`, `serviceaccounts.yaml` (one per workload, `automountServiceAccountToken: false`), `configmap.yaml` (every key of architecture 4.4 with the shipped values and a one-line comment on `TEMPERATURE`, `RELEVANCE_FLOOR`, `CACHE_THRESHOLD`), `secret.placeholder.yaml` (`REPLACE_ME`, not in the kustomization), `api.yaml`, `ui.yaml`, `chroma-statefulset.yaml` (`volumeClaimTemplates` `chroma-data` 2Gi), `redis.yaml` (Deployment plus PVC `cache-data` 1Gi, strategy `Recreate` because the volume is `ReadWriteOnce`), `services.yaml` (four ClusterIP), `kustomization.yaml`.
- `k8s/overlays/dev/kustomization.yaml`: images `rahbar-<name>:dev`, `imagePullPolicy: IfNotPresent`, namespace `rahbar`.
- `make apply`: applies the dev overlay (and, once K2 lands, deletes a finished indexer Job first).

### Design notes
- ConfigMap `rahbar-config` is injected into api, indexer and CronJob with `envFrom`; the name is stable (AD-17). `RETRIEVER=chroma` and `EMBED_MODEL=nomic-embed-text`, `LLM_PROVIDER=ollama-host`, `LLM_TIMEOUT_SECONDS=300`, `RELEVANCE_FLOOR=0.70`, `CACHE_THRESHOLD=0.96` (these differ from the older architecture 4.4 table where it still shows 0.50: use the H-7 values and fix the table in the same PR as a doc change).
- Security on every container: pod `runAsNonRoot: true`, `runAsUser`/`runAsGroup` 10001 (ui 101), `fsGroup` 10001 for the PVC pods, `seccompProfile: RuntimeDefault`; container `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities.drop: [ALL]`; `emptyDir` at `/tmp` for api and ui; PVC at `/data` for chroma and redis.
- api: 3 replicas, the three probes with the exact values of 4.8, `maxSurge: 1`, `maxUnavailable: 0`, `terminationGracePeriodSeconds: 30`, native `preStop` `sleep: seconds: 10` (verify with `kubectl explain pod.spec.containers.lifecycle.preStop.sleep`; if the cluster rejects it, use an `exec` sleep and log the deviation, assumption A-5), requests 100m/256Mi and limits 500m/512Mi, `secretKeyRef` for `LLM_API_KEY` with `optional: true`.
- ui: startup, liveness and readiness probes on `/healthz` port 8080; requests 25m/32Mi, limits 100m/64Mi.
- chroma: probes `GET /api/v2/heartbeat`; requests 100m/256Mi, limits 500m/1Gi; `serviceName: chroma`. redis: `redis-cli ping` probes; requests 100m/256Mi, limits 500m/512Mi.
- Labels on every object: `app.kubernetes.io/name` and `app.kubernetes.io/part-of: rahbar`. Pin every image tag.
- Without the indexer there is no collection yet, so the api pods stay `0/1` (readyz: collection missing). That is correct (architecture 4.13). Verify the api is alive (`/healthz` through `kubectl port-forward`) and that `/readyz` returns 503 naming `collection`.
- Verify assumption A-5 and the `fsGroup` mechanism for both PVCs here (H-2 and H-3 noted they were only simulated in Docker). Record both results in architecture section 9 and in `deviations.md` if reality differs.

### Out of scope
Indexer, Ingress, HPA, NetworkPolicy, other overlays, anything in `ui/index.html`.

### Acceptance criteria
- [x] `sg docker -c "make images"` builds all three images and loads them into minikube; the `ui` image runs with `--read-only --tmpfs /tmp --user 101` and serves `/` and `/healthz` on 8080.
- [x] `kustomize build k8s/overlays/dev | kubeconform -strict -summary` passes.
- [x] `kubectl apply -k k8s/overlays/dev` gives: 3 api pods (running, `0/1` Ready until K2), 1 ui pod Ready, `chroma-0` Ready with its PVC bound, `redis` Ready with `cache-data` bound; every container has requests and limits.
- [x] Data survives: write a marker to the Chroma PVC (create a throwaway collection through a port-forward), `kubectl delete pod chroma-0`, and show it is still there; same for a key in Redis.
- [x] `/readyz` of an api pod returns 503 with `failed: ["collection"]`, `/healthz` returns 200 (via port-forward); saved to `docs/evidence/k01-api-before-index.txt`.
- [x] `scripts/check_submission.py` section G has no failure for the objects that exist now.
- [x] No secret in Git; `secret.placeholder.yaml` is not in any kustomization (`kustomize build` output has no `Secret`).
- [x] A-5 and the PVC `fsGroup` mechanism verified and recorded.
- [x] `make test && make lint` green.

### Verify
```bash
sg docker -c "make images"
kustomize build k8s/overlays/dev | kubeconform -strict -summary
kubectl apply -k k8s/overlays/dev && kubectl get pods,pvc -n rahbar
kubectl port-forward -n rahbar deploy/api 8000:8000 & sleep 2; curl -s localhost:8000/healthz; curl -si localhost:8000/readyz | head -12; kill %1
python3 scripts/check_submission.py | sed -n '/G · kubernetes/,/H · evaluation/p'
```

### Hand-off
None. Record "k8s base running" in the progress log.

---

## Phase K2: Indexer Job, CronJob, corpus delivery, real index in the cluster (A-04, milestone I-2)

**Status:** DONE (with deviation DEV-010) · **Branch:** `feat/k8s-k02-indexer` · **Est:** 3 h · **Priority:** P0 · **Delivers:** H-9 and H-10 to the RAG plan

### Objective
The real index of 981 chunks exists in the cluster's Chroma, built by the indexer Job from documents delivered into the `corpus-data` PVC, and the api pods become Ready because of it.

### Read first
Architecture 4.2 (indexer and reindex rows), 4.5 (storage and corpus delivery, AD-08), 4.13 (bring-up order), 5.4 (indexing: stage-and-swap), AD-02, AD-08; requirements R-K8S-JOB, R-K8S-CRON, R-RES-3; `indexer/pipeline/run.py` (contract C-4: waits for Chroma 120 s and Ollama 60 s, exit codes, re-hashes against `_index.json`), `corpus/raw/_index.json` and `corpus/MANIFEST.md`; H-4 (indexer peak 438 MB, wall time 9 min 40 s on the host, suggested request 512Mi, limit 1Gi, `activeDeadlineSeconds: 1800` "not by a wide margin"); assumptions A-1 and A-4 in architecture section 9.

### Scope
- `k8s/base/corpus-pvc.yaml` (`corpus-data`, 1Gi).
- `k8s/base/indexer-job.yaml` (Job `indexer`: `restartPolicy: OnFailure`, `backoffLimit` set, `activeDeadlineSeconds`, PVC read-only at `/corpus`, `emptyDir` `/tmp`, same security context, requests 250m/512Mi, limits 1/2Gi per architecture 4.2, `envFrom` the ConfigMap) and `k8s/base/reindex-cronjob.yaml` (`0 3 * * 0`, `concurrencyPolicy: Forbid`, same pod template; use a kustomize patch or YAML anchors so the two cannot drift).
- `Makefile`: `corpus` (create namespace and PVC, start a non-root helper pod `corpus-loader` that mounts the PVC, `kubectl cp corpus/raw/. rahbar/corpus-loader:/corpus`, wait, delete the helper), `apply` (first `kubectl delete job indexer --ignore-not-found`), `index` (already exists), and a `down` target that deletes the namespace.
- Add the Job and CronJob to `k8s/base/kustomization.yaml`.

### Design notes
- The Job must not need Redis (invariant: only the API touches Redis). It needs egress only to Chroma and the Ollama host; K4 adds the policy, so verify here with no policy in place and re-verify in K4.
- **Ollama from a pod (assumption A-1).** Ollama runs on the laptop with `OLLAMA_HOST=0.0.0.0`. Verify `host.minikube.internal` resolves inside a pod and that `curl http://host.minikube.internal:11434/api/tags` works. Record the host IP (`minikube ssh "grep host.minikube.internal /etc/hosts"`) for the K4 `ipBlock`. If it fails, log a deviation and fix (for example the node IP).
- The helper pod runs as non-root with `fsGroup` matching the Job's group so the copied files are readable. Verify `kubectl cp` works into it (assumption A-4); if `kubectl cp` needs `tar` in the image, use an image that has it (a pinned `busybox` or `alpine`).
- Watch the Job: `kubectl logs -f job/indexer -n rahbar` shows the stage lines; capture wall time and peak memory (`kubectl top pod` during the run) into the results register. If the limit is too low (OOMKilled, exit 137) raise it and say why. If `activeDeadlineSeconds: 1800` is tight, raise it.
- The Ollama host must be running with both models during the Job. Start it with `OLLAMA_HOST=0.0.0.0 ollama serve` and stop it afterwards with `pkill -x ollama`.
- After the Job: restart the api (`kubectl rollout restart deploy/api -n rahbar`) only if it does not turn Ready by itself within `INDEX_REFRESH_SECONDS`; note which happened.
- Prove the re-index path: `make index` (Job from the CronJob), and that the API keeps serving during the swap and `rahbar_index_info` shows the new `index_id` afterwards.

### Out of scope
Ingress, HPA, NetworkPolicy, CI.

### Acceptance criteria
- [x] `make corpus` copies the nine documents plus `_index.json` and `MANIFEST.md` into `corpus-data` (listing saved) and removes the helper pod.
- [x] The indexer Job completes (`kubectl get job indexer -n rahbar` shows `1/1`), the logs show every stage, the collection has 980 chunks (981 expected, DEV-010) and the `index_id` appears in `/readyz` or `rahbar_index_info`.
- [x] api pods become `1/1 Ready` after the index exists; before it they were `0/1`.
- [x] A question through `kubectl port-forward` to an api pod returns a cited answer (`answered_from_context: true`, citations in `retrieved`), and a repeat question shows `X-Cache: HIT`.
- [x] `make index` creates a Job from the CronJob (`kubectl create job --from=cronjob/reindex`), it completes, `index_id` changes, and no request failed while a loop of questions ran against the API during the swap.
- [x] A-1 and A-4 are verified and recorded in architecture section 9; any deviation is logged.
- [x] Wall time, peak memory and chunk count recorded in the results register; H-9 and H-10 ticked in `IMPLEMENTATION_PLAN.md` section 3.
- [x] `docs/evidence/k02-indexer-job.txt` (Job description, logs excerpt, chunk count) and `docs/evidence/k02-first-answer.txt` saved.
- [x] `kubeconform -strict` still passes; `make test && make lint` green.

### Verify
```bash
OLLAMA_HOST=0.0.0.0 ollama serve &   # then make corpus && make apply
sg docker -c "make corpus" ; make apply
kubectl logs -f job/indexer -n rahbar
kubectl get pods,job -n rahbar
kubectl port-forward -n rahbar deploy/api 8000:8000 &
curl -s -XPOST localhost:8000/api/ask -H 'content-type: application/json' -d '{"question":"What is the minimum attendance required to sit the final exam?"}'
pkill -x ollama
```

### Hand-off
H-9 and H-10 to the RAG plan (tick them in `IMPLEMENTATION_PLAN.md` section 3 and say so in the progress log of both files).

---

## Phase K3: Ingress, HPA, rollout hardening (A-05)

**Status:** DONE · **Branch:** `feat/k8s-k03-ingress-hpa` · **Est:** 2 h · **Priority:** P0

### Objective
Questions reach the API through one Ingress host, the api scales on CPU between 3 and 8 pods with a real percentage, and a rolling update drops no request.

### Read first
Architecture 4.3 (Ingress, annotations), 4.9 (rollouts, scaling, graceful shutdown), requirements R-K8S-ING, R-K8S-HPA, R-RES-4, R-RES-5, R-ROL-1..3; `docs/ENGINEERING-NOTES.md` Q3 (the HPA signal question: CPU is a poor signal for an I/O-bound generation service).

### Scope
- `k8s/base/ingress.yaml`: class `nginx`, host `rahbar.local`, `/api` Prefix to `api:8000` (no rewrite), `/` Prefix to `ui:80`; annotations `proxy-read-timeout: "310"` and `proxy-body-size: "16k"`.
- `k8s/base/hpa.yaml`: `autoscaling/v2`, 3 to 8, CPU `averageUtilization: 70`.
- `k8s/base/pdb.yaml`: PodDisruptionBudget for the api (`minAvailable: 2`), if it does not conflict with the checker.
- Confirm or fix `make ask` and `make eval` (Host header, `INGRESS_IP`).

### Design notes
- Linux: the minikube IP is reachable directly (`minikube ip`); the Ingress addon runs in `ingress-nginx`. On other platforms use `minikube tunnel`.
- The HPA needs `requests.cpu` on the api (K1) and metrics-server (addon enabled by `make cluster`); `kubectl get hpa` must show a number, not `<unknown>`. If it shows `<unknown>`, wait 60 s and check `kubectl top pods`.
- Load test for the HPA: because the api spends its time waiting on the model, CPU stays low. Generate CPU with cache-miss questions only if cheap; otherwise demonstrate scaling by temporarily lowering the target (for example `kubectl patch hpa api -p '{"spec":{"metrics":[{"type":"Resource","resource":{"name":"cpu","target":{"type":"Utilization","averageUtilization":5}}}]}}'`), show the replicas rising, and revert. Say plainly in the evidence that CPU does not rise with generation load and refer to Q3.
- The rolling update demonstration is part of the evidence in K10; here, run a quick version: while a request loop runs (`curl` every 0.5 s against `/api/ask` with a cached question, or `/healthz` through the Ingress is not routed, so use a cached question), `kubectl rollout restart deploy/api -n rahbar` and count failures. The target is zero failed requests; if there are some, tune `preStop` and the readiness settings.
- `/healthz`, `/readyz` and `/metrics` are not routed through the Ingress.

### Out of scope
NetworkPolicies, TLS.

### Acceptance criteria
- [x] `kubectl get ingress -n rahbar` shows `rahbar.local` with an address; `make ask Q="..."` returns a cited answer through the Ingress; `curl -H 'Host: rahbar.local' http://$(minikube ip)/` returns the UI HTML.
- [x] `kubectl get hpa -n rahbar` shows a real `x%/70%`, min 3, max 8.
- [x] A forced scale test shows replicas rising above 3 and falling back, output saved.
- [x] A request loop during `kubectl rollout restart deploy/api` shows zero failed requests (the count is in the results register).
- [x] `kubectl get endpoints api -n rahbar` lists 3 pod IPs.
- [x] `kustomize build k8s/overlays/dev | kubeconform -strict` passes; `make test && make lint` green.
- [x] `docs/evidence/k03-hpa.txt`, `k03-rollout-loop.txt` and `k03-ingress.txt` saved.

### Verify
```bash
kubectl apply -k k8s/overlays/dev
kubectl get ingress,hpa,endpoints -n rahbar
make ask Q="What CGPA puts a student on academic warning?"
```

### Hand-off
None.

---

## Phase K4: NetworkPolicies and proof (A-06)

**Status:** NOT STARTED · **Branch:** `feat/k8s-k04-networkpolicy` · **Est:** 3 h · **Priority:** P0

### Objective
The cluster denies all traffic except the paths the architecture needs, the system still works under that policy, and a captured experiment proves that `ui` cannot reach `chroma` while `api` can.

### Read first
Architecture 4.6 (the whole section: policies table and diagram), 4.7; requirements R-K8S-NP, R-SEC-4; the host IP from K2 (`minikube ssh "grep host.minikube.internal /etc/hosts"`, normally `192.168.49.1`); risk R-07 (policy unenforced on kind).

### Scope
- `k8s/base/networkpolicy.yaml`: `default-deny-all` (empty `podSelector`, ingress and egress), `allow-dns-egress` (to `k8s-app=kube-dns` in `kube-system`, UDP and TCP 53), `ui-ingress` (from the `ingress-nginx` namespace, 8080), `api-ingress` (from `ingress-nginx` on 8000 and from `ui` on 8000), `api-egress` (to `chroma:8000`, `redis:6379`, the Ollama `ipBlock` on 11434), `chroma-ingress` (from `api` and `indexer` on 8000), `redis-ingress` (from `api` on 6379), `indexer-egress` (to `chroma:8000` and the Ollama `ipBlock` on 11434).
- The `ipBlock` lives in the `dev` overlay as a patch (default `192.168.49.1/32`); the base has a documented placeholder.

### Design notes
- Calico is installed (`--cni=calico`), so the policies are enforced; prove enforcement, do not assume it (the proof is the point).
- The namespace `ingress-nginx` needs the label `kubernetes.io/metadata.name=ingress-nginx` (set automatically on current Kubernetes); verify it.
- Probes come from the kubelet on the node and are allowed by Calico; confirm all pods stay Ready after the deny is applied.
- Apply the policy last, after the system works (K2 and K3), so a failure is attributable to the policy. Check each of: UI loads through the Ingress, `make ask` works, the indexer Job still completes (run `make index`), the api still reaches Redis (cache HIT) and Ollama (a cache-miss question is answered).
- The proof experiment, saved verbatim to `docs/evidence/k04-networkpolicy-proof.txt`: from a `ui` pod `wget -T3 -qO- http://chroma:8000/api/v2/heartbeat` fails; the same from an `api` pod succeeds; also show `ui` to `redis:6379` fails, `indexer` to `redis:6379` fails. The images may lack `wget` or `nc`: use an ephemeral debug container (`kubectl debug`) or `python -c` in the api pod. Document how.
- Also capture the "before" (policy not yet applied, the connection from `ui` to `chroma` succeeds) to show that the policy is what changed it.

### Out of scope
TLS, mTLS, egress to the internet in `hosted` mode (an overlay concern, not shipped).

### Acceptance criteria
- [ ] All eight policy objects exist; `kubectl get netpol -n rahbar` lists them.
- [ ] After applying them: pods Ready, UI loads, `make ask` answers (including a cache-miss question, which needs Ollama), `make index` completes.
- [ ] The proof file shows: before = `ui` reaches `chroma`; after = `ui` to `chroma` refused or timed out, `ui` to `redis` blocked, `indexer` to `redis` blocked, `api` to `chroma` and `redis` allowed.
- [ ] `kubeconform -strict` passes; the policy file has no policy that selects by anything other than `app.kubernetes.io/name` labels and namespaces.
- [ ] `make test && make lint` green.

### Verify
```bash
kubectl apply -k k8s/overlays/dev
kubectl get netpol -n rahbar
make ask Q="What is the minimum attendance required to sit the final exam?"
kubectl exec -n rahbar deploy/ui -- wget -T3 -qO- http://chroma:8000/api/v2/heartbeat   # expect failure
kubectl exec -n rahbar deploy/api -- python -c "import urllib.request;print(urllib.request.urlopen('http://chroma:8000/api/v2/heartbeat',timeout=3).read())"
```

### Hand-off
None. Update `docs/SETUP.md` with the Ollama host IP check if it was not there.

---

## Phase K5: Overlays `ci` and `prod`, manifest validation (A-07)

**Status:** NOT STARTED · **Branch:** `feat/k8s-k05-overlays` · **Est:** 2 h · **Priority:** P0

### Objective
Three overlays exist and all build and validate: `dev` (minikube), `ci` (kind in GitHub Actions: fixture corpus, hashing embedder, extractive provider, no Ollama egress), `prod` (registry images by commit SHA).

### Read first
Architecture 4.11 (layout and the overlay comparison table), 4.15 (e2e-eval and CD smoke test), 4.5 (the `corpus-fixtures` ConfigMap in `ci`), AD-18, AD-27; requirements R-CI-3, R-CI-6, R-CD-3; H-8 (the `ci` overlay must set `RELEVANCE_FLOOR=0.20` because the hashing embedder's scores run 0.00 to 0.43); `eval/fixtures/` (three documents, `golden.fixture.yaml`, `baseline.fixture.json`); `indexer/pipeline/run.py` (how `CORPUS_DIR` and `_index.json` are read, and how the fixture markdown front matter carries `doc_version` and `superseded`).

### Scope
- `k8s/overlays/ci/`: patches ConfigMap (`EMBED_MODEL=hashing-bow-768`, `LLM_PROVIDER=extractive`, `RELEVANCE_FLOOR=0.20`, `CORPUS_DIR=/corpus`, whatever the fixtures need), a `ConfigMapGenerator` `corpus-fixtures` built from `eval/fixtures/*.md` (no secrets; the generator must also produce `_index.json` or the Job must tolerate its absence: check what the verify stage requires and choose the smaller change, logging it), the Job and CronJob mount that ConfigMap at `/corpus` instead of the PVC, removes the Ollama `ipBlock` egress, `imagePullPolicy: IfNotPresent`, replicas of the api reduced if kind is small (keep 3 if it fits).
- `k8s/overlays/prod/`: images `docker.io/<dockerhub-namespace>/rahbar-<name>` with a placeholder tag, set by `kustomize edit set image ...:<sha>` in CD; the Ollama `ipBlock` placeholder; documented as the definition of the production shape.
- `Makefile`: a `manifests` target that builds and validates all three overlays (`kustomize build k8s/overlays/<x> | kubeconform -strict -summary`).

### Design notes
- Install `kind` locally (`$HOME/.local/bin`, pinned version) only to rehearse the `ci` overlay before K7; this is optional here but strongly recommended, because a CI-only failure costs a push and a wait for each fix. Rehearse: create a kind cluster, install ingress-nginx, load the images (`kind load docker-image`), apply the `ci` overlay, wait for the Job, run `eval/run_eval.py` with the fixture golden set and baseline, and confirm the gate passes. If you cannot install `kind` (Docker permission), rehearse the `ci` overlay on minikube in a throwaway namespace instead, and say so.
- The `ci` overlay must contain no reference to the host Ollama.
- Use the same images and ConfigMap shape in all overlays so a mistake is one patch.
- Do not list the placeholder Secret anywhere.

### Out of scope
The workflows themselves (K6, K7, K8).

### Acceptance criteria
- [ ] `make manifests` passes for `dev`, `ci` and `prod`.
- [ ] `dev` still applies on minikube unchanged in behaviour (re-run `kubectl apply -k k8s/overlays/dev`; pods stay Ready).
- [ ] The `ci` overlay was exercised end to end (kind or throwaway namespace): the Job indexed the fixtures, the api turned Ready, `eval/run_eval.py` with `golden.fixture.yaml` and `baseline.fixture.json` exits 0; output saved to `docs/evidence/k05-ci-overlay-rehearsal.txt`.
- [ ] `prod` builds with a placeholder SHA and contains no `:latest`.
- [ ] `grep -rn ":latest" k8s` returns nothing.
- [ ] `make test && make lint` green.

### Verify
```bash
make manifests
grep -rn ":latest" k8s || echo "no latest"
```

### Hand-off
None.

---

## Phase K6: CI part 1: lint, test, manifests, build, scan (A-08)

**Status:** NOT STARTED · **Branch:** `ci/k06-ci-core` · **Est:** 3 h · **Priority:** P0

### Objective
A pull request runs five jobs in GitHub Actions and any of them can fail it: `lint`, `test`, `manifests`, `build`, `scan`.

### Read first
Architecture 4.15 (diagram, table), AD-27; requirements R-CI-1..5, R-CD-5, rubric section on workflows (deductions for missing `needs:`, `permissions:`, `:latest`, unpinned actions); `scripts/check_submission.py` `check_workflows` (what it looks for); `Makefile` (`test`, `lint`); `.github/pull_request_template.md`.

### Scope
- `.github/workflows/ci.yml`: triggers `pull_request` (to `main` and `dev`) and `push` to `dev`; top-level `permissions: contents: read`; jobs:
  - `lint`: Python 3.12, install `api/requirements-dev.txt` and `indexer/requirements-dev.txt`, `make lint`.
  - `test`: `make test`, plus coverage of the api package at least 60% (`pytest --cov=app --cov-fail-under=60` in `api/`), uses the stub, no network, no model. Note the 19 tests skipped without `REDIS_URL`: either start a Redis Stack service container for them or leave them skipped and say so.
  - `manifests`: install `kustomize` and `kubeconform` (pinned versions), build the three overlays and validate with `kubeconform -strict`.
  - `build`: `needs: [lint, test, manifests]`; `docker build` of the three images with the Buildx action (cache optional), no push; `if` conditions so it never pushes on a PR.
  - `scan`: `needs: build`; Trivy on each image, failing on HIGH and CRITICAL findings that have a fix (`--ignore-unfixed`); the result of a first run decides whether base images need a bump (record it in the results register and fix real findings: bump a base tag, or document an accepted risk in `docs/adr/0004-*` only if no fix exists).
- All third-party actions pinned to a version tag or, better, a commit SHA (record the version you used).

### Design notes
- No secret is needed in this workflow.
- Action versions must be real: check the action's latest release tag before pinning (use `gh api repos/<owner>/<repo>/releases/latest` for each). Do not invent tags.
- The workflow cannot be run locally. Validate it with `actionlint` if installable (a pinned binary into `$HOME/.local/bin`), and with a real run: push the branch, open the PR, watch the run (`gh run watch`, `gh run view --log-failed`). Iterate until green. **A PR that is red cannot be merged by you: fix it, do not bypass it.**
- Prove the checks can fail: open a short-lived second branch that breaks a manifest (for example an invalid `apiVersion`) and show `manifests` failing; close that PR without merging and save the run URL and the failing log excerpt in `docs/evidence/k06-failing-check.txt` (K9 needs a gate demonstration on a protected branch; this is the rehearsal).
- Job names are the future required check names: keep them exactly `lint`, `test`, `manifests`, `build`, `scan` (and `e2e-eval` in K7).

### Out of scope
e2e-eval (K7), CD (K8), branch protection (K9).

### Acceptance criteria
- [ ] A pull request into `dev` shows the five jobs; the run URL is in the log; all green on the final commit.
- [ ] A deliberately broken manifest fails `manifests` (evidence file).
- [ ] The workflow has a top-level `permissions:` block, every action is pinned, `build` and `scan` have `needs:`, and no `:latest` appears.
- [ ] Trivy ran on all three images; the findings and the action taken are in the results register.
- [ ] `python3 scripts/check_submission.py | sed -n '/I · CI/,/J · docs/p'` has no failures for what exists (`cd.yml` and e2e may still be missing).
- [ ] The README CI badge (already in the README) points at the workflow file and turns green.
- [ ] `make test && make lint` green.

### Verify
```bash
gh run list --workflow=ci.yml --limit 3
gh run view <id>
python3 scripts/check_submission.py | sed -n '/I · CI/,/J · docs/p'
```

### Hand-off
None.

---

## Phase K7: CI part 2: e2e-eval on kind (A-09)

**Status:** NOT STARTED · **Branch:** `ci/k07-e2e-eval` · **Est:** 4 h · **Priority:** P0 · **Hardest CI job**

### Objective
A `e2e-eval` job creates a kind cluster, deploys the `ci` overlay with the three images, indexes the fixture corpus with the Job, waits for the api, runs the evaluation harness against the Ingress, and fails the pull request when the gate fails.

### Read first
Architecture 4.15 (e2e-eval row, "what e2e-eval proves"), 5.13 (evaluation architecture, the gate), AD-27, requirement R-CI-6; K5 results (the `ci` overlay rehearsal) and its evidence file; `eval/run_eval.py` (CLI, exit codes), `eval/fixtures/*`; H-5, H-8.

### Scope
- Add the job `e2e-eval` to `.github/workflows/ci.yml` (`needs: build` or build the images itself and share them as artifacts; choose the simpler): kind cluster (single node), ingress-nginx installed from a pinned manifest, the three images built and loaded with `kind load docker-image`, `kubectl apply -k k8s/overlays/ci`, wait for the Job (`kubectl wait --for=condition=complete job/indexer --timeout=...`), wait for the api rollout, run
  `python eval/run_eval.py --api http://localhost --host rahbar.local --golden eval/fixtures/golden.fixture.yaml --baseline eval/fixtures/baseline.fixture.json --out eval/fixtures/results.fixture.json`
  (the ingress must be reachable from the runner: map `rahbar.local` or send the `Host` header as the CLI does), on failure dump `kubectl get pods`, `describe`, and the logs of api, chroma, redis and the Job (`if: failure()`), upload `results.fixture.json` as an artifact.
- Set a job timeout and reasonable `kubectl wait` timeouts; keep the whole job under about 15 minutes.

### Design notes
- kind has no Calico by default: the default kind CNI does not enforce NetworkPolicy. Either (a) exclude the policy file from the `ci` overlay and say clearly in the README and ADR that policy enforcement is proven on minikube, not in CI (risk R-07, recommended), or (b) install Calico in kind (more time). Pick (a) unless time is abundant, and write the sentence into the evidence notes.
- Redis Stack in kind: same image as minikube; the first pull is slow, so cache nothing exotic. The extractive provider and hashing embedder need no Ollama.
- Make the failure demonstrations real: a branch that breaks retrieval (for example lowers the relevance floor in the `ci` overlay to 0.0 so a must-abstain question gets an answer, or sets `RETRIEVER=stub`) must turn the job red. Capture the failing run and the gate's messages in `docs/evidence/k07-gate-fail.txt`; this doubles as the material for K9's screenshot.
- Iterate with the real runner. Expect several failed runs (image loading, ingress readiness, PVC vs ConfigMap corpus). Keep a short list of what broke in the spec's implementation notes: it is useful for the engineering notes.
- `workflow_dispatch` trigger is useful for re-runs.

### Out of scope
Pushing images (K8).

### Acceptance criteria
- [ ] The job passes on `dev` (run URL in the log) and `results.fixture.json` is uploaded; recall@5, citation validity and abstention correctness are in the results register.
- [ ] A change that breaks retrieval turns the job red with the gate message; evidence file saved, the broken branch not merged.
- [ ] The job fails closed: if the Job does not complete or the api does not become Ready, the job fails (no `|| true`).
- [ ] Total job time recorded in the results register.
- [ ] `python3 scripts/check_submission.py` section I (CI/CD) shows kind and `needs:` satisfied.
- [ ] `make test && make lint` green.

### Verify
```bash
gh run list --workflow=ci.yml --limit 3
gh run view <id> --log | tail -60
```

### Hand-off
None.

---

## Phase K8: CD: Docker Hub, build-push, deploy (A-10)

**Status:** NOT STARTED · **Branch:** `ci/k08-cd` · **Est:** 3 h · **Priority:** P0 · **Blocked until:** HP-1 (Docker Hub account and secrets)

### Objective
A push to `main` tests the code, builds and pushes three images to Docker Hub tagged with the commit SHA, deploys them to an ephemeral kind cluster, and smoke-tests an answer through the Ingress.

### Read first
Architecture 4.15 (CD diagram and table), requirements R-CD-1..5, R-SUB-2, R-SUB-3; the rubric deductions on CD (publishing job without `needs:`, `:latest`, secrets in logs); K5 `prod` and `ci` overlays; open decision D-013 (Docker Hub names).

### Scope
- `.github/workflows/cd.yml`: trigger `push` to `main` (and `workflow_dispatch` so it can be exercised from `dev` before the final merge, with a repository variable or input that guards pushes to non-`main` refs if you choose to allow it); top-level `permissions: contents: read`; jobs `test` (re-runs `make lint` and `make test`), `build-push` (`needs: test`; Docker login with `secrets.DOCKERHUB_USERNAME` and `secrets.DOCKERHUB_TOKEN`; build and push `rahbar-api`, `rahbar-indexer`, `rahbar-ui` tagged `${{ github.sha }}` only), `deploy` (`needs: build-push`; kind; apply the `ci` overlay with the three images set to the pushed SHA tags via `kustomize edit set image`; wait for the Job and rollout; smoke test through the Ingress: one question must return `answered_from_context: true` with a citation, one must-abstain question must decline; print the evidence).
- Docker Hub: three repositories named per D-013; images public.
- A step that prints the pushed image names and digests into the run summary (`$GITHUB_STEP_SUMMARY`), for the submission.

### Design notes
- HP-1 first: tell Zain the exact commands and wait. Do not create the account, and never read, print or store the token. If the secrets are missing, build everything up to the login step and stop with a clear message.
- Before running on `main`, rehearse from `dev` with `workflow_dispatch` against a throwaway tag prefix if the workflow supports it; every pushed tag must still be a SHA. The submission needs a green run on `main`, which only happens after the `dev` to `main` merge in Phase 15; keep this rehearsal honest about that.
- Pin actions; use `docker/login-action`, `docker/build-push-action` (version-checked as in K6). Never `:latest`, not even as an additional tag.
- Image sizes and the SHA tag go in the results register; the Docker Hub page URL goes in the progress log (not a secret).
- Public images must contain no documents: re-verify with `docker run --rm <image> ls /corpus` (nothing) and that `corpus/raw` is not in the build context.

### Out of scope
Deploying to a real cloud cluster.

### Acceptance criteria
- [ ] `cd.yml` exists with `test` -> `build-push` (`needs: test`) -> `deploy` (`needs: build-push`), a `permissions:` block, pinned actions, SHA tags only.
- [ ] A rehearsal run (from `dev` via `workflow_dispatch`, or the first run after the `dev` to `main` merge) is green: three images visible on Docker Hub tagged with the SHA, and the deploy job's smoke test passed (run URL in the log).
- [ ] No secret value appears in any log or file (`git log -p | grep -iE "dckr_pat|password"` returns nothing; the run logs show `***`).
- [ ] `python3 scripts/check_submission.py` section I has no failure about CD, `needs:`, `permissions:` or `:latest`.
- [ ] `make test && make lint` green.

### Verify
```bash
gh workflow run cd.yml --ref dev      # only if workflow_dispatch is enabled
gh run watch
git log -p | grep -iE "dckr_pat|password" || echo clean
```

### Hand-off
Tell Zain the run URL and the Docker Hub repository links: both go in the submission (R-SUB-2, R-SUB-3).

---

## Phase K9: Branch protection and the gate demonstration (A-11)

**Status:** NOT STARTED · **Branch:** `docs/k09-gate-demo` · **Est:** 1.5 h · **Priority:** P0 · **Blocked until:** HP-2 (Zain approves the settings change)

### Objective
`main` accepts changes only through a pull request with passing required checks and one approval, and the repository contains the evidence: the settings, a merge button blocked by a failing check, and the same pull request green after the fix.

### Read first
Requirements R-CD-6 and the branch-protection rows of the rubric; open decision D-014 (required checks, admin enforcement); K6 and K7 (the job names `lint`, `test`, `manifests`, `build`, `scan`, `e2e-eval`); current state (`gh api repos/Zain-Shykh/RAHBAR-Grounded-RAG/branches/main/protection`): one required approval, no required status checks, admin enforcement off.

### Scope
- **Ask Zain first** and wait (hard stop): "I will set required checks `lint`, `test`, `manifests`, `build`, `scan`, `e2e-eval` and admin enforcement on `main`. This also blocks Zain's own direct merges. OK?" Only then run `gh api -X PUT repos/Zain-Shykh/RAHBAR-Grounded-RAG/branches/main/protection` with the required checks, `strict: true`, one approval, no force push, no deletion. (Admin enforcement: recommended on for the evidence, and tell Zain the one-line command to relax it if it blocks the final merge.)
- The gate demonstration, on `dev` as a throwaway branch: open a PR into `main` from a branch whose change makes `e2e-eval` (or `manifests`) fail; capture the pull request page showing the failed check and the merge button blocked; fix; capture it green. The screenshots need a browser: use the available browser tooling, or give Zain the exact two pages to screenshot and the filenames to save under `docs/evidence/`. Also save `gh pr view`/`gh pr checks` text output, which does not need a browser.
- Settings evidence: `docs/evidence/k09-branch-protection.txt` (the `gh api` JSON output, redacted of nothing sensitive) and a screenshot of the settings page if possible.

### Design notes
- The PR #2 style `dev` to `main` merge in Phase 15 will have to pass these required checks; a red `e2e-eval` blocks the submission, so K7 must be solid first.
- Do not merge the failing demonstration PR. Close it, delete the branch.
- Ahmad is the only second approver today. If he is unavailable, the one-approval rule blocks the final merge: raise this with Zain explicitly (options: temporarily allow admin bypass for that one merge and document it honestly, or have the other instructor account approve). Do not silently weaken the protection.

### Out of scope
Protecting `dev`.

### Acceptance criteria
- [ ] `gh api repos/.../branches/main/protection` shows the six required checks, one required approval, force pushes and deletions disabled; saved in `docs/evidence/k09-branch-protection.txt`.
- [ ] A blocked-merge capture exists (screenshot or `gh pr checks` output plus the "merging is blocked" message) and a green capture of the fixed PR; both saved in `docs/evidence/` with the PR number.
- [ ] D-013 and D-014 updated to DECIDED.
- [ ] `make test && make lint` green.

### Verify
```bash
gh api repos/Zain-Shykh/RAHBAR-Grounded-RAG/branches/main/protection | python3 -m json.tool | head -40
gh pr checks <number>
```

### Hand-off
Tell Zain the exact situation of the one-approval rule for the final merge (Phase 15).

---

## Phase K10: Cluster evidence (A-13)

**Status:** NOT STARTED · **Branch:** `docs/k10-evidence` · **Est:** 3 h · **Priority:** P0

### Objective
`docs/evidence/` holds one plain-text file per demonstration the assignment asks for, each with the command and its real output from the running cluster, and the resource numbers in the manifests are justified by them.

### Read first
Requirements R-RES-2, R-ROL-2, R-ROL-3, R-SEC-4, R-PIN-3, R-CAC-*, R-CD-6; rubric section "evidence"; `docs/FAILURE-ANALYSIS.md` stage C (the pin demonstration on the host); `scripts/check_submission.py` (evidence check: at least five files named for branch protection, blocked merge, `kubectl top`, endpoints, HPA); results of K1 to K9.

### Scope
For each item, run it for real on minikube with the application deployed (apply the dev overlay, `make corpus`, `make apply`, Ollama running), save the command and output, and add a short header line in each file stating the date and the cluster. Files (name them so the checker matches: include the words `top`, `endpoints`, `hpa`, `branch`, `blocked`):
1. `kubectl top pods -n rahbar` while idle and while a cache-miss question runs; then **update the requests and limits in `k8s/base` to match** and justify each in a table in `docs/evidence/resources.md` (what was measured, what was set, why). Include the indexer during a re-index (peak) and show no `OOMKilled`.
2. `kubectl get endpoints api -n rahbar` with 3 or more IPs; scale to 5 (`kubectl scale`, or via the HPA) and show 5, then back.
3. `kubectl get hpa -n rahbar` idle and scaled (from K3).
4. Rolling update: `kubectl set image deploy/api api=rahbar-api:<second tag>` (build a second image whose `/healthz` version string or a log line differs, tag it `v2`), `kubectl rollout status`, a request loop with zero failures, then `kubectl rollout undo`, `rollout history`, and the previous version serving again.
5. Pod deletion while asking: `kubectl delete pod` of one api pod while a request loop runs; show no failed request.
6. Pin mismatch: change `EMBED_MODEL` in the ConfigMap, `kubectl rollout restart deploy/api`, `kubectl get pods` showing `0/1`, `curl /readyz` (via port-forward) showing 503 `embed_pin`, the pod log line with both model names; revert and show `1/1` again. (Reuse the H-14 capture format from `docs/FAILURE-ANALYSIS.md` stage C.)
7. Manual re-index and cache: ask a question (MISS), ask again (HIT, with `X-Cache`), `make index`, wait for the new `index_id`, ask again (MISS), then again (HIT).
8. NetworkPolicy proof (from K4) copied or referenced.
9. Branch protection and blocked merge (from K9) referenced.
10. A final `make eval` through the Ingress against the real corpus in the cluster; compare with `eval/baseline.json`: the gate must pass; record cold answer latency (p50, p95) in the results register. This takes about 15 to 25 minutes of model time; run it once.
- `docs/evidence/README.md`: an index of the files with one line each.

### Design notes
- Plain text only; screenshots go in as PNG next to the matching text file when they exist (UI chat screenshot through `http://rahbar.local`, one with a citation, one abstention).
- If the real `make eval` through the cluster misses the baseline by more than the gate allows, do not edit the baseline: diagnose (cluster config differing from the local run: chunk size, floor, timeout) and report.
- Quote only real output; never edit values.

### Out of scope
New features.

### Acceptance criteria
- [ ] At least ten evidence files exist as listed, each with its command at the top and real output; `docs/evidence/README.md` indexes them.
- [ ] `resources.md` justifies every request and limit with a measured number, and `k8s/base` was updated to match (and `kubeconform` still passes).
- [ ] The rollout, the pod deletion and the endpoints demonstrations show zero failed requests and 3 or more IPs.
- [ ] The pin demonstration shows `0/1`, the 503 body naming `embed_pin`, the log line, and the recovery.
- [ ] The cache sequence shows MISS, HIT, (re-index), MISS, HIT.
- [ ] `make eval` through the Ingress passes the gate; numbers recorded.
- [ ] `python3 scripts/check_submission.py` shows at least five evidence files and no evidence failure.
- [ ] `make test && make lint` green.

### Verify
```bash
ls docs/evidence && python3 scripts/check_submission.py | grep -i evidence
make eval
```

### Hand-off
Tell Zain which screenshots still need a browser (UI chat with a citation and an abstention) if tooling could not capture them.

---

## Phase K11: Platform documents (A-14)

**Status:** NOT STARTED · **Branch:** `docs/k11-platform-docs` · **Est:** 3 h · **Priority:** P0

### Objective
The documents that explain the platform are accurate, specific to this repository and written from the actual deployment: the Kubernetes halves of the engineering notes, the README apply order tested on a clean clone, `SETUP.md`, the ADR 0001 manifest references.

### Read first
Requirements R-ENG-* (all seven questions, their wording), R-DOC-*, the rubric deductions on README order (−5) and generic answers (scores zero); `docs/ENGINEERING-NOTES.md` (the sections marked **AHMAD** for Q1 to Q4 and the Kubernetes half of Q6), `docs/adr/0001-indexer-as-job.md` (drafted, marked for review), `README.md`, `docs/SETUP.md`, `docs/architecture/architecture.md` 4.10, 4.13; the K1 to K10 evidence and results register.

### Scope
- `docs/ENGINEERING-NOTES.md`: replace each **AHMAD** marker with a real answer from the deployment: file and line in `k8s/` for each object (the manifest that prevents a double write, the probe values, the HPA with its measured reading, the memory limit and the `kubectl top` figure, the pin demonstration), real commands and numbers. Mark them "answers written from the actual deployment, by Zain's session". Do not invent: if something was not measured, say so.
- `docs/adr/0001-indexer-as-job.md`: add the manifest lines (Job, CronJob `concurrencyPolicy: Forbid`, the `chroma-ingress` policy, the probes) and the evidence references; keep the status line honest about who reviewed it.
- `README.md`: the apply order (`make cluster`, `make fetch`, `make images`, `make corpus`, `make apply`, wait, `make ask`, `make eval`) matches the `Makefile` exactly (including the `make corpus` target that now exists), the API table is still right, the CI and CD badges point at real workflows, the "project status" section says what is built and what is deferred.
- **Clean-clone test**: clone the repository into a fresh directory (no `.venv`, no `corpus/raw`, no local state), follow the README line by line on the existing minikube (delete the namespace first with `make down`), and fix every step that fails. Record the transcript summary in `docs/evidence/k11-clean-clone.txt`.
- `docs/SETUP.md`: fix whatever was wrong or unclear; note the Ollama host-IP check and `sg docker` behaviour; Linux, WSL2, macOS sections stay consistent.
- `docs/AI-USAGE.md`: an honest entry for every platform phase.
- `docs/architecture/architecture.md` section 9: assumptions A-1, A-4, A-5 and the PVC `fsGroup` item marked verified with the date; `deviations.md` reviewed (every entry has a status and a decision).
- `docs/IMPLEMENTATION_PLAN.md` section 3: H-9, H-10 final state; platform plan marked DONE.

### Design notes
- A generic answer scores zero: every answer cites a real file with a line number or a real command output.
- The HPA answer must say what the CPU-based HPA measured in this deployment (real numbers from K3 and K10) and which signal would scale a generation service better, with the metric already exported by the API (`rahbar_generation_seconds`, in-flight requests via `LLM_MAX_CONCURRENCY`) as the candidate.
- Do not claim anything about CI results that was not seen in a real run.

### Out of scope
UI polish (A-12), new features.

### Acceptance criteria
- [ ] No **AHMAD** marker is left in `docs/ENGINEERING-NOTES.md`; each Q1 to Q4 and the Q6 platform half has file and line references that exist (a script or the tester checks every `k8s/...:NN` reference resolves).
- [ ] The clean-clone transcript exists and every README step worked, or the README was fixed until it did.
- [ ] `python3 scripts/check_submission.py` shows no failure in sections G, I, J, and "structure" for evidence and workflows (what remains must be listed and explained).
- [ ] `docs/architecture/deviations.md` has no entry that is OPEN without a decision.
- [ ] `make test && make lint` green.

### Verify
```bash
python3 scripts/check_submission.py | tail -40
grep -n "AHMAD" docs/ENGINEERING-NOTES.md || echo "no markers left"
```

### Hand-off
HP-5: tell Zain what Ahmad still owns (A-00 and A-12) and what he should review (ADR 0001, the engineering-notes answers).

---

## 6. How this plan meets the RAG plan's Phase 15

[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) lists **Phase 15, integration support and final verification**, as the last phase. It was written when two people were building two lanes in parallel, so it said "integration support": make the lanes meet. With this plan the integration happens inside K2 (the real index in the cluster, milestone I-2), K7 (the fixture gate in CI, milestone I-3 for CI), K10 (the real corpus evaluated through the Ingress, I-3 on the cluster) and K11 (the clean clone). What remains of Phase 15 after K11 is only the final verification, in this order:

1. `make test && make lint && make check`, every remaining warning explained.
2. No leftover placeholder marker (`grep -rn STARTER-TODO --exclude-dir=.venv .`) and no `NotImplementedError`.
3. Secret scan of the Git history; no `corpus/raw` content committed.
4. Deviation log and `OPEN_DECISIONS.md` reviewed: nothing open that affects the delivered system.
5. Baselines consistent with the shipped config; every number in `PIPELINE.md` matches the committed results.
6. Tick `docs/rubric_checklist.md` with evidence for every box that is true.
7. The `dev` to `main` pull request (all required checks green, the one approval handled, see K9), the green `cd.yml` run on `main`, and the submission list: repository URL, the `cd.yml` run URL, the Docker Hub links, `eval/results.json` and `eval/baseline.json`.
8. Both people can explain every part: a short walkthrough note per lane.

Order of work from now: **K1 to K11, then Phase 15.** Platform first because nothing else can be proven without a running cluster and passing pipelines; Phase 15 last because it verifies the whole.

## 7. Schedule (from Thursday 5 Nov, 22:00 PKT)

| Window | Phases | Why this order |
| --- | --- | --- |
| Thu night | K1, K2 | Cluster up and the real index in it (largest unknowns: A-1, A-4, A-5, `fsGroup`, Job memory) |
| Fri | K3, K4, K5 | Ingress, HPA, policy and overlays; K5 unlocks CI |
| Fri night to Sat | K6, K7 | CI: five jobs, then e2e-eval (iterating against real runners takes time) |
| Sat | K8 (needs HP-1 early), K9 | CD and the gate; the `dev` to `main` PR should be opened Saturday night so CD has a day to be fixed |
| Sat night to Sun morning | K10, K11 | Evidence and documents, written from the finished system |
| Sun 14:00 | freeze; Phase 15 | Final verification and submission by 18:00 |

**Cut line if time runs out (in this order):** K10 items 4 and 5 (keep the rest), K6 Trivy tuning (keep the job, document what was left), K5 `prod` overlay detail (keep it building), K11 clean-clone (keep the README order tested once). **Never cut:** K2 (real index in the cluster), K4 (policy proof), K7 (the gate), K8 (CD green and Docker Hub), K9 (branch protection evidence), K10 evidence files.

## 8. Risks and contingencies

| Risk | Likelihood | If it happens |
| --- | --- | --- |
| Ollama unreachable from pods (A-1) | Medium | Check the `host.minikube.internal` IP and `OLLAMA_HOST=0.0.0.0`; allow the node IP in the `ipBlock`; log a deviation. |
| `kubectl cp` or PVC permissions fail (A-4, `fsGroup`) | Medium | Use an alpine/busybox helper with a matching `fsGroup`; fall back to an init container that fetches the documents (D-003 option) only with a deviation entry. |
| Indexer Job slower in the cluster than on the host (9 min 40 s) | Medium | `activeDeadlineSeconds` generous; limit 2Gi; run it once and keep the index; re-index only for the demonstration. |
| CPU contention: minikube, Ollama and a browser on one laptop | High | `minikube stop` when idle; stop Ollama when not needed (`pkill -x ollama`); run one heavy job at a time. |
| e2e-eval flaky or slow on kind | Medium | Fixtures only; single node; pinned manifests; job timeout; dump logs on failure. |
| Docker Hub not ready by Saturday | Low | HP-1 is on the dashboard; ask Zain on Thursday night. |
| One-approval rule blocks the final merge (Ahmad unavailable) | Medium | Decide with Zain in K9: temporary admin bypass for the one merge, documented honestly, or a second approver. Do not weaken the protection silently. |
| Trivy finds HIGH findings with a fix in a base image | Medium | Bump the pinned base tag (re-run tests and the baseline checks), record it. |
| Actions pinned to a version that does not exist | Low | Verify each tag with `gh api` before pinning. |
| Ahmad pushes his own version of the same files | Low | Hard stop: report, then merge his work into the plan; do not overwrite. |

## 9. Definition of done (any phase)

1. It does what its acceptance criteria say and you ran it on the real cluster (or the real Actions runner).
2. The evidence file exists with the command and its real output.
3. `kustomize build ... | kubeconform -strict` passes for every overlay that changed; `make test && make lint` pass.
4. Matches the architecture, or a `deviations.md` entry exists.
5. Docs and `AI-USAGE.md` updated; the status in this file, the dashboard and Current focus updated in the same PR.
6. Independent tester passed; PR merged into `dev`.
