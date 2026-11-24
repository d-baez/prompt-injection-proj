#!/usr/bin/env bash
# Live view of the Ollama marker sweeps: overall progress per sweep and the
# tqdm bar of the experiment currently running. Ctrl-C to stop.
# Usage: scripts/watch_sweep.sh [final|llama] [refresh_seconds]
#   final: watch the 100-case final sweeps (both models log to log/final100_runs.log)
#   llama: watch the llama3.1:8b 100-case sweep (counted from result/ folders)
cd "$(dirname "$0")/.." || exit 1
final=0
llama=0
if [[ "$1" == "final" ]]; then final=1; shift; fi
if [[ "$1" == "llama" ]]; then llama=1; shift; fi
refresh="${1:-5}"

while true; do
  clear
  date
  if (( llama )); then
    pat="ollama_llama3.1-8b_sst2final_injected_marker_100_"
    done_n=$(ls result/${pat}*/experiment.json 2>/dev/null | wc -l | tr -d ' ')
    current=$(ls -t log/${pat}*.txt 2>/dev/null | head -1)
    echo
    echo "[llama3.1-8b] $done_n/50 completed"
    if [[ -n "$current" ]]; then
      name=$(basename "$current" .txt)
      [[ -f "result/$name/experiment.json" ]] || echo "  running: ${name#${pat}}"
      tr '\r' '\n' < "$current" | grep -o "Querying:.*sample[^]]*]" | tail -1 | sed 's/^/  /'
    fi
    sleep "$refresh"
    continue
  fi
  for model in mistral qwen3-8b; do
    echo
    if (( final )); then
      runner="log/final100_runs.log"
      pat="ollama_${model}"; [[ "$model" == mistral ]] && pat="ollama_mistral_final"
      tag="_100_"
    else
      runner="log/ollama_marker_${model}_runner.log"
      pat="ollama_${model}"
      tag="_20_"
    fi
    if [[ ! -f "$runner" ]] || ! grep -q "Started ${pat}_" "$runner"; then
      echo "[$model] not started yet"
      continue
    fi
    done_n=$(grep -c "Completed ${pat}_" "$runner")
    fail_n=$(grep -E "${pat}_" "$runner" | grep -ciE "failed|Traceback")
    current=$(grep "Started ${pat}_" "$runner" | tail -1 | sed -E 's/.*Started ([^ ]+).*/\1/')
    echo "[$model] $done_n/50 completed, $fail_n failure lines"
    if [[ -n "$current" ]] && ! grep -q "Completed $current" "$runner"; then
      echo "  running: ${current#*${tag}}"
      # Last tqdm bar from the experiment log (tqdm redraws with \r).
      tr '\r' '\n' < "log/${current}.txt" | grep -o "Querying:.*sample[^]]*]" | tail -1 | sed 's/^/  /'
    fi
  done
  sleep "$refresh"
done
