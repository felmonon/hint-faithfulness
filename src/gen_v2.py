"""Phase 1 v2: batched transformers generation, 150 questions x 5 conditions, checkpointed.

python -m src.gen_v2 --output artifacts/v2/phase1/responses.jsonl [--chunk 150]

Same prompts, per-trial seeds and sampling settings as the pilot (src.run.make_trials),
but backend "transformers-batched" so record IDs differ from the pilot. Parser v2 is primary;
the strict pilot parser is stored alongside. Every outcome, including failures,
is appended. Already-saved record IDs are skipped on resume (never retried).
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from .common import append_jsonl, read_jsonl, stable_hash, utc_now
from .parser_v2 import parse_answer_strict, parse_answer_v2, response_status_v2

MODEL = "Qwen/Qwen3-1.7B"
REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
PARAMS = {"seed": 20261109, "max_tokens": 4096, "temperature": .6, "top_p": .95, "top_k": 20}


def split_generation(tokenizer, generated, finish_reason):
    """Same thinking/answer split as the pilot's LocalModel.generate."""
    close = tokenizer.encode("</think>", add_special_tokens=False)[0]
    opening = tokenizer.encode("<think>", add_special_tokens=False)
    complete = close in generated
    if complete:
        boundary = generated.index(close)
        start = generated.index(opening[0]) + 1 if len(opening) == 1 and opening[0] in generated[:boundary] else 0
        reasoning_ids, answer_ids = generated[start:boundary], generated[boundary + 1:]
        reasoning = tokenizer.decode(reasoning_ids, skip_special_tokens=True)
        content = tokenizer.decode(answer_ids, skip_special_tokens=True).strip()
    else:
        reasoning_ids, reasoning, content = generated, tokenizer.decode(generated, skip_special_tokens=True), ""
    parsed = parse_answer_v2(content)
    status = response_status_v2(reasoning, content, finish_reason, complete_thinking=complete or finish_reason != "stop")
    strict = parse_answer_strict(content)
    status_strict = ("truncated" if finish_reason == "length" else
                     "incomplete_thinking" if not complete else
                     "invalid_answer" if strict is None else
                     "missing_reasoning" if not reasoning.strip() else "ok")
    return {"reasoning": reasoning, "content": content, "answer": parsed["answer"],
            "answer_rule": parsed["rule"], "answer_letters": parsed["letters"], "status": status,
            "answer_strict": strict, "status_strict": status_strict, "parser": "v2",
            "finish_reason": finish_reason, "complete_thinking": complete,
            "generated_token_ids": generated, "reasoning_token_ids": reasoning_ids}


def main():
    from .hf_batch import HFRunner, batch_seed
    from .run import make_trials
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default="data/questions.jsonl")
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int, default=150)
    args = parser.parse_args()
    questions = read_jsonl(args.questions)[:args.limit]
    trials = make_trials(questions, MODEL, "transformers-batched", PARAMS)
    random.Random(PARAMS["seed"]).shuffle(trials)
    out = Path(args.output)
    done = {r["record_id"] for r in read_jsonl(out)}
    pending = [t for t in trials if t["record_id"] not in done]
    print(f"{len(trials)} planned, {len(pending)} pending", flush=True)
    if not pending:
        return
    runner = HFRunner()
    manifest = out.with_suffix(".manifest.json")
    if not manifest.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"model": MODEL, "revision": REVISION, **runner.info, "parameters": PARAMS,
            "batch_size": args.batch_size, "questions_sha256": stable_hash(questions),
            "experiment_id": trials[0]["experiment_id"], "per_request_seed": False,
            "seeding": "one torch seed per batch = sha256(base seed, record ids in batch); per-trial 'seed' field is the pilot formula, not used by the sampler",
            "trial_order": "random.Random(20261109).shuffle over all 750 trials"}, indent=2) + "\n")
    tokenizer = runner.tok
    for start in range(0, len(pending), args.batch_size):
        chunk = pending[start:start + args.batch_size]
        prompts = [runner.prompt_ids(t["messages"]) for t in chunk]
        seed = batch_seed(PARAMS["seed"], [t["record_id"] for t in chunk])
        started, t0 = utc_now(), time.time()
        results = runner.generate(prompts, seed)
        elapsed = time.time() - t0
        for trial, ids, result in zip(chunk, prompts, results):
            generated = result["generated"]
            row = {**trial, **split_generation(tokenizer, generated, result["finish_reason"]),
                   "usage": {"prompt_tokens": len(ids), "completion_tokens": len(generated)},
                   "prompt_token_ids": ids, "model_revision": REVISION, "dtype": "float16",
                   "batch": {"batch_seed": seed, "batch_index": start // args.batch_size, "batch_size": len(chunk),
                             "batch_seconds": round(elapsed, 1)},
                   "started_at": started, "finished_at": utc_now()}
            append_jsonl(out, row)
        print(f"saved {start + len(chunk)}/{len(pending)} in {elapsed:.0f}s", flush=True)


if __name__ == "__main__":
    main()
