# xCodeEval — Setup & Run Guide

## What This Is

xCodeEval is a multilingual multitask benchmark for code generation, translation, and repair.
It covers 7 tasks across 17 programming languages with execution-based evaluation (ExecEval).

**Paper:** https://arxiv.org/abs/2303.03004
**Repo:** https://github.com/UJ2202/xcodeEval

---

## Prerequisites

```bash
python3 --version   # 3.10+ recommended
docker --version    # for ExecEval
```

---

## Step 1 — Create the virtualenv

```bash
python3 -m venv ~/xcodeeval-env
source ~/xcodeeval-env/bin/activate

# CRITICAL: exact versions — newer breaks things
pip install "openai==0.28.0"       # old API style (ChatCompletion.create)
pip install "datasets==2.16.1"     # newer drops xCodeEval loading script
pip install "setuptools<80"        # provides pkg_resources for promptsource
pip install jsonlines tqdm numpy requests python-pptx

# promptsource — custom fork required
pip install git+https://github.com/sbmaruf/promptsource.git@70dc08c
```

---

## Step 2 — Start ExecEval (Docker)

```bash
git clone https://github.com/ntunlp/ExecEval
cd ExecEval
docker build . -t exec-eval:1.0

# Run detached on port 5000
docker run -d -p 5000:5000 -e NUM_WORKERS=8 exec-eval:1.0

# Verify it's up
curl http://localhost:5000/api/all_runtimes | python3 -m json.tool | head -5
```

> **Note:** Java and Kotlin are memory-heavy. On machines with <32GB RAM use `NUM_WORKERS=4`.

---

## Step 3 — Configure model endpoints

All gen scripts read three env vars:

```bash
export OPENAI_API_BASE="http://localhost:4000"   # LiteLLM proxy or direct vLLM
export OPENAI_API_KEY="sk-local-dev"             # any string for local endpoints
export XCODEEVAL_MODEL="gpt4o"                   # must match model_name in LiteLLM
```

### Models configured in this run

| Alias | Backend | Max tokens | Notes |
|---|---|---|---|
| `gpt4o` | Azure via LiteLLM | 8192 | n≤8 enforced (Azure limit) |
| `qwen-nvfp4` | vLLM :8000 | 4096 | requires `enable_thinking: False` |
| `laguna-nvfp4` | vLLM :8001 | 4096 | requires `enable_thinking: False` |
| `nemotron-ultra-nvfp4` | vLLM (separate host) | 32768 | 32k context |

LiteLLM config is at `/home/ujjwal.tiwari/ace/benchmarks/litellm_config.yaml`.

Test endpoint:
```bash
curl -s -X POST http://localhost:4000/chat/completions \
  -H "Authorization: Bearer sk-local-dev" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt4o", "messages": [{"role": "user", "content": "Say hi"}], "max_tokens": 10}' \
  | python3 -m json.tool
```

---

## Step 4 — Dataset (already in repo — no download needed)

All data is committed to https://github.com/UJ2202/xcodeEval — no HuggingFace access required at runtime.

| Path | Contents | Size |
|---|---|---|
| `dataset_subset/ps_compact.jsonl` | 106 PS problems (compact split) | 1 MB |
| `dataset_subset/ct_compact_small.jsonl` | 440 CT problems (compact_small split) | 4 MB |
| `apr_test_data/` | APR test JSONL for all 11 languages | ~30 MB |
| `baseline_filelist/ps.txt` | 405 filenames defining the PS baseline subset | tiny |
| `baseline_filelist/ct.txt` | 1689 filenames defining the CT baseline subset | tiny |
| `baseline_filelist/apr.txt` | 1364 filenames defining the APR baseline subset | tiny |

These splits are **fixed** — every model run uses the same rows so results are directly comparable.

---

## Step 4b — Fresh VM setup (clone and run)

```bash
# 1. Clone — all data included, no HuggingFace needed
git clone https://github.com/UJ2202/xcodeEval.git
cd xcodeEval

# 2. Prevent datasets library from phoning home
export HF_DATASETS_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

# 3. Virtualenv (Step 1 above)
python3 -m venv ~/xcodeeval-env
source ~/xcodeeval-env/bin/activate
pip install "openai==0.28.0" "datasets==2.16.1" "setuptools<80"
pip install jsonlines tqdm numpy requests python-pptx
pip install git+https://github.com/sbmaruf/promptsource.git@70dc08c

# 4. ExecEval Docker (Step 2 above)
docker run -d -p 5000:5000 -e NUM_WORKERS=8 exec-eval:1.0

# 5. Set model endpoint (Step 3 above)
export OPENAI_API_BASE="http://<model-host>:4000"
export OPENAI_API_KEY="sk-local-dev"

# 6. Run — baseline-matched subset (same 404 PS / 1689 CT / 1362 APR as all prior models)
MODEL=<your-model-alias>

MODEL_OUT_NAME=$MODEL XCODEEVAL_DATA_DIR=dataset_subset XCODEEVAL_FILELIST_DIR=baseline_filelist \
  python3 gen_nemotron_baseline.py ps  > dumped/$MODEL/logs/gen_ps.log 2>&1 &

MODEL_OUT_NAME=$MODEL XCODEEVAL_DATA_DIR=dataset_subset XCODEEVAL_FILELIST_DIR=baseline_filelist \
  python3 gen_nemotron_baseline.py ct  > dumped/$MODEL/logs/gen_ct.log 2>&1 &

MODEL_OUT_NAME=$MODEL XCODEEVAL_DATA_DIR=dataset_subset XCODEEVAL_FILELIST_DIR=baseline_filelist \
  python3 gen_nemotron_baseline.py apr > dumped/$MODEL/logs/gen_apr.log 2>&1 &
```

> For full runs (all 106 PS / 440 CT / all 7 APR langs) use `--data-dir dataset_subset` on the regular gen scripts — see Step 5.

---

## Step 5 — Generate outputs

### Baseline-matched runs (new models)

Use `gen_nemotron_baseline.py` — runs only the same (idx, lang) pairs as the gpt4o baseline:

```bash
cd xcodeEval
source ~/xcodeeval-env/bin/activate
MODEL=<your-model-alias>

mkdir -p dumped/$MODEL/logs

MODEL_OUT_NAME=$MODEL XCODEEVAL_DATA_DIR=dataset_subset XCODEEVAL_FILELIST_DIR=baseline_filelist \
  python3 gen_nemotron_baseline.py ps  > dumped/$MODEL/logs/gen_ps.log  2>&1 &

MODEL_OUT_NAME=$MODEL XCODEEVAL_DATA_DIR=dataset_subset XCODEEVAL_FILELIST_DIR=baseline_filelist \
  python3 gen_nemotron_baseline.py ct  > dumped/$MODEL/logs/gen_ct.log  2>&1 &

MODEL_OUT_NAME=$MODEL XCODEEVAL_DATA_DIR=dataset_subset XCODEEVAL_FILELIST_DIR=baseline_filelist \
  python3 gen_nemotron_baseline.py apr > dumped/$MODEL/logs/gen_apr.log 2>&1 &
```

env vars for `gen_nemotron_baseline.py`:

| Var | Purpose | Default |
|---|---|---|
| `XCODEEVAL_MODEL` | model alias passed to the API | `nvidia/nemotron-3-ultra-550b-a55b` |
| `MODEL_OUT_NAME` | output folder under `dumped/` | `nemotron-550b` |
| `NSAMPLE` | number of samples per problem | `5` |
| `NUM_PROC` | parallel API workers | `16` |
| `XCODEEVAL_DATA_DIR` | path to dataset_subset/ (local JSONL) | unset → uses HF |
| `XCODEEVAL_FILELIST_DIR` | path to baseline_filelist/ | unset → scans baseline dir |

### Full runs (all problems, all 7 languages)

```bash
LANGS="C++ Go Java Javascript PHP Python Kotlin"

# Program Synthesis
XCODEEVAL_MODEL=$MODEL python3 evaluation/program_synthesis/gen_program_synthesis.py \
  --data-dir dataset_subset \
  --output-dir dumped/$MODEL/program_synthesis \
  --num-proc 4 --nsample 8 --languages $LANGS \
  > dumped/$MODEL/program_synthesis.log 2>&1 &

# Code Translation
XCODEEVAL_MODEL=$MODEL python3 evaluation/code_translation/gen_code_translation.py \
  --data-dir dataset_subset \
  --output-dir dumped/$MODEL/code_translation \
  --num-proc 4 --nsample 8 --languages $LANGS \
  > dumped/$MODEL/code_translation.log 2>&1 &

# APR
XCODEEVAL_MODEL=$MODEL python3 evaluation/apr/gen_apr.py \
  --output-dir dumped/$MODEL/apr \
  --num-proc 4 --nsample 8 --languages $LANGS \
  --apr-data-dir apr_test_data \
  > dumped/$MODEL/apr.log 2>&1 &
```

### Check progress

```bash
for model in gpt4o qwen-nvfp4 laguna-nvfp4 nemotron-550b; do
  ps_count=$(ls dumped/$model/program_synthesis/ 2>/dev/null | wc -l)
  ct_count=$(ls dumped/$model/code_translation/compact_small/ 2>/dev/null | wc -l)
  apr_count=$(ls dumped/$model/apr/ 2>/dev/null | wc -l)
  echo "$model: PS=$ps_count/742  CT=$ct_count/2800  APR=$apr_count/11274"
done
```

### Expected totals per model

| Task | Total files | Calculation |
|---|---|---|
| program_synthesis | 742 | 106 problems × 7 languages |
| code_translation | 2800 | 440 compact_small × ~6.4 target langs avg |
| apr | 11274 | test split rows for 7 languages |

---

## Step 6 — Score with ExecEval

ExecEval must be running (`docker ps` to verify).

### Program Synthesis

```bash
mkdir -p dumped/$MODEL/oai
ln -sfn "$(pwd)/dumped/$MODEL/program_synthesis" "$(pwd)/dumped/$MODEL/oai/prog_synthesis_n_sample_20"

DUMP_FOLDER="$(pwd)/dumped/$MODEL" python3 evaluation/program_synthesis/eval_program_synthesis.py
```

### Code Translation

```bash
mkdir -p dumped/$MODEL/oai/code_translation_n_sample_20
ln -sfn "$(pwd)/dumped/$MODEL/code_translation/compact_small" \
        "$(pwd)/dumped/$MODEL/oai/code_translation_n_sample_20/compact_small"

DUMP_FOLDER="$(pwd)/dumped/$MODEL" python3 evaluation/code_translation/eval_code_translation.py
```

### APR (nemotron baseline layout)

```bash
ln -sfn "$(pwd)/dumped/$MODEL/apr_n_sample_20" "$(pwd)/dumped/$MODEL/oai/apr_n_sample_20"

DUMP_FOLDER="$(pwd)/dumped/$MODEL" python3 evaluation/apr/eval_apr.py
```

---

## Step 7 — Compute pass@k scores

```bash
# Program Synthesis — prints pass@5 per language + average
DUMP_FOLDER="$(pwd)/dumped/$MODEL" python3 evaluation/program_synthesis/get_result.py

# Code Translation
DUMP_FOLDER="$(pwd)/dumped/$MODEL" python3 evaluation/code_translation/get_result.py

# APR
DUMP_FOLDER="$(pwd)/dumped/$MODEL" python3 evaluation/apr/get_result.py
```

Output is a LaTeX-style table row: `& lang1 & lang2 ... & avg`
Numbers are pass@5 × 100 (percentage).

---

## Current Results — GPT-5.1 (gpt4o alias)

### Program Synthesis — pass@5

| C++ | Go | Java | Javascript | Kotlin | PHP | Python | Avg |
|---|---|---|---|---|---|---|---|
| 62.83% | 44.53% | 24.87% | 59.42% | 49.44% | 58.68% | 49.04% | **49.8%** |

560 / 742 problems scored (182 had empty dataset fields).

---

## Output structure

```
dumped/
  <model>/
    program_synthesis/
      <idx>_<temp>_<lang>.json       ← raw API response + source data
    code_translation/
      compact_small/
        <idx>_<temp>_<src>--<tgt>.json
    apr/  (or apr_n_sample_20/ for nemotron baseline script)
      <idx>_<temp>_<lang>.json
    oai/
      prog_synthesis_n_sample_20/    ← symlink → program_synthesis/
        reproduce_1/
          GNU C++17.jsonl            ← ExecEval scored output
      code_translation_n_sample_20/
        compact_small/               ← symlink → code_translation/compact_small/
      apr_n_sample_20/               ← symlink → apr/
    logs/
      gen_ps.log
      gen_ct.log
      gen_apr.log
```

---

## Common pitfalls

| Problem | Fix |
|---|---|
| `KeyError: DUMP_FOLDER` | Use `export DUMP_FOLDER=...` not inline |
| `trust_remote_code` error | Use `datasets==2.16.1`, not newer |
| `pkg_resources` missing | `pip install "setuptools<80"` |
| gpt4o stuck at 0% | Azure n≤8 limit — already handled via `MAX_N = 8 if MODEL == "gpt4o"` |
| vLLM context window exceeded | `MAX_TOKENS=4096` for qwen/laguna (already set) |
| datasets tries to reach HF | `export HF_DATASETS_OFFLINE=1` |
| ExecEval OOM on Java/Kotlin | Reduce `NUM_WORKERS` in docker run to 4 |
| nemotron connection error | Model server down — restart vLLM, then re-run (script skips existing files) |

---

## Scoring pipeline diagram

```
dataset_subset/ or apr_test_data/  (in repo — no download)
    ↓
gen_nemotron_baseline.py / gen_<task>.py  →  dumped/<model>/<task>/*.json
    ↓
eval_<task>.py  →  reproduce_1/<compiler>.jsonl   (per-test PASSED/FAILED)
    ↓
get_result.py   →  pass@k table printed to stdout
```

---

## Notes

- `--num-proc 4` keeps API workers moderate; raise to 8–16 on fast endpoints
- `--nsample 8` matches Azure gpt4o limit and gives pass@1–pass@8 metrics
- The paper reports **pass@5** as the primary metric
- APR prompt uses simplified format (bug code + error type)
- `apr_test_data/` filenames use URL encoding: `C%23.jsonl` = C#, `C%2B%2B.jsonl` = C++
- `baseline_filelist/` defines the fixed subset — do not modify, all models must use the same rows
