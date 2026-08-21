import os
import time
import tqdm
import json
import openai
import argparse
import datasets
import concurrent
import numpy as np
from promptsource.templates import Template

SHORT_LANG_MAP = {
    "GNU C++": "C++",
    "GNU C++17": "C++",
    "MS C++ 2017": "C++",
    "MS C++": "C++",
    "Java 8": "Java",
    "Java 6": "Java",
    "GNU C++11": "C++",
    "Java 11": "Java",
    "GNU C++14": "C++",
    "Mono C#": "C#",
    "GNU C": "C",
    "Python 3": "Python",
    "PyPy 3": "Python",
    "GNU C11": "C",
    "Go": "Go",
    "Rust": "Rust",
    "PyPy 2": "Python",
    "Python 2": "Python",
    "MS C#": "C#",
    "Kotlin": "Kotlin",
    "GNU C++0x": "C++",
    "Java 7": "Java",
    "Node.js": "Javascript",
    ".NET Core C#": "C#",
    "PHP": "PHP",
    "GNU C++17 Diagnostics": "C++",
    "Clang++17 Diagnostics": "C++",
    "JavaScript": "Javascript",
    "Ruby": "Ruby",
    "C# 10": "C#",
    "C# 8": "C#",
    "Clang++20 Diagnostics": "C++",
    "GNU C++17 (64)": "C++",
    "GNU C++20 (64)": "C++",
    "Java 17": "Java",
    "Kotlin 1.4": "Kotlin",
    "Kotlin 1.5": "Kotlin",
    "Kotlin 1.6": "Kotlin",
    "Kotlin 1.7": "Kotlin",
    "PyPy 3-64": "Python",
    "Python 3 + libs": "Python",
    "Ruby 3": "Ruby",
    "Rust 2021": "Rust",
}

LANGS = sorted(set([v for k, v in SHORT_LANG_MAP.items()]))


openai.api_key = os.environ.get("OPENAI_API_KEY", "sk-local-dev")
openai.api_base = os.environ.get("OPENAI_API_BASE", "http://localhost:4000")
MODEL = os.environ.get("XCODEEVAL_MODEL", "gpt4o")

VLLM_MODELS = {"qwen-nvfp4", "laguna-nvfp4"}
NEMOTRON_ULTRA = "nvidia/nemotron-3-ultra-550b-a55b"
EXTRA_KWARGS = {"chat_template_kwargs": {"enable_thinking": False}} if MODEL in VLLM_MODELS else {}
CLAUDE_MODELS = {"claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5", "claude-sonnet-4-5"}
MAX_TOKENS = 16384 if MODEL == NEMOTRON_ULTRA else (32768 if MODEL in CLAUDE_MODELS else (4096 if MODEL in VLLM_MODELS or MODEL == "nemotron-ultra-nvfp4" else 8192))
MAX_N = 8 if MODEL == "gpt4o" else 20

# ── Anthropic / Azure AI Foundry support ─────────────────────────────────────
# Direct Anthropic: set ANTHROPIC_API_KEY only.
# Azure AI Foundry:  set ANTHROPIC_API_KEY + ANTHROPIC_BASE_URL
#   e.g. ANTHROPIC_BASE_URL=https://<resource>.services.ai.azure.com/anthropic
#   Uses AnthropicFoundry client which handles Azure auth correctly.
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL")
USE_ANTHROPIC = bool(ANTHROPIC_API_KEY or ANTHROPIC_BASE_URL)
_IS_AZURE = bool(ANTHROPIC_BASE_URL and "azure.com" in ANTHROPIC_BASE_URL)

_anth_client = None
if USE_ANTHROPIC:
    import anthropic as _anthropic_module
    if _IS_AZURE:
        _anth_client = _anthropic_module.AnthropicFoundry(
            api_key=ANTHROPIC_API_KEY,
            base_url=ANTHROPIC_BASE_URL,
        )
    else:
        _anth_client = _anthropic_module.Anthropic(
            api_key=ANTHROPIC_API_KEY,
            **({"base_url": ANTHROPIC_BASE_URL} if ANTHROPIC_BASE_URL else {}),
            timeout=120.0,
        )

def _gen_anthropic(prompt, temperature, nsample, max_tokens):
    choices = []
    for _ in range(nsample):
        cnt = 0
        while True:
            if cnt >= 20:
                break
            try:
                resp = _anth_client.messages.create(
                    model=MODEL, max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
                choices.append({"message": {"content": resp.content[0].text}})
                break
            except Exception as e:
                cnt += 1
                time.sleep(3)
                print(f"  anthropic retry {cnt}/20: {e}")
    return {"choices": choices, "prompt": prompt}


def gen(prompt, temperature, nsample):
    if USE_ANTHROPIC:
        return _gen_anthropic(prompt, temperature, nsample, MAX_TOKENS)
    cnt = 0
    while True:
        if cnt == 999:
            return None
        try:
            c = openai.ChatCompletion.create(
                model=MODEL,
                messages=[
                    {"role": "user", "content": f"{prompt}"},
                ],
                temperature=temperature,
                max_completion_tokens=MAX_TOKENS,
                top_p=1,
                n=min(nsample, MAX_N),
                frequency_penalty=0.0,
                presence_penalty=0.0,
                **EXTRA_KWARGS,
            )
            break
        except Exception as e:
            cnt += 1
            time.sleep(5)
            print(f"{e}")
    c["prompt"] = prompt
    return c


xcodeeval_prompt_template = {
    "code_translation": [
        "Here is code in {{source_lang}} programming lanaguge. Translate the following code from {{source_lang}} to {{target_lang}} programming lanaguge. Do not output any extra description or tokens other than the translated code. \n\n{{source_code}}||END-of-SRC|| "
    ]
}


def process_prompt(
    dt, temperature, template, language, nsample, output_dir, index, dry_run=0
):
    dt["source_lang"] = dt["lang"]
    dt["target_lang"] = language
    language = f"{dt['source_lang']}--{dt['target_lang']}"
    file_path = os.path.join(output_dir, f"{index}_{temperature}_{language}.json")
    if not os.path.exists(file_path):
        dt["prob_desc_sample_inputs"] = json.loads(dt["prob_desc_sample_inputs"])
        dt["prob_desc_sample_outputs"] = json.loads(dt["prob_desc_sample_outputs"])
        lm_io = template.apply(dt)
        assert len(lm_io) == 2, f"{json.dumps(lm_io, indent=4)}"
        if dry_run:
            open(file_path, "w").write(f"{json.dumps(lm_io[0], indent=4)}")
        else:
            out = gen(lm_io[0], temperature, nsample)
            export_data = {"oai_response": out, "source_data": dt}
            open(file_path, "w").write(f"{json.dumps(export_data, indent=4)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="dumped/oai/code_translation_n_sample_20",
        help="Output Folder to save the API request.",
    )
    parser.add_argument(
        "--num-proc",
        default=1,
        help="Number of parallel API request.",
    )
    parser.add_argument(
        "--dry-run",
        default=0,
        help="Number of parallel API request.",
    )
    parser.add_argument(
        "--nsample",
        default=20,
        type=int,
        help="Number of parallel API request.",
    )
    parser.add_argument(
        "--languages",
        default=None,
        nargs="+",
        help="Subset of target languages. e.g. --languages Python Java C++. Default: all.",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Path to dataset_subset/ with ct_compact_small.jsonl. Skips HuggingFace download.",
    )
    args = parser.parse_args()
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir, exist_ok=True)
    selected_langs = args.languages if args.languages else LANGS
    invalid = [l for l in selected_langs if l not in LANGS]
    if invalid:
        print(f"Warning: unknown languages {invalid}. Valid: {LANGS}")
        selected_langs = [l for l in selected_langs if l in LANGS]
    print(f"Target languages: {selected_langs}")
    templates = [
        Template(
            f"code_translation_{idx}", template, "xCodeEval", delimeter="||END-of-SRC||"
        )
        for idx, template in enumerate(xcodeeval_prompt_template["code_translation"])
    ]
    template = templates[0]

    if args.data_dir:
        code_translation_dataset_small = datasets.load_dataset(
            "json", data_files=os.path.join(args.data_dir, "ct_compact_small.jsonl")
        )["train"]
        code_translation_dataset = code_translation_dataset_small
    else:
        code_translation_dataset_small = datasets.load_dataset(
            "NTU-NLP-sg/xCodeEval", "code_translation", trust_remote_code=True
        )["compact_small"]
        code_translation_dataset = datasets.load_dataset(
            "NTU-NLP-sg/xCodeEval", "code_translation", trust_remote_code=True
        )["compact"]
    temperature_list = [1]

    out_dir = args.output_dir + "/compact_small"
    if not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=int(args.num_proc)
    ) as executor:
        futures = []
        for idx, dt in tqdm.tqdm(
            enumerate(code_translation_dataset_small),
            total=len(code_translation_dataset_small),
            desc=f"Preparing samples",
        ):
            for language in selected_langs:
                if SHORT_LANG_MAP[dt["lang"]] == language:
                    continue
                for temperature in temperature_list:
                    future = executor.submit(
                        process_prompt,
                        dt,
                        temperature,
                        template,
                        language,
                        args.nsample,
                        out_dir,
                        idx,
                        args.dry_run,
                    )
                    futures.append(future)

        for future in tqdm.tqdm(
            concurrent.futures.as_completed(futures),
            total=len(futures),
            desc=f"Calling OpenAI API",
        ):
            try:
                future.result()
            except Exception as e:
                print(f"Error occurred: {e}")

    out_dir = args.output_dir + "/compact"
    if not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=int(args.num_proc)
    ) as executor:
        futures = []
        for idx, dt in tqdm.tqdm(
            enumerate(code_translation_dataset),
            total=len(code_translation_dataset),
            desc=f"Preparing samples",
        ):
            for language in ["Python"]:
                if SHORT_LANG_MAP[dt["lang"]] == language:
                    continue
                for temperature in temperature_list:
                    future = executor.submit(
                        process_prompt,
                        dt,
                        temperature,
                        template,
                        language,
                        args.nsample,
                        out_dir,
                        idx,
                        args.dry_run,
                    )
                    futures.append(future)

        for future in tqdm.tqdm(
            concurrent.futures.as_completed(futures),
            total=len(futures),
            desc=f"Calling OpenAI API",
        ):
            try:
                future.result()
            except Exception as e:
                print(f"Error occurred: {e}")


if __name__ == "__main__":
    main()
