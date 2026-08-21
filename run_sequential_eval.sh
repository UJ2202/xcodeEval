#!/bin/bash
# Sequential PS + CT evaluation — all 6 models, one at a time, single execeval container
# Logs: benchmark/{model}/logs/eval_ps.log  eval_ct.log  eval_run.log
# Results: benchmark/{model}/ps/reproduce_1/*.jsonl
#          benchmark/{model}/ct_compact_small/eval_code_translation_compact_small_execeval/*.jsonl

XCODEEVAL=/home/ujjwal.tiwari/ace/benchmarks/xcodeEval
BENCH=$XCODEEVAL/benchmark
EVAL_PS=$XCODEEVAL/evaluation/program_synthesis/eval_program_synthesis.py
EVAL_CT=$XCODEEVAL/evaluation/code_translation/eval_code_translation.py
PYTHON=/home/ujjwal.tiwari/xcodeeval-env/bin/python3
EXECEVAL_URL=http://localhost:5000

MODELS=(claude-opus-5 claude-sonnet-5 gpt4o nemotron-550b laguna-nvfp4 qwen-nvfp4 gpt-5.6-sol)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "=== Sequential eval START — $(date) ==="
log "Models: ${MODELS[*]}"
log "ExecEval: $EXECEVAL_URL"
echo ""

for MODEL in "${MODELS[@]}"; do
  DUMP=$XCODEEVAL/eval_runs/$MODEL
  LOGDIR=$BENCH/$MODEL/logs
  mkdir -p "$LOGDIR"
  RUNLOG=$LOGDIR/eval_run.log

  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$RUNLOG"
  log "START: $MODEL" | tee -a "$RUNLOG"

  # ── Program Synthesis ──
  PS_DIR="$DUMP/oai/prog_synthesis_n_sample_20"
  PS_COUNT=$(ls "$PS_DIR"/*.json 2>/dev/null | wc -l)

  if [ "$PS_COUNT" -gt 0 ]; then
    log "$MODEL PS: $PS_COUNT input files → running" | tee -a "$RUNLOG"
    DUMP_FOLDER=$DUMP EXECEVAL_URL=$EXECEVAL_URL \
      $PYTHON $EVAL_PS > "$LOGDIR/eval_ps.log" 2>&1
    PS_EXIT=$?
    PS_RESULTS=$(ls "$BENCH/$MODEL/ps/reproduce_1/"*.jsonl 2>/dev/null | wc -l)
    log "$MODEL PS: done (exit=$PS_EXIT, $PS_RESULTS result files)" | tee -a "$RUNLOG"
  else
    log "$MODEL PS: SKIP — no input files" | tee -a "$RUNLOG"
  fi

  # ── Code Translation ──
  CT_DIR="$DUMP/oai/code_translation_n_sample_20/compact_small"
  CT_COUNT=$(ls "$CT_DIR"/*.json 2>/dev/null | wc -l)

  if [ "$CT_COUNT" -gt 0 ]; then
    log "$MODEL CT: $CT_COUNT input files → running" | tee -a "$RUNLOG"
    DUMP_FOLDER=$DUMP EXECEVAL_URL=$EXECEVAL_URL \
      $PYTHON $EVAL_CT > "$LOGDIR/eval_ct.log" 2>&1
    CT_EXIT=$?
    CT_RESULTS=$(ls "$BENCH/$MODEL/ct_compact_small/eval_code_translation_compact_small_execeval/"*.jsonl 2>/dev/null | wc -l)
    log "$MODEL CT: done (exit=$CT_EXIT, $CT_RESULTS result files)" | tee -a "$RUNLOG"
  else
    log "$MODEL CT: SKIP — no input files" | tee -a "$RUNLOG"
  fi

  log "DONE: $MODEL" | tee -a "$RUNLOG"
  echo "" | tee -a "$RUNLOG"
done

log "=== ALL MODELS COMPLETE — $(date) ==="
