#!/bin/bash
# Run PS + CT + APR eval for all 4 models in parallel, each on its own execeval instance
# Usage: bash run_all_evals.sh [gpt4o|nemotron-550b|laguna-nvfp4|qwen-nvfp4]
# No args = run all 4

XCODEEVAL=/home/ujjwal.tiwari/ace/benchmarks/xcodeEval
EVAL_PS=$XCODEEVAL/evaluation/program_synthesis/eval_program_synthesis.py
EVAL_CT=$XCODEEVAL/evaluation/code_translation/eval_code_translation.py
EVAL_APR=$XCODEEVAL/evaluation/apr/eval_apr.py
VENV=$XCODEEVAL/../xcodeeval-env/bin/activate

declare -A PORTS
PORTS["gpt4o"]=5000
PORTS["nemotron-550b"]=5001
PORTS["laguna-nvfp4"]=5002
PORTS["qwen-nvfp4"]=5003

MODELS=("gpt4o" "nemotron-550b" "laguna-nvfp4" "qwen-nvfp4")
if [ $# -gt 0 ]; then
  MODELS=("$@")
fi

run_model() {
  MODEL=$1
  PORT=${PORTS[$MODEL]}
  DUMP_FOLDER=$XCODEEVAL/eval_runs/$MODEL
  LOG_DIR=$XCODEEVAL/eval_runs/$MODEL/logs
  mkdir -p $LOG_DIR

  source $VENV
  export DUMP_FOLDER=$DUMP_FOLDER
  export EXECEVAL_URL=http://localhost:$PORT

  echo "[$(date +%T)] Starting eval for $MODEL (port $PORT)"

  # PS
  if [ -d "$DUMP_FOLDER/oai/prog_synthesis_n_sample_20" ] && \
     [ $(ls "$DUMP_FOLDER/oai/prog_synthesis_n_sample_20"/*.json 2>/dev/null | wc -l) -gt 0 ]; then
    echo "[$(date +%T)] $MODEL: Running PS eval"
    python3 $EVAL_PS > $LOG_DIR/eval_ps.log 2>&1
    echo "[$(date +%T)] $MODEL: PS eval done"
  else
    echo "[$(date +%T)] $MODEL: Skipping PS (no data)"
  fi

  # CT
  if [ $(ls "$DUMP_FOLDER/oai/code_translation_n_sample_20/compact_small"/*.json 2>/dev/null | wc -l) -gt 0 ]; then
    echo "[$(date +%T)] $MODEL: Running CT eval"
    python3 $EVAL_CT > $LOG_DIR/eval_ct.log 2>&1
    echo "[$(date +%T)] $MODEL: CT eval done"
  else
    echo "[$(date +%T)] $MODEL: Skipping CT (no data)"
  fi

  # APR
  if [ -d "$DUMP_FOLDER/oai/apr_n_sample_20" ] && \
     [ $(ls "$DUMP_FOLDER/oai/apr_n_sample_20"/*.json 2>/dev/null | wc -l) -gt 0 ]; then
    echo "[$(date +%T)] $MODEL: Running APR eval"
    python3 $EVAL_APR > $LOG_DIR/eval_apr.log 2>&1
    echo "[$(date +%T)] $MODEL: APR eval done"
  else
    echo "[$(date +%T)] $MODEL: Skipping APR (no data)"
  fi

  echo "[$(date +%T)] $MODEL: ALL DONE"
}

export -f run_model
export XCODEEVAL EVAL_PS EVAL_CT EVAL_APR VENV
export -A PORTS 2>/dev/null || true
for MODEL in "${MODELS[@]}"; do
  export PORT_$MODEL=${PORTS[$MODEL]}
done

# Launch all models in parallel
pids=()
for MODEL in "${MODELS[@]}"; do
  run_model "$MODEL" &
  pids+=($!)
  echo "Launched $MODEL (PID $!)"
done

echo "All $# evals launched. Waiting..."
for pid in "${pids[@]}"; do
  wait $pid
done

echo "=== ALL EVALS COMPLETE ==="
