# RAHBAR starter Makefile. `make` or `make help` lists the targets.
# Targets marked (needs yours) work once you have written the Dockerfiles or manifests.

SHELL := /bin/bash
NS ?= rahbar
TAG ?= dev
PY ?= python3
VENV ?= .venv
BIN := $(abspath $(VENV))/bin
# The Ingress address. On Linux this is the minikube IP. On macOS or Windows with the
# docker driver, run `minikube tunnel` in another terminal and use INGRESS_IP=127.0.0.1.
INGRESS_IP ?= $(shell minikube ip 2>/dev/null)
HOST ?= rahbar.local
CORPUS_SRC ?= corpus/raw
# Local data services (phase 2). Tags verified in docs/specs/phase-02-local-services.md.
CHROMA_IMAGE ?= chromadb/chroma:1.0.12
REDIS_IMAGE ?= redis/redis-stack-server:7.4.0-v8

.DEFAULT_GOAL := help
.PHONY: eval-job eval-ctx eval-image gate-config suite suite-twice candidate release rollback ingest-batch inbox-delete restore lake-ls results-pull traces-pull baseline resources help install test lint dev dev-services dev-services-stop dev-services-reset cluster images corpus apply down secret index ask fetch eval eval-fixtures check manifests

help: ## list the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

install: ## create .venv and install the api, indexer and tool dependencies
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -r api/requirements-dev.txt -r indexer/requirements-dev.txt

test: ## run the api, indexer and eval tests (stubs only: no cluster, no model, no network)
	cd api && $(BIN)/pytest -q
	cd indexer && $(BIN)/pytest -q
	cd eval && $(BIN)/pytest -q

lint: ## ruff and mypy over everything in Python
	$(BIN)/ruff check api indexer eval corpus scripts/verify_services.py scripts/verify_ollama.py scripts/check_golden_extract.py scripts/chunk_report.py scripts/check_index.py scripts/live_check_phase10.py scripts/live_check_phase11.py scripts/calibrate_cache.py scripts/make_batch_b.py scripts/enrich_manifest.py scripts/calibrate_neardup.py scripts/build_golden_jsonl.py scripts/trace_tool.py scripts/trace_report.py scripts/add_batch.py scripts/check_registry.py
	cd api && $(BIN)/mypy app
	cd indexer && $(BIN)/mypy pipeline

dev: ## run the API with stubs on http://localhost:8000, serving the chat UI too
	cd api && SERVE_UI_DIR=../ui RETRIEVER=stub LLM_PROVIDER=stub $(BIN)/uvicorn app.main:app --reload --port 8000

dev-services: ## start Chroma :8100 and Redis Stack :6379 (until re-login: sg docker -c "make dev-services")
	-@docker rm -f rahbar-dev-chroma rahbar-dev-redis >/dev/null 2>&1
	docker run -d --name rahbar-dev-chroma -p 127.0.0.1:8100:8000 -v rahbar-dev-chroma:/data \
	  -e IS_PERSISTENT=TRUE -e PERSIST_DIRECTORY=/data -e ANONYMIZED_TELEMETRY=FALSE $(CHROMA_IMAGE)
	docker run -d --name rahbar-dev-redis -p 127.0.0.1:6379:6379 -v rahbar-dev-redis:/data \
	  -e REDIS_ARGS="--appendonly yes" $(REDIS_IMAGE)
	@for i in $$(seq 30); do \
	  curl -sf http://localhost:8100/api/v2/heartbeat >/dev/null && docker exec rahbar-dev-redis redis-cli ping 2>/dev/null | grep -q PONG && break; \
	  [ $$i = 30 ] && { echo "services did not become ready in 30 s"; exit 1; }; sleep 1; done
	@echo "ready. export CHROMA_HOST=localhost CHROMA_PORT=8100 REDIS_HOST=localhost REDIS_PORT=6379"

dev-services-stop: ## stop and remove the two dev containers (data volumes are kept)
	-docker rm -f rahbar-dev-chroma rahbar-dev-redis

dev-services-reset: dev-services-stop ## also delete the dev data volumes
	-docker volume rm rahbar-dev-chroma rahbar-dev-redis

manifests: ## build and kubeconform-validate the dev, ci and prod overlays
	@set -e; for o in dev ci prod; do echo "== $$o"; kustomize build --load-restrictor LoadRestrictionsNone k8s/overlays/$$o > /tmp/rahbar-$$o.yaml; kubeconform -strict -summary < /tmp/rahbar-$$o.yaml; done
	kubeconform -strict -summary k8s/eval-job.yaml k8s/trace-report-job.yaml k8s/candidate/indexer-job.yaml
	kustomize build k8s/candidate | kubeconform -strict -summary

cluster: ## start minikube with Calico, then enable metrics-server and ingress
	minikube start --driver=docker --cni=calico --memory=6144 --cpus=4
	minikube addons enable metrics-server
	minikube addons enable ingress

images: ## build the three images and load them into minikube (needs yours: Dockerfiles)
	docker build -t rahbar-api:$(TAG) api
	docker build -t rahbar-indexer:$(TAG) indexer
	docker build -t rahbar-ui:$(TAG) ui
	minikube image load rahbar-api:$(TAG)
	minikube image load rahbar-indexer:$(TAG)
	minikube image load rahbar-ui:$(TAG)
	$(MAKE) eval-image TAG=$(TAG)

corpus: ## copy $(CORPUS_SRC) (default corpus/raw) into the corpus-data PVC (namespace, PVC, helper pod, kubectl cp)
	kubectl apply -f k8s/base/namespace.yaml -f k8s/base/corpus-pvc.yaml
	kubectl apply -f k8s/base/serviceaccounts.yaml
	kubectl delete pod corpus-loader -n $(NS) --ignore-not-found
	kubectl apply -f k8s/tools/corpus-loader.yaml
	kubectl wait --for=condition=Ready pod/corpus-loader -n $(NS) --timeout=120s
	kubectl cp $(CORPUS_SRC)/. $(NS)/corpus-loader:/corpus
	kubectl cp $(CORPUS_SRC)/../MANIFEST.md $(NS)/corpus-loader:/corpus/MANIFEST.md
	kubectl exec -n $(NS) corpus-loader -- ls -l /corpus
	kubectl delete pod corpus-loader -n $(NS) --wait=false

apply: ## apply the dev overlay; a finished indexer Job is deleted first (immutable template), so it runs again
	kubectl delete job indexer -n $(NS) --ignore-not-found
	kubectl apply -k k8s/overlays/dev

down: ## delete the namespace and everything in it (PVCs too)
	kubectl delete namespace $(NS) --ignore-not-found

secret: ## create the LLM key Secret from the LLM_API_KEY variable; never from a file
	@test -n "$$LLM_API_KEY" || { echo "export LLM_API_KEY=... first"; exit 1; }
	kubectl create secret generic rahbar-secret -n $(NS) \
	  --from-literal=LLM_API_KEY="$$LLM_API_KEY" --dry-run=client -o yaml | kubectl apply -f -

index: ## run the indexer once, from the CronJob's template (needs yours: CronJob reindex)
	kubectl create job --from=cronjob/reindex reindex-$$(date +%s) -n $(NS)
	@echo "watch it with: kubectl get jobs -n $(NS) -w"

ask: ## ask through the Ingress: make ask Q="What CGPA puts a student on academic warning?"
	@test -n "$(INGRESS_IP)" || { echo "INGRESS_IP is empty: 'minikube ip' failed. Docker permission? Run: sg docker -c 'make $@ ...'. macOS/Windows: minikube tunnel and INGRESS_IP=127.0.0.1"; exit 1; }
	@curl -s -X POST "http://$(INGRESS_IP)/api/ask" -H "Host: $(HOST)" \
	  -H 'Content-Type: application/json' -d "$$(Q="$(Q)" $(PY) -c 'import json,os; print(json.dumps({"question": os.environ["Q"]}))')" \
	  | $(PY) -m json.tool

fetch: ## download the documents listed in corpus/sources.yaml
	$(BIN)/python corpus/fetch.py

eval: ## score eval/golden.yaml through the Ingress and apply the CI gate
	@test -n "$(INGRESS_IP)" || { echo "INGRESS_IP is empty: 'minikube ip' failed. Docker permission? Run: sg docker -c 'make $@ ...'. macOS/Windows: minikube tunnel and INGRESS_IP=127.0.0.1"; exit 1; }
	$(BIN)/python eval/run_eval.py --api "http://$(INGRESS_IP)" --host $(HOST)

eval-fixtures: ## score the CI fixture golden set against a local `make dev`
	$(BIN)/python eval/run_eval.py --api http://localhost:8000 --golden eval/fixtures/golden.fixture.yaml --out /tmp/rahbar-fixture-results.json

check: ## run the submission checker
	$(PY) scripts/check_submission.py

# ---- Assignment 03 (RAGOps): see k8s/README.md for the order ---------------------------------------------------
eval-ctx: ## stage the small build context of rahbar-eval (eval/ plus scripts/)
	rm -rf /tmp/rahbar-eval-ctx && mkdir -p /tmp/rahbar-eval-ctx/scripts
	cp -r eval /tmp/rahbar-eval-ctx/eval && rm -rf /tmp/rahbar-eval-ctx/eval/results /tmp/rahbar-eval-ctx/eval/tests /tmp/rahbar-eval-ctx/eval/tuning /tmp/rahbar-eval-ctx/eval/__pycache__
	cp scripts/trace_report.py scripts/trace_tool.py /tmp/rahbar-eval-ctx/scripts/
	cp eval/Dockerfile /tmp/rahbar-eval-ctx/Dockerfile

eval-image: eval-ctx ## build rahbar-eval from the staged context and load it into minikube
	docker build -t rahbar-eval:$(TAG) /tmp/rahbar-eval-ctx
	minikube image load rahbar-eval:$(TAG)

gate-config: ## create or update ConfigMap rahbar-gate from eval/gate.yaml (edit a threshold, run this, re-run the eval Job)
	kubectl create configmap rahbar-gate -n $(NS) --from-file=gate.yaml=eval/gate.yaml --dry-run=client -o yaml | kubectl apply -f -

suite: ## the whole Part B suite against API_URL (default: local make dev), one timestamped result in eval/results/
	PYTHONPATH=. $(BIN)/python -m eval.suite.run_suite --api $${API_URL:-http://localhost:8000} --label $${LABEL:-run} --subset $${SUBSET:-A}

suite-twice: ## run the suite twice and write the per-metric difference (R3-B-8)
	PYTHONPATH=. $(BIN)/python -m eval.suite.run_suite --api $${API_URL:-http://localhost:8000} --label $${LABEL:-run}-1 --subset $${SUBSET:-A}
	PYTHONPATH=. $(BIN)/python -m eval.suite.run_suite --api $${API_URL:-http://localhost:8000} --label $${LABEL:-run}-2 --subset $${SUBSET:-A}
	PYTHONPATH=. $(BIN)/python -m eval.suite.stochasticity $$(ls -t eval/results/suite-*-$${LABEL:-run}-1.json | head -1) $$(ls -t eval/results/suite-*-$${LABEL:-run}-2.json | head -1)

ingest-batch: ## ingest a batch of documents: make ingest-batch BATCH=corpus/batch_b  (copies to corpus-data, runs the reindex Job)
	test -n "$(BATCH)"
	kubectl apply -f k8s/base/namespace.yaml -f k8s/base/corpus-pvc.yaml
	kubectl delete pod corpus-loader -n $(NS) --ignore-not-found
	kubectl apply -f k8s/tools/corpus-loader.yaml
	kubectl wait --for=condition=Ready pod/corpus-loader -n $(NS) --timeout=120s
	kubectl exec -n $(NS) corpus-loader -- sh -c 'cat /corpus/_index.json 2>/dev/null || true' > /tmp/rahbar-existing-index.json
	rm -rf /tmp/rahbar-merged && $(BIN)/python scripts/add_batch.py $(BATCH) /tmp/rahbar-existing-index.json /tmp/rahbar-merged
	kubectl cp /tmp/rahbar-merged/. $(NS)/corpus-loader:/corpus
	kubectl delete pod corpus-loader -n $(NS) --wait=false
	kubectl create job --from=cronjob/reindex ingest-$$(date +%s) -n $(NS)

inbox-delete: ## delete a document from the inbox (file and manifest entry); the next `make index` removes its chunks: make inbox-delete FILE=b12-sports-facilities-2026.md
	test -n "$(FILE)"
	kubectl delete pod corpus-loader -n $(NS) --ignore-not-found
	kubectl apply -f k8s/tools/corpus-loader.yaml
	kubectl wait --for=condition=Ready pod/corpus-loader -n $(NS) --timeout=120s
	kubectl exec -n $(NS) corpus-loader -- rm -f /corpus/$(FILE)
	kubectl exec -n $(NS) corpus-loader -- cat /corpus/_index.json > /tmp/rahbar-index.json
	$(BIN)/python scripts/manifest_remove.py /tmp/rahbar-index.json $(FILE)
	kubectl cp /tmp/rahbar-index.json $(NS)/corpus-loader:/corpus/_index.json
	kubectl delete pod corpus-loader -n $(NS) --wait=false

restore: ## roll back: make restore SOURCE=<older file> SUPERSEDE=<newer file> (one-off Job, zero embeddings)
	test -n "$(SOURCE)"
	kubectl delete job restore -n $(NS) --ignore-not-found
	sed 's/RESTORE_SOURCE/$(SOURCE)/; s/RESTORE_SUPERSEDE/$(SUPERSEDE)/' k8s/tools/restore-job.yaml | kubectl apply -f -
	kubectl wait --for=condition=complete job/restore -n $(NS) --timeout=1800s
	kubectl logs job/restore -n $(NS)

lake-ls: ## list the lake volume (registry, quarantine, archive, reports) through a throw-away pod
	kubectl delete pod lake-viewer -n $(NS) --ignore-not-found
	sed 's/CLAIM/lake-data/' k8s/tools/volume-viewer.yaml | sed 's/NAME/lake-viewer/' | kubectl apply -f -
	kubectl wait --for=condition=Ready pod/lake-viewer -n $(NS) --timeout=120s
	kubectl exec -n $(NS) lake-viewer -- find /data -type f
	kubectl delete pod lake-viewer -n $(NS) --wait=false

results-pull: ## copy the eval Job's result files from the eval-results volume into eval/results/
	kubectl delete pod results-viewer -n $(NS) --ignore-not-found
	sed 's/CLAIM/eval-results/' k8s/tools/volume-viewer.yaml | sed 's/NAME/results-viewer/' | kubectl apply -f -
	kubectl wait --for=condition=Ready pod/results-viewer -n $(NS) --timeout=120s
	kubectl cp $(NS)/results-viewer:/data eval/results/cluster
	kubectl delete pod results-viewer -n $(NS) --wait=false

traces-pull: ## copy the trace files from the traces-data volume into traces/cluster/
	kubectl delete pod traces-viewer -n $(NS) --ignore-not-found
	sed 's/CLAIM/traces-data/' k8s/tools/volume-viewer.yaml | sed 's/NAME/traces-viewer/' | kubectl apply -f -
	kubectl wait --for=condition=Ready pod/traces-viewer -n $(NS) --timeout=120s
	kubectl cp $(NS)/traces-viewer:/data traces/cluster
	kubectl delete pod traces-viewer -n $(NS) --wait=false

candidate: ## build a candidate collection and point api-candidate at it: make candidate CHUNK=300 OVERLAP=50 [COLL=rahbar_cand]
	kubectl delete job indexer-candidate -n $(NS) --ignore-not-found
	sed 's/CANDIDATE_CHUNK_SIZE/$(CHUNK)/; s/CANDIDATE_CHUNK_OVERLAP/$(OVERLAP)/; s/CANDIDATE_COLLECTION/$(or $(COLL),rahbar_cand)/' k8s/candidate/indexer-job.yaml | kubectl apply -f -
	kubectl wait --for=condition=complete job/indexer-candidate -n $(NS) --timeout=3000s
	$(MAKE) candidate-serve COLL=$(or $(COLL),rahbar_cand)

candidate-serve: ## point api-candidate at an existing collection: make candidate-serve COLL=rahbar_cand
	kubectl kustomize k8s/candidate | sed 's/CANDIDATE_COLLECTION/$(or $(COLL),rahbar_cand)/' | kubectl apply -f -
	kubectl rollout restart deployment/api-candidate -n $(NS)
	kubectl rollout status deployment/api-candidate -n $(NS) --timeout=300s

release: ## release the candidate collection to the live api by a rolling update (only after the gate passed)
	kubectl set env deployment/api -n $(NS) CHROMA_COLLECTION=$(COLLECTION)
	kubectl rollout status deployment/api -n $(NS) --timeout=600s

rollback: ## reverse the last release
	kubectl rollout undo deployment/api -n $(NS)
	kubectl rollout status deployment/api -n $(NS) --timeout=600s

eval-job: ## run the eval Job: make eval-job [API=http://api:8000] [LABEL=live] [SUBSET=A|B|all] [SET_BASELINE=false] [GATE_ONLY=/results/<file>.json]
	kubectl delete job eval -n $(NS) --ignore-not-found
	sed 's|{name: API_URL, value: "http://api:8000"}|{name: API_URL, value: "$(or $(API),http://api:8000)"}|; s|{name: RUN_LABEL, value: "live"}|{name: RUN_LABEL, value: "$(or $(LABEL),live)"}|; s|{name: SUBSET, value: "A"}|{name: SUBSET, value: "$(or $(SUBSET),A)"}|; s|{name: SET_BASELINE, value: "false"}|{name: SET_BASELINE, value: "$(or $(SET_BASELINE),false)"}|; s|{name: GATE_ONLY, value: ""}|{name: GATE_ONLY, value: "$(GATE_ONLY)"}|' k8s/eval-job.yaml | kubectl apply -f -
