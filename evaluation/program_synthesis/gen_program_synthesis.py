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

# vLLM models need thinking disabled; gpt4o goes through LiteLLM which doesn't accept this param
VLLM_MODELS = {"qwen-nvfp4", "laguna-nvfp4"}
EXTRA_KWARGS = {"chat_template_kwargs": {"enable_thinking": False}} if MODEL in VLLM_MODELS else {}
MAX_TOKENS = 4096 if MODEL in VLLM_MODELS or MODEL == "nemotron-ultra-nvfp4" else 8192
MAX_N = 8 if MODEL == "gpt4o" else 20  # Azure gpt4o hard limit is n<=8


def gen(prompt, temperature, nsample):
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
                max_tokens=MAX_TOKENS,
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
    "program_synthesis": [
        "Write a program in {{lang_cluster}} to solve this programming problem:\nDescription: {{prob_desc_description}}\nInput Specification: {{prob_desc_input_spec}}\nOutput Specification: {{prob_desc_output_spec}}\n{% for input, output in zip(prob_desc_sample_inputs, prob_desc_sample_outputs) %}\nSample Input:\n{{input}}\nSample Output:\n{{output}}\n{% endfor %}\nNotes: {{prob_desc_notes}}\nTake input from {{prob_desc_input_from}} and output to {{prob_desc_output_to}}\nProvide the {{lang_cluster}} code without any extra description or tokens. Target code: ||END-of-SRC|| ",
    ]
}


def process_prompt(
    dt, temperature, nsample, language, template, output_dir, index, dry_run=0
):
    file_path = os.path.join(output_dir, f"{index}_{temperature}_{language}.json")
    if not os.path.exists(file_path):
        dt["lang_cluster"] = language
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
        default="dumped/oai/program_synthesis_n_sample_20",
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
        help="Subset of languages to evaluate. e.g. --languages Python Java C++. Default: all 11.",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Path to dataset_subset/ with ps_compact.jsonl. Skips HuggingFace download.",
    )
    args = parser.parse_args()
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir, exist_ok=True)
    templates = [
        Template(f"prog_syn_{idx}", template, "xCodeEval", delimeter="||END-of-SRC||")
        for idx, template in enumerate(xcodeeval_prompt_template["program_synthesis"])
    ]
    template = templates[0]

    if args.data_dir:
        prog_synthesis_dataset = datasets.load_dataset(
            "json", data_files=os.path.join(args.data_dir, "ps_compact.jsonl")
        )["train"]
    else:
        prog_synthesis_dataset = datasets.load_dataset(
            "NTU-NLP-sg/xCodeEval", "program_synthesis", trust_remote_code=True
        )["compact"]
    # temperature_list = np.linspace(0, 2, args.nsample)
    temperature_list = [0.3157894736842105]
    selected_langs = args.languages if args.languages else LANGS
    invalid = [l for l in selected_langs if l not in LANGS]
    if invalid:
        print(f"Warning: unknown languages {invalid}. Valid: {LANGS}")
        selected_langs = [l for l in selected_langs if l in LANGS]
    print(f"Running for languages: {selected_langs}")
    for language in selected_langs:
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=int(args.num_proc)
        ) as executor:
            futures = []
            for idx, dt in tqdm.tqdm(
                enumerate(prog_synthesis_dataset),
                total=len(prog_synthesis_dataset),
                desc=f"Preparing samples {language} lang",
            ):
                for temperature in temperature_list:
                    future = executor.submit(
                        process_prompt,
                        dt,
                        temperature,
                        args.nsample,
                        language,
                        template,
                        args.output_dir,
                        idx,
                        args.dry_run,
                    )
                    futures.append(future)

            for future in tqdm.tqdm(
                concurrent.futures.as_completed(futures),
                total=len(futures),
                desc=f"Calling OpenAI API for {language} lang",
            ):
                try:
                    future.result()
                except Exception as e:
                    print(f"Error occurred: {e}")


if __name__ == "__main__":
    main()
