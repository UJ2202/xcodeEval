import os, json
from collections import defaultdict, Counter

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
LANGS = [
    ("C++", "GNU C++17"), ("Go", "Go"), ("Java", "Java 17"),
    ("Javascript", "Node.js"), ("Kotlin", "Kotlin 1.4"),
    ("PHP", "PHP"), ("Python", "PyPy 3"),
]

def ps_path(m, c):
    return os.path.join(BASE, m, "ps", "reproduce_1", f"{c}.jsonl")
def ct_path(m, c):
    return os.path.join(BASE, m, "ct_compact_small",
                        "eval_code_translation_compact_small_execeval", f"{c}.jsonl")

def breakdown(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    nprob = 0
    nsamples = []
    fail = Counter()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            s = json.loads(line)
            utr = s["unit_test_results"]
            nprob += 1
            nsamples.append(len(utr))
            for attempt in utr:  # one attempt = list of test results
                if isinstance(attempt, dict) and "error" in attempt:
                    continue
                # did this attempt pass all tests?
                first_fail = None
                allpass = True
                for t in attempt:
                    if t["exec_outcome"] != "PASSED":
                        allpass = False
                        if first_fail is None:
                            first_fail = t["exec_outcome"]
                if not allpass:
                    fail[first_fail or "UNKNOWN"] += 1
    return {"nprob": nprob, "nsamples": nsamples, "fail": fail}

for m, disp in MODELS:
    print("#"*80)
    print(f"MODEL {disp} ({m})")
    for task, pf in (("PS", ps_path), ("CT", ct_path)):
        print(f"  -- {task} --")
        for lang, comp in LANGS:
            b = breakdown(pf(m, comp))
            if not b:
                print(f"    {lang:11} : (no data)")
                continue
            ns = b["nsamples"]
            nrange = f"{min(ns)}" if min(ns)==max(ns) else f"{min(ns)}..{max(ns)}"
            fails = ", ".join(f"{k}={v}" for k,v in b["fail"].most_common())
            print(f"    {lang:11} : {b['nprob']:3} probs, n={nrange:6} fails[{fails}]")
