#!/usr/bin/env python3
"""Prepare/finalize the fixed ten-slot recovery. No inference or shell commands.

Download this file outside the frozen checkout, then run:
  python /content/recover_pilot.py prepare --project /content/hint-faithfulness
Run the original frozen src.run separately against recovery-composite/responses.jsonl.
  python /content/recover_pilot.py finalize --project /content/hint-faithfulness
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SOURCE_REVISION = "fe4de16013bf9e3e9a9d66abd5b47401becbe24a"
SOURCE_HASHES = {
    "src/__init__.py": "fe44e39aca7a377aa6d373837543100d578cd7c4669e20d1cdf7980d867624e1",
    "src/common.py": "665d1d7866e87dac4afd0cff9e12c7be190a57e6daaa9cb692441e1475cc9d9d",
    "src/run.py": "00ddfbfae2aa3dc5f1de34a690c8a6d98497bdb353992f31f0e497b71bac002e",
    "src/local_model.py": "b7a549ace225611660eb0c27ca03ba12cb1d4a180407b7138c1fd223fdb68766",
}
QUESTION_HASH = "027ec5964680541b8f0c24310611a7b85670760fa011cd071b255a9622ea313b"
QUESTION_BYTES_HASH = "e659d7f6a13e6c596fc8b3aee4058090d2338ab5f585c360aa614ac3f5eaff60"
MODEL = "Qwen/Qwen3-1.7B"
MODEL_REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
PARAMETERS = {"seed": 20261109, "max_tokens": 4096, "temperature": .6, "top_p": .95, "top_k": 20}
MISSING_BY_ORDINAL = {
    9: "56eb54c340a8fab1fdc084f8", 10: "9401acc6eb1ba91c6fd0f593", 11: "72b0eb898a913ea07c61bf45",
    12: "1e7982bf8dd33ea4edb4b098", 13: "21c4733d63a33222e277ca87", 14: "c7aca6252fe59b3745dba582",
    15: "e82036ed9c984233febd9438", 16: "3655610b6c73cdb9613c2b14",
    25: "d2f3a52213ca8cda500eb816", 26: "30fa7eb2bc600f9270a4a4e0",
}
RAW_NAME, MANIFEST_NAME = "responses.jsonl", "responses.jsonl.manifest.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def timestamp(value):
    require(isinstance(value, str), "Missing timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.utcoffset() == timedelta(0), "Timestamps must include UTC timezone")
    return parsed


def parse_rows(raw):
    require(raw.endswith(b"\n"), "JSONL must end with a complete newline before recovery")
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    require(all(isinstance(row, dict) and isinstance(row.get("record_id"), str) for row in rows), "Malformed response objects")
    require(len({row["record_id"] for row in rows}) == len(rows), "Duplicate response IDs")
    return rows


def _head(project):
    git_dir = project / ".git"
    require(git_dir.is_dir(), "Expected a normal frozen Git checkout with a .git directory")
    value = (git_dir / "HEAD").read_text().strip()
    if value.startswith("ref: "):
        ref = value[5:]
        require(ref.startswith("refs/") and ".." not in Path(ref).parts, "Invalid HEAD reference")
        loose = git_dir / ref
        if loose.is_file():
            return loose.read_text().strip()
        for line in (git_dir / "packed-refs").read_text().splitlines():
            if line.endswith(" " + ref):
                return line.split()[0]
        raise ValueError("Cannot resolve frozen HEAD")
    return value


def verify_project(project):
    project = Path(project).resolve()
    require(not Path(__file__).resolve().is_relative_to(project), "Run the downloaded helper OUTSIDE the frozen checkout")
    require(_head(project) == SOURCE_REVISION, "Project HEAD is not the frozen fe4 source revision")
    for name, digest in SOURCE_HASHES.items():
        require(sha((project / name).read_bytes()) == digest, f"Frozen source differs: {name}")
    # An isolated package avoids accidentally importing a newer checkout's src
    # already present in sys.modules (including when this helper is unit-tested).
    package = "_frozen_recovery_" + sha(str(project).encode())[:16]
    if package not in sys.modules:
        spec = importlib.util.spec_from_file_location(package, project / "src/__init__.py",
                                                     submodule_search_locations=[str(project / "src")])
        module = importlib.util.module_from_spec(spec)
        sys.modules[package] = module
        spec.loader.exec_module(module)
    common, runner = importlib.import_module(package + ".common"), importlib.import_module(package + ".run")
    raw = (project / "data/questions.jsonl").read_bytes()
    require(sha(raw) == QUESTION_BYTES_HASH, "Frozen question file bytes differ")
    questions = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    require(common.stable_hash(questions) == QUESTION_HASH and len(questions) == 150, "Frozen question objects differ")
    all_trials = runner.make_trials(questions, MODEL, "local", PARAMETERS)
    selected_ids = {question["question_id"] for question in questions[:20]}
    trials = [trial for trial in all_trials if trial["question_id"] in selected_ids]
    random.Random(PARAMETERS["seed"]).shuffle(trials)
    require(len(trials) == 100, "Expected 100 frozen trials")
    require(all(trials[n - 1]["record_id"] == rid for n, rid in MISSING_BY_ORDINAL.items()), "Fixed missing ordinals do not match reconstructed trials")
    manifest = {"experiment_id": trials[0]["experiment_id"], "model": MODEL, "backend": "local",
                "revision": MODEL_REVISION, "provider": None, "parameters": PARAMETERS,
                "questions_sha256": QUESTION_HASH, "device": "cuda",
                "prompts_sha256": common.stable_hash([trial["messages"] for trial in all_trials])}
    return common, trials, manifest


def check_rows(rows, trials, common):
    expected = {trial["record_id"]: trial for trial in trials}
    for row in rows:
        require(row["record_id"] in expected, "Unexpected response ID")
        require(all(key in row and common.stable_hash(row[key]) == common.stable_hash(value)
                    for key, value in expected[row["record_id"]].items()), "Response trial metadata differs from frozen settings")
        require(timestamp(row.get("finished_at")) >= timestamp(row.get("started_at")), "Reversed response timestamps")
        if row.get("status") == "error":
            require(row.get("finish_reason") is None and row.get("answer") is None, "Malformed error response")
            continue
        require(row.get("model_revision") == MODEL_REVISION and row.get("dtype") == "torch.float16"
                and re.fullmatch(r"cuda(?::\d+)?", str(row.get("device", ""))), "Response model/precision/device differs")
        require(row.get("finish_reason") in ("stop", "length") and type(row.get("complete_thinking")) is bool,
                "Malformed generation status")
        require(isinstance(row.get("reasoning"), str) and isinstance(row.get("content"), str), "Missing response text")
        expected_status = common.response_status(row["reasoning"], row["content"], row["finish_reason"])
        if not row["complete_thinking"] and row["finish_reason"] == "stop":
            expected_status = "incomplete_thinking"
        require(row.get("status") == expected_status and row.get("answer") == common.parse_answer(row["content"]), "Response status/answer disagrees with frozen parser")


def original_snapshot(original, trials, manifest, common):
    names = [RAW_NAME, MANIFEST_NAME, "collection.log"]
    if (original / "runtime.json").exists():
        names.append("runtime.json")
    files = {name: (original / name).read_bytes() for name in names}
    require(json.loads(files[MANIFEST_NAME]) == manifest, "Original runner manifest differs from frozen settings")
    rows = parse_rows(files[RAW_NAME])
    expected_ids = {trial["record_id"] for trial in trials}
    require(len(rows) == 90 and expected_ids - {row["record_id"] for row in rows} == set(MISSING_BY_ORDINAL.values()),
            "Original loss is not exactly the fixed ten slots; do not expand recovery silently")
    check_rows(rows, trials, common)
    matches = re.findall(r"(?m)^\[(\d+)/100\] (\S+) (\S+) -> ([a-z_]+)\s*$", files["collection.log"].decode("utf-8"))
    require(len(matches) == 100 and [int(match[0]) for match in matches] == list(range(1, 101)),
            "Original collection log does not show exactly 100 completed attempts in order")
    statuses = {}
    for trial, (_, question, hint, status) in zip(trials, matches):
        require(question == trial["question_id"] and hint == trial["hint_type"], "Original log order differs from frozen trial order")
        statuses[trial["record_id"]] = status
    require(all(statuses[row["record_id"]] == row["status"] for row in rows), "Retained responses disagree with original logged statuses")
    if "runtime.json" in files:
        require(json.loads(files["runtime.json"]).get("git_commit") == SOURCE_REVISION, "Original runtime records a different source revision")
    return files, rows, statuses


def paths(project, original=None, composite=None):
    project = Path(project).resolve()
    original = Path(original).resolve() if original else project / "artifacts/pilot-20-qwen3-1.7b"
    composite = Path(composite).resolve() if composite else original / "recovery-composite"
    require(original != composite, "Recovery directory must differ from original")
    return project, original, composite


def prepare(project, original=None, composite=None):
    project, original, composite = paths(project, original, composite)
    require(not composite.exists(), "Recovery directory already exists; nothing will be overwritten")
    common, trials, manifest = verify_project(project)
    files, rows, statuses = original_snapshot(original, trials, manifest, common)
    preparation = {"schema_version": 1, "prepared_at": utc_now(), "source_revision": SOURCE_REVISION,
                   "project": str(project), "original_directory": str(original), "composite_directory": str(composite),
                   "script_sha256": sha(Path(__file__).read_bytes()), "source_file_sha256": SOURCE_HASHES,
                   "questions_sha256": QUESTION_HASH,
                   "original_files": {name: {"sha256": sha(data), "bytes": len(data)} for name, data in files.items()},
                   "original_record_ids": [row["record_id"] for row in rows],
                   "missing_record_ids": list(MISSING_BY_ORDINAL.values()), "original_logged_statuses": statuses,
                   "original_attempts": 100, "preserved_original_rows": 90,
                   "notice": "Recovery generates new responses; matching seeds do not establish equality to lost text."}
    composite.mkdir(parents=True, exist_ok=False)
    for name in (RAW_NAME, MANIFEST_NAME):
        with (composite / name).open("xb") as handle:
            handle.write(files[name])
    with (composite / "lineage-preparation.json").open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(preparation, indent=2) + "\n")
    return preparation


def finalize(project, original=None, composite=None):
    project, original, composite = paths(project, original, composite)
    require(not (composite / "lineage.json").exists(), "Final lineage already exists; nothing will be overwritten")
    common, trials, manifest = verify_project(project)
    preparation_bytes = (composite / "lineage-preparation.json").read_bytes()
    prep = json.loads(preparation_bytes)
    require(prep.get("project") == str(project) and prep.get("original_directory") == str(original)
            and prep.get("composite_directory") == str(composite), "Preparation paths differ")
    require(prep.get("script_sha256") == sha(Path(__file__).read_bytes()) and prep.get("source_revision") == SOURCE_REVISION
            and prep.get("missing_record_ids") == list(MISSING_BY_ORDINAL.values()), "Recovery helper/source or fixed plan changed")
    files, original_rows, statuses = original_snapshot(original, trials, manifest, common)
    require(prep.get("original_files") == {name: {"sha256": sha(data), "bytes": len(data)} for name, data in files.items()},
            "Original evidence changed after preparation")
    require(prep.get("original_record_ids") == [row["record_id"] for row in original_rows]
            and prep.get("original_logged_statuses") == statuses, "Original identities changed after preparation")
    raw = (composite / RAW_NAME).read_bytes()
    require(raw.startswith(files[RAW_NAME]), "Retained original byte prefix was changed or replaced")
    require((composite / MANIFEST_NAME).read_bytes() == files[MANIFEST_NAME], "Copied manifest changed")
    rows = parse_rows(raw)
    require(len(rows) == 100 and {row["record_id"] for row in rows} == {trial["record_id"] for trial in trials},
            "Composite does not contain exactly the expected 100 unique slots")
    require(rows[:90] == original_rows, "Retained original record identities or contents changed")
    appended = rows[90:]
    require({row["record_id"] for row in appended} == set(MISSING_BY_ORDINAL.values()), "Appended responses are not exactly the fixed ten slots")
    check_rows(appended, trials, common)
    require(all(timestamp(row["started_at"]) >= timestamp(prep["prepared_at"]) for row in appended), "Recovery timestamps precede preparation")
    original_runtime = {(row.get("model_revision"), row.get("dtype"), row.get("device")) for row in original_rows if row.get("status") != "error"}
    require(len(original_runtime) == 1 and all((row.get("model_revision"), row.get("dtype"), row.get("device")) in original_runtime
            for row in appended if row.get("status") != "error"), "Recovery model/precision/device differs from retained originals")
    original_ids = set(prep["original_record_ids"])
    ordinals = {trial["record_id"]: n for n, trial in enumerate(trials, 1)}
    lineage = {"schema_version": 1, "finalized_at": utc_now(), "prepared_at": prep["prepared_at"],
               "source_revision": SOURCE_REVISION, "script_sha256": prep["script_sha256"],
               "preparation_sha256": sha(preparation_bytes), "original_files": prep["original_files"],
               "composite_responses_sha256": sha(raw), "composite_manifest_sha256": sha(files[MANIFEST_NAME]),
               "counts": {"original_attempts": 100, "preserved_original_rows": 90, "recovery_attempts": 10,
                          "composite_rows": 100, "total_generation_attempts": 110},
               "records": [{"record_id": row["record_id"], "original_ordinal": ordinals[row["record_id"]],
                            "origin": "retained_original" if row["record_id"] in original_ids else "recovery_generation",
                            "record_sha256": common.stable_hash(row), "original_logged_status": statuses[row["record_id"]]}
                           for row in rows], "notice": prep["notice"]}
    with (composite / "lineage.json").open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(lineage, indent=2) + "\n")
    return lineage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "finalize"))
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--original", type=Path, help="Original run directory; defaults to project/artifacts/pilot-20-qwen3-1.7b")
    parser.add_argument("--composite", type=Path, help="New composite directory; defaults to original/recovery-composite")
    args = parser.parse_args()
    try:
        result = (prepare if args.phase == "prepare" else finalize)(args.project, args.original, args.composite)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Recovery {args.phase} refused: {exc}\n")
    print(json.dumps({"phase": args.phase, "ok": True, "prepared_at": result["prepared_at"],
                      "counts": result.get("counts", {"original_attempts": 100, "preserved_original_rows": 90, "missing_slots": 10})}, indent=2))


if __name__ == "__main__":
    main()
