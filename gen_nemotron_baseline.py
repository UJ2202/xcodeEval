"""
Generate nvidia/nemotron-3-ultra-550b-a55b outputs ONLY for baseline files.
Baseline = filenames in dumped/baseline/gpt4o/<task>/

PS:  106 problems × N languages → check each against baseline set
CT:  440 compact_small problems × N target langs → check against baseline set
APR: 17699 rows → check against baseline set

Usage (run 3 in parallel):
  XCODEEVAL_MODEL=nvidia/nemotron-3-ultra-550b-a55b python3 gen_nemotron_baseline.py ps
  XCODEEVAL_MODEL=nvidia/nemotron-3-ultra-550b-a55b python3 gen_nemotron_baseline.py ct
  XCODEEVAL_MODEL=nvidia/nemotron-3-ultra-550b-a55b python3 gen_nemotron_baseline.py apr
"""
import os, sys, time, json, openai, datasets, concurrent.futures, tqdm
from promptsource.templates import Template

openai.api_key  = os.environ.get("OPENAI_API_KEY", "sk-local-dev")
openai.api_base = os.environ.get("OPENAI_API_BASE", "http://localhost:4000")
MODEL      = os.environ.get("XCODEEVAL_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
NSAMPLE    = int(os.environ.get("NSAMPLE", "5"))
MAX_TOKENS = 4096
NUM_WORKERS = int(os.environ.get("NUM_PROC", "16"))

BASELINE_ROOT = "/home/ujjwal.tiwari/ace/benchmarks/xcodeEval/dumped/baseline/gpt4o"
# Set MODEL_OUT_NAME to name the output dir (e.g. "llama-4-scout"); defaults to nemotron-550b
_model_out = os.environ.get("MODEL_OUT_NAME", "nemotron-550b")
OUT_ROOT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "dumped", _model_out
)
TEMP = 1

# When set, load PS/CT from local JSONL and use filelist/ instead of scanning BASELINE_ROOT.
# Set to the dataset_subset/ directory on the repo.  Leave unset to use HF cache + live dir scan.
DATA_DIR     = os.environ.get("XCODEEVAL_DATA_DIR", None)
FILELIST_DIR = os.environ.get("XCODEEVAL_FILELIST_DIR", None)

SHORT_LANG_MAP = {
    "GNU C++17": "C++", "GNU C++": "C++", "MS C++ 2017": "C++",
    "GNU C++14": "C++", "GNU C++11": "C++", "GNU C++0x": "C++",
    "GNU C++17 (64)": "C++", "GNU C++20 (64)": "C++",
    "Clang++17 Diagnostics": "C++", "Clang++20 Diagnostics": "C++",
    "GNU C++17 Diagnostics": "C++",
    "Java 8": "Java", "Java 6": "Java", "Java 11": "Java",
    "Java 17": "Java", "Java 7": "Java",
    "GNU C11": "C", "GNU C": "C",
    "Mono C#": "C#", ".NET Core C#": "C#", "MS C#": "C#",
    "C# 10": "C#", "C# 8": "C#",
    "Python 3": "Python", "PyPy 3": "Python", "PyPy 3-64": "Python",
    "Python 3 + libs": "Python", "PyPy 2": "Python", "Python 2": "Python",
    "Go": "Go", "Rust": "Rust", "Rust 2021": "Rust",
    "Node.js": "Javascript", "JavaScript": "Javascript",
    "Kotlin": "Kotlin", "Kotlin 1.4": "Kotlin", "Kotlin 1.5": "Kotlin",
    "Kotlin 1.6": "Kotlin", "Kotlin 1.7": "Kotlin",
    "PHP": "PHP", "Ruby": "Ruby", "Ruby 3": "Ruby",
}
LANGS = sorted(set(SHORT_LANG_MAP.values()))


def gen(prompt):
    cnt = 0
    while True:
        if cnt >= 20:
            return None
        try:
            c = openai.ChatCompletion.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=TEMP,
                max_completion_tokens=MAX_TOKENS,
                top_p=1,
                n=NSAMPLE,
                frequency_penalty=0.0,
                presence_penalty=0.0,
            )
            break
        except Exception as e:
            cnt += 1
            time.sleep(3)
            if cnt <= 3:
                print(f"  retry {cnt}: {e}")
    c["prompt"] = prompt
    return c


# ── Program Synthesis ────────────────────────────────────────────────────────
def run_ps():
    PS_TMPL = (
        "Write a program in {{lang_cluster}} to solve this programming problem:\n"
        "Description: {{prob_desc_description}}\n"
        "Input Specification: {{prob_desc_input_spec}}\n"
        "Output Specification: {{prob_desc_output_spec}}\n"
        "{% for input, output in zip(prob_desc_sample_inputs, prob_desc_sample_outputs) %}\n"
        "Sample Input:\n{{input}}\nSample Output:\n{{output}}\n"
        "{% endfor %}\n"
        "Notes: {{prob_desc_notes}}\n"
        "Take input from {{prob_desc_input_from}} and output to {{prob_desc_output_to}}\n"
        "Provide the {{lang_cluster}} code without any extra description or tokens. "
        "Target code: ||END-of-SRC|| "
    )
    baseline_dir = os.path.join(BASELINE_ROOT, "program_synthesis")
    out_dir = os.path.join(OUT_ROOT, "program_synthesis")
    os.makedirs(out_dir, exist_ok=True)

    if FILELIST_DIR:
        with open(os.path.join(FILELIST_DIR, "ps.txt")) as f:
            baseline_files = set(l.strip() for l in f if l.strip())
    else:
        baseline_files = set(os.listdir(baseline_dir))
    template = Template("ps_0", PS_TMPL, "xCodeEval", delimeter="||END-of-SRC||")
    if DATA_DIR:
        ds = list(datasets.load_dataset(
            "json", data_files=os.path.join(DATA_DIR, "ps_compact.jsonl")
        )["train"])
    else:
        ds = list(datasets.load_dataset(
            "NTU-NLP-sg/xCodeEval", "program_synthesis", trust_remote_code=True
        )["compact"])

    # Build task list: (idx, problem_dict, target_language) for each baseline file
    tasks = []
    for idx, dt in enumerate(ds):
        for language in LANGS:
            fname = f"{idx}_{TEMP}_{language}.json"
            if fname in baseline_files:
                tasks.append((idx, dict(dt), language, fname))

    print(f"PS: {len(tasks)} baseline files to generate")

    def process(args):
        idx, dt, language, fname = args
        out_path = os.path.join(out_dir, fname)
        if os.path.exists(out_path):
            return
        try:
            dt["lang_cluster"] = language
            dt["prob_desc_sample_inputs"]  = json.loads(dt["prob_desc_sample_inputs"])
            dt["prob_desc_sample_outputs"] = json.loads(dt["prob_desc_sample_outputs"])
            lm_io = template.apply(dt)
            resp = gen(lm_io[0])
            json.dump({"oai_response": resp, "source_data": dt}, open(out_path, "w"))
        except Exception as e:
            print(f"PS {fname} error: {e}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
        list(tqdm.tqdm(ex.map(process, tasks), total=len(tasks), desc="PS"))

    done = len([f for f in os.listdir(out_dir) if f.endswith(".json")])
    print(f"PS done: {done}/{len(tasks)} files")


# ── Code Translation ─────────────────────────────────────────────────────────
def run_ct():
    CT_TMPL = (
        "Here is code in {{source_lang}} programming lanaguge. "
        "Translate the following code from {{source_lang}} to {{target_lang}} programming lanaguge. "
        "Do not output any extra description or tokens other than the translated code. "
        "\n\n{{source_code}}||END-of-SRC|| "
    )
    baseline_dir = os.path.join(BASELINE_ROOT, "code_translation/compact_small")
    out_dir = os.path.join(OUT_ROOT, "code_translation_n_sample_20/compact_small")
    os.makedirs(out_dir, exist_ok=True)

    if FILELIST_DIR:
        with open(os.path.join(FILELIST_DIR, "ct.txt")) as f:
            baseline_files = set(l.strip() for l in f if l.strip())
    else:
        baseline_files = set(os.listdir(baseline_dir))
    template = Template("ct_0", CT_TMPL, "xCodeEval", delimeter="||END-of-SRC||")
    if DATA_DIR:
        ds = list(datasets.load_dataset(
            "json", data_files=os.path.join(DATA_DIR, "ct_compact_small.jsonl")
        )["train"])
    else:
        ds = list(datasets.load_dataset(
            "NTU-NLP-sg/xCodeEval", "code_translation", trust_remote_code=True
        )["compact_small"])

    # Filename format: {idx}_{temp}_{raw_source_lang}--{mapped_target_lang}.json
    tasks = []
    for idx, dt in enumerate(ds):
        raw_src = dt["lang"]
        mapped_src = SHORT_LANG_MAP.get(raw_src, raw_src)
        for tgt in LANGS:
            if mapped_src == tgt:
                continue
            fname = f"{idx}_{TEMP}_{raw_src}--{tgt}.json"
            if fname in baseline_files:
                tasks.append((idx, dict(dt), raw_src, tgt, fname))

    print(f"CT: {len(tasks)} baseline files to generate")

    def process(args):
        idx, dt, raw_src, tgt, fname = args
        out_path = os.path.join(out_dir, fname)
        if os.path.exists(out_path):
            return
        try:
            dt["source_lang"] = raw_src
            dt["target_lang"] = tgt
            dt["prob_desc_sample_inputs"]  = json.loads(dt.get("prob_desc_sample_inputs", "[]"))
            dt["prob_desc_sample_outputs"] = json.loads(dt.get("prob_desc_sample_outputs", "[]"))
            lm_io = template.apply(dt)
            resp = gen(lm_io[0])
            json.dump({"oai_response": resp, "source_data": dt}, open(out_path, "w"))
        except Exception as e:
            print(f"CT {fname} error: {e}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
        list(tqdm.tqdm(ex.map(process, tasks), total=len(tasks), desc="CT"))

    done = len([f for f in os.listdir(out_dir) if f.endswith(".json")])
    print(f"CT done: {done}/{len(tasks)} files")


# ── APR ──────────────────────────────────────────────────────────────────────
def run_apr():
    APR_TMPL = (
        "Fix the following buggy {{lang_cluster}} program. "
        "The bug causes a {{bug_exec_outcome}} error.\n\n"
        "Buggy code:\n\n{{bug_source_code}}\n\n"
        "Provide the fixed {{lang_cluster}} code without any description or extra tokens.\n\n"
        "Fixed source code:\n ||END-of-SRC|| "
    )
    baseline_dir = os.path.join(BASELINE_ROOT, "apr")
    out_dir = os.path.join(OUT_ROOT, "apr_n_sample_20")
    os.makedirs(out_dir, exist_ok=True)

    if FILELIST_DIR:
        with open(os.path.join(FILELIST_DIR, "apr.txt")) as f:
            baseline_files = set(l.strip() for l in f if l.strip())
    else:
        baseline_files = set(os.listdir(baseline_dir))
    APR_DATA_DIR = os.environ.get("XCODEEVAL_APR_DATA_DIR",
                      os.path.join(os.path.dirname(os.path.abspath(__file__)), "apr_test_data"))
    LANG_TO_FILE = {
        "C": "C.jsonl", "C#": "C%23.jsonl", "C++": "C%2B%2B.jsonl",
        "Go": "Go.jsonl", "Java": "Java.jsonl", "Javascript": "Javascript.jsonl",
        "Kotlin": "Kotlin.jsonl", "PHP": "PHP.jsonl", "Python": "Python.jsonl",
        "Ruby": "Ruby.jsonl", "Rust": "Rust.jsonl",
    }
    template = Template("apr_0", APR_TMPL, "xCodeEval", delimeter="||END-of-SRC||")

    # Baseline APR was generated with C++ only — indices enumerate the C++ JSONL from 0
    apr_dataset = []
    cpp_path = os.path.join(APR_DATA_DIR, "C%2B%2B.jsonl")
    if os.path.exists(cpp_path):
        apr_dataset.extend(json.loads(l) for l in open(cpp_path) if l.strip())

    tasks = []
    for idx, dt in enumerate(apr_dataset):
        lang = dt.get("lang_cluster", "")
        fname = f"{idx}_{TEMP}_{lang}.json"
        if fname in baseline_files:
            tasks.append((idx, dt, fname))

    print(f"APR: {len(tasks)} baseline files to generate")

    def process(args):
        idx, dt, fname = args
        out_path = os.path.join(out_dir, fname)
        if os.path.exists(out_path):
            return
        try:
            lm_io = template.apply(dt)
            resp = gen(lm_io[0])
            json.dump({"oai_response": resp, "source_data": dt}, open(out_path, "w"))
        except Exception as e:
            print(f"APR {fname} error: {e}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
        list(tqdm.tqdm(ex.map(process, tasks), total=len(tasks), desc="APR"))

    done = len([f for f in os.listdir(out_dir) if f.endswith(".json")])
    print(f"APR done: {done}/{len(tasks)} files")


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "all"
    if task in ("ps",  "all"): run_ps()
    if task in ("ct",  "all"): run_ct()
    if task in ("apr", "all"): run_apr()
