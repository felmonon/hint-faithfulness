#!/usr/bin/env python3
"""Run or exactly resume the fixed 198-response Phase 3 pilot on CUDA."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from src.common import read_jsonl, utc_now
from src.phase3 import load_records, paired_prompts, target_stratified_split


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    os.chdir(PROJECT)
    plan_path = PROJECT / "docs/phase3-pilot-plan.json"
    plan = json.loads(plan_path.read_text())
    source = PROJECT / plan["source_path"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == plan["source_sha256"]
    rows, _ = load_records(source, include_invalid_source_outcomes=True)
    _, hinted, ids = paired_prompts(rows, require_complete=True)
    targets = {qid: hinted[qid][0]["hint_letter"] for qid in ids}
    train, test = target_stratified_split(ids, targets, plan["seed"])
    assert train == plan["train_question_ids"] and test == plan["test_question_ids"]
    assert targets == plan["assigned_targets"] and len(test) * 33 == plan["planned_generations"]
    out = PROJECT / "artifacts/pilot-20-phase3-v1"
    if out.exists() and not args.resume:
        raise FileExistsError("Preserve existing results; use explicit --resume for this identical plan")
    if args.resume and (not (out / "plan.json").exists()
                        or json.loads((out / "plan.json").read_text()) != plan):
        raise ValueError("Resume requires the identical saved plan")
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("This fixed run requires a CUDA GPU")
    from src.provenance import capture
    out.mkdir(parents=True, exist_ok=True)
    runtime = "runtime.json" if not args.resume else "runtime-resume-" + utc_now().replace(":", "-") + ".json"
    (out / runtime).write_text(json.dumps(capture(), indent=2) + "\n")
    if not args.resume:
        (out / "plan.json").write_bytes(plan_path.read_bytes())
    command = [sys.executable, "-u", "-m", "src.phase3", "--records", str(source),
               "--out-dir", str(out), "--include-invalid-source-outcomes", "--stratify-targets",
               "--layer", str(plan["layer"]), "--strengths", "0,1,2,4,8",
               "--max-new-tokens", str(plan["max_new_tokens"]), "--seed", str(plan["seed"]),
               "--device", "cuda"]
    if args.resume:
        command.append("--resume")
    print("PHASE3_START", utc_now(), flush=True)
    subprocess.run(command, check=True)
    results = read_jsonl(out / "steering.jsonl")
    assert len(results) == plan["planned_generations"] == len({r["record_id"] for r in results})
    (out / "completion.json").write_text(json.dumps({"finished_at": utc_now(),
        "records": len(results), "status": "complete_fixed_sweep", "human_labels": 0}, indent=2) + "\n")
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "checksums.sha256")
    (out / "checksums.sha256").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out)}\n" for p in files))
    print("PHASE3_COMPLETE", utc_now(), flush=True)


if __name__ == "__main__":
    main()
