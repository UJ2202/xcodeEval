#!/bin/bash
# Run eval scripts on the standardised baseline — all 3 models IN PARALLEL.
# Each model gets its own ExecEval container on a dedicated port.
#   gpt4o       → localhost:5000  (already running)
#   laguna-nvfp4 → localhost:5001
#   qwen-nvfp4  → localhost:5002

VENV="/home/ujjwal.tiwari/xcodeeval-env"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASELINE="$SCRIPT_DIR/dumped/baseline"

declare -A MODEL_PORT=(
    ["gpt4o"]="5000"
    ["laguna-nvfp4"]="5001"
    ["qwen-nvfp4"]="5002"
)

source "$VENV/bin/activate"

run_model_evals() {
    local model=$1
    local port=$2
    local MODEL_BASE="$BASELINE/$model"
    local OAI="$MODEL_BASE/oai"
    local LOG_DIR="$MODEL_BASE/eval_logs"
    local EXECEVAL_URL="http://localhost:$port"

    mkdir -p "$OAI" "$LOG_DIR"

    # Wire up the oai/ symlink layout the eval scripts expect
    [ -L "$OAI/apr_n_sample_20" ] || \
        ln -s "$MODEL_BASE/apr" "$OAI/apr_n_sample_20"
    [ -L "$OAI/prog_synthesis_n_sample_20" ] || \
        ln -s "$MODEL_BASE/program_synthesis" "$OAI/prog_synthesis_n_sample_20"
    mkdir -p "$OAI/code_translation_n_sample_20"
    [ -L "$OAI/code_translation_n_sample_20/compact_small" ] || \
        ln -s "$MODEL_BASE/code_translation/compact_small" \
              "$OAI/code_translation_n_sample_20/compact_small"

    echo "[$(date '+%H:%M:%S')] START $model (ExecEval → $EXECEVAL_URL)"

    DUMP_FOLDER="$MODEL_BASE" EXECEVAL_URL="$EXECEVAL_URL" \
        python3 "$SCRIPT_DIR/evaluation/program_synthesis/eval_program_synthesis.py" \
        > "$LOG_DIR/eval_program_synthesis.log" 2>&1 &
    local PID_PS=$!

    DUMP_FOLDER="$MODEL_BASE" EXECEVAL_URL="$EXECEVAL_URL" \
        python3 "$SCRIPT_DIR/evaluation/code_translation/eval_code_translation.py" \
        > "$LOG_DIR/eval_code_translation.log" 2>&1 &
    local PID_CT=$!

    DUMP_FOLDER="$MODEL_BASE" EXECEVAL_URL="$EXECEVAL_URL" \
        python3 "$SCRIPT_DIR/evaluation/apr/eval_apr_compile.py" \
        > "$LOG_DIR/eval_apr_compile.log" 2>&1 &
    local PID_APR=$!

    echo "  [$model] PIDs — ps:$PID_PS  ct:$PID_CT  apr:$PID_APR"
    wait $PID_PS $PID_CT $PID_APR
    echo "[$(date '+%H:%M:%S')] DONE  $model"

    # Compute pass@k scores
    DUMP_FOLDER="$MODEL_BASE" python3 "$SCRIPT_DIR/evaluation/program_synthesis/get_result.py" \
        > "$LOG_DIR/result_ps.log" 2>&1 || true
    DUMP_FOLDER="$MODEL_BASE" python3 "$SCRIPT_DIR/evaluation/code_translation/get_result.py" \
        > "$LOG_DIR/result_ct.log" 2>&1 || true
    DUMP_FOLDER="$MODEL_BASE" python3 "$SCRIPT_DIR/evaluation/apr/get_result_apr_compile.py" \
        > "$LOG_DIR/result_apr_compile.log" 2>&1 || true

    echo "[$(date '+%H:%M:%S')] SCORES written for $model"
}

export -f run_model_evals
export VENV SCRIPT_DIR BASELINE

# Launch all 3 models in parallel
PIDS=()
for model in "${!MODEL_PORT[@]}"; do
    port="${MODEL_PORT[$model]}"
    run_model_evals "$model" "$port" &
    PIDS+=($!)
done

echo "All 3 models running in parallel. PIDs: ${PIDS[*]}"
echo "Logs: dumped/baseline/<model>/eval_logs/"

wait "${PIDS[@]}"
echo ""
echo "============================================"
echo "All evals complete. Results in dumped/baseline/<model>/eval_logs/"
echo "============================================"
