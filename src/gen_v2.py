"""Phase 1 v2: vLLM generation (per-request seeds); --backend hf is the batched-transformers fallback, 150 questions x 5 conditions, checkpointed.

python -m src.gen_v2 --output artifacts/v2/phase1/responses.jsonl [--chunk 150]

Same prompts, per-trial seeds and sampling settings as the pilot (src.run.make_trials),
but backend "vllm" (or "transformers-batched") so record IDs differ from the pilot. Parser v2 is primary;
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


def main_hf(args):
    from .hf_batch import HFRunner, batch_seed
    from .run import make_trials
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


def load_vllm(max_model_len=6144, max_num_seqs=128, enforce_eager=False):
    from vllm import LLM
    return LLM(model=MODEL, revision=REVISION, tokenizer_revision=REVISION, dtype="float16",
               max_model_len=max_model_len, max_num_seqs=max_num_seqs, seed=0,
               gpu_memory_utilization=.88, enable_prefix_caching=False, enforce_eager=enforce_eager)


def prompt_ids(tokenizer, messages):
    return tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                         enable_thinking=True, return_dict=False)


def main_vllm(args):
    from .run import make_trials
    questions = read_jsonl(args.questions)[:args.limit]
    trials = make_trials(questions, MODEL, "vllm", PARAMS)
    random.Random(PARAMS["seed"]).shuffle(trials)
    out = Path(args.output)
    done = {r["record_id"] for r in read_jsonl(out)}
    pending = [t for t in trials if t["record_id"] not in done]
    print(f"{len(trials)} planned, {len(pending)} pending", flush=True)
    if not pending:
        return
    import vllm
    from vllm import SamplingParams
    from vllm.inputs import TokensPrompt
    llm = load_vllm(max_num_seqs=args.max_num_seqs)
    tokenizer = llm.get_tokenizer()
    manifest = out.with_suffix(".manifest.json")
    info = {"model": MODEL, "revision": REVISION, "backend": "vllm", "vllm_version": vllm.__version__,
            "dtype": "float16", "parameters": PARAMS, "max_num_seqs": args.max_num_seqs,
            "chunk_size": args.chunk, "questions_sha256": stable_hash(questions),
            "experiment_id": trials[0]["experiment_id"], "per_request_seed": True,
            "prefix_caching": False, "engine": "vLLM V1 (default engine of this version)"}
    try:
        import torch
        info["gpu"] = torch.cuda.get_device_name(0)
        info["torch"] = torch.__version__
    except Exception:
        pass
    if not manifest.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(info, indent=2) + "\n")
    for start in range(0, len(pending), args.chunk):
        chunk = pending[start:start + args.chunk]
        prompts, sampling = [], []
        for trial in chunk:
            ids = prompt_ids(tokenizer, trial["messages"])
            prompts.append(TokensPrompt(prompt_token_ids=ids))
            sampling.append(SamplingParams(n=1, temperature=PARAMS["temperature"], top_p=PARAMS["top_p"],
                                           top_k=PARAMS["top_k"], max_tokens=PARAMS["max_tokens"],
                                           seed=trial["seed"], skip_special_tokens=False))
        started = utc_now()
        t0 = time.time()
        results = llm.generate(prompts, sampling, use_tqdm=True)
        elapsed = time.time() - t0
        for trial, prompt, result in zip(chunk, prompts, results):
            completion = result.outputs[0]
            generated = list(completion.token_ids)
            finish = "length" if completion.finish_reason == "length" else "stop" if completion.finish_reason == "stop" else str(completion.finish_reason)
            row = {**trial, "backend": "vllm", **split_generation(tokenizer, generated, finish),
                   "usage": {"prompt_tokens": len(prompt["prompt_token_ids"]), "completion_tokens": len(generated)},
                   "prompt_token_ids": prompt["prompt_token_ids"], "model_revision": REVISION,
                   "dtype": "float16", "batch": {"chunk_start": start, "chunk_size": len(chunk),
                                                "max_num_seqs": args.max_num_seqs, "chunk_seconds": round(elapsed, 1)},
                   "started_at": started, "finished_at": utc_now()}
            append_jsonl(out, row)
        print(f"saved {start + len(chunk)}/{len(pending)} in {elapsed:.0f}s", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("vllm", "hf"), default="vllm")
    parser.add_argument("--questions", default="data/questions.jsonl")
    parser.add_argument("--output", required=True)
    parser.add_argument("--chunk", type=int, default=150)
    parser.add_argument("--max-num-seqs", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int, default=150)
    args = parser.parse_args()
    (main_vllm if args.backend == "vllm" else main_hf)(args)


if __name__ == "__main__":
    main()
