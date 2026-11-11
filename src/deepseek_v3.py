"""v3: DeepSeek through OpenRouter on the same 750 prompts as Phase 1 v2.

python -m src.deepseek_v3 smoke --model v41              # 5 prompts, check that full reasoning comes back
python -m src.deepseek_v3 run --model v41 --workers 8    # all 750 (resumes; failures kept, never retried)
python -m src.deepseek_v3 merge --model v41|r1           # shard files -> responses.jsonl

Primary: deepseek/deepseek-v4.1-flash-1017 with reasoning_effort pinned to "high" (owner's instruction).
Partial second condition: deepseek/deepseek-r1-0528 (stopped at 225/750; R1 has no effort dial).
Settings: temperature 0.6, top-p 0.95, max 8,192 output tokens, reasoning enabled and
not excluded, per-trial seed (pilot formula), no provider fallbacks. Provider recorded per call.
Parsed with the fixed parser v2. Spend counts toward the shared US$25 cap (src.judge_v2.spent)
and is also bounded by the remaining OpenRouter account credit.
"""
from __future__ import annotations

import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .common import append_jsonl, read_jsonl, write_jsonl, utc_now
from .parser_v2 import parse_answer_strict, parse_answer_v2, response_status_v2

CONFIGS = {
    "v41": {"model": "deepseek/deepseek-v4.1-flash-1017", "out": Path("artifacts/v2/deepseek-v41"),
            "params": {"seed": 20261109, "max_tokens": 8192, "temperature": .6, "top_p": .95,
                       "reasoning_effort": "high"},
            # One endpoint for every call: supports seed + reasoning_effort, fp8 (not fp4).
            "provider": "deepinfra/fp8"},
    "r1": {"model": "deepseek/deepseek-r1-0528", "out": Path("artifacts/v2/deepseek"),
           "params": {"seed": 20261109, "max_tokens": 8192, "temperature": .6, "top_p": .95}},
}
CFG = CONFIGS["v41"]
GEN_CAP_USD = 3.0  # generation share; the account credit, not the US$25 cap, is the binding limit
CREDIT_RESERVE_USD = 1.0  # account credit kept back for the j3 judge (OpenRouter)


def trials():
    from .run import make_trials
    rows = make_trials(read_jsonl("data/questions.jsonl")[:150], CFG["model"], "openrouter", CFG["params"])
    return sorted(rows, key=lambda t: t["record_id"])


def to_row(trial, result):
    reasoning, content, finish = result["reasoning"], result["content"], result["finish_reason"]
    parsed = parse_answer_v2(content)
    return {**trial, "reasoning_effort": CFG["params"].get("reasoning_effort"), "provider_pinned": CFG.get("provider"),
            "reasoning": reasoning, "content": content, "answer": parsed["answer"],
            "answer_rule": parsed["rule"], "answer_letters": parsed["letters"],
            "status": response_status_v2(reasoning, content, finish, complete_thinking=True),
            "answer_strict": parse_answer_strict(content), "parser": "v2", "finish_reason": finish,
            "usage": result["usage"], "cost_usd": result["cost_usd"], "cost_is_estimate": result["cost_is_estimate"],
            "provider": result["provider"], "resolved_model": result["resolved_model"],
            "reasoning_chars": len(reasoning), "finished_at": utc_now()}


def call(client, trial):
    try:
        p = CFG["params"]
        price = CFG.get("endpoint_price")
        result = client.complete(trial["messages"], CFG["model"], max_tokens=p["max_tokens"],
                                 temperature=p["temperature"], top_p=p["top_p"], top_k=None,
                                 seed=trial["seed"], reasoning=True, request_key=trial["record_id"],
                                 reasoning_effort=p.get("reasoning_effort"), provider=CFG.get("provider"),
                                 max_price=price)
        return to_row(trial, result)
    except Exception as error:  # noqa: BLE001 - every failure is kept as a row, not retried
        return {**trial, "reasoning_effort": CFG["params"].get("reasoning_effort"), "status": "error", "error": f"{type(error).__name__}: {error}", "finished_at": utc_now()}


def run(selected, shard_name, workers, cap):
    from .judge_v2 import spent
    from .providers import OpenRouterClient, credit_left
    OUT = CFG["out"]
    OUT.mkdir(parents=True, exist_ok=True)
    budget = min(cap, 25.0 - spent(), credit_left() - CREDIT_RESERVE_USD)
    if budget <= 0:
        raise SystemExit(f"No budget: cap ${cap}, account credit after reserve ${credit_left() - CREDIT_RESERVE_USD:.2f}")
    print(f"generation budget ${budget:.2f}", flush=True)
    per = budget / workers
    lock = threading.Lock()

    def worker(k):
        path = OUT / f"{shard_name}_{k}.jsonl"
        ledger = OUT / f"{shard_name}_{k}.jsonl.billing.jsonl"
        done = {r["record_id"] for r in read_jsonl(path)}
        mine = [t for i, t in enumerate(selected) if i % workers == k and t["record_id"] not in done]
        if not mine:
            return 0
        client = OpenRouterClient(budget_usd=per, ledger_path=ledger, timeout=1200)
        for trial in mine:
            row = call(client, trial)
            append_jsonl(path, row)
            with lock:
                print(f"{shard_name}_{k}: {trial['hint_type']} {row['status']} answer={row.get('answer')} "
                      f"reasoning_chars={row.get('reasoning_chars')} provider={row.get('provider')} "
                      f"cost={row.get('cost_usd')}", flush=True)
            if row["status"] == "error" and "Budget guard" in row.get("error", ""):
                break
        return len(mine)
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(worker, range(workers)))


def merge():
    OUT = CFG["out"]
    rows = {}
    for path in sorted(OUT.glob("*.jsonl")):
        if path.name.endswith(".billing.jsonl") or path.name == "responses.jsonl":
            continue
        for row in read_jsonl(path):
            rows[row["record_id"]] = row  # smoke rows are the same record IDs; a later full-run row never replaces them
    write_jsonl(OUT / "responses.jsonl", sorted(rows.values(), key=lambda r: r["record_id"]))
    print(f"merged {len(rows)} rows")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("smoke", "run", "merge"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--model", choices=tuple(CONFIGS), required=True)
    args = parser.parse_args()
    CFG.update(CONFIGS[args.model])
    if CFG.get("provider") and args.step != "merge":
        import urllib.request
        url = f"https://openrouter.ai/api/v1/models/{CFG['model']}/endpoints"
        with urllib.request.urlopen(url, timeout=30) as response:
            endpoints = json.load(response)["data"]["endpoints"]
        match = [e for e in endpoints if e.get("tag") == CFG["provider"]]
        if len(match) != 1:
            raise SystemExit(f"pinned endpoint {CFG['provider']} not found for {CFG['model']}")
        CFG["endpoint_price"] = {k: match[0]["pricing"][k] for k in ("prompt", "completion")}
    OUT = CFG["out"]
    all_trials = trials()
    if args.step == "smoke":
        run(all_trials[:5], "smoke", 5, cap=1.0)
    elif args.step == "run":
        done = {r["record_id"] for p in OUT.glob("smoke_*.jsonl") if not p.name.endswith(".billing.jsonl")
                for r in read_jsonl(p)}  # smoke failures stay failures (no retries)
        run([t for t in all_trials if t["record_id"] not in done], "run", args.workers, cap=GEN_CAP_USD)
    else:
        merge()


if __name__ == "__main__":
    main()
