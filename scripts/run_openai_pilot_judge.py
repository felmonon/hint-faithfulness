#!/usr/bin/env python3
"""Run the approved fixed judge stages; one shared $2 journal, no automatic retries."""
import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from src.common import read_jsonl
from src.judge import run_judge
from src.providers import ledger_state
MODEL = "gpt-4.1-mini-2025-04-14"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_approved_key(project):
    """Only the confirmed file and secure helper's literal syntax; no expansion."""
    path = Path(project) / ".env.local"
    require(not path.is_symlink(), "Credential file must not be a symlink")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
        info = os.fstat(handle.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_mode & 0o077 == 0, "Credential file must be private")
        content = handle.read(16385)
    require(len(content) <= 16384, "Credential file exceeds supported size")
    lines = [line.strip() for line in content.splitlines()
             if re.match(r"^(?:export[ \t]+)?OPENAI_API_KEY=", line.strip())]
    require(len(lines) == 1, "Expected one literal OPENAI_API_KEY assignment")
    match = re.fullmatch(r"(?:export[ \t]+)?OPENAI_API_KEY=(sk-[A-Za-z0-9_-]+)", lines[0])
    require(match is not None, "Unsupported credential assignment syntax")
    return match.group(1)


def inspect_saved(output):
    saved = read_jsonl(output)
    ledger = output.with_suffix(output.suffix + ".billing.jsonl")
    require(not saved or ledger.exists(), "Saved verdicts require their original billing journal")
    spent, pending = ledger_state(ledger) if ledger.exists() else (0.0, {})
    require(not pending, "Pending API request requires reconciliation; no retry was made")
    require(0 <= spent <= 2, "Shared recorded/reserved budget is invalid or exhausted")
    require(all(row.get("status") == "ok" for row in saved), "Saved judge error requires inspection; no retry was made")
    ids = {row["record_id"] for row in saved}
    require(len(ids) == len(saved), "Duplicate saved verdict IDs")
    return ids, spent


def execute_stage(stage, project=PROJECT):
    project = Path(project)
    folder = project / "results/pilot-20-openai-v1"
    plan = json.loads((folder / "run-plan.json").read_text())
    original = plan["original_eligible_ids"]
    allowed = set(original[:5] if stage == "smoke" else original if stage == "original" else plan["composite_eligible_ids"])
    source = project / "artifacts/pilot-20-qwen3-1.7b" / ("recovery-composite/responses.jsonl" if stage == "composite" else "responses.jsonl")
    raw = source.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == plan["source_sha256"]["composite100" if stage == "composite" else "original90"], "Source differs from approved plan")
    output = folder / "judgments.jsonl"
    existing, _ = inspect_saved(output)
    require(existing <= allowed, "This stage has already been passed")
    prerequisites = set(original[:5]) if stage == "original" else set(original) if stage == "composite" else set()
    require(prerequisites <= existing, "Complete and inspect the preceding stage first")
    remaining = len(allowed - existing)
    if remaining:
        os.environ["OPENAI_API_KEY"] = load_approved_key(project)
        try:
            run_judge([json.loads(line) for line in raw.splitlines() if line.strip()], output,
                      model=MODEL, budget=2.0, max_tokens=800, limit=remaining,
                      retry_errors=False, backend="openai")
        finally:
            os.environ.pop("OPENAI_API_KEY", None)
    completed, spent = inspect_saved(output)
    require(completed == allowed, "Stage incomplete; inspect saved artifacts before continuing")
    return {"stage": stage, "ok": True, "completed_unique_verdicts": len(completed),
            "shared_recorded_or_reserved_usd": spent, "human_validation": "pending; machine judgments only"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("smoke", "original", "composite"))
    args = parser.parse_args()
    try:
        result = execute_stage(args.stage)
    except Exception as exc:
        # Never echo arbitrary exception bodies, which could include credentials.
        parser.exit(1, f"Judge stage stopped ({type(exc).__name__}); inspect saved artifacts. No automatic retry.\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
