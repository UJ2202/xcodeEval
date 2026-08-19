"""
APR eval without hidden unit tests.
Metric: compilation pass@k — the generated fix at least compiles.
Sends a single dummy test {"input": "", "output": [""]} to ExecEval;
records COMPILATION_ERROR vs anything else.
"""

import os
import json
import tqdm
import jsonlines
import concurrent.futures
import itertools
import requests
from dataclasses import dataclass, field
from typing import List, Optional, Union, Tuple
from enum import Enum


class ExecOutcome(Enum):
    PASSED = "PASSED"
    WRONG_ANSWER = "WRONG_ANSWER"
    TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    COMPILATION_ERROR = "COMPILATION_ERROR"
    MEMORY_LIMIT_EXCEEDED = "MEMORY_LIMIT_EXCEEDED"


class APICommunication:
    def __init__(self, server_url: str = "http://localhost:5000"):
        self._session = requests.Session()
        self.execute_code_url = f"{server_url}/api/execute_code"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._session.close()

    def execute_code(self, language, source_code, unittests, task_id=None):
        body = dict(
            language=language,
            source_code=source_code,
            unittests=unittests,
            stop_on_first_fail=True,
            block_network=True,
        )
        resp = self._session.post(
            self.execute_code_url,
            json=body,
            headers={"Content-Type": "application/json"},
        ).json()
        if "data" not in resp:
            return resp, None, task_id
        return resp["data"], None, task_id


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

DUMMY_TEST = [{"input": "", "output": [""]}]


LANG_TAGS = {"cpp", "go", "java", "javascript", "js", "php", "python", "python3",
             "kotlin", "ruby", "rust", "c", "csharp", "c#", "typescript", "ts"}

def sanitize_code(code):
    FLAG = True
    while FLAG:
        FLAG = False
        if code.startswith("```"):
            FLAG = True
            code = code.replace("```", "", 1)
        last_index = code.rfind("```")
        if last_index != -1:
            FLAG = True
            code = code[:last_index] + code[last_index + 3:]
        first_line = code.split("\n")[0].strip().lower()
        if first_line in LANG_TAGS:
            FLAG = True
            code = code[code.index("\n") + 1:] if "\n" in code else ""
    return code.strip()


def process(args):
    sample, execeval = args
    src_uid = sample["source_data"]["src_uid"]
    compiler = LANG_CLUSTER_TO_LANG_COMPILER[sample["source_data"]["lang_cluster"]]
    sample["unit_test_results"] = []
    for choice in sample["oai_response"]["choices"]:
        code = sanitize_code(choice["message"]["content"])
        result, _, _ = execeval.execute_code(compiler, code, DUMMY_TEST, task_id=src_uid)
        # Normalise to list of dicts
        if isinstance(result, list):
            sample["unit_test_results"].append(result)
        else:
            sample["unit_test_results"].append([{"exec_outcome": "RUNTIME_ERROR", "error": str(result)}])
    return sample


def main():
    path = f'{os.environ["DUMP_FOLDER"]}/oai/apr_n_sample_20/'
    execeval_url = os.environ.get("EXECEVAL_URL", "http://localhost:5000")

    for k, debug_compiler in LANG_CLUSTER_TO_LANG_COMPILER.items():
        output_path = os.path.join(path, "eval_apr_compile_execeval")
        os.makedirs(output_path, exist_ok=True)
        output_file = os.path.join(output_path, f"{debug_compiler}.jsonl")
        with jsonlines.open(output_file, "w") as jwp:
            with concurrent.futures.ThreadPoolExecutor(max_workers=64) as executor:
                files = sorted(os.listdir(path))
                with APICommunication(server_url=execeval_url) as execeval:
                    all_samples = []
                    for file in files:
                        full_path = os.path.join(path, file)
                        if os.path.isdir(full_path):
                            continue
                        sample = json.load(open(full_path))
                        if sample["source_data"]["lang_cluster"] not in LANG_CLUSTER_TO_LANG_COMPILER:
                            continue
                        compiler = LANG_CLUSTER_TO_LANG_COMPILER[sample["source_data"]["lang_cluster"]]
                        if compiler != debug_compiler:
                            continue
                        all_samples.append(sample)

                    futures = {
                        executor.submit(process, args)
                        for args in itertools.product(all_samples, [execeval])
                    }
                    for fut in tqdm.tqdm(
                        concurrent.futures.as_completed(futures),
                        total=len(all_samples),
                        desc=debug_compiler,
                    ):
                        try:
                            jwp.write(fut.result())
                        except Exception as e:
                            print(f"Exception: {e}")


if __name__ == "__main__":
    main()
