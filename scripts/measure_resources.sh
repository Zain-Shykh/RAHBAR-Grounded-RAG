#!/usr/bin/env bash
# Sample `kubectl top pod` every 5 s (R3-F5-1). Usage: scripts/measure_resources.sh <seconds> [namespace] > samples.txt
# Output lines: <epoch> <pod> <cpu_millicores> <mem_Mi>. Summarise with scripts/summarize_resources.py.
set -u
secs=${1:?seconds}; ns=${2:-rahbar}; end=$(( $(date +%s) + secs ))
while [ "$(date +%s)" -lt "$end" ]; do
  now=$(date +%s)
  kubectl top pod -n "$ns" --no-headers 2>/dev/null | awk -v t="$now" '{gsub(/m/,"",$2); gsub(/Mi/,"",$3); print t, $1, $2, $3}'
  sleep 5
done
