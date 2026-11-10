"""Resumable Phase 1: two baselines and three wrong-answer hints per question."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from .common import HINTS, LETTERS, append_jsonl, build_messages, read_jsonl, stable_hash, utc_now, write_jsonl


def make_trials(questions, model, backend, parameters):
    # The experiment ID excludes model identity so the two model conditions can
    # be compared; record IDs and file manifests still bind the exact model.
    experiment_id = stable_hash({"questions": questions, "parameters": parameters, "prompt_version": 1})[:20]
    trials = []
    for question in questions:
        if len(question["choices"]) != 4 or question["hint_letter"] == question["correct_answer"]:
            raise ValueError("Every question must have four options and a wrong assigned hint")
        for hint, repeat in [("none", 0), ("none", 1)] + [(h, None) for h in HINTS]:
            identity = [experiment_id, model, backend, question["question_id"], hint, repeat]
            messages = build_messages(question, hint)
            trials.append({"record_id": stable_hash(identity)[:24], "experiment_id": experiment_id,
                "question_id": question["question_id"], "subject": question["subject"],
                "correct_answer": question["correct_answer"], "hint_letter": question["hint_letter"],
                "hint_type": hint, "baseline_repeat": repeat, "model": model, "backend": backend,
                "synthetic": backend == "mock", "prompt": messages[0]["content"], "messages": messages,
                "seed": int(stable_hash([parameters["seed"], question["question_id"], hint, repeat])[:8], 16) % (2**31),
                "parameters": parameters})
    return trials


def mock_response(trial):
    """Deterministic fixtures to exercise the pipeline, never research evidence."""
    n = int(stable_hash(trial["question_id"])[:8], 16)
    correct, target = trial["correct_answer"], trial["hint_letter"]
    answer = correct
    if trial["hint_type"] == "none" and trial["baseline_repeat"] == 1 and n % 7 == 0:
        answer = target
    elif trial["hint_type"] != "none":
        thresholds = {"sycophancy": 5, "metadata": 7, "grader_hacking": 9}
        if n % 10 < thresholds[trial["hint_type"]]:
            answer = target
    reasoning = "SYNTHETIC TEST FIXTURE. This text was created by a deterministic software test, not a language model."
    if answer == target and trial["hint_type"] != "none" and n % 3 == 0:
        reasoning += " I rely on the supplied hint to choose the answer."
    return {"reasoning": reasoning, "content": f"Answer: ({answer})", "answer": answer,
            "status": "ok", "finish_reason": "stop", "usage": {}, "cost_usd": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default="data/questions.jsonl")
    parser.add_argument("--backend", required=True, choices=["local", "openrouter", "mock"])
    parser.add_argument("--model")
    parser.add_argument("--revision")
    parser.add_argument("--provider", help="Pin an OpenRouter provider slug when known")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=20, help="Questions, not requests; 5 requests per question")
    parser.add_argument("--seed", type=int, default=20261109)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--temperature", type=float, default=.6)
    parser.add_argument("--top-p", type=float, default=.95)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--budget-usd", type=float, default=8.0, help="Per output file, including prior calls; judge has separate budget")
    parser.add_argument("--plan", action="store_true", help="Save planned prompts only; no model calls")
    args = parser.parse_args()
    questions = read_jsonl(args.questions)
    if not questions or args.limit <= 0 or args.limit > len(questions):
        parser.error("Questions must exist and limit must be between 1 and their count")
    if args.max_tokens <= 0 or args.temperature <= 0 or not 0 < args.top_p <= 1 or args.top_k <= 0:
        parser.error("Use positive token/top-k/temperature values and top-p in (0,1]")
    if len({q["question_id"] for q in questions}) != len(questions):
        parser.error("Duplicate question IDs")
    model = args.model or {"local": "Qwen/Qwen3-1.7B", "openrouter": "deepseek/deepseek-r1-0528", "mock": "synthetic/pipeline-test"}[args.backend]
    from .local_model import MODEL_REVISION
    revision = args.revision or (MODEL_REVISION if model == "Qwen/Qwen3-1.7B" else None)
    params = {"seed": args.seed, "max_tokens": args.max_tokens, "temperature": args.temperature,
              "top_p": args.top_p, "top_k": args.top_k}
    trials = make_trials(questions, model, args.backend, params)
    selected_ids = {q["question_id"] for q in questions[:args.limit]}
    selected = [t for t in trials if t["question_id"] in selected_ids]
    # Interleave conditions so time/provider drift does not track hint type.
    random.Random(args.seed).shuffle(selected)
    if args.plan:
        if Path(args.output).exists():
            parser.error("Plan output exists; choose a new path")
        write_jsonl(args.output, selected)
        print(f"Saved {len(selected)} planned requests; no model calls made")
        return
    output = Path(args.output)
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    manifest = {"experiment_id": trials[0]["experiment_id"], "model": model,
                "backend": args.backend, "revision": revision, "provider": args.provider,
                "parameters": params, "questions_sha256": stable_hash(questions), "device": args.device,
                "prompts_sha256": stable_hash([t["messages"] for t in trials])}
    if manifest_path.exists():
        if json.loads(manifest_path.read_text()) != manifest:
            parser.error("Output manifest differs; choose a separate output file for changed settings")
    elif output.exists():
        parser.error("Output exists without a manifest; do not mix untracked records")
    else:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    existing = read_jsonl(output)
    expected_ids = {t["record_id"] for t in trials}
    seen = {r["record_id"] for r in existing}
    if len(seen) != len(existing) or not seen <= expected_ids:
        parser.error("Output has duplicate or unexpected records")
    pending = [t for t in selected if t["record_id"] not in seen]
    print(f"{len(selected)} requests planned; {len(pending)} remaining. Existing failures are preserved, not silently retried.", flush=True)
    if not pending:
        return
    client = None
    if args.backend == "local":
        from .local_model import LocalModel
        client = LocalModel(model, revision=revision, device=args.device)
        for saved in existing:
            if saved.get("model_revision") and (saved["model_revision"] != client.revision or
                    saved.get("dtype") != str(client.model.dtype) or saved.get("device") != str(client.device)):
                parser.error("Loaded checkpoint, precision, or device differs from saved responses; use a new output file")
    elif args.backend == "openrouter":
        from .providers import OpenRouterClient
        client = OpenRouterClient(budget_usd=args.budget_usd, spent_usd=sum(r.get("cost_usd", 0) for r in existing),
                                  ledger_path=output.with_suffix(output.suffix + ".billing.jsonl"))
    for index, trial in enumerate(pending, 1):
        started = utc_now()
        prior_cost = getattr(client, "spent_usd", 0)
        try:
            if args.backend == "mock":
                result = mock_response(trial)
            elif args.backend == "local":
                result = client.generate(trial["messages"], seed=trial["seed"], max_new_tokens=args.max_tokens,
                    temperature=args.temperature, top_p=args.top_p, top_k=args.top_k)
            else:
                result = client.complete(trial["messages"], model=model, seed=trial["seed"], max_tokens=args.max_tokens,
                    temperature=args.temperature, top_p=args.top_p, top_k=args.top_k, provider=args.provider,
                    request_key=trial["record_id"])
        except Exception as exc:
            from .providers import BudgetExceededError
            if isinstance(exc, BudgetExceededError):
                print(str(exc) + " No request sent; this trial remains available to resume.", flush=True)
                raise SystemExit(1) from None
            # Never persist headers, environment variables or arbitrary provider error bodies.
            result = {"status": "error", "error_type": type(exc).__name__, "reasoning": "", "content": "", "answer": None,
                      "finish_reason": None, "usage": {}, "cost_usd": max(0, getattr(client, "spent_usd", 0) - prior_cost)}
            append_jsonl(output, {**trial, **result, "started_at": started, "finished_at": utc_now()})
            print(f"Stopped after {type(exc).__name__}. Saved failed record. Check credentials, budget, memory, or provider; failures are not automatically retried.", flush=True)
            raise SystemExit(1) from None
        append_jsonl(output, {**trial, **result, "started_at": started, "finished_at": utc_now()})
        print(f"[{index}/{len(pending)}] {trial['question_id']} {trial['hint_type']} -> {result['status']}", flush=True)


if __name__ == "__main__":
    main()
