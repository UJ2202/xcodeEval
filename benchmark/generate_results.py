#!/usr/bin/env python3
"""Generate benchmark/RESULTS.txt: 4 pass@k tables + cost metrics + per-model issue reports."""
import os, json
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(BASE, "RESULTS.txt")

# order: best-known first, but keep a stable reporting order
MODELS = [
    ("claude-opus-5",   "Claude Opus 5"),
    ("claude-sonnet-5", "Claude Sonnet 5"),
    ("gpt-5.6-sol",     "GPT-5.6-sol"),
    ("gpt4o",           "GPT-5.1 (gpt4o)"),
    ("laguna-nvfp4",    "Laguna NV-FP4"),
    ("nemotron-550b",   "Nemotron-550B"),
    ("qwen-nvfp4",      "Qwen NV-FP4"),
]
LANGS = [("C++","GNU C++17"),("Go","Go"),("Java","Java 17"),
         ("Javascript","Node.js"),("Kotlin","Kotlin 1.4"),("PHP","PHP"),("Python","PyPy 3")]
LANG_NAMES = [l for l,_ in LANGS]

def ps_path(m,c): return os.path.join(BASE,m,"ps","reproduce_1",f"{c}.jsonl")
def ct_path(m,c): return os.path.join(BASE,m,"ct_compact_small",
                     "eval_code_translation_compact_small_execeval",f"{c}.jsonl")

def estimator(n,c,k):
    if n-c < k: return 1.0
    p=1.0
    for i in range(n-c+1,n+1): p*=(1.0-k/i)
    return 1.0-p

def load(path):
    if not os.path.exists(path) or os.path.getsize(path)==0: return None
    from collections import defaultdict
    res=defaultdict(list); fail=Counter(); nsamp=[]
    with open(path) as f:
        for line in f:
            line=line.strip()
            if not line: continue
            s=json.loads(line)
            uid=s["source_data"]["src_uid"]
            attempts=s["unit_test_results"]; nsamp.append(len(attempts))
            for a in attempts:
                if isinstance(a,dict) and "error" in a: continue
                res[uid].append(a)
                first=None; ok=True
                for t in a:
                    if t["exec_outcome"]!="PASSED":
                        ok=False
                        if first is None: first=t["exec_outcome"]
                if not ok: fail[first or "UNKNOWN"]+=1
    if not res: return None
    total=[]; correct=[]
    for v in res.values():
        passed=[all(t["exec_outcome"]=="PASSED" for t in a) for a in v]
        total.append(len(passed)); correct.append(sum(passed))
    def pk(k):
        if not all(t>=k for t in total): return None
        return 100.0*sum(estimator(t,c,k) for t,c in zip(total,correct))/len(total)
    return {"p1":pk(1),"p5":pk(5),"fail":fail,
            "nmin":min(nsamp),"nmax":max(nsamp),"nprob":len(total)}

# collect all
DATA={}
for m,_ in MODELS:
    for lang,comp in LANGS:
        DATA[("PS",m,lang)]=load(ps_path(m,comp))
        DATA[("CT",m,lang)]=load(ct_path(m,comp))

def cell(v): return f"{v:.1f}" if v is not None else "—"

def table(task, metric, title):
    L=[]
    L.append(title)
    hdr=f"  {'Model':<18}" + "".join(f"{l:>12}" for l in LANG_NAMES) + f"{'Avg':>9}"
    L.append(hdr)
    L.append("  "+"-"*(18+12*7+9-2))
    for m,disp in MODELS:
        vals=[]; row=f"  {disp:<18}"
        for lang in LANG_NAMES:
            r=DATA[(task,m,lang)]
            v=r[metric] if r else None
            row+=f"{cell(v):>12}"
            if v is not None: vals.append(v)
        avg=f"{sum(vals)/len(vals):.1f}" if vals else "—"
        row+=f"{avg:>9}"
        L.append(row)
    L.append("")
    return "\n".join(L)

# ---- per-model failure narratives (qualitative issue faced) ----
ISSUES = {
"claude-opus-5": [
 "SAMPLING LIMIT: Azure Anthropic API does not support n>1, so only n=1 was",
 "  generated. pass@1 is exact; pass@5 is NOT COMPUTABLE (blank) for this model.",
 "RUN: PS 560 input files, CT 1688 input files. Both completed clean (exit=0).",
 "STRONGEST model on both tasks. Main weakness: Javascript CT (71.6%) — most",
 "  failures are RUNTIME_ERROR in translated JS (40 cases).",
],
"claude-sonnet-5": [
 "SAMPLING LIMIT: same Azure n=1 constraint → pass@1 only, pass@5 blank.",
 "RUN: PS 560, CT 1688 files, completed clean (exit=0).",
 "JAVASCRIPT COLLAPSE: PS Javascript only 32.3% — 36 RUNTIME_ERRORs, a",
 "  systematic failure mode in generated Node.js code (not an infra issue).",
 "PHP CT weak (68.0%): 40 WRONG_ANSWER + 29 RUNTIME_ERROR.",
],
"gpt-5.6-sol": [
 "SAMPLES: n=5 → pass@1 and pass@5 both available.",
 "RERUN NEEDED: first eval left gaps; eval_ps_rerun / eval_ct_rerun were run to",
 "  fill missing compiler outputs before scoring.",
 "KOTLIN BROKEN: catastrophic COMPILATION_ERROR (PS 180, CT 572 attempts) →",
 "  Kotlin CT drops to 49.8%. Model emits Kotlin that does not compile.",
 "Otherwise the strongest sampling model (CT avg 90.2% @5).",
],
"gpt4o": [
 "ALIAS: 'gpt4o' endpoint routes to GPT-5.1 via LiteLLM/Azure.",
 "SAMPLING CAP: Azure enforces n<=8, so n=8 (not 20). pass@1/pass@5 both valid.",
 "SCOPE: CT ran the FULL compact split (400 problems/lang, 2804 input files),",
 "  a larger set than the n=5 baseline models — longer run (~2h).",
 "Weakest spots: Kotlin (COMPILATION_ERROR 485) and PHP (RUNTIME_ERROR 503).",
],
"laguna-nvfp4": [
 "BACKEND: local vLLM NV-FP4, enable_thinking=False, max_tokens=4096.",
 "SAMPLES: PS n=20, CT n=8. Several CT languages show n=0..8 — some prompts",
 "  produced empty/short generations that yielded fewer valid samples.",
 "COMPILED-LANG WEAKNESS: very high COMPILATION_ERROR (Go 289 PS / 257 CT,",
 "  Kotlin 471 PS). Lowest overall of the FP4 pair on PS (41.9% @1).",
],
"nemotron-550b": [
 "BASELINE SUBSET: run on the fixed baseline idx/lang pairs (PS 418 input files,",
 "  CT 1723), NOT the full set — rows are comparable to gpt4o's baseline.",
 "PS SAMPLING: PS is n=1 for every language EXCEPT C++, which was partially",
 "  re-run to n=5 (eval_ps_rerun, 22 files). Because not all PS problems reach",
 "  n>=5, PS pass@5 is NOT COMPUTABLE (blank). CT is a clean n=5 → CT pass@5 OK.",
 "COMPILED-LANG WEAKNESS: dominant COMPILATION_ERROR on CT Go (205), Kotlin",
 "  (369), Java (128). PHP CT is the floor (43.8%).",
],
"qwen-nvfp4": [
 "BACKEND: local vLLM NV-FP4, enable_thinking=False, max_tokens=4096.",
 "SAMPLES: PS n=20, CT n=8; port moved mid-run (5000->5001) and reruns were",
 "  needed (eval_ps_full / eval_ct_full) to complete scoring.",
 "MISSING DATA: PS Kotlin produced NO usable output (blank cell). PS Python",
 "  yielded only 4 scorable problems (most gens empty) → Python PS 16.2% is on a",
 "  tiny sample and is not comparable.",
 "COMPILATION-HEAVY: Go PS COMPILATION_ERROR=818, Go CT=466 — worst compiler",
 "  reliability of any model.",
],
}

def model_section(m, disp):
    L=[]
    L.append("━"*80)
    L.append(f"MODEL : {disp}   ({m})")
    L.append("━"*80)
    L.append("")
    L.append("  ISSUES FACED / RUN NOTES")
    for line in ISSUES[m]:
        L.append(f"  • {line}" if not line.startswith("  ") else f"    {line.strip()}")
    L.append("")
    for task,label in (("PS","Program Synthesis (PS)"),("CT","Code Translation (CT)")):
        L.append(f"  ┌─ {label}")
        L.append(f"  │  {'Language':<12}{'pass@1':>9}{'pass@5':>9}   Top failure modes (attempt-level counts)")
        L.append("  │  "+"-"*74)
        for lang in LANG_NAMES:
            r=DATA[(task,m,lang)]
            if not r:
                L.append(f"  │  {lang:<12}{'—':>9}{'—':>9}   (no data)")
                continue
            p1=cell(r["p1"]); p5=cell(r["p5"])
            top=", ".join(f"{k}={v}" for k,v in r["fail"].most_common(4)) or "none (all passed)"
            L.append(f"  │  {lang:<12}{p1:>9}{p5:>9}   {top}")
        L.append("  └"+"─"*76)
        L.append("")
    return "\n".join(L)

# ---------- assemble ----------
from datetime import datetime, timezone
now=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

# preserved token/cost block (from prior RESULTS.txt)
TOKEN_BLOCK = """\
====================================================================================================
  TOKEN & COST SUMMARY — PROGRAM SYNTHESIS (PS)
====================================================================================================

Model                        n Input / Output Tokens Rate /1M (in/out)          Cost
───────────────────────────────────────────────────────────────────────────────────
Claude Opus 5                1   390.1K / 758.1K      $5.00 / $25.00         $20.90
Claude Sonnet 5              1    384.9K / 1.51M      $2.00 / $10.00         $15.91
GPT-5.1 (dep: gpt4o)         8    272.5K / 1.93M      $2.00 / $8.00          $15.96
GPT-5.6-sol                  5    272.5K / 3.25M      $5.00 / $20.00         $66.36
Nemotron-550B                5    215.9K / 6.34M          — / —                   —
Laguna NV-FP4               20    303.6K / 6.52M          — / —                   —
Qwen NV-FP4                 20   213.9K / 12.79M          — / —                   —
Nemo Ultra                   —        0 / 0               — / —                   —
───────────────────────────────────────────────────────────────────────────────────
TOTAL (API models only)                                                     $119.14

====================================================================================================
  TOKEN & COST SUMMARY — CODE TRANSLATION (CT)
====================================================================================================

Model                        n Input / Output Tokens Rate /1M (in/out)          Cost
───────────────────────────────────────────────────────────────────────────────────
Claude Opus 5                1    936.0K / 1.09M      $5.00 / $25.00         $31.94
Claude Sonnet 5              1    1.12M / 1.29M       $2.00 / $10.00         $15.10
GPT-5.1 (dep: gpt4o)         8    1.27M / 8.30M       $2.00 / $8.00          $68.93
GPT-5.6-sol                  5    754.7K / 3.31M      $5.00 / $20.00         $70.04
Nemotron-550B                5   825.4K / 11.33M          — / —                   —
Laguna NV-FP4                8    879.0K / 4.77M          — / —                   —
Qwen NV-FP4                  8    809.3K / 5.11M          — / —                   —
Nemo Ultra                   —        0 / 0               — / —                   —
───────────────────────────────────────────────────────────────────────────────────
TOTAL (API models only)                                                     $186.01

====================================================================================================
  GRAND TOTAL API COST (PS + CT, Claude + OpenAI): $305.15
====================================================================================================
"""

parts=[]
parts.append("="*100)
parts.append("  xCodeEval Benchmark — pass@1 & pass@5 (7 models, 7 languages)")
parts.append(f"  Generated : {now}")
parts.append("  Tasks     : Program Synthesis (PS), Code Translation (CT)")
parts.append("="*100)
parts.append("")
parts.append("METRICS")
parts.append("  pass@1 : unbiased estimator; equals correct/total when n=1. Reported for all models.")
parts.append("  pass@5 : unbiased estimator 1 - C(n-c,5)/C(n,5); requires n>=5 samples for EVERY")
parts.append("           problem in a language, otherwise left blank (—).")
parts.append("  —      : not computable / not available for that model+language.")
parts.append("")
parts.append("WHY SOME pass@5 CELLS ARE BLANK")
parts.append("  • Claude Opus 5 & Claude Sonnet 5 : Azure Anthropic API supports only n=1 → no pass@5.")
parts.append("  • Nemotron-550B PS               : PS was generated at n=1 (C++ partially n=5) → PS")
parts.append("                                     pass@5 blank; its CT is n=5 so CT pass@5 is shown.")
parts.append("  • Qwen NV-FP4 Kotlin PS          : no usable generations (blank in every metric).")
parts.append("")
parts.append("#"*100)
parts.append("  SUMMARY TABLES")
parts.append("#"*100)
parts.append("")
parts.append(table("PS","p1","TABLE 1 — Program Synthesis (PS) · pass@1  (%)"))
parts.append(table("PS","p5","TABLE 2 — Program Synthesis (PS) · pass@5  (%)"))
parts.append(table("CT","p1","TABLE 3 — Code Translation (CT) · pass@1  (%)"))
parts.append(table("CT","p5","TABLE 4 — Code Translation (CT) · pass@5  (%)"))
parts.append("#"*100)
parts.append("  TOKENS & COST")
parts.append("#"*100)
parts.append("")
parts.append(TOKEN_BLOCK)
parts.append("#"*100)
parts.append("  PER-MODEL REPORTS — issues faced + results + failure breakdown")
parts.append("#"*100)
parts.append("")
parts.append("FAILURE TYPE GLOSSARY")
parts.append("  WRONG_ANSWER=ran but wrong output  RUNTIME_ERROR=crashed  COMPILATION_ERROR=won't build")
parts.append("  TIME_LIMIT_EXCEEDED=too slow       MEMORY_LIMIT_EXCEEDED=too much memory")
parts.append("  (Counts are attempt-level: summed over all n samples × problems for that language.)")
parts.append("")
for m,disp in MODELS:
    parts.append(model_section(m,disp))

out="\n".join(parts)+"\n"
open(OUT,"w").write(out)
print(out)
