#!/usr/bin/env python3
"""Threaded generator for nemotron-ultra PS — thinking disabled, n=1, 4 workers."""
import os, json, time, requests, datasets, tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

MODEL      = "nvidia/nemotron-3-ultra-550b-a55b"
API_BASE   = os.environ.get("OPENAI_API_BASE", "http://localhost:4000")
API_KEY    = os.environ.get("OPENAI_API_KEY",  "sk-local-dev")
MAX_TOKENS = 4096
NSAMPLE    = 1
NUM_WORKERS = 4
OUTPUT_DIR = "dumped/ultra/program_synthesis"
DATA_DIR   = "dataset_subset"
LANGS      = ["C++", "Go", "Java", "Javascript", "PHP", "Python", "Kotlin"]
TEMPERATURE = 1

PROMPT_TMPL = (
    "Write a program in {lang} to solve this programming problem:\n"
    "Description: {desc}\n"
    "Input Specification: {input_spec}\n"
    "Output Specification: {output_spec}\n"
    "{samples}"
    "Notes: {notes}\n"
    "Take input from {input_from} and output to {output_to}\n"
    "Provide the {lang} code without any extra description or tokens."
)

os.makedirs(OUTPUT_DIR, exist_ok=True)
ds = datasets.load_dataset("json", data_files=os.path.join(DATA_DIR, "ps_compact.jsonl"))["train"]
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def call_api(prompt):
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "n": NSAMPLE,
        "temperature": TEMPERATURE,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    for attempt in range(5):
        try:
            r = requests.post(f"{API_BASE}/v1/chat/completions",
                              json=payload, headers=HEADERS, timeout=180)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"  retry {attempt+1}/5: {e}")
            time.sleep(5)
    return None


def build_prompt(dt, lang):
    si = json.loads(dt["prob_desc_sample_inputs"])
    so = json.loads(dt["prob_desc_sample_outputs"])
    samples = "".join(f"Sample Input:\n{a}\nSample Output:\n{b}\n" for a, b in zip(si, so))
    return PROMPT_TMPL.format(
        lang=lang, desc=dt["prob_desc_description"],
        input_spec=dt["prob_desc_input_spec"],
        output_spec=dt["prob_desc_output_spec"],
        samples=samples,
        notes=dt.get("prob_desc_notes", ""),
        input_from=dt.get("prob_desc_input_from", "stdin"),
        output_to=dt.get("prob_desc_output_to", "stdout"),
    )


def process_one(args):
    idx, dt, lang = args
    fpath = os.path.join(OUTPUT_DIR, f"{idx}_{TEMPERATURE}_{lang}.json")
    if os.path.exists(fpath):
        return idx, lang, "skip"
    prompt = build_prompt(dt, lang)
    resp = call_api(prompt)
    if resp is None:
        return idx, lang, "error"
    export = {"oai_response": resp, "source_data": dict(dt)}
    with open(fpath, "w") as f:
        json.dump(export, f)
    return idx, lang, "done"


for lang in LANGS:
    items = [(idx, dt, lang) for idx, dt in enumerate(ds)]
    skipped = done = errors = 0
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
        futures = {ex.submit(process_one, item): item for item in items}
        bar = tqdm.tqdm(as_completed(futures), total=len(items), desc=lang)
        for fut in bar:
            idx, lg, status = fut.result()
            if status == "skip":   skipped += 1
            elif status == "done": done += 1
            else:                  errors += 1
            bar.set_postfix(done=done, skip=skipped, err=errors)
    print(f"{lang}: done={done}  skipped={skipped}  errors={errors}")

print("ALL DONE")
