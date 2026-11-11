#!/usr/bin/env python3
"""Offline acquisition check for notebook08 exports; not the completed-data audit.

Never executes notebook cells, fetches files, reads credentials, or runs a model.
Only a fresh output directory is accepted. The source download is preserved.
"""
from __future__ import annotations

import argparse
import ast
import base64
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tempfile

PROJECT = Path(__file__).resolve().parents[1]
REFERENCE = "notebooks/08_resume_phase3_latest_checkpoint.ipynb"
REFERENCE_COMMIT = "cef711f2da01e9b1799b9f6e238737652cb0a460"
REFERENCE_SHA256 = "6f797815077c6757ea61d01c1b0fb0af759c35db17ba5aa60a045f3400a8b495"
CHECKPOINT_COMMIT = "06ff192c6662819b893ebdec931f2bbbf2d70b17"
SCIENTIFIC_COMMIT = "ef90362c287774a9d22ffa05a87f9faa960cad4e"
RUN = "artifacts/pilot-20-phase3-v1/"
CHECKPOINT = "artifacts/pilot-20-phase3-checkpoint-1110/"
FINAL = {"summary.jsonl", "explanation_labels.csv", "EXPLANATION_SUMMARY.md", "LABELING.md",
         "steering_rates.png", "completion.json", "checksums.sha256"}
PROTOCOLS = {"docs/PHASE3_SECOND_RESUME_PROTOCOL.md", "docs/PHASE3_RESUME_PROTOCOL.md",
             "docs/PHASE3_L4_ADDENDUM_ERRATUM.md"}
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def stable_hash(value):
    # Exact frozen src.common.stable_hash serialization; no inference imports.
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def json_object(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    def reject_constant(_):
        raise ValueError("Non-finite JSON number")

    result = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=reject_constant)
    require(isinstance(result, dict), "Expected a JSON object")
    return result


def checked_path(path):
    path = Path(path).absolute()
    require(not any(part.is_symlink() for part in (path, *path.parents)), "Symlink path rejected")
    return path.resolve()


def read_bytes(path):
    path = checked_path(path)
    require(path.is_file(), "Expected a regular input file")
    require(path.stat().st_size <= MAX_TOTAL, "Input exceeds 256 MiB limit")
    return path.read_bytes()


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0, "Timestamp must be UTC")
    return parsed


def load_reference(project):
    raw = read_bytes(project / REFERENCE)
    require(sha(raw) == REFERENCE_SHA256, "Published notebook08 reference hash differs")
    notebook = json_object(raw)
    constants = {}
    for node in ast.parse("".join(notebook["cells"][2]["source"])).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                constants[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    return notebook, constants


def extract_snapshot(raw, reference):
    document = json_object(raw)
    if document.get("schema") == "phase3-recovery-snapshot-v1":
        return document, "standalone_json", False
    cells = document.get("cells", [])
    require(len(cells) == len(reference["cells"]) == 8, "Notebook cell count differs")
    for current, expected in zip(cells, reference["cells"]):
        source = "".join(current["source"]).replace("COPIED_TO_DRIVE = True", "COPIED_TO_DRIVE = False")
        require(current["cell_type"] == expected["cell_type"] and source == "".join(expected["source"]),
                "Notebook08 source differs")
    snapshots = [output.get("data", {}).get("application/json")
                 for cell in cells for output in cell.get("outputs", [])]
    snapshots = [value for value in snapshots if isinstance(value, dict)
                 and value.get("schema") == "phase3-recovery-snapshot-v1"]
    require(len(snapshots) == 1, "Expected exactly one structured snapshot; no automatic latest selection")
    return snapshots[0], "notebook", True


def decode_files(files):
    require(isinstance(files, dict), "Missing snapshot files")
    decoded, total = {}, 0
    for name, item in files.items():
        relative = PurePosixPath(name)
        require(name and not relative.is_absolute() and ".." not in relative.parts
                and str(relative) == name and "\\" not in name, "Unsafe payload path")
        require(relative.parts[0] in ("artifacts", "docs"), "Unexpected payload root")
        require(item.get("encoding") == "gzip+base64", "Unknown payload encoding")
        require(type(item.get("bytes")) is int and 0 <= item["bytes"] <= MAX_FILE, "Invalid payload size")
        require(type(item.get("compressed_bytes")) is int and 0 <= item["compressed_bytes"] <= MAX_FILE,
                "Invalid compressed size")
        compressed = base64.b64decode(item["base64"], validate=True)
        require(len(compressed) == item["compressed_bytes"] and sha(compressed) == item["compressed_sha256"],
                "Compressed payload size/hash differs")
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            raw = stream.read(item["bytes"] + 1)
        require(len(raw) == item["bytes"] and sha(raw) == item["sha256"], "Decoded payload size/hash differs")
        total += len(raw)
        require(total <= MAX_TOTAL, "Decoded snapshot exceeds 256 MiB limit")
        decoded[name] = raw
    return decoded


def jsonl(raw):
    require(raw.endswith(b"\n"), "JSONL lacks a complete final newline")
    return [json_object(line) for line in raw.splitlines()]


def validate_snapshot(snap, decoded, constants, project, prior_paths):
    count = snap.get("retained_records")
    require(type(count) is int and 28 <= count <= 198, "Unexpected retained count")
    require(type(snap.get("complete_verified")) is bool, "Completion flag must be boolean")
    require(snap.get("checkpoint_commit") == CHECKPOINT_COMMIT
            and snap.get("scientific_commit") == SCIENTIFIC_COMMIT, "Source commit differs")
    require(snap.get("original_retained_records") == 8 and snap.get("restored_checkpoint_records") == 28,
            "Checkpoint lineage differs")
    old = constants["EXPECTED_SNAPSHOT_FILES"]
    publication = constants["LATEST_PUBLICATION_HASHES"]
    require(snap.get("restored_snapshot_sha256") == publication["snapshot.json"]
            and snap.get("second_resume_protocol_sha256") == constants["SECOND_PROTOCOL_SHA256"],
            "Frozen recovery identity differs")
    require(set(old) <= set(decoded), "Prior payloads missing")
    for name, identity in old.items():
        if name != RUN + "steering.jsonl":
            require(sha(decoded[name]) == identity["sha256"] and len(decoded[name]) == identity["bytes"],
                    "Preserved prior payload changed: " + name)
    for name, expected in publication.items():
        require(sha(decoded.get(CHECKPOINT + name, b"")) == expected, "Published checkpoint changed: " + name)
    for name in PROTOCOLS:
        require(decoded.get(name) == read_bytes(project / name), "Preserved protocol differs: " + name)
    require(sha(decoded["docs/PHASE3_SECOND_RESUME_PROTOCOL.md"]) == constants["SECOND_PROTOCOL_SHA256"],
            "Second protocol hash differs")
    original_name = "artifacts/pilot-20-phase3-checkpoint-0430/steering.jsonl"
    original = read_bytes(project / original_name)
    require(original == decoded[original_name], "Local original checkpoint differs from frozen payload")
    restored = decoded[CHECKPOINT + "steering.jsonl"]
    source = decoded[RUN + "steering.jsonl"]
    require(source.startswith(original) and restored.startswith(original) and source.startswith(restored),
            "Original eight-row or restored 28-row byte prefix changed")
    rows = jsonl(source)
    manifest = json_object(decoded[RUN + "manifest.json"])
    plan = json_object(decoded[RUN + "plan.json"])
    conditions = [("baseline", None, 0.0)] + [(d, letter, float(s)) for d in ("vector", "random")
                  for letter in "ABCD" for s in plan["strengths"] if s > 0]
    grid = [(stable_hash([stable_hash(manifest), q, d, letter, s]), q, d, letter, s)
            for q in plan["test_question_ids"] for d, letter, s in conditions]
    require(len(grid) == 198 and len(rows) == count, "Retained grid length differs")
    observed = [(r["record_id"], r["question_id"], r["direction"], r["target_letter"], r["strength"]) for r in rows]
    require(observed == grid[:count], "Unexpected, repeated or reordered grid identity")
    prior_checks = []
    for path in prior_paths:
        prior = read_bytes(path)
        prior_rows = jsonl(prior)
        require(28 <= len(prior_rows) <= count and prior.startswith(restored) and source.startswith(prior),
                "Supplied prior acquisition is not an unchanged prefix")
        prior_checks.append({"source_name": Path(path).name, "sha256": sha(prior), "records": len(prior_rows)})
    setups = [name for name in decoded if re.fullmatch(
        r"artifacts/pilot-20-phase3-resume-notebook-\d{8}T\d{6}\.\d{6}Z/setup\.json", name)]
    new_setups = set(setups) - set(old)
    require(len(setups) == 2 and len(new_setups) == 1, "Expected exactly two distinct setup records")
    setup_name = next(iter(new_setups))
    setup = json_object(decoded[setup_name])
    fixed_setup = {"checkpoint_commit": CHECKPOINT_COMMIT, "scientific_commit": SCIENTIFIC_COMMIT,
        "hardware_addendum_path": "docs/phase3-l4-resume-addendum.json",
        "hardware_addendum_sha256": constants["ADDENDUM_SHA256"],
        "hardware_addendum": json_object(decoded["docs/phase3-l4-resume-addendum.json"]),
        "second_resume_protocol_path": "docs/PHASE3_SECOND_RESUME_PROTOCOL.md",
        "restored_checkpoint_path": CHECKPOINT.rstrip("/"), "retained_original_records": 8,
        "restored_publication_sha256": publication,
        "restored_payload_sha256": {name: item["sha256"] for name, item in old.items()}}
    require(all(setup.get(key) == value for key, value in fixed_setup.items()), "New setup frozen identities differ")
    require(sha(decoded["docs/phase3-l4-resume-addendum.json"]) == constants["ADDENDUM_SHA256"],
            "Hardware declaration hash differs")
    require(setup["runtime"]["gpu_name"] == "NVIDIA L4"
            and setup["imported_versions"] == constants["EXPECTED_IMPORTED_VERSIONS"], "New L4 setup differs")
    require(setup["runtime"].get("git_commit") == CHECKPOINT_COMMIT
            and setup["runtime"].get("git_tracked_changes") == ""
            and setup["runtime"].get("cuda_available") is True
            and setup["runtime"].get("torch_version") == constants["EXPECTED_IMPORTED_VERSIONS"]["torch"]
            and setup["runtime"].get("cuda_version") == "13.0"
            and setup["runtime"].get("gpu_memory_bytes", 0) >= 22 * 1024**3,
            "New setup commit/clean tree/CUDA identity differs")
    require(setup["restored_retained_records"] == 28 and setup["planned_missing_positions"] == 170
            and setup["second_resume_protocol_sha256"] == constants["SECOND_PROTOCOL_SHA256"], "Setup lineage differs")
    log_name = str(PurePosixPath(setup_name).with_name("resume-execution.log"))
    runtimes = {name for name in decoded if re.fullmatch(re.escape(RUN) + r"runtime-resume-[0-9T:.+\-]+\.json", name)}
    require(len(runtimes) in (1, 2) and (count == 28 or len(runtimes) == 2), "Resumed runtime records missing/ambiguous")
    for name in runtimes:
        require(json_object(decoded[name])["gpu_name"] == "NVIDIA L4", "Resumed runtime is not L4")
    require(timestamp(rows[27]["finished_at"]) < timestamp(setup["runtime"]["captured_at"])
            <= timestamp(snap["captured_at_utc"]), "Snapshot/setup chronology differs")
    new_runtimes = runtimes - set(old)
    require(len(new_runtimes) <= 1 and (count == 28 or len(new_runtimes) == 1),
            "Second continuation runtime is missing/ambiguous")
    if new_runtimes:
        runtime = json_object(decoded[next(iter(new_runtimes))])
        require({k: v for k, v in runtime.items() if k != "captured_at"}
                == {k: v for k, v in setup["runtime"].items() if k != "captured_at"},
                "Runner runtime differs from checked setup")
        require(timestamp(setup["runtime"]["captured_at"]) <= timestamp(runtime["captured_at"])
                <= timestamp(snap["captured_at_utc"]), "Runner capture chronology differs")
    if count > 28:
        require(timestamp(runtime["captured_at"])
                <= timestamp(rows[28]["started_at"]) <= timestamp(rows[-1]["finished_at"])
                <= timestamp(snap["captured_at_utc"]), "Second continuation chronology differs")
        previous_finish = timestamp(runtime["captured_at"])
        for row in rows[28:]:
            started, finished = timestamp(row["started_at"]), timestamp(row["finished_at"])
            require(previous_finish <= started <= finished <= timestamp(snap["captured_at_utc"]),
                    "Retained continuation row chronology differs")
            previous_finish = finished
    allowed = set(old) | {CHECKPOINT + name for name in publication} | PROTOCOLS | runtimes | {setup_name, log_name}
    if snap["complete_verified"]:
        require(count == 198, "Incomplete grid marked complete")
        allowed |= {RUN + name for name in FINAL}
    require(set(decoded) == allowed, "Missing or unexpected snapshot payloads")
    if snap["complete_verified"]:
        completion = json_object(decoded[RUN + "completion.json"])
        require(completion.get("status") == "complete_fixed_sweep" and completion.get("records") == 198,
                "Completion marker differs")
        inventory = {}
        for line in decoded[RUN + "checksums.sha256"].decode("utf-8").splitlines():
            expected, name = line.split("  ", 1)
            require(name not in inventory and name != "checksums.sha256", "Duplicate or self checksum")
            require(RUN + name in decoded and sha(decoded[RUN + name]) == expected, "Final checksum differs")
            inventory[name] = expected
        require(set(inventory) == {name[len(RUN):] for name in decoded if name.startswith(RUN)} - {"checksums.sha256"},
                "Final checksum inventory is incomplete")
    return {"retained_records": count, "producer_complete_verified_claim": snap["complete_verified"],
            "payload_count": len(decoded), "original_eight_row_prefix_unchanged": True,
            "restored_28_row_prefix_unchanged": True, "ordered_grid_prefix_verified": True,
            "supplied_prior_prefixes": prior_checks,
            "prior_scope": "Only explicitly supplied prior JSONL files were checked; no acquisition history was discovered automatically."}


def verify_export(source, out, project=PROJECT, prior_paths=(), expected_bytes=None,
                  expected_sha256=None, source_modified_at=None):
    source, out, project = checked_path(source), checked_path(out), checked_path(project)
    require(not out.exists() and out.parent.is_dir(), "Output must be a fresh directory with an existing parent")
    require(not out.is_relative_to(project / "artifacts"), "Do not extract into raw artifact directories")
    raw = read_bytes(source)
    require(expected_bytes is None or len(raw) == expected_bytes, "Source download byte length differs")
    require(expected_sha256 is None or sha(raw) == expected_sha256, "Source download SHA-256 differs")
    if source_modified_at is not None:
        timestamp(source_modified_at)
    reference, constants = load_reference(project)
    snap, kind, notebook_checked = extract_snapshot(raw, reference)
    decoded = decode_files(snap["files"])
    checks = validate_snapshot(snap, decoded, constants, project, prior_paths)
    snapshot_raw = (json.dumps(snap, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()
    now = datetime.now(timezone.utc).isoformat()
    require(timestamp(snap["captured_at_utc"]) <= timestamp(now), "Snapshot capture is in the future")
    provenance = {"schema": "phase3-colab-acquisition-verification-v1", "verified_at_utc": now,
        "source": {"name": source.name, "bytes": len(raw), "sha256": sha(raw), "format": kind,
                   "provided_expected_bytes": expected_bytes, "provided_expected_sha256": expected_sha256,
                   "provided_modified_at": source_modified_at},
        "snapshot_sha256": sha(snapshot_raw), "snapshot_captured_at_utc": snap["captured_at_utc"],
        "reference_notebook": {"path": REFERENCE, "commit": REFERENCE_COMMIT, "sha256": REFERENCE_SHA256},
        "notebook_cells_checked": notebook_checked, "checks": checks,
        "tool_sha256": sha(Path(__file__).read_bytes()),
        "files_sha256": {name: sha(data) for name, data in decoded.items()},
        "limits": ["Offline preservation/transport checks only; the full198 token/text/scientific audit remains separate.",
                   "Source timestamps/checksum expectations are caller supplied, not authenticated by this tool.",
                   "Standalone JSON does not carry notebook source cells, so their equality was not checked.",
                   "Retained grid outcomes do not count unknown unarchived historical attempts.",
                   "No model, tokenizer, network, judge call, semantic label or full-read attestation was produced."]}
    # All validation precedes writes. Reserve exclusively; never reuse partial output.
    out.mkdir(exist_ok=False)
    with tempfile.TemporaryDirectory(prefix=".staging-", dir=out) as temporary:
        stage = Path(temporary)
        bundle = {"payloads/" + name: data for name, data in decoded.items()}
        bundle["source-export.ipynb" if kind == "notebook" else "source-export.json"] = raw
        bundle["snapshot.json"] = snapshot_raw
        bundle["acquisition-provenance.json"] = (json.dumps(provenance, indent=2, allow_nan=False) + "\n").encode()
        for name, data in bundle.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
        (stage / "checksums.sha256").write_text("".join(f"{sha(data)}  {name}\n" for name, data in sorted(bundle.items())))
        for item in stage.iterdir():
            require(not (out / item.name).exists(), "Output changed during staged extraction")
            item.rename(out / item.name)
    # A partial directory without this final marker must never be called preserved.
    with (out / "verification-complete.json").open("x") as stream:
        json.dump({"status": "acquisition_checks_passed", "retained_records": checks["retained_records"],
                   "checksums_sha256": sha((out / "checksums.sha256").read_bytes()),
                   "full_scientific_audit_passed": False}, stream, indent=2)
        stream.write("\n")
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Downloaded notebook08 .ipynb or standalone snapshot JSON")
    parser.add_argument("--out-dir", type=Path, required=True, help="New destination; existing directories are refused")
    parser.add_argument("--project", type=Path, default=PROJECT, help="Repository containing the pinned reference and checkpoints")
    parser.add_argument("--prior-jsonl", type=Path, action="append", default=[], help="Previously verified retained prefix; repeat for each acquisition")
    parser.add_argument("--expected-bytes", type=int)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--source-modified-at", help="Optional caller-supplied UTC acquisition metadata")
    args = parser.parse_args()
    result = verify_export(args.source, args.out_dir, args.project, args.prior_jsonl,
                           args.expected_bytes, args.expected_sha256, args.source_modified_at)
    print(json.dumps({"status": "acquisition_checks_passed", **result["checks"],
                      "source_sha256": result["source"]["sha256"], "full_scientific_audit_passed": False}))


if __name__ == "__main__":
    main()
