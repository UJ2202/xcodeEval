#!/usr/bin/env python3
"""
Token consumption and cost analysis across all xcodeEval models.
Reads generation JSON files from benchmark/<model>/ps/ and benchmark/<model>/ct_compact_small/
Outputs TOKEN_STATS.txt in the benchmark directory.
"""

import json
import glob
from pathlib import Path

BENCH = Path(__file__).parent / "benchmark"

# Pricing per 1M tokens (input, output)
# Claude: exact Anthropic API rates (2026-08-20, intro pricing still active through 2026-08-31)
# OpenAI: approximate — update if exact Azure/OpenAI rates are known
# On-prem NV models: infrastructure cost, not per-token API pricing
PRICING = {
    # model_key: (input_per_1M, output_per_1M, note)
    "claude-opus-5":    (5.00,  25.00, "Anthropic API"),
    "claude-sonnet-5":  (2.00,  10.00, "Anthropic API (intro rate, expires 2026-08-31)"),
    "gpt4o":            (2.00,   8.00, "GPT-5.1 via Azure (approx.)"),
    "gpt-5.6-sol":      (5.00,  20.00, "GPT-5.6-sol via Azure (approx.)"),
    "nemotron-550b":    (None,  None,  "On-prem vLLM (infra cost)"),
    "laguna-nvfp4":     (None,  None,  "On-prem vLLM (infra cost)"),
    "qwen-nvfp4":       (None,  None,  "On-prem vLLM (infra cost)"),
    "ultra":            (None,  None,  "On-prem vLLM (infra cost)"),
}

MODELS = [
    {"key": "claude-opus-5",   "display": "Claude Opus 5",        "actual_model": "claude-opus-5"},
    {"key": "claude-sonnet-5", "display": "Claude Sonnet 5",      "actual_model": "azure_ai/claude-sonnet-5"},
    {"key": "gpt4o",           "display": "GPT-5.1 (dep: gpt4o)", "actual_model": "gpt4o"},
    {"key": "gpt-5.6-sol",     "display": "GPT-5.6-sol",          "actual_model": "gpt-5.6-sol-2026-07-09"},
    {"key": "nemotron-550b",   "display": "Nemotron-550B",        "actual_model": "nvidia/nemotron-3-ultra-550b-a55b"},
    {"key": "laguna-nvfp4",    "display": "Laguna NV-FP4",        "actual_model": "laguna-nvfp4"},
    {"key": "qwen-nvfp4",      "display": "Qwen NV-FP4",          "actual_model": "qwen-nvfp4"},
    {"key": "ultra",           "display": "Nemo Ultra",           "actual_model": "N/A"},
]


def collect_token_stats(files):
    """Return dict with aggregated token counts from a list of JSON files."""
    total_prompt = 0
    total_completion = 0
    total_cached = 0
    total_cache_write = 0
    n_files = 0
    n_samples_total = 0

    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        oai = d.get("oai_response") or {}
        usage = oai.get("usage") or {}
        if not usage:
            continue

        prompt = usage.get("prompt_tokens", 0) or 0
        completion = usage.get("completion_tokens", 0) or 0
        cached = usage.get("cached_tokens", usage.get("cache_read_input_tokens", 0)) or 0
        cache_write = usage.get("cache_write_tokens", usage.get("cache_creation_input_tokens", 0)) or 0

        # Also check nested prompt_tokens_details for OpenAI cache
        ptd = usage.get("prompt_tokens_details", {})
        if ptd and not cached:
            cached = ptd.get("cached_tokens", 0) or 0

        n_samples = len(oai.get("choices", [])) or 1

        total_prompt += prompt
        total_completion += completion
        total_cached += cached
        total_cache_write += cache_write
        n_files += 1
        n_samples_total += n_samples

    return {
        "files": n_files,
        "prompt": total_prompt,
        "completion": total_completion,
        "cached": total_cached,
        "cache_write": total_cache_write,
        "n_samples": n_samples_total,
        "avg_prompt": total_prompt / n_files if n_files else 0,
        "avg_completion": total_completion / n_files if n_files else 0,
        "avg_n": n_samples_total / n_files if n_files else 0,
    }


def compute_cost(prompt_tokens, completion_tokens, pricing_key):
    inp_rate, out_rate, note = PRICING[pricing_key]
    if inp_rate is None:
        return None, None, note
    inp_cost = prompt_tokens / 1_000_000 * inp_rate
    out_cost = completion_tokens / 1_000_000 * out_rate
    return inp_cost, out_cost, note


def fmt_tokens(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def fmt_cost(c, blank_if_none=False):
    if c is None:
        return "" if blank_if_none else "N/A (infra)"
    return f"${c:.2f}"


def main():
    lines = []
    lines.append("=" * 100)
    lines.append("  xcodeEval — TOKEN CONSUMPTION & COST ANALYSIS")
    lines.append("=" * 100)
    lines.append("")

    summary_rows = []

    for m in MODELS:
        key = m["key"]
        display = m["display"]

        ps_files = glob.glob(str(BENCH / key / "ps" / "*.json"))
        ct_files = glob.glob(str(BENCH / key / "ct_compact_small" / "*.json"))

        ps = collect_token_stats(ps_files)
        ct = collect_token_stats(ct_files)

        inp_rate, out_rate, pricing_note = PRICING[key]

        lines.append(f"{'─'*100}")
        lines.append(f"  Model: {display}  |  Actual: {m['actual_model']}")
        lines.append(f"  Pricing: {pricing_note}")
        if inp_rate is not None:
            lines.append(f"  Rates:   ${inp_rate:.2f}/1M input   ${out_rate:.2f}/1M output")
        lines.append("")

        # PS section
        if ps["files"] > 0:
            ps_inp_cost, ps_out_cost, _ = compute_cost(ps["prompt"], ps["completion"], key)
            ps_total_cost = (ps_inp_cost + ps_out_cost) if ps_inp_cost is not None else None
            lines.append(f"  [PS — Program Synthesis]  files={ps['files']}  avg_n={ps['avg_n']:.1f} samples/file")
            lines.append(f"    Total prompt tokens    : {fmt_tokens(ps['prompt']):>10}  (avg/file: {fmt_tokens(int(ps['avg_prompt']))})")
            lines.append(f"    Total completion tokens: {fmt_tokens(ps['completion']):>10}  (avg/file: {fmt_tokens(int(ps['avg_completion']))})")
            if ps["cached"] > 0:
                lines.append(f"    Cached input tokens    : {fmt_tokens(ps['cached']):>10}")
            if ps["cache_write"] > 0:
                lines.append(f"    Cache write tokens     : {fmt_tokens(ps['cache_write']):>10}")
            lines.append(f"    Cost  → input: {fmt_cost(ps_inp_cost, True):>12}  output: {fmt_cost(ps_out_cost, True):>12}  total: {fmt_cost(ps_total_cost, True):>12}")
        else:
            ps_total_cost = None
            lines.append(f"  [PS]  No generation files found.")

        lines.append("")

        # CT section
        if ct["files"] > 0:
            ct_inp_cost, ct_out_cost, _ = compute_cost(ct["prompt"], ct["completion"], key)
            ct_total_cost = (ct_inp_cost + ct_out_cost) if ct_inp_cost is not None else None
            lines.append(f"  [CT — Code Translation]  files={ct['files']}  avg_n={ct['avg_n']:.1f} samples/file")
            lines.append(f"    Total prompt tokens    : {fmt_tokens(ct['prompt']):>10}  (avg/file: {fmt_tokens(int(ct['avg_prompt']))})")
            lines.append(f"    Total completion tokens: {fmt_tokens(ct['completion']):>10}  (avg/file: {fmt_tokens(int(ct['avg_completion']))})")
            if ct["cached"] > 0:
                lines.append(f"    Cached input tokens    : {fmt_tokens(ct['cached']):>10}")
            if ct["cache_write"] > 0:
                lines.append(f"    Cache write tokens     : {fmt_tokens(ct['cache_write']):>10}")
            lines.append(f"    Cost  → input: {fmt_cost(ct_inp_cost, True):>12}  output: {fmt_cost(ct_out_cost, True):>12}  total: {fmt_cost(ct_total_cost, True):>12}")
        else:
            ct_total_cost = None
            lines.append(f"  [CT]  No generation files found.")

        lines.append("")

        # Combined
        combined_prompt = ps["prompt"] + ct["prompt"]
        combined_completion = ps["completion"] + ct["completion"]
        if ps["files"] + ct["files"] > 0:
            ci, co, _ = compute_cost(combined_prompt, combined_completion, key)
            combined_cost = (ci + co) if ci is not None else None
            lines.append(f"  [COMBINED PS+CT]")
            lines.append(f"    Total prompt tokens    : {fmt_tokens(combined_prompt):>10}")
            lines.append(f"    Total completion tokens: {fmt_tokens(combined_completion):>10}")
            lines.append(f"    Total cost             : {fmt_cost(combined_cost, True):>12}")
        else:
            combined_cost = None
            ci = co = None
            lines.append(f"  [COMBINED]  No files found.")

        lines.append("")

        summary_rows.append({
            "display": display,
            "ps_files": ps["files"],
            "ct_files": ct["files"],
            "ps_n": ps["avg_n"],
            "ct_n": ct["avg_n"],
            "ps_prompt": ps["prompt"],
            "ps_compl": ps["completion"],
            "ct_prompt": ct["prompt"],
            "ct_compl": ct["completion"],
            "tot_prompt": combined_prompt,
            "tot_compl": combined_completion,
            "ps_cost": ps_total_cost,
            "ct_cost": ct_total_cost,
            "combined_cost": combined_cost,
            "pricing_note": pricing_note,
        })

    # Summary table split by PS and CT
    col_m = 24
    col_s =  5   # n per file
    col_t = 20   # input / output tokens
    col_r = 18   # rate
    col_c = 12   # cost

    def table_header():
        return (
            f"{'Model':<{col_m}} {'n':>{col_s}} {'Input / Output Tokens':^{col_t}} "
            f"{'Rate /1M (in/out)':^{col_r}} {'Cost':>{col_c}}"
        )

    def table_row(display, n, files, inp_tok, out_tok, inp_rate, out_rate, cost):
        tok_str    = f"{fmt_tokens(inp_tok)} / {fmt_tokens(out_tok)}"
        rate_str   = f"${inp_rate:.2f} / ${out_rate:.2f}" if inp_rate is not None else "— / —"
        cost_str   = fmt_cost(cost, True) if inp_rate is not None else "—"
        n_str      = str(int(n)) if n else "—"
        return (
            f"{display:<{col_m}} {n_str:>{col_s}} {tok_str:^{col_t}} "
            f"{rate_str:^{col_r}} {cost_str:>{col_c}}"
        )

    sep = "─" * (col_m + col_s + col_t + col_r + col_c + 4)

    total_combined_cost = 0.0
    summary_lines = []  # collect just the table portion for appending to RESULTS.txt

    for task_label, prompt_key, compl_key, files_key, n_key, cost_key in [
        ("PROGRAM SYNTHESIS (PS)", "ps_prompt", "ps_compl", "ps_files", "ps_n", "ps_cost"),
        ("CODE TRANSLATION (CT)",  "ct_prompt", "ct_compl", "ct_files", "ct_n", "ct_cost"),
    ]:
        block = []
        block.append("=" * 100)
        block.append(f"  TOKEN & COST SUMMARY — {task_label}")
        block.append("=" * 100)
        block.append("")
        block.append(table_header())
        block.append(sep)

        task_api_cost = 0.0
        for r in summary_rows:
            mkey = next(m["key"] for m in MODELS if m["display"] == r["display"])
            inp_rate, out_rate, _ = PRICING[mkey]
            n_val   = r.get(n_key, 0)
            files   = r.get(files_key, 0)
            inp_tok = r[prompt_key]
            out_tok = r[compl_key]
            cost    = r[cost_key]
            block.append(table_row(r["display"], n_val, files, inp_tok, out_tok, inp_rate, out_rate, cost))
            if cost is not None:
                task_api_cost += cost

        block.append(sep)
        block.append(
            f"{'TOTAL (API models only)':<{col_m}} {'':>{col_s}} {'':^{col_t}} "
            f"{'':^{col_r}} {'$'+f'{task_api_cost:.2f}':>{col_c}}"
        )
        block.append("")
        total_combined_cost += task_api_cost

        lines.extend(block)
        summary_lines.extend(block)

    footer = [
        "=" * 100,
        f"  GRAND TOTAL API COST (PS + CT, Claude + OpenAI): ${total_combined_cost:.2f}",
        "=" * 100,
        "",
    ]
    lines.extend(footer)
    summary_lines.extend(footer)

    # Grand totals across ALL models
    grand_prompt    = sum(r["tot_prompt"] for r in summary_rows)
    grand_compl     = sum(r["tot_compl"]  for r in summary_rows)
    onprem_prompt   = sum(r["tot_prompt"] for r in summary_rows if r["combined_cost"] is None)
    onprem_compl    = sum(r["tot_compl"]  for r in summary_rows if r["combined_cost"] is None)
    api_prompt      = sum(r["tot_prompt"] for r in summary_rows if r["combined_cost"] is not None)
    api_compl       = sum(r["tot_compl"]  for r in summary_rows if r["combined_cost"] is not None)

    lines.append("")
    lines.append("  TOKEN TOTALS ACROSS ALL MODELS:")
    lines.append(f"  {'':30} {'Prompt':>14} {'Completion':>14} {'Combined':>14}")
    lines.append(f"  {'─'*74}")
    lines.append(f"  {'API models (Claude + OpenAI)':<30} {fmt_tokens(api_prompt):>14} {fmt_tokens(api_compl):>14} {fmt_tokens(api_prompt+api_compl):>14}")
    lines.append(f"  {'On-prem (Nemotron+Laguna+Qwen+Ultra)':<30} {fmt_tokens(onprem_prompt):>14} {fmt_tokens(onprem_compl):>14} {fmt_tokens(onprem_prompt+onprem_compl):>14}")
    lines.append(f"  {'─'*74}")
    lines.append(f"  {'GRAND TOTAL (all models)':<30} {fmt_tokens(grand_prompt):>14} {fmt_tokens(grand_compl):>14} {fmt_tokens(grand_prompt+grand_compl):>14}")
    lines.append("")
    lines.append(f"  Total API cost (Claude + OpenAI models only): ${total_combined_cost:.2f}")
    lines.append(f"  On-prem models: infrastructure/GPU cost — not billed per token")
    lines.append("")
    lines.append("  Notes:")
    lines.append("  - OpenAI pricing is approximate; verify actual Azure invoice rates")
    lines.append("  - Claude Sonnet 5 intro rate ($2/$10 per 1M) active through 2026-08-31")
    lines.append("  - gpt4o = Azure deployment name; actual model = GPT-5.1")
    lines.append("  - gpt-5.6-sol actual model = gpt-5.6-sol-2026-07-09")
    lines.append("  - ultra PS generation not yet complete (0 files); rerun after ultra finishes")
    lines.append("=" * 100)

    out_text = "\n".join(lines)
    print(out_text)

    out_path = BENCH / "TOKEN_STATS.txt"
    out_path.write_text(out_text)
    print(f"\nSaved to {out_path}")

    # Append summary tables to RESULTS.txt
    results_path = BENCH / "RESULTS.txt"
    if results_path.exists():
        existing = results_path.read_text()
        # Strip any previously appended token section
        marker = "\n\n" + "=" * 100 + "\n  TOKEN & COST SUMMARY"
        if marker in existing:
            existing = existing[:existing.index(marker)]
        results_path.write_text(existing.rstrip() + "\n\n\n" + "\n".join(summary_lines))
        print(f"Appended token/cost tables to {results_path}")
    else:
        print(f"Warning: {results_path} not found — skipping append")


if __name__ == "__main__":
    main()
