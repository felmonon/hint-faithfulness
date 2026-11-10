#!/usr/bin/env python3
"""Audit the completed resumed Phase 3 artifacts offline, without model inference.

Checks exact checkpoint identity, ordered grid, cached tokenizer decoding, vectors,
and timestamp-based runtime lineage. Writes a separate AI audit, never raw artifacts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from scripts.analyze_phase3_pilot import require, validate_run, verify_inventory
from src.common import LETTERS, read_jsonl, stable_hash, utc_now
from src.phase3 import load_records

ORIGINAL_COMMIT = "ef90362c287774a9d22ffa05a87f9faa960cad4e"
CHECKPOINT_COMMIT = "3cf3f5b357ce273540d98dfcf2df1e64c96bfa6e"
HARDWARE_ADDENDUM_SHA256 = "b9c9afeeddc099297bfd3eb1c9652590afea97ffcf4be03a4c2ad16ef9716607"
MODEL = "Qwen/Qwen3-1.7B"
REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
CHECKPOINT_HASHES = {
    "manifest.json": "b6ab6444ac32113f1e00ebf3f1cba43a6344f00ada0b431ff7b4fdc03b74565c",
    "plan.json": "5ecc12c4f4d79161de442582f2bea7b89815a0ba06808eb130b00054de52d1f2",
    "runtime.json": "46c1201b9755f0ac8f317773cfdff9e82ed5c5ae966ee3528ff88232e59d0b64",
    "steering.jsonl": "5bec0702c11667104b6a37a3f15487b19dceb7358f771748e467b346ae63044b",
    "vector_metadata.json": "cf3a7ff327d4ef6eb496a0819c8af2539b1d5ee43636db284cbb5266dc0cba20",
    "vectors.npz": "9808b154bd3e584c53ba8fe784d3b5d47c67ec131a9c246fe0ca5dfc828e8c57",
    "execution.log": "5b580df84a568b4de5ad1f601844354302fdfaaf01e351f31d1e417d015373d9",
}
CHECKPOINT_PROVENANCE_SHA256 = "f012a8d91fc57206913e76a56416a3583a03f0053a691fcaed8e222095fd20a2"
CODE_HASHES = {
    "src/phase3.py": "57bb529ac9096f8892d3da6253d43b728d7fb562b1c1565a64c5b0691a28fcdc",
    "src/local_model.py": "b7a549ace225611660eb0c27ca03ba12cb1d4a180407b7138c1fd223fdb68766",
    "src/common.py": "665d1d7866e87dac4afd0cff9e12c7be190a57e6daaa9cb692441e1475cc9d9d",
    "scripts/run_phase3_pilot.py": "8e616c5b20f21c01682e215ea2ba0e8b5bf0ed8d145fd529c6497190474ef714",
}
FINAL_REQUIRED = set(CHECKPOINT_HASHES) | {
    "completion.json", "summary.jsonl", "explanation_labels.csv", "LABELING.md",
    "EXPLANATION_SUMMARY.md", "steering_rates.png",
}
CHECKLIST = [
    "Verify completed inventory and seven archived checkpoint hashes.",
    "Bind source, manifest, plan, vectors and frozen scientific code to the checkpoint.",
    "Require exact eight-row byte prefix and all 198 planned IDs in original order.",
    "Validate every grid row, seed, source link, strict parser, token boundary and termination.",
    "Independently retokenize all source prompts and decode all generated traces using cached pinned files.",
    "Verify finite float32 vectors, training counts, norm-matched seeded random controls.",
    "Check sequential UTC timestamps and original/resumed runtime segments; disclose inferred attribution.",
    "Rehash inputs after auditing; keep historical attempt count unknown and human validation absent.",
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def artifact_label(path, project=PROJECT):
    path = Path(path)
    return str(path.relative_to(project)) if path.is_relative_to(project) else str(path)


def utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.utcoffset() == timedelta(0), "Timestamp must explicitly use UTC")
    return parsed


def ordered_ids(manifest):
    conditions = [("baseline", None, 0.0)] + [
        (direction, target, float(strength)) for direction in ("vector", "random")
        for target in LETTERS for strength in manifest["strengths"] if strength > 0]
    digest = stable_hash(manifest)
    return [stable_hash([digest, qid, direction, target, strength])
            for qid in manifest["test_question_ids"] for direction, target, strength in conditions]


def audit_prefix(original, retained, expected_ids):
    require(original.endswith(b"\n") and retained.endswith(b"\n"), "JSONL must end on a complete newline")
    old = [json.loads(line) for line in original.splitlines()]
    rows = [json.loads(line) for line in retained.splitlines()]
    require(len(old) == 8 and retained.startswith(original), "Original eight-row byte prefix changed")
    require(len(rows) == len(expected_ids) == 198, "Expected 198 retained outcomes")
    require([row["record_id"] for row in rows] == expected_ids, "Retained IDs differ from the ordered fixed grid")
    return rows


def check_immutable(root, checkpoint):
    require(sha(checkpoint / "checkpoint-provenance.json") == CHECKPOINT_PROVENANCE_SHA256,
            "Checkpoint acquisition provenance bytes differ")
    provenance = json.loads((checkpoint / "checkpoint-provenance.json").read_text())
    require(provenance["files_sha256"] == CHECKPOINT_HASHES, "Checkpoint acquisition hashes differ from fixed evidence")
    require(provenance["retained_records"] == 8 and provenance["complete"] is False
            and provenance["captured_at_utc"] == "2026-11-10T04:28:37.649111+00:00", "Checkpoint metadata differs")
    for name, expected in CHECKPOINT_HASHES.items():
        require(not (checkpoint / name).is_symlink() and sha(checkpoint / name) == expected,
                f"Archived checkpoint differs: {name}")
        if name != "steering.jsonl":
            require(not (root / name).is_symlink() and sha(root / name) == expected,
                    f"Immutable resumed artifact differs: {name}")
    return provenance


def check_code(runtime_commit, project=PROJECT):
    require(isinstance(runtime_commit, str) and len(runtime_commit) == 40
            and all(c in "0123456789abcdef" for c in runtime_commit), "Runtime must identify a full commit")
    checked = {}
    for name, expected in CODE_HASHES.items():
        require(sha(project / name) == expected, f"Current scientific code differs: {name}")
        try:
            raw = subprocess.check_output(["git", "-C", str(project), "show", f"{runtime_commit}:{name}"],
                                          stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"Runtime commit {runtime_commit} is not locally available; no network fetch attempted") from exc
        require(hashlib.sha256(raw).hexdigest() == expected, f"Runtime commit changed scientific code: {name}")
        checked[name] = expected
    return checked


def audit_vectors(path, metadata, plan):
    import numpy as np
    counts = dict(Counter(plan["assigned_targets"][q] for q in plan["train_question_ids"]))
    require(counts == metadata["training_questions_per_letter"] == plan["train_target_counts"],
            "Training target counts differ")
    rng = np.random.default_rng(plan["seed"])
    results = []
    with np.load(path, allow_pickle=False) as data:
        require(set(data.files) == {f"{kind}_{letter}" for kind in ("vector", "random") for letter in LETTERS},
                "Unexpected vector array names")
        for letter in LETTERS:
            vector, random_vector = data[f"vector_{letter}"], data[f"random_{letter}"]
            require(vector.shape == random_vector.shape == (2048,) and
                    vector.dtype == random_vector.dtype == np.dtype("float32"), "Vector shape/dtype differs")
            require(np.isfinite(vector).all() and np.isfinite(random_vector).all(), "Nonfinite vector")
            norm, random_norm = float(np.linalg.norm(vector)), float(np.linalg.norm(random_vector))
            require(norm > 0 and np.isclose(norm, metadata["vector_norms"][letter], rtol=2e-7, atol=0),
                    "Steering norm differs from metadata")
            require(np.isclose(norm, random_norm, rtol=2e-7, atol=0), "Random control is not norm-matched")
            draw = rng.standard_normal(vector.shape).astype("float32")
            reproduced = draw * norm / np.linalg.norm(draw)
            require(np.allclose(reproduced, random_vector, rtol=2e-7, atol=1e-7), "Random direction differs from seeded recipe")
            results.append({"target": letter, "training_questions": counts[letter], "shape": list(vector.shape),
                            "dtype": str(vector.dtype), "finite": True, "vector_norm": norm,
                            "random_norm": random_norm, "random_reproduction_exact": bool(np.array_equal(reproduced, random_vector)),
                            "random_reproduction_max_abs_difference": float(np.max(np.abs(reproduced - random_vector)))})
    return {"arrays": results, "numpy": np.__version__, "norm_rtol": 2e-7,
            "identity_gate": "Exact NPZ file SHA256; numeric tolerances only handle local reduction roundoff",
            "weighting": "Equal three-hint mean within each question, then equal question mean within target group",
            "limitation": "Training activations are not stored; steering means were not independently recomputed."}


def load_cached_tokenizer(model=MODEL, revision=REVISION):
    """Load tokenizer/config only; never download or instantiate a model."""
    require(model == MODEL and revision == REVISION, "Unexpected pinned tokenizer identity")
    from huggingface_hub import try_to_load_from_cache
    from transformers import AutoTokenizer
    files = {}
    for name in ("config.json", "tokenizer_config.json", "tokenizer.json"):
        path = try_to_load_from_cache(model, name, revision=revision)
        require(isinstance(path, str) and Path(path).is_file(),
                f"Pinned tokenizer cache is incomplete ({name}); no download fallback was attempted")
        files[name] = {"sha256": sha(path), "bytes": Path(path).stat().st_size}
    config_path = try_to_load_from_cache(model, "config.json", revision=revision)
    config = json.loads(Path(config_path).read_text())
    require(config.get("vocab_size") == 151936 and config.get("eos_token_id") == 151645,
            "Cached pinned model config differs")
    tokenizer = AutoTokenizer.from_pretrained(model, revision=revision, local_files_only=True, trust_remote_code=False)
    generation_path = try_to_load_from_cache(model, "generation_config.json", revision=revision)
    generation_note = "Not cached; frozen local-adapter audit EOS IDs are used: 151643 and 151645."
    if isinstance(generation_path, str):
        generation = json.loads(Path(generation_path).read_text())
        eos = generation.get("eos_token_id")
        require(set(eos if isinstance(eos, list) else [eos]) == {151643, 151645}, "Generation EOS IDs differ")
        files["generation_config.json"] = {"sha256": sha(generation_path), "bytes": Path(generation_path).stat().st_size}
        generation_note = "Cached generation config confirms both frozen EOS IDs."
    return tokenizer, {"model": model, "revision": revision, "local_files_only": True, "trust_remote_code": False,
                       "model_weights_loaded": False, "model_vocab_size": config["vocab_size"],
                       "files": files, "generation_config": generation_note}


def audit_token_text(source_rows, rows, tokenizer, vocab_size=151936):
    require(tokenizer.encode("<think>", add_special_tokens=False) == [151667]
            and tokenizer.encode("</think>", add_special_tokens=False) == [151668], "Thinking-marker tokenizer IDs differ")
    cache = {}
    for row in [*source_rows, *rows]:
        key = stable_hash(row["messages"])
        if key not in cache:
            cache[key] = list(tokenizer.apply_chat_template(row["messages"], tokenize=True,
                             add_generation_prompt=True, enable_thinking=True, return_dict=False))
        require(cache[key] == row["prompt_token_ids"], f"Saved prompt tokens differ: {row['record_id']}")
    preambles = []
    for row in rows:
        generated = row["generated_token_ids"]
        require(generated and all(type(token) is int and 0 <= token < vocab_size for token in generated),
                f"Generated token outside model vocabulary: {row['record_id']}")
        require(not any(token in (151643, 151645) for token in generated[:-1]),
                f"EOS appears before the end: {row['record_id']}")
        if 151668 in generated:
            boundary = generated.index(151668)
            opening = generated.index(151667) if 151667 in generated[:boundary] else None
            start = opening + 1 if opening is not None else 0
            reasoning = tokenizer.decode(generated[start:boundary], skip_special_tokens=True)
            content = tokenizer.decode(generated[boundary + 1:], skip_special_tokens=True).strip()
            if opening is not None and tokenizer.decode(generated[:opening], skip_special_tokens=True).strip():
                preambles.append(row["record_id"])
        else:
            reasoning = tokenizer.decode(generated, skip_special_tokens=True)
            content = ""
        require(reasoning == row["reasoning"], f"Reasoning text differs from exact token decoding: {row['record_id']}")
        require(content == row["content"], f"Content text differs from exact token decoding: {row['record_id']}")
    return {"source_prompt_records": len(source_rows), "generation_prompt_records": len(rows),
            "distinct_prompt_tokenizations": len(cache), "exact_trace_decodes": len(rows),
            "substantive_preamble_discarded_by_frozen_adapter_ids": preambles,
            "note": "Uses exact adapter boundaries; never assumes encode(decode(tokens)) is an inverse."}


def critical_packages(runtime):
    names = {"torch", "transformers", "tokenizers", "numpy", "huggingface-hub", "scipy", "scikit-learn"}
    selected = {name: [] for name in sorted(names)}
    for item in runtime.get("installed_packages", []):
        name, separator, version = item.partition("==")
        normalized = name.lower().replace("_", "-")
        if separator and normalized in names:
            selected[normalized].append(version)
    return {name: sorted(set(versions)) for name, versions in selected.items()}


def runtime_changes(original, resumed):
    changes = {key: {"original": original.get(key), "resumed": resumed.get(key)}
               for key in ("python", "platform", "git_commit", "torch_version", "cuda_version", "gpu_name", "nvidia_driver")
               if resumed.get(key) != original.get(key)}
    old_packages, new_packages = critical_packages(original), critical_packages(resumed)
    if old_packages != new_packages:
        changes["critical_package_distributions"] = {"original": old_packages, "resumed": new_packages}
    return changes


def audit_runtime_lineage(rows, original, resumed, checkpoint_at):
    """Infer segments from timestamps; rows have no cryptographic runtime identifier."""
    require(resumed, "No resumed-runtime metadata")
    old_time, checkpoint_time = utc(original["captured_at"]), utc(checkpoint_at)
    captures = sorted([(utc(runtime["captured_at"]), name, runtime) for name, runtime in resumed])
    require(len({time for time, _, _ in captures}) == len(captures), "Duplicate runtime capture timestamps")
    require(old_time <= utc(rows[0]["started_at"]) and utc(rows[7]["finished_at"]) <= checkpoint_time,
            "Original runtime/checkpoint timestamps do not bound the retained original segment")
    require(all(time >= checkpoint_time for time, _, _ in captures), "Resume runtime predates checkpoint")
    segments = {name: {"runtime_file": name, "captured_at": runtime["captured_at"], "record_ids": [],
                      "runtime": runtime, "critical_package_distributions": critical_packages(runtime),
                      "changes_from_original": runtime_changes(original, runtime)} for _, name, runtime in captures}
    previous_finish = None
    question_gpus = {}
    for index, row in enumerate(rows):
        start, finish = utc(row["started_at"]), utc(row["finished_at"])
        require(start <= finish and (previous_finish is None or start >= previous_finish),
                "Saved generation intervals overlap or are out of order")
        previous_finish = finish
        if index < 8:
            if row.get("question_id"):
                question_gpus.setdefault(row["question_id"], set()).add(original.get("gpu_name"))
            continue
        eligible = [(time, name) for time, name, _ in captures if time <= start]
        require(eligible, "Resumed response predates all resumed-runtime captures")
        _, name = eligible[-1]
        require(not any(start < time <= finish for time, _, _ in captures), "Response interval straddles a new runtime capture")
        segments[name]["record_ids"].append(row["record_id"])
        if row.get("question_id"):
            question_gpus.setdefault(row["question_id"], set()).add(segments[name]["runtime"].get("gpu_name"))
    return {"original_retained_records": 8, "resumed_retained_records": len(rows) - 8,
            "original_runtime": original, "original_critical_package_distributions": critical_packages(original),
            "question_gpu_names": {qid: sorted(gpus) for qid, gpus in question_gpus.items()},
            "questions_spanning_gpu_names": sorted(qid for qid, gpus in question_gpus.items() if len(gpus) > 1),
            "checkpoint_captured_at": checkpoint_at,
            "segments": [dict(segment, retained_records=len(segment["record_ids"])) for segment in segments.values()],
            "historical_total_attempts": None,
            "attribution": "Inferred from ordered timestamps and preserved metadata; rows do not directly attest runtime identity.",
            "unknown_attempts": "Original unarchived/in-flight attempts may exist; retained counts do not bound total historical calls."}


def audit_hardware_addendum(addendum, rows, manifest, lineage):
    require(addendum.get("allowed_resume_gpu") == "L4", "Hardware addendum must explicitly name the L4 continuation")
    require(utc(lineage["checkpoint_captured_at"]) <= utc(addendum["frozen_at_utc"]) < utc(rows[8]["started_at"]),
            "Hardware addendum was not frozen between checkpoint and first retained resumed generation")
    require(addendum.get("primary_test_question_ids") == manifest["test_question_ids"], "Hardware addendum changes primary question set")
    first_question = rows[0]["question_id"]
    require(addendum.get("mixed_question_id") == first_question
            and addendum.get("secondary_exclude_question_ids") == [first_question],
            "Secondary sensitivity must exclude exactly the predeclared mixed-runtime first question")
    require(lineage["questions_spanning_gpu_names"] == [first_question], "Observed mixed-GPU question differs from addendum")
    require(all("L4" in segment["runtime"].get("gpu_name", "") for segment in lineage["segments"] if segment["retained_records"]),
            "A retained resumed segment differs from the declared L4 hardware")
    retained = [q for q in manifest["test_question_ids"] if q != first_question]
    require(addendum.get("secondary_test_question_ids") == retained
            and addendum.get("primary_retained_grid_outcomes") == 198
            and addendum.get("secondary_retained_grid_outcomes") == 165
            and addendum.get("original_retained_records") == 8 and addendum.get("planned_resumed_records") == 190,
            "Hardware addendum changes fixed retained counts or secondary membership")
    require(addendum.get("scientific_commit") == ORIGINAL_COMMIT and addendum.get("checkpoint_commit") == CHECKPOINT_COMMIT
            and addendum.get("human_validation") is False and addendum.get("outcome_based_selection") is False,
            "Hardware declaration provenance differs")
    return {"declaration": addendum, "frozen_before_first_retained_resume": True,
            "primary_question_count": 6, "primary_retained_outcomes": len(rows),
            "secondary_question_ids": retained, "secondary_retained_outcomes": sum(r["question_id"] in retained for r in rows),
            "note": "Subset membership only; primary outcomes retained and no new effect estimate computed."}


def run_audit(root, checkpoint, metadata_dirs=None, project=PROJECT, hardware_addendum=None):
    inventory = verify_inventory(root)
    require(FINAL_REQUIRED <= set(inventory), "Completed inventory omits a required result or explanation-summary file")
    resumed_paths = sorted(root.glob("runtime-resume-*.json"))
    require(resumed_paths and all(path.name in inventory for path in resumed_paths), "Resumed runtime files must be checksummed")
    observed = {path: sha(path) for path in [*(root / name for name in inventory), root / "checksums.sha256",
                *(checkpoint / name for name in CHECKPOINT_HASHES), checkpoint / "checkpoint-provenance.json"]}
    provenance = check_immutable(root, checkpoint)
    plan = json.loads((root / "plan.json").read_text())
    require(plan == json.loads((project / "docs/phase3-pilot-plan.json").read_text()), "Repository plan differs")
    require(plan["model"] == MODEL and plan["model_revision"] == REVISION, "Unexpected model identity")
    manifest = json.loads((root / "manifest.json").read_text())
    rows = audit_prefix((checkpoint / "steering.jsonl").read_bytes(), (root / "steering.jsonl").read_bytes(), ordered_ids(manifest))
    completion = json.loads((root / "completion.json").read_text())
    require(completion.get("records") == 198 and completion.get("status") == "complete_fixed_sweep", "Completion marker differs")
    source_path = project / plan["source_path"]
    require(sha(source_path) == plan["source_sha256"], "Phase 1 source bytes differ")
    observed[source_path] = sha(source_path)
    source, _ = load_records(source_path, include_invalid_source_outcomes=True)
    grid = validate_run(rows, manifest, plan, source)
    vectors = audit_vectors(root / "vectors.npz", json.loads((root / "vector_metadata.json").read_text()), plan)
    original = json.loads((root / "runtime.json").read_text())
    resumed = [(path.name, json.loads(path.read_text())) for path in resumed_paths]
    require(original.get("git_commit") == ORIGINAL_COMMIT, "Original runtime commit differs")
    for runtime in [original, *(runtime for _, runtime in resumed)]:
        require(runtime.get("git_tracked_changes") == "", "Runtime reports tracked-file modifications")
        require(runtime.get("cuda_available") is True and any(gpu in runtime.get("gpu_name", "") for gpu in ("T4", "L4")),
                "Runtime is not recorded CUDA/T4 or CUDA/L4")
        check_code(runtime.get("git_commit"), project)
    lineage = audit_runtime_lineage(rows, original, resumed, provenance["captured_at_utc"])
    hardware = None
    if any("L4" in runtime.get("gpu_name", "") for _, runtime in resumed) and hardware_addendum is None:
        hardware_addendum = project / "docs/phase3-l4-resume-addendum.json"
    if hardware_addendum is not None:
        require(hardware_addendum.is_file() and not hardware_addendum.is_symlink(), "Hardware addendum must be a regular file")
        require(sha(hardware_addendum) == HARDWARE_ADDENDUM_SHA256, "Hardware addendum differs from published frozen bytes")
        observed[hardware_addendum] = sha(hardware_addendum)
        hardware = audit_hardware_addendum(json.loads(hardware_addendum.read_text()), rows, manifest, lineage)
        hardware["path"] = artifact_label(hardware_addendum, project)
        hardware["sha256"] = observed[hardware_addendum]
    tokenizer, tokenizer_provenance = load_cached_tokenizer(plan["model"], plan["model_revision"])
    token_text = audit_token_text(source, rows, tokenizer, tokenizer_provenance["model_vocab_size"])
    metadata_dirs = metadata_dirs if metadata_dirs is not None else sorted(root.parent.glob("pilot-20-phase3-resume-notebook-*"))
    notebook_metadata = []
    for directory in metadata_dirs:
        require(directory.is_dir() and not directory.is_symlink(), "Notebook metadata path is not a regular directory")
        setup, log = directory / "setup.json", directory / "resume-execution.log"
        require(setup.is_file() and log.is_file() and not setup.is_symlink() and not log.is_symlink(),
                "Notebook setup or separate resume log missing")
        setup_data = json.loads(setup.read_text())
        require(setup_data.get("scientific_commit") == ORIGINAL_COMMIT, "Notebook scientific revision differs")
        check_code(setup_data.get("checkpoint_commit"), project)
        if hardware is not None:
            require(setup_data.get("hardware_addendum_path") == "docs/phase3-l4-resume-addendum.json"
                    and setup_data.get("hardware_addendum_sha256") == HARDWARE_ADDENDUM_SHA256
                    and setup_data.get("hardware_addendum") == hardware["declaration"],
                    "Notebook setup does not bind the frozen hardware addendum")
        for path in (setup, log):
            observed[path] = sha(path)
        notebook_metadata.append({"directory": artifact_label(directory, project), "setup_sha256": sha(setup), "resume_log_sha256": sha(log),
                                  "notebook_checkout_commit": setup_data.get("checkpoint_commit"),
                                  "hardware_addendum_sha256": setup_data.get("hardware_addendum_sha256"),
                                  "imported_numpy": setup_data.get("imported_numpy"),
                                  "imported_transformers": setup_data.get("imported_transformers"),
                                  "recorded_runtime_changes": setup_data.get("runtime_changes")})
    for name, expected in CODE_HASHES.items():
        observed[project / name] = expected
    require(all(sha(path) == expected for path, expected in observed.items()), "An input changed during auditing")
    warnings = []
    if not notebook_metadata:
        warnings.append("Notebook setup/separate resume log not supplied; runtime lineage uses checksummed runner runtime files only.")
    if token_text["substantive_preamble_discarded_by_frozen_adapter_ids"]:
        warnings.append("Some generated text precedes an opening thinking marker and is omitted by the frozen adapter; record IDs are listed.")
    if hardware is not None:
        warnings.append("Eight preserved T4 outcomes and 190 resumed L4 outcomes form the primary dataset; only the first question spans both GPUs. The five-question sensitivity was declared before retained resumed generation.")
    warnings.extend(f"Runtime environment differs from original in {segment['runtime_file']}; see explicit hardware/software deltas."
                    for segment in lineage["segments"] if segment["changes_from_original"])
    warnings.extend(f"Runtime capture {segment['runtime_file']} has no retained rows; preserve as a zero-row setup event."
                    for segment in lineage["segments"] if not segment["retained_records"])
    return {"status": "passed_with_documented_limits", "reviewer": "Codex AI artifact audit; not human validation",
            "audited_at_utc": utc_now(), "checklist": CHECKLIST, "inventory_files": len(inventory),
            "input_sha256": {artifact_label(path, project): value for path, value in observed.items()}, "grid": grid,
            "original_eight_row_byte_prefix_unchanged": True, "scientific_code_sha256": CODE_HASHES,
            "vectors": vectors, "tokenizer_provenance": tokenizer_provenance, "token_text": token_text,
            "runtime_lineage": lineage, "hardware_addendum": hardware, "notebook_metadata": notebook_metadata, "warnings": warnings,
            "raw_artifacts_unchanged": True, "new_model_inference": False, "human_validation": False,
            "audit_environment": {"python": platform.python_version(), "platform": platform.platform(),
                **{name: importlib.metadata.version(name) for name in ("numpy", "transformers", "tokenizers")}},
            "limits": ["Consistency and hashes do not independently prove that inference occurred.",
                       "Unknown original unarchived attempts preclude an exact total historical attempt count.",
                       "Runtime assignment is inferred from timestamps; package/driver differences are disclosed, not erased.",
                       "No new model forward pass, vector refit, explanation labeling, or statistical claim is performed.",
                       "Original distribution metadata lists two NumPy versions; it does not identify the imported version by itself."]}


def write_report(out, report):
    out.mkdir(parents=True, exist_ok=False)
    (out / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Phase 3 retained-artifact audit", "", f"Status: **{report['status']}**.", "",
             "AI-assisted integrity review; no human validation, new inference, or explanation labels.", ""]
    if "error" in report:
        lines += [f"Audit incomplete: {report['error']}", "", "No successful full-run audit is claimed."]
    else:
        lines += ["All 198 retained grid outcomes, the exact original eight-row byte prefix, immutable checkpoint files, "
                  "and frozen scientific source passed verification. Every saved response was independently decoded using "
                  "the cached pinned tokenizer. Historical total attempts remain unknown.", "",
                  f"Checked {report['token_text']['source_prompt_records']} source prompts and "
                  f"{report['token_text']['exact_trace_decodes']} response traces. No model weights were loaded.", "",
                  "Checklist:", "", *[f"- {item}" for item in CHECKLIST], "",
                  "Runtime attribution is inferred from timestamps; full segments, environment differences and checksums "
                  "are in `audit.json`. A successful audit establishes saved-artifact consistency, not steering efficacy or honesty.", "",
                  *[f"- {warning}" for warning in report["warnings"]], "", *[f"- {limit}" for limit in report["limits"]]]
    (out / "audit.md").write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=PROJECT / "artifacts/pilot-20-phase3-v1")
    parser.add_argument("--checkpoint-dir", type=Path, default=PROJECT / "artifacts/pilot-20-phase3-checkpoint-0430")
    parser.add_argument("--metadata-dir", action="append", type=Path, help="Notebook metadata directory; otherwise auto-discover siblings")
    parser.add_argument("--out-dir", type=Path, default=PROJECT / "results/pilot-20-phase3-v1/artifact_audit")
    parser.add_argument("--hardware-addendum", type=Path, help="Frozen JSON declaration for an L4 continuation and mixed-question sensitivity")
    parser.add_argument("--checklist", action="store_true", help="Print planned read-only checks without reading artifacts")
    args = parser.parse_args()
    if args.checklist:
        print("\n".join(f"- {item}" for item in CHECKLIST))
        return
    require(not args.out_dir.exists(), "Audit output already exists; preserve it and choose another directory")
    require(not args.out_dir.resolve().is_relative_to((PROJECT / "artifacts").resolve())
            and not args.out_dir.resolve().is_relative_to(args.input_dir.resolve())
            and not args.out_dir.resolve().is_relative_to(args.checkpoint_dir.resolve()), "Write the audit outside raw artifacts")
    try:
        report = run_audit(args.input_dir, args.checkpoint_dir, args.metadata_dir, hardware_addendum=args.hardware_addendum)
    except Exception as error:
        report = {"status": "incomplete_or_failed", "audited_at_utc": utc_now(), "error": f"{type(error).__name__}: {error}",
                  "new_model_inference": False, "human_validation": False, "checklist": CHECKLIST}
        write_report(args.out_dir, report)
        print(f"Audit incomplete; see {args.out_dir / 'audit.json'}", file=sys.stderr)
        raise SystemExit(1) from error
    write_report(args.out_dir, report)
    print(f"Saved independent offline artifact audit to {args.out_dir}")


if __name__ == "__main__":
    main()
