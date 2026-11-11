#!/usr/bin/env python3
"""Execute the frozen 20-question Phase 2 extension on a CUDA GPU."""
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from src.common import read_jsonl, utc_now
from src.phase2 import run_early, run_probe, select_local_records


def main():
    os.chdir(PROJECT)
    plan = json.loads((PROJECT / "artifacts/pilot-20-phase2-v1/plan.json").read_text())
    out = PROJECT / "artifacts/pilot-20-phase2-v1"
    if out.exists():
        raise FileExistsError("Preserve the existing run; do not silently rerun or overwrite it")
    sources = {}
    for name, spec in plan["sources"].items():
        path = PROJECT / spec["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != spec["sha256"]:
            raise ValueError("Phase 1 evidence hash differs from frozen plan")
        sources[name] = read_jsonl(path)
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("This fixed run requires a CUDA GPU")
    from src.local_model import LocalModel
    from src.provenance import capture
    out.mkdir(parents=True)
    (out / "runtime.json").write_text(json.dumps(capture(), indent=2) + "\n")
    (out / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    local = LocalModel(plan["model"], revision=plan["model_revision"], device="cuda")
    assert local.revision == plan["model_revision"]
    for name, source in sources.items():
        rows = select_local_records(source)
        destination = out / name
        destination.mkdir()
        args = SimpleNamespace(seed=plan["seed"], source_count=len(source),
                               source_status_counts=dict(Counter(r["status"] for r in source)))
        for command, run in (("early", run_early), ("probe", run_probe)):
            args.command = command
            print(f"START {name} {command} {utc_now()}", flush=True)
            run(local, rows, destination, args)
            print(f"DONE {name} {command} {utc_now()}", flush=True)
    files = sorted(p for p in out.rglob("*") if p.is_file())
    (out / "checksums.sha256").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out)}\n" for p in files))
    print("PHASE2_COMPLETE", utc_now(), flush=True)


if __name__ == "__main__":
    main()
