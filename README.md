<div align="center">

# 🧪 xCodeEval — Multilingual LLM Code Benchmark

**Execution-based evaluation of LLMs on Program Synthesis & Code Translation across 7 programming languages.**

[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![ExecEval](https://img.shields.io/badge/ExecEval-Docker-2496ED?logo=docker&logoColor=white)](https://github.com/ntunlp/ExecEval)
[![Tasks](https://img.shields.io/badge/tasks-PS%20%7C%20CT-2E9B57)](#-benchmark-results)
[![Languages](https://img.shields.io/badge/languages-7-E8710A)](#-benchmark-results)
[![Paper](https://img.shields.io/badge/paper-arXiv%3A2303.03004-B31B1B)](https://arxiv.org/abs/2303.03004)

[Results](#-benchmark-results) · [Quick Start](#-quick-start) · [Add a Model](#-running-a-new-model) · [Re-run Eval](#-re-running-eval-only) · [Repo Layout](#-repository-structure) · [Troubleshooting](#-troubleshooting)

</div>

---

## Overview

**xCodeEval** measures how well language models can *write* and *translate* code that actually **runs and passes hidden test cases** — not just how plausible the code looks. Every submission is executed inside [ExecEval](https://github.com/ntunlp/ExecEval), a Docker sandbox, and scored with the unbiased **pass@k** estimator.

| | |
|---|---|
| **Tasks** | Program Synthesis (PS) · Code Translation (CT) |
| **Languages** | C++ · Go · Java · JavaScript · Kotlin · PHP · Python |
| **Models evaluated** | 7 (Claude, GPT, and on-prem NV-FP4 models) |
| **Metrics** | `pass@1` (all models) · `pass@5` (models with ≥5 samples) |
| **Execution** | ExecEval — Docker sandbox, deterministic scoring |
| **Dataset** | Compact subset — 106 PS problems, ~440 CT problems (fixed across all models) |

> Based on [**xCodeEval**](https://arxiv.org/abs/2303.03004), the largest multilingual multitask code benchmark.

---

## 📊 Benchmark Results

> [!IMPORTANT]
> All figures below are from the **corrected run** after fixing a silent-failure bug in ExecEval,
> where some test cases were skipped without raising an error. Any figures predating this fix are superseded.

### 🏆 Leaderboard — `pass@1`, averaged across 7 languages

| Rank | Model | Program Synthesis | Code Translation | Overall\* |
|:---:|---|:---:|:---:|:---:|
| 🥇 | **Claude Opus 5** | 90.8% | 87.4% | **89.1%** |
| 🥈 | **GPT-5.6-sol** | 81.0% | 85.5% | **83.3%** |
| 🥉 | **Claude Sonnet 5** | 77.7% | 81.4% | **79.6%** |
| 4 | GPT-5.1 (gpt4o) | 52.1% | 81.4% | 66.8% |
| 5 | Nemotron-550B | 54.2% | 67.5% | 60.9% |
| 6 | Laguna NV-FP4 | 41.9% | 65.1% | 53.5% |
| 7 | Qwen NV-FP4 | 43.0% | 62.8% | 52.9% |

<sub>\* Overall = mean of the two per-task language averages (equal weight). Task splits differ in size, so treat it as an at-a-glance rank, not a precise score.</sub>

> [!NOTE]
> **How to read the tables.** `---` = not computed or unavailable. `pass@5` requires **≥5 samples per problem**.
> Some `pass@5` rows are blank by design:
> - **Claude Opus 5 & Sonnet 5** — the Anthropic API does not support the `n` parameter for multiple samples, so these ran at n=1 → **pass@1 only** (5 samples would have cost ~5×).
> - **Nemotron-550B (PS)** — very slow (~400s/response), so PS ran at n=1 → **PS pass@5 omitted**; CT is n=5, so CT pass@5 is reported.
> - **Qwen NV-FP4 (PS)** — Kotlin produced no usable output; Python scored on only 4 problems (not comparable).

<details open>
<summary><b>Program Synthesis — detailed pass@1 / pass@5</b></summary>

<br>

**Program Synthesis — `pass@1`**

| Model | C++ | Go | Java | JavaScript | Kotlin | PHP | Python | **Avg** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Claude Opus 5 | 90.7% | 90.7% | 89.5% | 89.5% | 89.3% | 94.4% | 91.8% | **90.8%** 🥇 |
| Claude Sonnet 5 | 83.6% | 90.5% | 85.5% | 32.3% | 83.3% | 86.2% | 82.4% | **77.7%** |
| GPT-5.1 (gpt4o) | 55.8% | 49.4% | 53.1% | 51.7% | 50.3% | 50.8% | 53.6% | **52.1%** |
| GPT-5.6-sol | 88.5% | 85.0% | 87.5% | 87.2% | 49.7% | 85.5% | 83.5% | **81.0%** |
| Nemotron-550B | 61.5% | 57.7% | 62.9% | 55.2% | 37.1% | 42.9% | 62.3% | **54.2%** |
| Laguna NV-FP4 | 48.1% | 42.8% | 50.2% | 29.8% | 38.6% | 37.8% | 46.3% | **41.9%** |
| Qwen NV-FP4 | 56.7% | 35.5% | 55.3% | 47.4% | --- | 46.9% | 16.2% | **43.0%** |

**Program Synthesis — `pass@5`**

| Model | C++ | Go | Java | JavaScript | Kotlin | PHP | Python | **Avg** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Claude Opus 5 | --- | --- | --- | --- | --- | --- | --- | **---** |
| Claude Sonnet 5 | --- | --- | --- | --- | --- | --- | --- | **---** |
| GPT-5.1 (gpt4o) | 62.8% | 60.0% | 62.8% | 59.4% | 61.9% | 60.0% | 63.6% | **61.5%** |
| GPT-5.6-sol | 91.2% | 88.8% | 91.2% | 91.2% | 72.5% | 90.0% | 86.2% | **87.3%** 🥇 |
| Nemotron-550B | --- | --- | --- | --- | --- | --- | --- | **---** |
| Laguna NV-FP4 | 58.7% | 59.4% | 62.2% | 49.2% | 53.2% | 53.5% | 60.2% | **56.6%** |
| Qwen NV-FP4 | 71.4% | 57.8% | 69.0% | 62.6% | --- | 68.2% | 49.9% | **63.1%** |

</details>

<details open>
<summary><b>Code Translation — detailed pass@1 / pass@5</b></summary>

<br>

**Code Translation — `pass@1`**

| Model | C++ | Go | Java | JavaScript | Kotlin | PHP | Python | **Avg** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Claude Opus 5 | 95.4% | 93.2% | 93.7% | 71.6% | 84.0% | 82.3% | 91.7% | **87.4%** 🥇 |
| Claude Sonnet 5 | 94.8% | 91.2% | 88.7% | 57.6% | 85.4% | 68.0% | 83.8% | **81.4%** |
| GPT-5.1 (gpt4o) | 90.1% | 88.5% | 85.3% | 80.9% | 73.1% | 67.0% | 84.7% | **81.4%** |
| GPT-5.6-sol | 96.5% | 91.8% | 94.8% | 91.5% | 49.8% | 83.4% | 90.5% | **85.5%** |
| Nemotron-550B | 87.1% | 75.7% | 83.9% | 49.6% | 54.6% | 43.8% | 78.0% | **67.5%** |
| Laguna NV-FP4 | 82.7% | 66.9% | 74.9% | 38.9% | 66.8% | 51.2% | 74.1% | **65.1%** |
| Qwen NV-FP4 | 84.4% | 49.4% | 80.3% | 39.1% | 59.6% | 48.7% | 78.0% | **62.8%** |

**Code Translation — `pass@5`**

| Model | C++ | Go | Java | JavaScript | Kotlin | PHP | Python | **Avg** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Claude Opus 5 | --- | --- | --- | --- | --- | --- | --- | **---** |
| Claude Sonnet 5 | --- | --- | --- | --- | --- | --- | --- | **---** |
| GPT-5.1 (gpt4o) | 92.9% | 93.2% | 89.4% | 87.1% | 78.6% | 78.2% | 88.8% | **86.9%** |
| GPT-5.6-sol | 97.5% | 94.6% | 96.5% | 92.8% | 68.1% | 89.7% | 92.3% | **90.2%** 🥇 |
| Nemotron-550B | 92.8% | 88.9% | 92.0% | 82.2% | 81.4% | 68.0% | 86.6% | **84.6%** |
| Laguna NV-FP4 | 92.0% | 82.4% | 86.6% | 60.9% | 80.4% | 68.3% | 82.4% | **79.0%** |
| Qwen NV-FP4 | 93.0% | 74.1% | 87.9% | 68.6% | 74.0% | 64.6% | 86.4% | **78.4%** |

</details>

> 📄 Full per-model breakdown with failure analysis → [`benchmark/RESULTS.txt`](benchmark/RESULTS.txt) · Slide deck → [`benchmark/RESULTS.pptx`](benchmark/RESULTS.pptx)

---

## ⚡ Quick Start

### Prerequisites

```bash
python3 --version    # 3.10+ required
docker --version     # for ExecEval
git --version
```

### 1 · Clone the repo

```bash
git clone https://github.com/UJ2202/xcodeEval.git
cd xcodeEval

# Prevent datasets from phoning home (data is already in the repo)
export HF_DATASETS_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
```

### 2 · Install Python dependencies

```bash
python3 -m venv ~/xcodeeval-env
source ~/xcodeeval-env/bin/activate

# CRITICAL: use these exact versions
pip install "openai==0.28.0"        # generation scripts use old-style ChatCompletion.create
pip install "datasets==2.16.1"      # newer drops the xCodeEval loading script
pip install "setuptools<80"         # provides pkg_resources for promptsource
pip install jsonlines tqdm numpy requests python-pptx

# promptsource — required custom fork
pip install git+https://github.com/sbmaruf/promptsource.git@70dc08c
```

### 3 · Start ExecEval (execution sandbox)

ExecEval is a Docker-based code execution engine.

```bash
# Build (one-time)
cd ExecEval
docker build . -t exec-eval:1.0
cd ..

# Run with required resource flags
docker run -d \
  --name execeval \
  -p 5000:5000 \
  -e NUM_WORKERS=32 \
  --cap-add SYS_RESOURCE \
  --ulimit nproc=65535:65535 \
  --ulimit nofile=65535:65535 \
  exec-eval:1.0

# Verify it's up
curl -s http://localhost:5000/api/all_runtimes | python3 -m json.tool | head -5
```

> [!WARNING]
> These flags are **required**, or Java / Kotlin / Go score near 0%.
> Without `--cap-add SYS_RESOURCE` the JVM cannot set resource limits and every Java/Kotlin submission crashes.
> Without the `ulimit` flags, Go goroutines and Node.js threads hit OS limits immediately.

### 4 · Configure your model endpoint

All generation scripts read from these environment variables:

```bash
export OPENAI_API_BASE="http://localhost:4000"   # LiteLLM proxy or direct OpenAI-compatible endpoint
export OPENAI_API_KEY="sk-your-key"              # real key for API models; any string for local vLLM
export XCODEEVAL_MODEL="your-model-alias"        # must match what the endpoint expects
```

<details>
<summary><b>Example endpoint setups</b></summary>

```bash
# Azure OpenAI via LiteLLM proxy
export OPENAI_API_BASE="http://localhost:4000"
export XCODEEVAL_MODEL="gpt4o"

# Local vLLM
export OPENAI_API_BASE="http://localhost:8000/v1"
export OPENAI_API_KEY="sk-local"
export XCODEEVAL_MODEL="meta-llama/Llama-3-70b-instruct"

# Direct Anthropic (via LiteLLM)
export OPENAI_API_BASE="http://localhost:4000"
export XCODEEVAL_MODEL="claude-opus-5"
```

</details>

---

## 🚀 Running a New Model

> The full flow is **generate → symlink → score → results**. Each step below is copy-pasteable.

### Step 1 · Generate outputs

Use `gen_nemotron_baseline.py` to run the same (problem, language) pairs used by every model in this benchmark, ensuring a fair comparison:

```bash
source ~/xcodeeval-env/bin/activate
MODEL=my-model   # this becomes the folder name under benchmark/

mkdir -p benchmark/$MODEL/logs

# Program Synthesis
MODEL_OUT_NAME=$MODEL \
  XCODEEVAL_DATA_DIR=dataset_subset \
  XCODEEVAL_FILELIST_DIR=baseline_filelist \
  python3 gen_nemotron_baseline.py ps \
  > benchmark/$MODEL/logs/gen_ps.log 2>&1 &

# Code Translation
MODEL_OUT_NAME=$MODEL \
  XCODEEVAL_DATA_DIR=dataset_subset \
  XCODEEVAL_FILELIST_DIR=baseline_filelist \
  python3 gen_nemotron_baseline.py ct \
  > benchmark/$MODEL/logs/gen_ct.log 2>&1 &
```

**Monitor progress:**

```bash
# PS: expect ~560 files (80 problems × 7 languages)
ls benchmark/$MODEL/ps/ | wc -l

# CT: expect ~1688 files (~440 problems × ~6 target languages)
ls benchmark/$MODEL/ct_compact_small/ | wc -l
```

**Generation environment variables:**

| Variable | Purpose | Default |
|---|---|---|
| `XCODEEVAL_MODEL` | Model alias sent to API | `nvidia/nemotron-3-ultra-550b-a55b` |
| `MODEL_OUT_NAME` | Output folder under `benchmark/` | `nemotron-550b` |
| `NSAMPLE` | Samples per problem (pass@k requires ≥k) | `5` |
| `NUM_PROC` | Parallel API workers | `16` |
| `XCODEEVAL_DATA_DIR` | Path to dataset JSONL files | uses HuggingFace |
| `XCODEEVAL_FILELIST_DIR` | Path to baseline file lists | uses HF |

### Step 2 · Set up eval symlinks

The eval scripts navigate via `eval_runs/<model>/oai/`. Create these symlinks once:

```bash
MODEL=my-model

mkdir -p eval_runs/$MODEL/oai/code_translation_n_sample_20

# PS symlink
ln -sfn "$(pwd)/benchmark/$MODEL/ps" \
        "$(pwd)/eval_runs/$MODEL/oai/prog_synthesis_n_sample_20"

# CT symlink
ln -sfn "$(pwd)/benchmark/$MODEL/ct_compact_small" \
        "$(pwd)/eval_runs/$MODEL/oai/code_translation_n_sample_20/compact_small"
```

### Step 3 · Score with ExecEval

Make sure ExecEval is running (`docker ps | grep execeval`), then:

```bash
MODEL=my-model

# Program Synthesis
DUMP_FOLDER=eval_runs/$MODEL \
  EXECEVAL_URL=http://localhost:5000 \
  python3 evaluation/program_synthesis/eval_program_synthesis.py \
  > benchmark/$MODEL/logs/eval_ps.log 2>&1 &

# Code Translation
DUMP_FOLDER=eval_runs/$MODEL \
  EXECEVAL_URL=http://localhost:5000 \
  python3 evaluation/code_translation/eval_code_translation.py \
  > benchmark/$MODEL/logs/eval_ct.log 2>&1 &
```

Scored output is written to:

- **PS** → `benchmark/$MODEL/ps/reproduce_1/<compiler>.jsonl`
- **CT** → `benchmark/$MODEL/ct_compact_small/eval_code_translation_compact_small_execeval/<compiler>.jsonl`

### Step 4 · Get results

```bash
MODEL=my-model

# pass@k for Program Synthesis
DUMP_FOLDER=eval_runs/$MODEL \
  python3 evaluation/program_synthesis/get_result.py

# pass@k for Code Translation
DUMP_FOLDER=eval_runs/$MODEL \
  python3 evaluation/code_translation/get_result.py
```

> [!TIP]
> If your model has only 1 sample per problem (n=1), `get_result.py` errors on `pass@5`.
> Use **`get_all_results.py`** instead — it computes both pass@1 and pass@5 automatically:
> ```bash
> python3 get_all_results.py
> ```

---

## 🔁 Re-running Eval Only

If generation files already exist in `benchmark/<model>/ps/` and `benchmark/<model>/ct_compact_small/`, you only need to re-score them — useful after fixing ExecEval container settings.

```bash
MODEL=my-model

# 1. Clear old scored output
rm -f benchmark/$MODEL/ps/reproduce_1/*.jsonl
rm -f benchmark/$MODEL/ct_compact_small/eval_code_translation_compact_small_execeval/*.jsonl

# 2. Verify symlinks exist (create if not)
ls eval_runs/$MODEL/oai/prog_synthesis_n_sample_20                  # → benchmark/$MODEL/ps
ls eval_runs/$MODEL/oai/code_translation_n_sample_20/compact_small  # → benchmark/$MODEL/ct_compact_small

# 3. Re-score
DUMP_FOLDER=eval_runs/$MODEL EXECEVAL_URL=http://localhost:5000 \
  python3 evaluation/program_synthesis/eval_program_synthesis.py \
  > benchmark/$MODEL/logs/eval_ps_rerun.log 2>&1 &

DUMP_FOLDER=eval_runs/$MODEL EXECEVAL_URL=http://localhost:5000 \
  python3 evaluation/code_translation/eval_code_translation.py \
  > benchmark/$MODEL/logs/eval_ct_rerun.log 2>&1 &
```

---

## 🗂 Repository Structure

```
xcodeEval/
│
├── benchmark/                        # All model data — generation + scored results
│   ├── RESULTS.txt                   # Full benchmark results with failure analysis
│   ├── RESULTS.pptx                  # Presentation deck of the results
│   ├── TOKEN_STATS.txt               # Token usage and API cost summary
│   │
│   └── <model>/                      # One directory per model
│       ├── ps/                       # Program Synthesis
│       │   ├── *.json                # Generation files (one per problem × language)
│       │   └── reproduce_1/          # ExecEval scored output
│       │       ├── GNU C++17.jsonl
│       │       ├── Go.jsonl
│       │       ├── Java 17.jsonl
│       │       ├── Kotlin 1.4.jsonl
│       │       ├── Node.js.jsonl
│       │       ├── PHP.jsonl
│       │       └── PyPy 3.jsonl
│       │
│       ├── ct_compact_small/         # Code Translation
│       │   ├── *.json                # Generation files
│       │   └── eval_code_translation_compact_small_execeval/
│       │       └── <compiler>.jsonl  # Scored output per target language
│       │
│       └── logs/                     # All run logs for this model
│           ├── gen_ps.log
│           ├── gen_ct.log
│           ├── eval_ps.log
│           └── eval_ct.log
│
├── eval_runs/                        # Symlink tree — eval scripts navigate here
│   └── <model>/
│       └── oai/
│           ├── prog_synthesis_n_sample_20/      → benchmark/<model>/ps/
│           └── code_translation_n_sample_20/
│               └── compact_small/               → benchmark/<model>/ct_compact_small/
│
├── dataset_subset/                   # Benchmark problems (no HuggingFace needed)
│   ├── ps_compact.jsonl              # 106 Program Synthesis problems
│   └── ct_compact_small.jsonl        # 440 Code Translation problems
│
├── baseline_filelist/                # Fixed problem subsets (same across all models)
│   ├── ps.txt                        # 560 PS (problem, language) pairs
│   └── ct.txt                        # 1689 CT (problem, src→tgt) pairs
│
├── apr_test_data/                    # APR test data (7 languages)
│
├── evaluation/                       # Eval and scoring scripts
│   ├── program_synthesis/
│   │   ├── gen_program_synthesis.py  # Generate PS outputs
│   │   ├── eval_program_synthesis.py # Score with ExecEval
│   │   └── get_result.py             # Compute pass@k
│   ├── code_translation/
│   │   ├── gen_code_translation.py
│   │   ├── eval_code_translation.py
│   │   └── get_result.py
│   └── apr/
│       ├── gen_apr.py
│       ├── eval_apr.py
│       └── get_result.py
│
├── gen_nemotron_baseline.py          # Main generation script (baseline-matched subset)
├── get_all_results.py                # Compute pass@1 + pass@5 for all models
├── get_token_stats.py                # Token usage and cost analysis
├── run_full_eval.sh                  # Run eval for all models sequentially
│
└── ExecEval/                         # Execution sandbox (Docker)
```

<details>
<summary><b>Data formats — generation JSON & scored JSONL</b></summary>

<br>

**Each generation JSON** (`benchmark/<model>/ps/*.json` or `ct_compact_small/*.json`):

```json
{
  "source_data": {
    "src_uid": "problem-id",
    "lang_cluster": "Python",
    "hidden_unit_tests": "[{\"input\": \"...\", \"output\": [\"...\"]}]"
  },
  "oai_response": {
    "choices": [
      {"message": {"content": "def solve(): ..."}}
    ],
    "usage": {
      "prompt_tokens": 1200,
      "completion_tokens": 340
    }
  }
}
```

**Each scored JSONL line** (`reproduce_1/<compiler>.jsonl`) adds `unit_test_results`:

```json
{
  "source_data": {...},
  "oai_response": {...},
  "unit_test_results": [
    [
      {"input": "5\n", "output": ["120"], "exec_outcome": "PASSED"},
      {"input": "0\n", "output": ["1"],   "exec_outcome": "WRONG_ANSWER"}
    ]
  ]
}
```

</details>

---

## ✅ Data Status

| Model | PS gen | PS scored | CT gen | CT scored |
|---|---|:---:|---|:---:|
| `claude-opus-5` | 560 files | ✅ | 1688 files | ✅ |
| `claude-sonnet-5` | 560 files | ✅ | 1688 files | ✅ |
| `gpt4o` (GPT-5.1) | 560 files | ✅ | 2804 files | ✅ |
| `gpt-5.6-sol` | 560 files | ✅ | 1688 files | ✅ |
| `nemotron-550b` | 736 files | ✅ | 1723 files | ✅ |
| `laguna-nvfp4` | 560 files | ✅ | 1688 files | ✅ |
| `qwen-nvfp4` | 404 files | ✅ | 1691 files | ✅ |

---

## 🧯 Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| Java/Kotlin/Go all 0% | ExecEval missing `--cap-add SYS_RESOURCE` | Recreate container with the flags in [Step 3](#3--start-execeval-execution-sandbox) |
| `MEMORY_LIMIT_EXCEEDED` dominant | `_as` virtual memory limit too low | Add `--ulimit memlock=-1` or rebuild with `_as = -1` in ExecEval config |
| `KeyError: DUMP_FOLDER` | Env var not exported | Use `export DUMP_FOLDER=...`, not inline assignment |
| `trust_remote_code` error | Wrong `datasets` version | `pip install "datasets==2.16.1"` |
| `pkg_resources` missing | `setuptools` too new | `pip install "setuptools<80"` |
| Generation stuck at 0% | Model endpoint unreachable | Test with `curl $OPENAI_API_BASE/models` |
| ExecEval OOM on Java/Kotlin | Too many workers | Reduce `NUM_WORKERS` to 8 or 4 in `docker run` |
| `lang_cluster` empty in PS files | Old generation format | Patch from filename (see `CLAUDE.md`) |
| `pass@5` KeyError in `get_result.py` | Only 1 sample per problem | Use `get_all_results.py`, which handles n=1 |

---

## 📝 Notes

- **Baseline subset** — all models are evaluated on the same fixed set of (problem, language) pairs defined in `baseline_filelist/`. **Do not modify these files.**
- **pass@5 vs pass@1** — Claude (API) and some on-prem models generate 1 sample per problem. GPT-5.1 generates 8, GPT-5.6-sol generates 5, on-prem models 5–20.
- **Determinism** — ExecEval scores code against hidden test cases (PASSED = all tests pass). Re-running eval on the same generation files yields identical scores.
- **Paper** — [xCodeEval: A Large Scale Multilingual Multitask Benchmark for Code Understanding, Generation, Translation and Retrieval](https://arxiv.org/abs/2303.03004)

<div align="center">
<sub>Execution-based · reproducible · baseline-matched — built on ExecEval.</sub>
</div>
