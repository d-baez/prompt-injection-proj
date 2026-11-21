#!/usr/bin/env bash
# Live view of the Ollama marker sweeps: overall progress per sweep and the
# tqdm bar of the experiment currently running. Ctrl-C to stop.
# Usage: scripts/watch_sweep.sh [refresh_seconds]
cd "$(dirname "$0")/.." || exit 1
refresh="${1:-5}"

while true; do
  clear
  date
  for model in mistral qwen3-8b; do
    runner="log/ollama_marker_${model}_runner.log"
    echo
    if [[ ! -f "$runner" ]]; then
      echo "[$model] not started yet"
      continue
    fi
    done_n=$(grep -c "Completed" "$runner")
    fail_n=$(grep -ciE "failed|Traceback" "$runner")
    current=$(grep "Started" "$runner" | tail -1 | sed -E 's/.*Started ([^ ]+).*/\1/')
    echo "[$model] $done_n/50 completed, $fail_n failure lines"
    if [[ -n "$current" ]] && ! grep -q "Completed $current" "$runner"; then
      echo "  running: ${current#*_20_}"
      # Last tqdm bar from the experiment log (tqdm redraws with \r).
      tr '\r' '\n' < "log/${current}.txt" | grep -o "Querying:.*sample[^]]*]" | tail -1 | sed 's/^/  /'
    fi
  done
  sleep "$refresh"
done
