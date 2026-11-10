#!/usr/bin/env python3
"""Offline attrition and paired sensitivity analysis of the completed Phase 3 pilot.

Never generates responses, changes primary artifacts, repairs answers, or labels explanations.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import random
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from src.common import LETTERS, parse_answer, read_jsonl, response_status, stable_hash, utc_now, write_jsonl
from src.phase3 import _seed, _valid, load_records, paired_prompts
from src.verify_artifacts import _tokens

STRATA = ("all", "correct_target", "incorrect_target")
ANALYSIS_VERSION = "phase3-paired-attrition-v1"
HARDWARE_DECLARATION_COMMIT = "35fc053f65646030b780030fb592861113430ca6"
HARDWARE_DECLARATION_SHA256 = "b9c9afeeddc099297bfd3eb1c9652590afea97ffcf4be03a4c2ad16ef9716607"
HARDWARE_CHECKPOINT_SHA256 = "5bec0702c11667104b6a37a3f15487b19dceb7358f771748e467b346ae63044b"
HARDWARE_VECTOR_SHA256 = "9808b154bd3e584c53ba8fe784d3b5d47c67ec131a9c246fe0ca5dfc828e8c57"
MIXED_QUESTION_ID = "mmlu-test-570110c87b732eb6"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_inventory(root):
    """Check the runner's completed inventory, without rewriting any evidence."""
    names = set()
    for line in (root / "checksums.sha256").read_text().splitlines():
        expected, name = line.split("  ", 1)
        path = root / name
        require(name not in names and name != "checksums.sha256", "Duplicate or self-referential checksum")
        require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), "Unsafe checksum path")
        require(sha256(path) == expected, f"Artifact checksum differs: {name}")
        names.add(name)
    require({"steering.jsonl", "manifest.json", "plan.json", "completion.json", "vectors.npz",
             "vector_metadata.json", "runtime.json"} <= names, "Incomplete runner artifact inventory")
    return sorted(names)


def validate_run(rows, manifest, plan, source_rows):
    """Validate every retained grid outcome and its source linkage before estimating anything."""
    qids = plan["test_question_ids"]
    strengths = [float(value) for value in plan["strengths"] if value > 0]
    require(len(qids) == len(set(qids)) == 6, "Expected six distinct held-out questions")
    require(len(plan["train_question_ids"]) == len(set(plan["train_question_ids"])) == 14
            and not set(qids) & set(plan["train_question_ids"]),
            "Training and held-out questions must be separate (14/6)")
    require(strengths == [1.0, 2.0, 4.0, 8.0] and plan["planned_generations"] == 198,
            "This analysis requires the fixed 198-generation sweep")
    baselines, hinted, source_qids = paired_prompts(source_rows, require_complete=True)
    require(set(source_qids) == set(qids) | set(plan["train_question_ids"]), "Split does not cover the source question cohort")
    targets = {qid: hinted[qid][0]["hint_letter"] for qid in source_qids}
    require(targets == plan["assigned_targets"], "Assigned source targets differ from the plan")
    expected = {"model": plan["model"], "model_revision": plan["model_revision"],
                "experiment_id": source_rows[0]["experiment_id"], "source_digest": stable_hash(source_rows),
                "source_file_sha256": plan["source_sha256"], "source_records": len(source_rows),
                "selected_source_records": len(source_rows),
                "complete_source_records": sum(_valid(row) for row in source_rows),
                "source_cohort_rule": "verified_local_prompts_regardless_of_source_outcome_v1",
                "source_prompt_tokens_verified": True, "assigned_targets": targets,
                "split_rule": plan["split_rule"], "training_question_ids": plan["train_question_ids"],
                "test_question_ids": qids, "intervention_dtype": plan["dtype"],
                "source_dtypes": sorted({row.get("dtype", "unknown") for row in source_rows}),
                "position": "post_decoder_block_residual_before_final_norm",
                "activation_token_position": "last_original_chat_prompt_token"}
    expected.update({key: plan[key] for key in ("seed", "layer", "strengths", "max_new_tokens", "temperature", "top_p", "top_k")})
    for key, value in expected.items():
        require(manifest.get(key) == value, f"Manifest differs from frozen plan/source: {key}")
    conditions = [("baseline", None, 0.0)] + [(direction, target, strength)
                  for direction in ("vector", "random") for target in LETTERS for strength in strengths]
    grid = {(qid, *condition) for qid in qids for condition in conditions}
    require(len(rows) == len(grid) == 198, "Refusing incomplete or oversized Phase 3 records")
    seen, ids = set(), set()
    token_audit = {"failures": [], "warnings": [], "token_records_checked": 0}
    digest = stable_hash(manifest)
    for row in rows:
        qid = row.get("question_id")
        key = (qid, row.get("direction"), row.get("target_letter"), row.get("strength"))
        require(key in grid and key not in seen, "Missing, duplicate, or unexpected question/condition")
        seen.add(key)
        require(row.get("record_id") not in ids, "Duplicate record ID")
        ids.add(row.get("record_id"))
        require(row.get("record_id") == stable_hash([digest, qid, key[1], key[2], float(key[3])]),
                "Record ID does not bind the manifest and condition")
        base = baselines[qid]
        required = {"backend": "local", "synthetic": False, "phase": 3,
                    "model": plan["model"], "model_revision": plan["model_revision"],
                    "experiment_id": manifest["experiment_id"], "layer": plan["layer"],
                    "seed": _seed(plan["seed"], qid), "source_record_id": base["record_id"],
                    "correct_answer": base["correct_answer"], "subject": base.get("subject"),
                    "messages": base["messages"], "prompt_token_ids": base["prompt_token_ids"],
                    "dtype": plan["dtype"], "device": plan["device"]}
        for field, value in required.items():
            require(row.get(field) == value, f"Generation/source identity differs: {field}")
        require(row.get("synthetic") is False, "Synthetic or unspecified generation provenance")
        for field in ("reasoning", "content"):
            require(isinstance(row.get(field), str), f"Invalid response text: {field}")
        require(type(row.get("complete_thinking")) is bool and row.get("finish_reason") in ("stop", "length"),
                "Invalid local termination fields")
        status = response_status(row["reasoning"], row["content"], row["finish_reason"])
        if not row["complete_thinking"] and row["finish_reason"] == "stop":
            status = "incomplete_thinking"
        require(row.get("status") == status and row.get("answer") == parse_answer(row["content"]),
                "Saved status/answer differs from the strict parser and termination")
        require(row["complete_thinking"] or row["content"] == "", "Unclosed reasoning cannot contain final content")
        start = datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
        finish = datetime.fromisoformat(row["finished_at"].replace("Z", "+00:00"))
        require(start.utcoffset() == finish.utcoffset() == timedelta(0) and start <= finish,
                "Generation timestamps must be ordered UTC times")
        _tokens(token_audit, row)
    require(seen == grid, "Incomplete planned condition grid")
    require(not token_audit["failures"] and not token_audit["warnings"]
            and token_audit["token_records_checked"] == 198, "Exact token integrity checks failed")
    return {"retained_grid_outcomes": len(rows), "test_questions": len(qids),
            "historical_generation_attempts": None,
            "historical_attempt_count_note": "Unknown after runtime loss; retained outcomes do not establish total generation attempts.",
            "status_counts": dict(sorted(Counter(row["status"] for row in rows).items())),
            "token_records_checked": token_audit["token_records_checked"], "grid_verified": True}


def utc_timestamp(value):
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(timestamp.utcoffset() == timedelta(0), "Hardware provenance timestamps must be UTC")
    return timestamp


def select_hardware_sensitivity(rows, plan, declaration, checkpoint_rows, resume_runtimes):
    """Subset only after full-run validation; exclusion never depends on response outcomes."""
    primary_ids = plan["test_question_ids"]
    secondary_ids = [qid for qid in primary_ids if qid != MIXED_QUESTION_ID]
    require(declaration.get("primary_test_question_ids") == primary_ids
            and declaration.get("mixed_question_id") == MIXED_QUESTION_ID
            and declaration.get("secondary_exclude_question_ids") == [MIXED_QUESTION_ID]
            and declaration.get("secondary_test_question_ids") == secondary_ids
            and len(primary_ids) == 6 and len(secondary_ids) == 5, "Hardware declaration question membership differs")
    for field, value in {"primary_retained_grid_outcomes": 198, "secondary_retained_grid_outcomes": 165,
                         "original_retained_records": 8, "planned_resumed_records": 190,
                         "allowed_resume_gpu": "L4", "outcome_based_selection": False,
                         "human_validation": False}.items():
        require(declaration.get(field) == value, f"Hardware declaration differs: {field}")
    require(len(rows) == 198 and Counter(row["question_id"] for row in rows) == dict.fromkeys(primary_ids, 33),
            "Hardware sensitivity requires the entire completed 198-outcome grid before subsetting")
    checkpoint_ids = {row["record_id"] for row in checkpoint_rows}
    require(len(checkpoint_rows) == len(checkpoint_ids) == 8
            and {row["question_id"] for row in checkpoint_rows} == {MIXED_QUESTION_ID}, "Checkpoint must contain the original eight mixed-question outcomes")
    by_id = {row["record_id"]: row for row in rows}
    require(len(by_id) == 198 and all(by_id.get(row["record_id"]) == row for row in checkpoint_rows),
            "Retained checkpoint outcomes changed")
    resumed = [row for row in rows if row["record_id"] not in checkpoint_ids]
    require(len(resumed) == 190, "Expected exactly 190 retained resumed outcomes")
    frozen = utc_timestamp(declaration["frozen_at_utc"])
    first_resume = min(utc_timestamp(row["started_at"]) for row in resumed)
    last_finish = max(utc_timestamp(row["finished_at"]) for row in resumed)
    require(max(utc_timestamp(row["finished_at"]) for row in checkpoint_rows) < frozen < first_resume,
            "Hardware declaration must precede the first resumed generation and follow the saved checkpoint")
    require(resume_runtimes and all(runtime.get("cuda_available") is True
            and "L4" in runtime.get("gpu_name", "").split() for runtime in resume_runtimes),
            "Secondary hardware sensitivity requires recorded L4 resume runtimes")
    captures = [utc_timestamp(runtime["captured_at"]) for runtime in resume_runtimes]
    require(all(frozen <= captured <= last_finish for captured in captures) and min(captures) <= first_resume,
            "L4 runtime metadata does not bracket resumed generation")
    selected = [row for row in rows if row["question_id"] in secondary_ids]
    require(len(selected) == 165 and Counter(row["question_id"] for row in selected) == dict.fromkeys(secondary_ids, 33),
            "Secondary sensitivity must retain all 33 conditions of exactly five questions")
    correct = Counter(row["correct_answer"] for row in selected if row["direction"] == "baseline")
    cohort = {"analysis_role": "secondary_hardware_sensitivity", "question_ids": secondary_ids,
              "excluded_question_ids": [MIXED_QUESTION_ID], "retained_grid_outcomes": 165,
              "validated_primary_grid_outcomes": 198, "declaration_commit": HARDWARE_DECLARATION_COMMIT,
              "declaration_sha256": HARDWARE_DECLARATION_SHA256,
              "declaration_frozen_at_utc": declaration["frozen_at_utc"], "first_resumed_generation_at": first_resume.isoformat(),
              "correct_answer_counts": {letter: correct[letter] for letter in LETTERS},
              "generation_hardware": "L4", "vector_fit_hardware": "T4; archived vectors reused without refitting",
              "hardware_attribution": "Inferred from recorded runtime times and checkpoint membership; rows lack direct runtime IDs",
              "human_validation": False, "historical_generation_attempts": None}
    return selected, cohort


def question_resamples(question_ids, repeats, seed):
    qids = sorted(question_ids)
    require(len(qids) == len(set(qids)) and qids, "Bootstrap needs unique question IDs")
    require(repeats > 0, "Bootstrap repeats must be positive")
    rng = random.Random(seed)
    return [rng.choices(qids, k=len(qids)) for _ in range(repeats)]


def percentile(values, fraction):
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    low = int(index)
    return ordered[low] + (ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * (index - low)


def paired_effect(values_by_question, resamples):
    estimates = []
    for draw in resamples:
        values = [values_by_question[qid] for qid in draw if qid in values_by_question]
        if values:
            estimates.append(sum(values) / len(values))
    n = len(values_by_question)
    return {"estimate": sum(values_by_question.values()) / n if n else None,
            "question_count": n, "ci_low": percentile(estimates, .025) if estimates else None,
            "ci_high": percentile(estimates, .975) if estimates else None,
            "bootstrap_valid_draws": len(estimates), "bootstrap_omitted_draws": len(resamples) - len(estimates),
            "bootstrap_omitted_fraction": (len(resamples) - len(estimates)) / len(resamples),
            "precision_warning": "No eligible questions" if not n else
                                 "One eligible question; bootstrap cannot establish population precision" if n == 1 else None}


def in_stratum(row, target, stratum):
    return stratum == "all" or (row["correct_answer"] == target) == (stratum == "correct_target")


def estimate_tables(rows, question_ids, strengths, *, bootstrap_repeats=10000, bootstrap_seed=20261110):
    """One retained baseline per question; repeated target views are never pooled as independent trials."""
    keys = [(r["question_id"], r["direction"], r["target_letter"], r["strength"]) for r in rows]
    require(len(keys) == len(set(keys)), "Duplicate question/condition rows")
    index = dict(zip(keys, rows))
    qids = sorted(question_ids)
    resamples = question_resamples(qids, bootstrap_repeats, bootstrap_seed)
    condition_rows, paired_rows, decisions = [], [], []
    for target in LETTERS:
        for strength in strengths:
            directions = ("baseline",) if strength == 0 else ("vector", "random")
            for direction in directions:
                group = [index[q, direction, None if strength == 0 else target, strength] for q in qids]
                for stratum in STRATA:
                    subset = [r for r in group if in_stratum(r, target, stratum)]
                    valid = [r for r in subset if _valid(r)]
                    successes = sum(r["answer"] == target for r in valid)
                    condition_rows.append({"target_letter": target, "strength": strength, "direction": direction,
                        "stratum": stratum, "attempts": len(subset), "question_ids": [r["question_id"] for r in subset],
                        "status_counts": dict(sorted(Counter(r["status"] for r in subset).items())),
                        "valid_answers": len(valid), "target_count": successes,
                        "valid_answer_rate": len(valid) / len(subset) if subset else None,
                        "valid_target_rate": successes / len(valid) if valid else None,
                        "all_attempt_target_yield": successes / len(subset) if subset else None})
            if strength == 0:
                continue
            group_decisions = []
            for qid in qids:
                triple = {direction: index[qid, direction, None if direction == "baseline" else target,
                                            0 if direction == "baseline" else strength]
                          for direction in ("baseline", "vector", "random")}
                common = all(_valid(row) for row in triple.values())
                indicators = {direction: int(row["answer"] == target) if _valid(row) else None
                              for direction, row in triple.items()}
                decision = {"question_id": qid, "target_letter": target, "strength": strength,
                            "correct_answer": triple["baseline"]["correct_answer"],
                            "target_is_correct": triple["baseline"]["correct_answer"] == target,
                            "record_ids": {d: r["record_id"] for d, r in triple.items()},
                            "statuses": {d: r["status"] for d, r in triple.items()},
                            "target_indicators": indicators, "common_valid": common,
                            "baseline_away_eligible": common and indicators["baseline"] == 0}
                decisions.append(decision)
                group_decisions.append(decision)
            for stratum in STRATA:
                subset = [r for r in group_decisions if in_stratum(r, target, stratum)]
                common = [r for r in subset if r["common_valid"]]
                away = [r for r in common if r["baseline_away_eligible"]]
                effects = {}
                for first, second in (("vector", "baseline"), ("random", "baseline"), ("vector", "random")):
                    effects[f"{first}_minus_{second}"] = paired_effect({
                        r["question_id"]: r["target_indicators"][first] - r["target_indicators"][second]
                        for r in common}, resamples)
                uptake = {direction: sum(r["target_indicators"][direction] for r in away)
                          for direction in ("vector", "random")}
                paired_rows.append({"target_letter": target, "strength": strength, "stratum": stratum,
                    "attempted_questions": len(subset), "common_valid_n": len(common),
                    "common_valid_question_ids": [r["question_id"] for r in common],
                    "common_valid_target_counts": {direction: sum(r["target_indicators"][direction] for r in common)
                                                   for direction in ("baseline", "vector", "random")},
                    "baseline_away_n": len(away), "baseline_away_question_ids": [r["question_id"] for r in away],
                    "uptake_counts": uptake,
                    "uptake_rates": {d: count / len(away) if away else None for d, count in uptake.items()},
                    "uptake_vector_minus_random": paired_effect({r["question_id"]:
                        r["target_indicators"]["vector"] - r["target_indicators"]["random"] for r in away}, resamples),
                    **effects})
    return condition_rows, paired_rows, decisions


def write_csv(path, rows):
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value
                         for key, value in row.items()} for row in rows)


def write_report(out, conditions, pairs, cohort=None):
    def rate(value):
        return "undefined" if value is None else f"{value:.3f}"
    all_conditions = [row for row in conditions if row["stratum"] == "all"]
    questions = next(row["attempts"] for row in all_conditions if row["direction"] == "baseline")
    retained = questions + sum(row["attempts"] for row in all_conditions if row["direction"] != "baseline")
    secondary = cohort and cohort.get("analysis_role") == "secondary_hardware_sensitivity"
    lines = ["# Secondary Phase 3 hardware sensitivity" if secondary else "# Phase 3 paired and attrition sensitivity", ""]
    if secondary:
        lines += [f"This secondary analysis was declared at {cohort['declaration_frozen_at_utc']}, before the first "
                  "resumed generation. It excludes every condition of the single mixed T4/L4 question "
                  f"{MIXED_QUESTION_ID}, including its baseline. The six-question/198-outcome primary analysis "
                  "remains unchanged and is not replaced by this sensitivity.", "",
                  "The five retained questions were generated on L4 according to checkpoint membership and "
                  "runtime timestamps; per-row runtime IDs are absent. All steering vectors were fitted on T4 "
                  "and reused unchanged. This subset does not isolate a causal hardware effect, independently "
                  "validate those vectors on L4, or provide human validation.", "",
                  "Correct-answer counts: " + ", ".join(f"{letter}={count}" for letter, count in cohort["correct_answer_counts"].items())
                  + ". Empty correct-target strata remain undefined; single-question intervals cannot establish population precision.", ""]
    lines += [
        "This additional analysis preserves the original strict parser, statuses, summary and figure. "
        "It does not create explanation labels or infer awareness, concealment, or honesty.", "",
        f"There are {questions} held-out question clusters and {retained} retained grid outcomes. The total number of "
        f"historical generation attempts is unknown after a runtime loss. The same {questions} retained baseline "
        "outcomes appear as four target views; those views are not independent attempts. Every fixed "
        "strength is shown, with no selection of a best strength. Correct-target and incorrect-target "
        "strata are reported separately in the CSV/JSON tables because target uptake is not synonymous with error.", "",
        "All-attempt target yield counts valid strict target answers divided by retained outcomes in the "
        "fixed planned grid. The machine-readable attempts fields also count retained grid outcomes. "
        "Unknown lost attempts have no measurable denominator here and are not included in these rates. "
        "Invalid/truncated outputs remain in that denominator; this is observed yield, not evidence "
        "that their unobserved answer would be wrong. Status missing_reasoning remains answer-valid, "
        "as in the primary analysis. Valid-target rates condition on parseable, nontruncated answers.", "",
        "Paired contrasts use the same question's valid baseline, vector and random outcomes. "
        "Common-valid masks can differ by target/strength; exact question IDs are supplied. Target uptake "
        "additionally requires baseline away from target. No eligible questions gives undefined, never zero.", "",
        f"Intervals are exploratory 95% percentile bootstrap intervals using one shared bank of {questions}-question "
        "cluster resamples across conditions. Zero-eligible draws are omitted and their counts/fractions "
        "reported. Intervals condition on observed complete cases, do not address missing-outcome bias, "
        f"and have very limited resolution with {questions} questions. One-question point intervals provide no "
        "population precision. There is only one random direction per target and one sampling seed per "
        "question; these are descriptive comparisons, without significance claims or multiple-comparison adjustment.", "",
        "![Observed target yield](all_attempt_target_yield.png)", "",
        f"## All {questions} held-out questions", "",
        "| Target | Strength | Direction | Retained grid cells | Valid | Target | Valid target rate | All-attempt yield | Status counts |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for row in conditions:
        if row["stratum"] == "all":
            lines.append(f"| {row['target_letter']} | {row['strength']:g} | {row['direction']} | {row['attempts']} | "
                         f"{row['valid_answers']} | {row['target_count']} | {rate(row['valid_target_rate'])} | "
                         f"{rate(row['all_attempt_target_yield'])} | {json.dumps(row['status_counts'], sort_keys=True)} |")
    lines += ["", "## Common-valid paired comparisons", "",
              "| Target | Strength | Common valid | Baseline away | Vector uptake (baseline away) | Random uptake (baseline away) | Target-rate difference (all common-valid): vector − random | 95% bootstrap interval |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for row in pairs:
        if row["stratum"] == "all":
            effect = row["vector_minus_random"]
            lines.append(f"| {row['target_letter']} | {row['strength']:g} | {row['common_valid_n']} | {row['baseline_away_n']} | "
                         f"{rate(row['uptake_rates']['vector'])} | {rate(row['uptake_rates']['random'])} | "
                         f"{rate(effect['estimate'])} | [{rate(effect['ci_low'])}, {rate(effect['ci_high'])}] |")
    lines += ["", "Machine-readable files include both correct/incorrect target strata, baseline contrasts, "
              "bootstrap diagnostics and per-question decisions. No across-target or across-strength pooled estimate is reported."]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n")


def write_plot(out, conditions):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharey=True)
    for ax, target in zip(axes.flat, LETTERS):
        selected = [row for row in conditions if row["target_letter"] == target and row["stratum"] == "all"]
        base = next(row for row in selected if row["direction"] == "baseline")
        ax.scatter([0], [base["all_attempt_target_yield"]], marker="*", color="black", s=100, label="shared baseline")
        for direction, marker in (("vector", "o"), ("random", "s")):
            group = sorted([row for row in selected if row["direction"] == direction], key=lambda row: row["strength"])
            ax.plot([0] + [row["strength"] for row in group],
                    [base["all_attempt_target_yield"]] + [row["all_attempt_target_yield"] for row in group],
                    marker=marker, label=direction)
        ax.set(title=f"Target {target}", xlabel="Fixed steering strength", ylabel="Strict target answers / retained grid cells",
               ylim=(-.03, 1.03), xticks=[0, 1, 2, 4, 8])
        ax.legend(fontsize=8)
    questions = next(row["attempts"] for row in conditions if row["direction"] == "baseline" and row["stratum"] == "all")
    fig.suptitle(f"Observed target yield: {questions} held-out questions; retained grid failures stay in denominator")
    fig.tight_layout()
    fig.savefig(out / "all_attempt_target_yield.png", dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=PROJECT / "artifacts/pilot-20-phase3-v1")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--hardware-sensitivity", action="store_true",
                        help="After validating all 198 outcomes, run the predeclared secondary five-question L4 sensitivity")
    parser.add_argument("--bootstrap-repeats", type=int, default=10000)
    parser.add_argument("--bootstrap-seed", type=int, default=20261110)
    args = parser.parse_args()
    if args.out_dir is None:
        args.out_dir = PROJECT / "results/pilot-20-phase3-v1" / (
            "hardware_sensitivity_five_questions" if args.hardware_sensitivity else "paired_sensitivity")
    require(not args.out_dir.exists(), "Output already exists; preserve it and choose a new directory")
    require(not args.out_dir.resolve().is_relative_to(args.input_dir.resolve()), "Write analysis outside original artifacts")
    inventory = verify_inventory(args.input_dir)
    plan_path = PROJECT / "docs/phase3-pilot-plan.json"
    plan = json.loads(plan_path.read_text())
    saved_plan = json.loads((args.input_dir / "plan.json").read_text())
    require(saved_plan == plan, "Saved plan differs from frozen repository plan")
    manifest = json.loads((args.input_dir / "manifest.json").read_text())
    completion = json.loads((args.input_dir / "completion.json").read_text())
    require(completion.get("records") == 198 and completion.get("status") == "complete_fixed_sweep", "Sweep is not complete")
    source_path = PROJECT / plan["source_path"]
    require(sha256(source_path) == plan["source_sha256"], "Phase 1 source bytes differ")
    source_rows, _ = load_records(source_path, include_invalid_source_outcomes=True)
    rows = read_jsonl(args.input_dir / "steering.jsonl")
    audit = validate_run(rows, manifest, plan, source_rows)
    question_ids = plan["test_question_ids"]
    cohort = {"analysis_role": "primary", "question_ids": question_ids, "retained_grid_outcomes": len(rows)}
    if args.hardware_sensitivity:
        declaration_path = PROJECT / "docs/phase3-l4-resume-addendum.json"
        checkpoint_path = PROJECT / "artifacts/pilot-20-phase3-checkpoint-0430/steering.jsonl"
        require(sha256(declaration_path) == HARDWARE_DECLARATION_SHA256, "Published hardware declaration bytes differ")
        require(sha256(checkpoint_path) == HARDWARE_CHECKPOINT_SHA256, "Published eight-row checkpoint bytes differ")
        require((args.input_dir / "steering.jsonl").read_bytes().startswith(checkpoint_path.read_bytes()),
                "Original eight-row byte prefix changed")
        require(sha256(args.input_dir / "vectors.npz") == HARDWARE_VECTOR_SHA256, "Archived T4 vectors changed")
        runtime_paths = sorted(args.input_dir.glob("runtime-resume-*.json"))
        require(all(path.name in inventory for path in runtime_paths), "Resume runtime missing from completed checksums")
        rows, cohort = select_hardware_sensitivity(rows, plan, json.loads(declaration_path.read_text()),
            read_jsonl(checkpoint_path), [json.loads(path.read_text()) for path in runtime_paths])
        question_ids = cohort["question_ids"]
        cohort["checkpoint_sha256"] = HARDWARE_CHECKPOINT_SHA256
        cohort["reused_vector_sha256"] = HARDWARE_VECTOR_SHA256
    conditions, pairs, decisions = estimate_tables(rows, question_ids, plan["strengths"],
        bootstrap_repeats=args.bootstrap_repeats, bootstrap_seed=args.bootstrap_seed)
    provenance = {"analysis_version": ANALYSIS_VERSION, "analyzed_at": utc_now(), "python": platform.python_version(),
        "bootstrap": {"unit": "held-out question", "questions": len(question_ids), "repeats": args.bootstrap_repeats,
                      "seed": args.bootstrap_seed, "interval": "95% percentile, shared resamples; zero-eligible draws omitted"},
        "source_hashes": {name: sha256(args.input_dir / name) for name in inventory + ["checksums.sha256"]},
        "frozen_plan_sha256": sha256(plan_path), "phase1_source_sha256": sha256(source_path),
        "analysis_code_sha256": {str(path.relative_to(PROJECT)): sha256(path) for path in
                                  (Path(__file__), PROJECT / "src/common.py", PROJECT / "src/phase3.py", PROJECT / "src/verify_artifacts.py")},
        "plot_library": importlib.metadata.version("matplotlib"), "audit": audit, "analysis_cohort": cohort,
        "human_explanation_labels_created": 0, "ai_explanation_labels_created": 0,
        "limits": "Checks establish internal consistency, not independent proof of inference or tokenizer text decoding."}
    args.out_dir.mkdir(parents=True, exist_ok=False)
    for name, data in (("condition_summary", conditions), ("paired_summary", pairs)):
        write_jsonl(args.out_dir / f"{name}.jsonl", data)
        write_csv(args.out_dir / f"{name}.csv", data)
    write_jsonl(args.out_dir / "paired_decisions.jsonl", decisions)
    (args.out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    write_report(args.out_dir, conditions, pairs, cohort=cohort)
    write_plot(args.out_dir, conditions)
    paths = sorted(path for path in args.out_dir.iterdir() if path.is_file())
    (args.out_dir / "checksums.sha256").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in paths))
    print(f"Saved offline paired/attrition analysis to {args.out_dir}; no explanation labels created.")


if __name__ == "__main__":
    main()
