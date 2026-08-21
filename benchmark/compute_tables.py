import os, json
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))

MODELS = [
    ("claude-opus-5",   "Claude Opus 5"),
    ("claude-sonnet-5", "Claude Sonnet 5"),
    ("gpt-5.6-sol",     "GPT-5.6-sol"),
    ("gpt4o",           "GPT-5.1 (gpt4o)"),
    ("laguna-nvfp4",    "Laguna NV-FP4"),
    ("nemotron-550b",   "Nemotron-550B"),
    ("qwen-nvfp4",      "Qwen NV-FP4"),
]

# display language -> ExecEval compiler filename
LANGS = [
    ("C++",        "GNU C++17"),
    ("Go",         "Go"),
    ("Java",       "Java 17"),
    ("Javascript", "Node.js"),
    ("Kotlin",     "Kotlin 1.4"),
    ("PHP",        "PHP"),
    ("Python",     "PyPy 3"),
]

def ps_path(model, compiler):
    return os.path.join(BASE, model, "ps", "reproduce_1", f"{compiler}.jsonl")

def ct_path(model, compiler):
    return os.path.join(BASE, model, "ct_compact_small",
                        "eval_code_translation_compact_small_execeval", f"{compiler}.jsonl")

def estimator(n, c, k):
    if n - c < k:
        return 1.0
    p = 1.0
    for i in range(n - c + 1, n + 1):
        p *= (1.0 - k / i)
    return 1.0 - p

def compute(path):
    """Return dict with pass@1, pass@5 (or None), and #problems."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    results = defaultdict(list)
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            sample = json.loads(line)
            src_uid = sample["source_data"]["src_uid"]
            task_id = src_uid  # per-lang file already, so uid is enough
            for ut_res in sample["unit_test_results"]:
                if isinstance(ut_res, dict) and "error" in ut_res:
                    continue
                results[task_id].append(ut_res)
    if not results:
        return None
    total, correct = [], []
    for res in results.values():
        passed = [all(x["exec_outcome"] == "PASSED" for x in ut_res) for ut_res in res]
        total.append(len(passed))
        correct.append(sum(passed))

    def pass_at_k(k):
        if not all(t >= k for t in total):
            return None
        vals = [estimator(t, c, k) for t, c in zip(total, correct)]
        return 100.0 * sum(vals) / len(vals)

    return {
        "pass@1": pass_at_k(1),
        "pass@5": pass_at_k(5),
        "nprob": len(total),
        "nsample_min": min(total),
        "nsample_max": max(total),
    }

# collect
data = {}  # (task, model, lang) -> result
for model, _ in MODELS:
    for lang, compiler in LANGS:
        data[("PS", model, lang)] = compute(ps_path(model, compiler))
        data[("CT", model, lang)] = compute(ct_path(model, compiler))

def fmt(v):
    return f"{v:.1f}" if v is not None else "—"

def print_table(task, metric):
    header = ["Model"] + [l for l, _ in LANGS]
    rows = []
    for model, disp in MODELS:
        row = [disp]
        for lang, _ in LANGS:
            r = data[(task, model, lang)]
            row.append(fmt(r[metric]) if r else "—")
        rows.append(row)
    # markdown
    print(f"\n### {task} — {metric}\n")
    print("| " + " | ".join(header) + " |")
    print("|" + "|".join(["---"] * len(header)) + "|")
    for row in rows:
        print("| " + " | ".join(row) + " |")

for task in ("PS", "CT"):
    for metric in ("pass@1", "pass@5"):
        print_table(task, metric)

# diagnostics: sample counts per model/task
print("\n\n### sample-count diagnostics (min..max samples per problem)\n")
print("| Model | PS n | CT n |")
print("|---|---|---|")
for model, disp in MODELS:
    def nrange(task):
        rs = [data[(task, model, l)] for l, _ in LANGS if data[(task, model, l)]]
        if not rs:
            return "—"
        lo = min(r["nsample_min"] for r in rs)
        hi = max(r["nsample_max"] for r in rs)
        return f"{lo}" if lo == hi else f"{lo}..{hi}"
    print(f"| {disp} | {nrange('PS')} | {nrange('CT')} |")
