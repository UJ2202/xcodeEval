#!/bin/bash
# Run xcodeEval benchmark for all 3 models in parallel
# Models: qwen-nvfp4, laguna-nvfp4, gpt4o (all via localhost:4000)

set -e

VENV="/home/ujjwal.tiwari/xcodeeval-env"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TASKS="${1:-program_synthesis}"   # default task; pass 'all' for all 3 tasks
NUM_PROC="${2:-4}"
NSAMPLE="${3:-20}"
LANGUAGES="${4:-}"                # e.g. "Python Java" — empty means all 11

MODELS=("qwen-nvfp4" "laguna-nvfp4" "gpt4o")

echo "============================================"
echo "xCodeEval Parallel Run"
echo "Tasks    : $TASKS"
echo "Models   : ${MODELS[*]}"
echo "Procs    : $NUM_PROC per model"
echo "NSample  : $NSAMPLE"
echo "Languages: ${LANGUAGES:-all}"
echo "============================================"

source "$VENV/bin/activate"

run_task() {
    local model=$1
    local task=$2
    local out_dir="$SCRIPT_DIR/dumped/$model/$task"
    mkdir -p "$out_dir"
    local log="$SCRIPT_DIR/dumped/$model/${task}.log"
    echo "[$(date '+%H:%M:%S')] START $model / $task -> $out_dir"
    local lang_args=""
    if [ -n "$LANGUAGES" ]; then
        lang_args="--languages $LANGUAGES"
    fi
    XCODEEVAL_MODEL="$model" python3 "$SCRIPT_DIR/evaluation/$task/gen_$task.py" \
        --output-dir "$out_dir" \
        --num-proc "$NUM_PROC" \
        --nsample "$NSAMPLE" \
        $lang_args \
        > "$log" 2>&1
    echo "[$(date '+%H:%M:%S')] DONE  $model / $task (log: $log)"
}

export -f run_task
export VENV SCRIPT_DIR NUM_PROC NSAMPLE

if [ "$TASKS" = "all" ]; then
    TASK_LIST=("program_synthesis" "code_translation" "apr")
else
    TASK_LIST=("$TASKS")
fi

# Launch all model+task combinations in parallel
PIDS=()
for model in "${MODELS[@]}"; do
    for task in "${TASK_LIST[@]}"; do
        run_task "$model" "$task" &
        PIDS+=($!)
    done
done

echo ""
echo "All jobs launched. PIDs: ${PIDS[*]}"
echo "Waiting for completion..."

FAILED=0
for pid in "${PIDS[@]}"; do
    if ! wait "$pid"; then
        echo "Job PID $pid FAILED"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "============================================"
if [ "$FAILED" -eq 0 ]; then
    echo "All jobs completed successfully."
else
    echo "$FAILED job(s) failed. Check logs in dumped/<model>/<task>.log"
fi
echo "============================================"
