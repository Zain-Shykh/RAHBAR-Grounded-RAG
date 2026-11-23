#!/usr/bin/env bash
# R9 rehearsal (R3-S-F5): the commands in order. Run by hand step by step (one LLM job at a time); every step's output
# is saved in docs/evidence/a3/r9-*.txt. Needs: cluster up, live api on `rahbar`, `make candidate` done for both collections.
set -u
NS=rahbar
# request loop inside the cluster during a rolling update: retrieval only (no model), one line per request
loop() { kubectl exec -n $NS deploy/ui -- sh -c 'while true; do printf "%s " "$(date -u +%T)"; curl -s -o /tmp/o -w "%{http_code} " -X POST http://api:8000/api/retrieve -H "Content-Type: application/json" -d "{\"question\":\"What CGPA puts a student on academic warning?\",\"k\":1}"; sed -n "s/.*\"index_id\": *\"\([^\"]*\)\".*/\1/p" /tmp/o; echo; sleep 0.5; done'; }
case "${1:-}" in
  # 1. the gate STOPS a candidate: re-apply the gate to the saved 100/0 result (no model calls); the Job ends Failed, nothing is released
  gate-fail) make gate-config; make eval-job LABEL=cand-100-0 GATE_ONLY=/results/suite-20261121T041138Z-cand-100-0.json ;;
  refuse)    make release COLLECTION=rahbar_bad ;;                                   # refused: its recorded gate verdict is FAIL
  # 2. a candidate the gate PASSED is released by a rolling update
  gate-pass) make gate-config; make eval-job LABEL=cand-600-100 GATE_ONLY=/results/suite-20261121T072649Z-cand-600-100.json ;;
  release)   make release COLLECTION=rahbar_c600 ;;                                  # the guard allows it (verdict PASS)
  # 3. a separate rollback DRILL: a release that bypasses the gate on purpose, then kubectl rollout undo
  drill)     make release COLLECTION=rahbar_drill FORCE=1 ;;
  undo)      make rollback ;;
  loop)      loop ;;
  *) echo "usage: $0 gate-fail|refuse|gate-pass|release|drill|undo|loop"; exit 2 ;;
esac
