#!/usr/bin/env python3
"""
get_all_results.py — compute pass@1 (and pass@5 where n>=5) for all models,
both Program Synthesis (PS) and Code Translation (CT).

Usage:
    python3 get_all_results.py [--output RESULTS_ALL.txt]

Reads scored JSONL files from benchmark/<model>/ps/reproduce_1/ and
benchmark/<model>/ct_compact_small/eval_code_translation_compact_small_execeval/
"""

import os
import sys
import argparse
import itertools
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Union

import numpy as np
import jsonlines

BENCH = Path(__file__).parent / "benchmark"

LANG_TO_COMPILER = {
    "C":          "GNU C11",
    "C#":         "Mono C#",
    "C++":        "GNU C++17",
    "Go":         "Go",
    "Java":       "Java 17",
    "Javascript": "Node.js",
    "Kotlin":     "Kotlin 1.4",
    "PHP":        "PHP",
    "Python":     "PyPy 3",
    "Ruby":       "Ruby 3",
    "Rust":       "Rust 2018",
}

# Primary 7 languages shown in the summary table
PRIMARY_LANGS = ["C++", "Go", "Java", "Javascript", "Kotlin", "PHP", "Python"]

# Model display names and their benchmark folder names.
# pass5: True if the model has n>=5 samples (pass@5 is meaningful).
# n=1 models get pass@1 only.
MODELS = [
    {"key": "claude-opus-5",   "display": "Claude Opus 5",    "pass5": False},
    {"key": "claude-sonnet-5", "display": "Claude Sonnet 5",  "pass5": False},
    {"key": "gpt4o",           "display": "GPT-4o (gpt4o)",   "pass5": True},
    {"key": "nemotron-550b",   "display": "Nemotron-550B",    "pass5": True},
    {"key": "laguna-nvfp4",    "display": "Laguna NV-FP4",    "pass5": True},
    {"key": "qwen-nvfp4",      "display": "Qwen NV-FP4",      "pass5": True},
    {"key": "gpt-5.6-sol",    "display": "GPT-5.6 (sol)",    "pass5": True},
    # Ultra added separately after re-run is copied into benchmark/
    {"key": "ultra",           "display": "Nemo Ultra",       "pass5": False},
]


def estimate_pass_at_k(
    num_samples: Union[int, List[int], np.ndarray],
    num_correct: Union[List[int], np.ndarray],
    k: int,
) -> np.ndarray:
    def estimator(n: int, c: int, k: int) -> float:
        if n - c < k:
            return 1.0
        return 1.0 - float(np.prod(1.0 - k / np.arange(n - c + 1, n + 1)))

    if isinstance(num_samples, int):
        it = itertools.repeat(num_samples, len(num_correct))
    else:
        assert len(num_samples) == len(num_correct)
        it = iter(num_samples)

    return np.array([estimator(int(n), int(c), k) for n, c in zip(it, num_correct)])


def read_ps_results(model_key: str):
    """
    Returns {lang: (total_arr, correct_arr)} for Program Synthesis.
    Reads from benchmark/<model>/ps/reproduce_1/<compiler>.jsonl
    """
    base = BENCH / model_key / "ps" / "reproduce_1"
    out = {}
    for lang, compiler in LANG_TO_COMPILER.items():
        fpath = base / f"{compiler}.jsonl"
        if not fpath.exists():
            continue
        results = defaultdict(list)
        with jsonlines.open(fpath) as jrp:
            for sample in jrp:
                src_uid = sample["source_data"]["src_uid"]
                task_id = f"{src_uid}|||{lang}"
                for ut_res in sample["unit_test_results"]:
                    if "error" in ut_res:
                        continue
                    results[task_id].append(ut_res)
        if not results:
            continue
        total, correct = [], []
        for result in results.values():
            passed = [all(x["exec_outcome"] == "PASSED" for x in ut_res)
                      for ut_res in result]
            total.append(len(passed))
            correct.append(sum(passed))
        out[lang] = (np.array(total), np.array(correct))
    return out


def read_ct_results(model_key: str):
    """
    Returns {lang: (total_arr, correct_arr)} for Code Translation.
    Reads from benchmark/<model>/ct_compact_small/eval_code_translation_compact_small_execeval/<compiler>.jsonl
    """
    base = BENCH / model_key / "ct_compact_small" / "eval_code_translation_compact_small_execeval"
    out = {}
    for lang, compiler in LANG_TO_COMPILER.items():
        fpath = base / f"{compiler}.jsonl"
        if not fpath.exists():
            continue
        results = defaultdict(list)
        with jsonlines.open(fpath) as jrp:
            for sample in jrp:
                src_uid = sample["source_data"]["src_uid"]
                task_id = f"{src_uid}|||{lang}"
                for ut_res in sample["unit_test_results"]:
                    if "error" in ut_res:
                        continue
                    results[task_id].append(ut_res)
        if not results:
            continue
        total, correct = [], []
        for result in results.values():
            passed = [all(x["exec_outcome"] == "PASSED" for x in ut_res)
                      for ut_res in result]
            total.append(len(passed))
            correct.append(sum(passed))
        out[lang] = (np.array(total), np.array(correct))
    return out


def compute_metrics(lang_data: dict, want_pass5: bool):
    """
    For each lang, compute pass@1 (always) and pass@5 (if want_pass5 and n>=5 everywhere).
    Returns {lang: {"pass@1": float, "pass@5": float|None, "n": int, "problems": int}}
    """
    metrics = {}
    for lang, (total, correct) in lang_data.items():
        if len(total) == 0:
            continue
        p1 = float(estimate_pass_at_k(total, correct, 1).mean())
        p5 = None
        if want_pass5 and (total >= 5).all():
            p5 = float(estimate_pass_at_k(total, correct, 5).mean())
        metrics[lang] = {
            "pass@1":    p1,
            "pass@5":    p5,
            "n":         int(total[0]),   # samples per problem (first problem as proxy)
            "problems":  len(total),
        }
    return metrics


def fmt(val, pct=True):
    if val is None:
        return "  —   "
    s = f"{val*100:.1f}%"
    return s.rjust(6)


def build_table(task_label: str, model_cfgs: list, all_metrics: dict, langs: list):
    lines = []
    sep = "─" * 96
    lines.append(sep)
    lines.append(f"  {task_label}")
    lines.append(sep)

    # Header
    hdr = f"  {'Model':<26}  {'n':>3}  "
    for lang in langs:
        hdr += f"  {lang[:7]:>8}"
    hdr += f"  {'Avg':>8}"
    lines.append(hdr)

    # Pass@1 block
    lines.append(f"\n  pass@1")
    lines.append("  " + "-" * 93)
    for cfg in model_cfgs:
        key = cfg["key"]
        if key not in all_metrics:
            continue
        met = all_metrics[key]
        n_val = next((m["n"] for m in met.values()), "?")
        row = f"  {cfg['display']:<26}  {n_val:>3}  "
        vals = []
        for lang in langs:
            if lang in met:
                v = met[lang]["pass@1"]
                row += f"  {fmt(v):>8}"
                vals.append(v)
            else:
                row += f"  {'—':>8}"
        avg = np.mean(vals) if vals else None
        row += f"  {fmt(avg):>8}"
        lines.append(row)

    # Pass@5 block (only models that have it)
    pass5_models = [c for c in model_cfgs if c.get("pass5") and c["key"] in all_metrics]
    if pass5_models:
        lines.append(f"\n  pass@5  (unbiased estimator from n samples)")
        lines.append("  " + "-" * 93)
        for cfg in pass5_models:
            key = cfg["key"]
            met = all_metrics[key]
            n_val = next((m["n"] for m in met.values()), "?")
            row = f"  {cfg['display']:<26}  {n_val:>3}  "
            vals = []
            for lang in langs:
                if lang in met and met[lang]["pass@5"] is not None:
                    v = met[lang]["pass@5"]
                    row += f"  {fmt(v):>8}"
                    vals.append(v)
                else:
                    row += f"  {'—':>8}"
            avg = np.mean(vals) if vals else None
            row += f"  {fmt(avg):>8}"
            lines.append(row)

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="benchmark/RESULTS_ALL.txt")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    out_lines = []
    out_lines.append("=" * 96)
    out_lines.append("  xcodeEval — pass@1 and pass@5 Results")
    out_lines.append(f"  Generated : {now}")
    out_lines.append("=" * 96)
    out_lines.append("")
    out_lines.append("  pass@1: unbiased estimator (= c/n exactly when k=1)")
    out_lines.append("  pass@5: unbiased estimator 1 - C(n-c,5)/C(n,5), requires n>=5 per problem")
    out_lines.append("  —     : model has n<5 samples (pass@5 not applicable) or results not yet available")
    out_lines.append("")

    # ── PS ──
    ps_metrics = {}
    print("Reading PS results...")
    for cfg in MODELS:
        key = cfg["key"]
        model_dir = BENCH / key
        if not model_dir.exists():
            print(f"  {key}: benchmark folder not found, skipping")
            continue
        data = read_ps_results(key)
        if not data:
            print(f"  {key} PS: no scored JSONL files found")
            continue
        ps_metrics[key] = compute_metrics(data, cfg["pass5"])
        n_val = next((m["n"] for m in ps_metrics[key].values()), "?")
        langs_found = sorted(ps_metrics[key].keys())
        print(f"  {key} PS: {len(langs_found)} langs, n={n_val}")

    # ── CT ──
    ct_metrics = {}
    print("\nReading CT results...")
    for cfg in MODELS:
        key = cfg["key"]
        model_dir = BENCH / key
        if not model_dir.exists():
            continue
        data = read_ct_results(key)
        if not data:
            print(f"  {key} CT: no scored JSONL files found")
            continue
        ct_metrics[key] = compute_metrics(data, cfg["pass5"])
        n_val = next((m["n"] for m in ct_metrics[key].values()), "?")
        langs_found = sorted(ct_metrics[key].keys())
        print(f"  {key} CT: {len(langs_found)} langs, n={n_val}")

    present_models = [c for c in MODELS if c["key"] in ps_metrics or c["key"] in ct_metrics]

    out_lines.append(build_table("PROGRAM SYNTHESIS (PS)", present_models, ps_metrics, PRIMARY_LANGS))
    out_lines.append(build_table("CODE TRANSLATION (CT)", present_models, ct_metrics, PRIMARY_LANGS))

    # Per-model n summary
    out_lines.append("─" * 96)
    out_lines.append("  Samples per problem (n)")
    out_lines.append("─" * 96)
    for cfg in present_models:
        key = cfg["key"]
        ps_n = next((m["n"] for m in ps_metrics.get(key, {}).values()), "—")
        ct_n = next((m["n"] for m in ct_metrics.get(key, {}).values()), "—")
        out_lines.append(f"  {cfg['display']:<26}  PS n={ps_n}  CT n={ct_n}  pass5={'yes' if cfg['pass5'] else 'no (n=1)'}")

    output = "\n".join(out_lines) + "\n"

    outpath = Path(__file__).parent / args.output
    outpath.parent.mkdir(parents=True, exist_ok=True)
    outpath.write_text(output)
    print(f"\nResults written to {outpath}")
    print("\n" + output)


if __name__ == "__main__":
    main()
