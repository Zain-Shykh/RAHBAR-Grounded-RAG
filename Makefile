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
# Local data services (phase 2). Tags verified in docs/specs/phase-02-local-services.md.
CHROMA_IMAGE ?= chromadb/chroma:1.0.12
REDIS_IMAGE ?= redis/redis-stack-server:7.4.0-v8

.DEFAULT_GOAL := help
.PHONY: help install test lint dev dev-services dev-services-stop dev-services-reset cluster images apply secret index ask fetch eval eval-fixtures check

help: ## list the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

install: ## create .venv and install the api, indexer and tool dependencies
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -r api/requirements-dev.txt -r indexer/requirements-dev.txt

test: ## run the api and indexer tests (stubs only: no cluster, no model, no network)
	cd api && $(BIN)/pytest -q
	cd indexer && $(BIN)/pytest -q

lint: ## ruff and mypy over everything in Python
	$(BIN)/ruff check api indexer eval corpus scripts/verify_services.py
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

apply: ## apply the dev overlay (needs yours: manifests)
	kubectl apply -k k8s/overlays/dev

secret: ## create the LLM key Secret from the LLM_API_KEY variable; never from a file
	@test -n "$$LLM_API_KEY" || { echo "export LLM_API_KEY=... first"; exit 1; }
	kubectl create secret generic rahbar-secret -n $(NS) \
	  --from-literal=LLM_API_KEY="$$LLM_API_KEY" --dry-run=client -o yaml | kubectl apply -f -

index: ## run the indexer once, from the CronJob's template (needs yours: CronJob reindex)
	kubectl create job --from=cronjob/reindex reindex-$$(date +%s) -n $(NS)
	@echo "watch it with: kubectl get jobs -n $(NS) -w"

ask: ## ask through the Ingress: make ask Q="What CGPA puts a student on academic warning?"
	@curl -s -X POST "http://$(INGRESS_IP)/api/ask" -H "Host: $(HOST)" \
	  -H 'Content-Type: application/json' -d "$$(Q="$(Q)" $(PY) -c 'import json,os; print(json.dumps({"question": os.environ["Q"]}))')" \
	  | $(PY) -m json.tool

fetch: ## download the documents listed in corpus/sources.yaml
	$(BIN)/python corpus/fetch.py

eval: ## score eval/golden.yaml through the Ingress and apply the CI gate
	$(BIN)/python eval/run_eval.py --api "http://$(INGRESS_IP)" --host $(HOST)

eval-fixtures: ## score the CI fixture golden set against a local `make dev`
	$(BIN)/python eval/run_eval.py --api http://localhost:8000 --golden eval/fixtures/golden.fixture.yaml --out /tmp/rahbar-fixture-results.json

check: ## run the submission checker
	$(PY) scripts/check_submission.py
