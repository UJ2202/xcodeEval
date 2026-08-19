"""
Compute compilation pass@k from eval_apr_compile.py output.
"Pass" = the generated fix did NOT get COMPILATION_ERROR.
"""

import os
import numpy as np
import jsonlines
import tqdm
import itertools
from collections import defaultdict
from typing import List, Union

LANG_CLUSTER_TO_LANG_COMPILER = {
    "C": "GNU C11",
    "C#": "Mono C#",
    "C++": "GNU C++17",
    "Go": "Go",
    "Java": "Java 17",
    "Javascript": "Node.js",
    "Kotlin": "Kotlin 1.4",
    "PHP": "PHP",
    "Python": "PyPy 3",
    "Ruby": "Ruby 3",
    "Rust": "Rust 2018",
}

path = f'{os.environ["DUMP_FOLDER"]}/oai/apr_n_sample_20/eval_apr_compile_execeval/'
ks = [1, 5, 10]


def estimate_pass_at_k(num_samples, num_correct, k):
    def estimator(n, c, k):
        if n - c < k:
            return 1.0
        return 1.0 - np.prod(1.0 - k / np.arange(n - c + 1, n + 1))
    if isinstance(num_samples, int):
        num_samples_it = itertools.repeat(num_samples, len(num_correct))
    else:
        num_samples_it = iter(num_samples)
    return np.array([estimator(int(n), int(c), k) for n, c in zip(num_samples_it, num_correct)])


pass_at_k = defaultdict(dict)

for lang, compiler in tqdm.tqdm(LANG_CLUSTER_TO_LANG_COMPILER.items()):
    fpath = os.path.join(path, f"{compiler}.jsonl")
    if not os.path.exists(fpath):
        continue
    results = defaultdict(list)
    with jsonlines.open(fpath) as jrp:
        for sample in jrp:
            src_uid = sample["source_data"]["src_uid"]
            task_id = f"{src_uid}|||{lang}"
            for ut_res in sample["unit_test_results"]:
                results[task_id].append(ut_res)

    total, correct = [], []
    for result in results.values():
        # "pass" = not COMPILATION_ERROR for ANY test result in the run
        passed = []
        for ut_res in result:
            if isinstance(ut_res, list):
                compiled = all(r.get("exec_outcome", "") != "COMPILATION_ERROR" for r in ut_res)
            else:
                compiled = ut_res.get("exec_outcome", "") != "COMPILATION_ERROR"
            passed.append(compiled)
        total.append(len(passed))
        correct.append(sum(passed))

    total = np.array(total)
    correct = np.array(correct)
    pass_at_k[lang] = {
        f"compile_pass@{k}": estimate_pass_at_k(total, correct, k).mean()
        for k in ks
        if len(total) > 0 and (total >= k).all()
    }

print("\n=== APR Compilation Pass@k (no hidden tests) ===")
langs = sorted(pass_at_k.keys())
for lang in langs:
    scores = pass_at_k[lang]
    score_str = "  ".join(f"{m}={round(v*100, 2)}%" for m, v in scores.items())
    print(f"  {lang:12s}  {score_str}")

if langs:
    for k in ks:
        key = f"compile_pass@{k}"
        vals = [pass_at_k[l][key] for l in langs if key in pass_at_k[l]]
        if vals:
            print(f"\n  Average compile_pass@{k}: {round(np.mean(vals)*100, 2)}%")
