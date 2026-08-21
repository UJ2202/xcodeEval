#!/bin/bash
# Full PS + CT evaluation for all 6 models in parallel
# Each model gets its own execeval container on a dedicated port
# Logs go to benchmark/{model}/logs/
# Results go to benchmark/{model}/ps/reproduce_1/ and benchmark/{model}/ct_compact_small/eval_.../

XCODEEVAL=/home/ujjwal.tiwari/ace/benchmarks/xcodeEval
BENCH=$XCODEEVAL/benchmark
EVAL_PS=$XCODEEVAL/evaluation/program_synthesis/eval_program_synthesis.py
EVAL_CT=$XCODEEVAL/evaluation/code_translation/eval_code_translation.py
VENV=/home/ujjwal.tiwari/xcodeeval-env/bin/activate

declare -A PORTS
PORTS["gpt4o"]=5000
PORTS["nemotron-550b"]=5001
PORTS["laguna-nvfp4"]=5002
PORTS["qwen-nvfp4"]=5003
PORTS["claude-opus-5"]=5004
PORTS["claude-sonnet-5"]=5005

MODELS=("gpt4o" "nemotron-550b" "laguna-nvfp4" "qwen-nvfp4" "claude-opus-5" "claude-sonnet-5")
if [ $# -gt 0 ]; then
  MODELS=("$@")
fi

run_model() {
  MODEL=$1
  PORT=${PORTS[$MODEL]}
  DUMP_FOLDER=$XCODEEVAL/eval_runs/$MODEL
  LOG_DIR=$BENCH/$MODEL/logs
  mkdir -p "$LOG_DIR"

  source $VENV
  export DUMP_FOLDER=$DUMP_FOLDER
  export EXECEVAL_URL=http://localhost:$PORT

  PS_DIR="$DUMP_FOLDER/oai/prog_synthesis_n_sample_20"
  CT_DIR="$DUMP_FOLDER/oai/code_translation_n_sample_20/compact_small"

  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$MODEL] Starting on port $PORT"

  # --- Program Synthesis ---
  PS_COUNT=$(ls "$PS_DIR"/*.json 2>/dev/null | wc -l)
  if [ "$PS_COUNT" -gt 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$MODEL] Running PS eval ($PS_COUNT files)"
    python3 $EVAL_PS > "$LOG_DIR/eval_ps.log" 2>&1
    PS_EXIT=$?
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$MODEL] PS eval done (exit=$PS_EXIT)"
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$MODEL] SKIP PS (no data)"
  fi

  # --- Code Translation ---
  CT_COUNT=$(ls "$CT_DIR"/*.json 2>/dev/null | wc -l)
  if [ "$CT_COUNT" -gt 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$MODEL] Running CT eval ($CT_COUNT files)"
    python3 $EVAL_CT > "$LOG_DIR/eval_ct.log" 2>&1
    CT_EXIT=$?
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$MODEL] CT eval done (exit=$CT_EXIT)"
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$MODEL] SKIP CT (no data)"
  fi

  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$MODEL] ALL DONE"
}

export -f run_model
export XCODEEVAL BENCH EVAL_PS EVAL_CT VENV

# Export ports as individual vars (bash can't export arrays cleanly)
for MODEL in "${MODELS[@]}"; do
  eval "export PORT_${MODEL//-/_}=${PORTS[$MODEL]}"
done

# Override PORTS inside subshell via the individual vars trick
# (Each subshell re-declares the associative array)

echo "=== Starting eval for ${#MODELS[@]} models at $(date) ==="
echo "Models: ${MODELS[*]}"
echo ""

pids=()
for MODEL in "${MODELS[@]}"; do
  # Inline to avoid export-array issues
  (
    PORT=${PORTS[$MODEL]}
    DUMP_FOLDER=$XCODEEVAL/eval_runs/$MODEL
    LOG_DIR=$BENCH/$MODEL/logs
    mkdir -p "$LOG_DIR"

    source $VENV
    export DUMP_FOLDER=$DUMP_FOLDER
    export EXECEVAL_URL=http://localhost:$PORT

    PS_DIR="$DUMP_FOLDER/oai/prog_synthesis_n_sample_20"
    CT_DIR="$DUMP_FOLDER/oai/code_translation_n_sample_20/compact_small"

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$MODEL] Starting on port $PORT"

    PS_COUNT=$(ls "$PS_DIR"/*.json 2>/dev/null | wc -l)
    if [ "$PS_COUNT" -gt 0 ]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$MODEL] Running PS ($PS_COUNT files)"
      python3 $EVAL_PS > "$LOG_DIR/eval_ps.log" 2>&1
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$MODEL] PS done (exit=$?)"
    fi

    CT_COUNT=$(ls "$CT_DIR"/*.json 2>/dev/null | wc -l)
    if [ "$CT_COUNT" -gt 0 ]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$MODEL] Running CT ($CT_COUNT files)"
      python3 $EVAL_CT > "$LOG_DIR/eval_ct.log" 2>&1
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$MODEL] CT done (exit=$?)"
    fi

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$MODEL] ALL DONE"
  ) >> "$BENCH/$MODEL/logs/eval_run.log" 2>&1 &
  pids+=($!)
  echo "Launched $MODEL (PID $!)"
done

echo ""
echo "All launched. Waiting for completion..."
for pid in "${pids[@]}"; do
  wait $pid
done

echo ""
echo "=== ALL EVALS COMPLETE at $(date) ==="
