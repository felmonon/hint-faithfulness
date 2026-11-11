"""v3: DeepSeek R1-0528 through OpenRouter on the same 750 prompts as Phase 1 v2.

python -m src.deepseek_v3 smoke              # 5 prompts, check that full reasoning comes back
python -m src.deepseek_v3 run --workers 8    # all 750 (resumes; failures kept, never retried)
python -m src.deepseek_v3 merge              # shard files -> responses.jsonl

Settings: temperature 0.6, top-p 0.95, max 8,192 output tokens, reasoning enabled and
not excluded, per-trial seed (pilot formula), no provider fallbacks. Provider recorded per call.
Parsed with the fixed parser v2. Spend counts toward the shared US$25 cap (src.judge_v2.spent).
"""
from __future__ import annotations

import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .common import append_jsonl, read_jsonl, write_jsonl, utc_now
from .parser_v2 import parse_answer_strict, parse_answer_v2, response_status_v2

MODEL = "deepseek/deepseek-r1-0528"
OUT = Path("artifacts/v2/deepseek")
PARAMS = {"seed": 20261109, "max_tokens": 8192, "temperature": .6, "top_p": .95}
GEN_CAP_USD = 15.0  # share of the US$25 total reserved for DeepSeek generation; judges use the rest


def trials():
    from .run import make_trials
    rows = make_trials(read_jsonl("data/questions.jsonl")[:150], MODEL, "openrouter", PARAMS)
    return sorted(rows, key=lambda t: t["record_id"])


def to_row(trial, result):
    reasoning, content, finish = result["reasoning"], result["content"], result["finish_reason"]
    parsed = parse_answer_v2(content)
    return {**trial, "reasoning": reasoning, "content": content, "answer": parsed["answer"],
            "answer_rule": parsed["rule"], "answer_letters": parsed["letters"],
            "status": response_status_v2(reasoning, content, finish, complete_thinking=True),
            "answer_strict": parse_answer_strict(content), "parser": "v2", "finish_reason": finish,
            "usage": result["usage"], "cost_usd": result["cost_usd"], "cost_is_estimate": result["cost_is_estimate"],
            "provider": result["provider"], "resolved_model": result["resolved_model"],
            "reasoning_chars": len(reasoning), "finished_at": utc_now()}


def call(client, trial):
    try:
        result = client.complete(trial["messages"], MODEL, max_tokens=PARAMS["max_tokens"],
                                 temperature=PARAMS["temperature"], top_p=PARAMS["top_p"], top_k=None,
                                 seed=trial["seed"], reasoning=True, request_key=trial["record_id"])
        return to_row(trial, result)
    except Exception as error:  # noqa: BLE001 - every failure is kept as a row, not retried
        return {**trial, "status": "error", "error": f"{type(error).__name__}: {error}", "finished_at": utc_now()}


def run(selected, shard_name, workers, cap):
    from .judge_v2 import spent
    from .providers import OpenRouterClient
    OUT.mkdir(parents=True, exist_ok=True)
    budget = min(cap, 25.0 - spent())
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
    args = parser.parse_args()
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
