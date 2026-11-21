#!/usr/bin/env bash
# R9 rehearsal (R3-S-F5): the commands in order. Run by hand step by step (one LLM job at a time); every step's output
# is saved in docs/evidence/a3/r9-*.txt. Needs: cluster up, live api on `rahbar`, `make candidate` done for both collections.
set -u
NS=rahbar
# request loop inside the cluster during a rolling update: retrieval only (no model), one line per request
loop() { kubectl exec -n $NS deploy/ui -- sh -c 'while true; do printf "%s " "$(date -u +%T)"; curl -s -o /tmp/o -w "%{http_code} " -X POST http://api:8000/api/retrieve -H "Content-Type: application/json" -d "{\"question\":\"What CGPA puts a student on academic warning?\",\"k\":1}"; sed -n "s/.*\"index_id\": *\"\([^\"]*\)\".*/\1/p" /tmp/o; echo; sleep 0.5; done'; }
case "${1:-}" in
  gate-fail) make eval-job LABEL=cand-bad GATE_ONLY=/results/<result>.json ;;       # Job Failed, no release
  release)   make release COLLECTION=rahbar_cand ;;                                  # gate passed first
  bad)       make release COLLECTION=rahbar_bad ;;                                   # forced, no gate
  undo)      make rollback ;;
  loop)      loop ;;
  *) echo "usage: $0 gate-fail|release|bad|undo|loop"; exit 2 ;;
esac
