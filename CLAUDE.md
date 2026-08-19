# xCodeEval — Setup & Run Guide

## What This Is

xCodeEval is a multilingual multitask benchmark for code generation, translation, and repair.
It covers 7 tasks across 17 programming languages with execution-based evaluation (ExecEval).

**Paper:** https://arxiv.org/abs/2303.03004
**HuggingFace dataset:** `NTU-NLP-sg/xCodeEval`

---

## Prerequisites

```bash
python3 --version   # 3.10+ recommended
docker --version    # for ExecEval
df -h               # need ~50GB free (datasets are large)
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

## Step 4 — Dataset download (run this on the source VM once)

All three datasets are downloaded here first. For fresh VMs, see **Step 4b** below — no re-download needed.

### Program Synthesis & Code Translation

The gen scripts call `datasets.load_dataset()` and cache Arrow files under `~/.cache/huggingface/`.
Run this once; subsequent runs (and fresh VMs given the cache) skip downloading.

```bash
source ~/xcodeeval-env/bin/activate
python3 -c "
import datasets
datasets.load_dataset('NTU-NLP-sg/xCodeEval', 'program_synthesis', trust_remote_code=True)
datasets.load_dataset('NTU-NLP-sg/xCodeEval', 'code_translation', trust_remote_code=True)
print('Done')
"
```

Cache goes to `~/.cache/huggingface/datasets/NTU-NLP-sg___x_code_eval/`.
`program_synthesis` is ~22 GB processed Arrow cache. Takes 10–30 min on first run.

### APR — download test files directly

The APR dataset is 16 GB raw but only the test split (~11K rows) is needed.

```bash
mkdir -p /home/ujjwal.tiwari/ace/benchmarks/xcodeEval/apr_test_data
cd /home/ujjwal.tiwari/ace/benchmarks/xcodeEval/apr_test_data

HF_BASE="https://huggingface.co/datasets/NTU-NLP-sg/xCodeEval/resolve/main/apr/test"
for lang in "C%23" "C%2B%2B" "C" "Go" "Java" "Javascript" "Kotlin" "PHP" "Python" "Ruby" "Rust"; do
  curl -sL "$HF_BASE/$lang.jsonl" -o "${lang}.jsonl"
  echo "$lang: $(wc -l < ${lang}.jsonl) rows"
done
```

File sizes per language (our 7 target languages):
- C++: 2026 rows, Go: 1427, Java: 2032, Javascript: 643
- Kotlin: 1978, PHP: 1156, Python: 2012 → **Total: 11,274 rows**

---

## Step 4b — Deploy to a fresh VM (no re-download)

Once Step 4 is complete on the source VM, copy datasets and the project to the target VM.
The target VM skips all downloading — `datasets` finds the cache on first use.

### What to copy

| Source path | Destination | Size (approx) |
|---|---|---|
| `~/.cache/huggingface/datasets/NTU-NLP-sg___x_code_eval/` | same path on target | ~25 GB |
| `/home/ujjwal.tiwari/ace/benchmarks/xcodeEval/apr_test_data/` | same path on target | ~200 MB |
| `/home/ujjwal.tiwari/ace/benchmarks/xcodeEval/` | same path on target | project + any existing `dumped/` outputs |

### Rsync commands (run from source VM)

```bash
TARGET_VM="user@<target-ip>"

# HuggingFace Arrow cache (PS + CT)
rsync -avz --progress \
  ~/.cache/huggingface/datasets/NTU-NLP-sg___x_code_eval/ \
  "$TARGET_VM:~/.cache/huggingface/datasets/NTU-NLP-sg___x_code_eval/"

# APR test files
rsync -avz --progress \
  /home/ujjwal.tiwari/ace/benchmarks/xcodeEval/apr_test_data/ \
  "$TARGET_VM:/home/ujjwal.tiwari/ace/benchmarks/xcodeEval/apr_test_data/"

# Project directory (code + any existing outputs)
rsync -avz --progress \
  /home/ujjwal.tiwari/ace/benchmarks/xcodeEval/ \
  "$TARGET_VM:/home/ujjwal.tiwari/ace/benchmarks/xcodeEval/"
```

### Fresh VM checklist (after copy)

```bash
# 1. Create virtualenv and install deps (same as Step 1)
python3 -m venv ~/xcodeeval-env
source ~/xcodeeval-env/bin/activate
pip install "openai==0.28.0" "datasets==2.16.1" "setuptools<80"
pip install jsonlines tqdm numpy requests python-pptx
pip install git+https://github.com/sbmaruf/promptsource.git@70dc08c

# 2. Start ExecEval Docker (same as Step 2)
#    If the image was already built, just run it:
docker run -d -p 5000:5000 -e NUM_WORKERS=8 exec-eval:1.0
#    If image not present, build first (Step 2).

# 3. Set env vars (same as Step 3)
export OPENAI_API_BASE="http://localhost:4000"
export OPENAI_API_KEY="sk-local-dev"
export XCODEEVAL_MODEL="gpt4o"

# 4. Verify datasets are found (should print sizes instantly, no download)
source ~/xcodeeval-env/bin/activate
python3 -c "
import datasets
ds = datasets.load_dataset('NTU-NLP-sg/xCodeEval', 'program_synthesis', trust_remote_code=True)
print('PS compact:', len(ds['compact']), 'rows')
ds2 = datasets.load_dataset('NTU-NLP-sg/xCodeEval', 'code_translation', trust_remote_code=True)
print('CT compact_small:', len(ds2['compact_small']), 'rows')
"

# 5. Verify APR files
ls /home/ujjwal.tiwari/ace/benchmarks/xcodeEval/apr_test_data/*.jsonl | wc -l
# should print 11

# 6. Run gen scripts (Step 5)
```

---

## Step 5 — Generate outputs

### Run all models in parallel

```bash
cd /home/ujjwal.tiwari/ace/benchmarks/xcodeEval
source ~/xcodeeval-env/bin/activate

LANGS="C++ Go Java Javascript PHP Python Kotlin"

# Program Synthesis
for model in gpt4o qwen-nvfp4 laguna-nvfp4; do
  XCODEEVAL_MODEL="$model" python3 evaluation/program_synthesis/gen_program_synthesis.py \
    --output-dir "dumped/$model/program_synthesis" \
    --num-proc 2 --nsample 8 --languages $LANGS \
    > "dumped/$model/program_synthesis.log" 2>&1 &
done

# Code Translation
for model in gpt4o qwen-nvfp4 laguna-nvfp4; do
  XCODEEVAL_MODEL="$model" python3 evaluation/code_translation/gen_code_translation.py \
    --output-dir "dumped/$model/code_translation" \
    --num-proc 2 --nsample 8 --languages $LANGS \
    > "dumped/$model/code_translation.log" 2>&1 &
done

# APR
for model in gpt4o qwen-nvfp4 laguna-nvfp4; do
  XCODEEVAL_MODEL="$model" python3 evaluation/apr/gen_apr.py \
    --output-dir "dumped/$model/apr" \
    --num-proc 2 --nsample 8 --languages $LANGS \
    --apr-data-dir /home/ujjwal.tiwari/ace/benchmarks/xcodeEval/apr_test_data \
    > "dumped/$model/apr.log" 2>&1 &
done
```

### Check progress

```bash
for model in gpt4o qwen-nvfp4 laguna-nvfp4; do
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
# Create symlink so eval script finds files at expected path
mkdir -p dumped/gpt4o/oai
ln -sfn "$(pwd)/dumped/gpt4o/program_synthesis" "$(pwd)/dumped/gpt4o/oai/prog_synthesis_n_sample_20"

DUMP_FOLDER="$(pwd)/dumped/gpt4o" python3 evaluation/program_synthesis/eval_program_synthesis.py
```

Outputs per-language JSONL files to `dumped/gpt4o/oai/prog_synthesis_n_sample_20/reproduce_1/`.

### Code Translation

```bash
mkdir -p dumped/gpt4o/oai/code_translation_n_sample_20
ln -sfn "$(pwd)/dumped/gpt4o/code_translation/compact_small" \
        "$(pwd)/dumped/gpt4o/oai/code_translation_n_sample_20/compact_small"

DUMP_FOLDER="$(pwd)/dumped/gpt4o" python3 evaluation/code_translation/eval_code_translation.py
```

### APR

```bash
mkdir -p dumped/gpt4o/oai
ln -sfn "$(pwd)/dumped/gpt4o/apr" "$(pwd)/dumped/gpt4o/oai/apr_n_sample_20"

DUMP_FOLDER="$(pwd)/dumped/gpt4o" python3 evaluation/apr/eval_apr.py
```

---

## Step 7 — Compute pass@k scores

```bash
# Program Synthesis — prints pass@5 per language + average
DUMP_FOLDER="$(pwd)/dumped/gpt4o" python3 evaluation/program_synthesis/get_result.py

# Code Translation
DUMP_FOLDER="$(pwd)/dumped/gpt4o" python3 evaluation/code_translation/get_result.py

# APR
DUMP_FOLDER="$(pwd)/dumped/gpt4o" python3 evaluation/apr/get_result.py
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
    apr/
      <idx>_<temp>_<lang>.json
    oai/
      prog_synthesis_n_sample_20/    ← symlink → program_synthesis/
        reproduce_1/
          GNU C++17.jsonl            ← ExecEval scored output
          Go.jsonl
          ...
      code_translation_n_sample_20/
        compact_small/               ← symlink → code_translation/compact_small/
      apr_n_sample_20/               ← symlink → apr/
    program_synthesis.log
    code_translation.log
    apr.log
```

Each JSON file contains:
```json
{
  "oai_response": {
    "choices": [                     ← n=8 solutions (or n=20 for vLLM models)
      {"message": {"content": "...generated code..."}},
      ...
    ]
  },
  "source_data": { ... }             ← original dataset row
}
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
| APR dataset won't load | Download test JSONL files directly (Step 4), bypass datasets library |
| ExecEval OOM on Java/Kotlin | Reduce `NUM_WORKERS` in docker run to 4 |
| nemotron connection error | Model server down — restart vLLM, then re-run (script skips existing files) |

---

## Scoring pipeline diagram

```
Dataset (HuggingFace)
    ↓
gen_<task>.py  →  dumped/<model>/<task>/*.json   (raw LLM outputs)
    ↓
eval_<task>.py →  reproduce_1/<compiler>.jsonl   (per-test PASSED/FAILED)
    ↓
get_result.py  →  pass@k table printed to stdout
```

---

## Notes

- `--num-proc 2` keeps API workers low to avoid rate limiting; raise to 4–8 on fast endpoints
- `--nsample 8` matches Azure gpt4o limit and gives pass@1–pass@8 metrics
- The paper reports **pass@5** as the primary metric
- APR prompt uses simplified format (bug code + error type) since test files lack problem descriptions
- `apr_test_data/` filenames use URL encoding: `C%23.jsonl` = C#, `C%2B%2B.jsonl` = C++
