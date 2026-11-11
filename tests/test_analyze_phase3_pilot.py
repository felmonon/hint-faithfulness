"""Entirely synthetic unit fixtures, never model outputs or research evidence."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from scripts.analyze_phase3_pilot import (estimate_tables, paired_effect, question_resamples,
                                        validate_run, verify_inventory, write_plot, write_report,
                                        select_hardware_sensitivity, HARDWARE_DECLARATION_SHA256, sha256)
from src.common import HINTS, LETTERS, stable_hash
from src.phase3 import _seed


def set_response(row, answer="A", status="ok"):
    """Represent local adapter invariants without claiming real token-to-text decoding."""
    generated = [151667, 100, 151668, 32, 151645]
    reasoning, content, reason_ids = "Synthetic unit fixture only", f"Answer: ({answer})", [100]
    if status == "missing_reasoning":
        generated, reasoning, reason_ids = [151667, 151668, 32, 151645], "", []
    elif status == "invalid_answer":
        content, answer = "Synthetic format failure", None
    elif status == "truncated":
        generated, content, answer = [100] * 4096, "", None
        reason_ids = list(generated)
    row.update(answer=answer, status=status, reasoning=reasoning, content=content,
               finish_reason="length" if status == "truncated" else "stop",
               complete_thinking=status != "truncated", generated_token_ids=generated,
               reasoning_token_ids=reason_ids, usage={"prompt_tokens": 2, "completion_tokens": len(generated)})


def fixture():
    qids = [f"synthetic-question-{i:02}" for i in range(20)]
    targets = {qid: LETTERS[i % 4] for i, qid in enumerate(qids)}
    plan = {"model": "synthetic-unit-fixture/model", "model_revision": "synthetic-unit-fixture-revision",
            "source_sha256": "a" * 64, "seed": 42, "layer": 14, "strengths": [0, 1, 2, 4, 8],
            "max_new_tokens": 4096, "temperature": .6, "top_p": .95, "top_k": 20,
            "dtype": "torch.float16", "device": "cuda", "planned_generations": 198,
            "train_question_ids": qids[:14], "test_question_ids": qids[14:],
            "assigned_targets": targets, "split_rule": "assigned_target_largest_remainder_v1"}
    source = []
    for i, qid in enumerate(qids):
        for hint, repeat in [("none", 0), ("none", 1)] + [(hint, None) for hint in HINTS]:
            row = {"record_id": f"{qid}-{hint}-{repeat}", "question_id": qid, "hint_type": hint,
                   "baseline_repeat": repeat, "hint_letter": targets[qid], "status": "ok", "answer": "A",
                   "correct_answer": LETTERS[(i + 1) % 4], "subject": "synthetic-test-only",
                   "backend": "local", "synthetic": False, "experiment_id": "synthetic-test-experiment",
                   "model": plan["model"], "model_revision": plan["model_revision"], "dtype": plan["dtype"],
                   "messages": [{"role": "user", "content": "Synthetic fixture; no actual question."}],
                   "prompt_token_ids": [1, 2]}
            source.append(row)
    manifest = {"model": plan["model"], "model_revision": plan["model_revision"],
        "experiment_id": "synthetic-test-experiment", "source_digest": stable_hash(source),
        "source_file_sha256": plan["source_sha256"], "source_records": 100,
        "selected_source_records": 100, "complete_source_records": 100,
        "source_cohort_rule": "verified_local_prompts_regardless_of_source_outcome_v1",
        "source_prompt_tokens_verified": True, "assigned_targets": targets, "split_rule": plan["split_rule"],
        "training_question_ids": qids[:14], "test_question_ids": qids[14:], "intervention_dtype": plan["dtype"],
        "source_dtypes": [plan["dtype"]], "position": "post_decoder_block_residual_before_final_norm",
        "activation_token_position": "last_original_chat_prompt_token"}
    manifest.update({key: plan[key] for key in ("seed", "layer", "strengths", "max_new_tokens", "temperature", "top_p", "top_k")})
    digest = stable_hash(manifest)
    rows = []
    conditions = [("baseline", None, 0.0)] + [(direction, target, float(strength))
                 for direction in ("vector", "random") for target in LETTERS for strength in (1, 2, 4, 8)]
    for qid in qids[14:]:
        base = next(r for r in source if r["question_id"] == qid and r["hint_type"] == "none" and r["baseline_repeat"] == 0)
        for direction, target, strength in conditions:
            row = {key: deepcopy(base[key]) for key in ("question_id", "correct_answer", "subject", "backend",
                   "synthetic", "experiment_id", "model", "model_revision", "dtype", "messages", "prompt_token_ids")}
            row.update(record_id=stable_hash([digest, qid, direction, target, strength]), source_record_id=base["record_id"],
                       phase=3, direction=direction, target_letter=target, strength=strength,
                       layer=plan["layer"], seed=_seed(plan["seed"], qid), device=plan["device"],
                       started_at="2026-11-10T00:00:00+00:00", finished_at="2026-11-10T00:01:00+00:00")
            set_response(row)
            rows.append(row)
    return rows, manifest, plan, source


def find(rows, qid, direction, target=None, strength=0):
    return next(r for r in rows if (r["question_id"], r["direction"], r["target_letter"], r["strength"])
                == (qid, direction, target, strength))


def hardware_fixture():
    """Synthetic outcomes under the real declared IDs; never observed research results."""
    rows, manifest, plan, source = fixture()
    path = Path(__file__).resolve().parents[1] / "docs/archive/pilot-v1/phase3-l4-resume-addendum.json"
    declaration = json.loads(path.read_text())
    mapping = dict(zip(plan["test_question_ids"], declaration["primary_test_question_ids"]))
    # Correct-answer strata are derived from the frozen question file, never addendum prose.
    questions = [json.loads(line) for line in (path.parents[3] / "data/questions.jsonl").read_text().splitlines()]
    answers = {q["question_id"]: q["correct_answer"] for q in questions}
    plan["test_question_ids"] = list(mapping.values())
    plan["assigned_targets"] = {mapping.get(qid, qid): target for qid, target in plan["assigned_targets"].items()}
    for row in source:
        if row["question_id"] in mapping:
            row["question_id"] = mapping[row["question_id"]]
            row["correct_answer"] = answers[row["question_id"]]
    manifest.update(test_question_ids=plan["test_question_ids"], assigned_targets=plan["assigned_targets"],
                    source_digest=stable_hash(source))
    digest = stable_hash(manifest)
    for index, row in enumerate(rows):
        row["question_id"] = mapping[row["question_id"]]
        row["correct_answer"] = answers[row["question_id"]]
        row["seed"] = _seed(plan["seed"], row["question_id"])
        row["record_id"] = stable_hash([digest, row["question_id"], row["direction"], row["target_letter"], row["strength"]])
        row["started_at"] = "2026-11-10T04:00:00+00:00" if index < 8 else "2026-11-10T12:00:00+00:00"
        row["finished_at"] = "2026-11-10T04:01:00+00:00" if index < 8 else "2026-11-10T12:01:00+00:00"
    runtime = {"cuda_available": True, "gpu_name": "NVIDIA L4", "captured_at": "2026-11-10T11:59:00+00:00"}
    return rows, manifest, plan, source, declaration, deepcopy(rows[:8]), [runtime]


class ValidationTests(unittest.TestCase):
    def test_complete_fixture_and_strict_denominator_statuses_pass(self):
        rows, manifest, plan, source = fixture()
        for row, status in zip(rows, ("missing_reasoning", "invalid_answer", "truncated")):
            set_response(row, status=status)
        result = validate_run(rows, manifest, plan, source)
        self.assertEqual(result["retained_grid_outcomes"], 198)
        self.assertIsNone(result["historical_generation_attempts"])
        self.assertEqual(result["token_records_checked"], 198)
        self.assertEqual(result["status_counts"], dict(ok=195, missing_reasoning=1, invalid_answer=1, truncated=1))

    def test_rejects_grid_identity_status_token_and_provenance_changes(self):
        rows, manifest, plan, source = fixture()
        mutations = {"record_id": "replacement", "seed": -1, "source_record_id": "wrong-source",
                     "messages": [{"role": "user", "content": "Changed prompt"}],
                     "prompt_token_ids": [1, 3], "answer": "B", "status": "invalid_answer",
                     "synthetic": True, "model_revision": "other", "finished_at": "2026-11-09T00:00:00+00:00",
                     "generated_token_ids": [151667, 100, 151668, 32]}
        for key, value in mutations.items():
            with self.subTest(key=key):
                bad = deepcopy(rows)
                bad[0][key] = value
                with self.assertRaises(ValueError):
                    validate_run(bad, manifest, plan, source)
        for bad in (rows[:-1], [rows[0], *rows[:-1]]):
            with self.assertRaises(ValueError):
                validate_run(bad, manifest, plan, source)
        altered_manifest = dict(manifest, max_new_tokens=2048)
        with self.assertRaisesRegex(ValueError, "Manifest differs"):
            validate_run(rows, altered_manifest, plan, source)

    def test_checksum_verification_does_not_accept_modified_artifact(self):
        import hashlib
        names = ("steering.jsonl", "manifest.json", "plan.json", "completion.json", "vectors.npz", "vector_metadata.json", "runtime.json")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in names:
                (root / name).write_bytes(b"synthetic fixture")
            checksum = hashlib.sha256(b"synthetic fixture").hexdigest()
            (root / "checksums.sha256").write_text("".join(f"{checksum}  {name}\n" for name in names))
            self.assertEqual(verify_inventory(root), sorted(names))
            (root / "steering.jsonl").write_text("modified fixture")
            with self.assertRaisesRegex(ValueError, "checksum differs"):
                verify_inventory(root)


class DenominatorTests(unittest.TestCase):
    def test_attrition_and_common_valid_away_target_denominators_are_distinct(self):
        rows, _, plan, _ = fixture()
        q = plan["test_question_ids"]
        for qid in q[1:]:
            set_response(find(rows, qid, "baseline"), "B")
        set_response(find(rows, q[1], "random", "A", 1), "B")
        set_response(find(rows, q[2], "vector", "A", 1), status="invalid_answer")
        set_response(find(rows, q[3], "baseline"), status="invalid_answer")
        set_response(find(rows, q[3], "random", "A", 1), "B")
        set_response(find(rows, q[4], "vector", "A", 1), status="missing_reasoning")
        set_response(find(rows, q[4], "random", "A", 1), status="truncated")
        set_response(find(rows, q[5], "vector", "A", 1), status="truncated")
        set_response(find(rows, q[5], "random", "A", 1), status="invalid_answer")
        conditions, pairs, _ = estimate_tables(rows, q, plan["strengths"], bootstrap_repeats=100)
        vector = next(r for r in conditions if (r["target_letter"], r["strength"], r["direction"], r["stratum"]) == ("A", 1, "vector", "all"))
        pair = next(r for r in pairs if (r["target_letter"], r["strength"], r["stratum"]) == ("A", 1, "all"))
        self.assertEqual((vector["attempts"], vector["valid_answers"], vector["target_count"]), (6, 4, 4))
        self.assertEqual((vector["valid_target_rate"], vector["all_attempt_target_yield"]), (1, 4 / 6))
        self.assertEqual(pair["common_valid_question_ids"], q[:2])
        self.assertEqual(pair["baseline_away_question_ids"], [q[1]])
        self.assertEqual(pair["uptake_rates"], dict(vector=1, random=0))
        self.assertEqual(pair["vector_minus_random"]["estimate"], .5)
        self.assertEqual(pair["uptake_vector_minus_random"]["estimate"], 1)
        self.assertIn("One eligible question", pair["uptake_vector_minus_random"]["precision_warning"])

    def test_disjoint_valid_conditions_are_undefined_in_common_valid_analysis(self):
        rows, _, plan, _ = fixture()
        qids = plan["test_question_ids"]
        for i, qid in enumerate(qids):
            set_response(find(rows, qid, "baseline"), "B")
            set_response(find(rows, qid, "vector", "A", 1), status="ok" if i < 3 else "invalid_answer")
            set_response(find(rows, qid, "random", "A", 1), status="invalid_answer" if i < 3 else "missing_reasoning")
        for row in rows:
            row["correct_answer"] = "B"
        conditions, pairs, _ = estimate_tables(rows, qids, plan["strengths"], bootstrap_repeats=100)
        group = [r for r in conditions if r["target_letter"] == "A" and r["strength"] == 1 and r["stratum"] == "all"]
        self.assertTrue(all(r["valid_target_rate"] == 1 and r["all_attempt_target_yield"] == .5 for r in group))
        pair = next(r for r in pairs if (r["target_letter"], r["strength"], r["stratum"]) == ("A", 1, "all"))
        self.assertEqual(pair["common_valid_n"], 0)
        self.assertIsNone(pair["vector_minus_random"]["estimate"])
        self.assertEqual(pair["vector_minus_random"]["bootstrap_omitted_draws"], 100)
        empty = next(r for r in conditions if (r["target_letter"], r["strength"], r["stratum"]) == ("A", 1, "correct_target"))
        self.assertEqual(empty["attempts"], 0)
        self.assertIsNone(empty["all_attempt_target_yield"])

    def test_shared_question_resamples_are_deterministic_and_preserve_repetitions(self):
        bank = [["q0", "q0", "q1"], ["q1", "q1", "q1"], ["q2", "q2", "q2"]]
        effect = paired_effect({"q0": 1, "q1": -1}, bank)
        self.assertEqual(effect["estimate"], 0)
        self.assertEqual((effect["question_count"], effect["bootstrap_valid_draws"], effect["bootstrap_omitted_draws"]), (2, 2, 1))
        self.assertAlmostEqual(effect["ci_low"], -.9666666667)
        self.assertAlmostEqual(effect["ci_high"], .3)
        self.assertEqual(question_resamples(["q1", "q0"], 10, 42), question_resamples(["q0", "q1"], 10, 42))
        with self.assertRaises(ValueError):
            question_resamples(["q0", "q0"], 10, 42)
        rows, _, plan, _ = fixture()
        original = estimate_tables(rows, plan["test_question_ids"], plan["strengths"], bootstrap_repeats=20)
        reversed_rows = estimate_tables(list(reversed(rows)), list(reversed(plan["test_question_ids"])), plan["strengths"], bootstrap_repeats=20)
        self.assertEqual(original, reversed_rows)
        self.assertTrue(all(r["vector_minus_random"]["question_count"] == 6 for r in original[1] if r["stratum"] == "all"))


class HardwareSensitivityTests(unittest.TestCase):
    def test_declared_entire_question_exclusion_retains_failures_and_five_question_bootstrap(self):
        rows, manifest, plan, source, declaration, checkpoint, runtimes = hardware_fixture()
        set_response(rows[34], status="truncated")
        set_response(rows[35], status="invalid_answer")
        self.assertEqual(validate_run(rows, manifest, plan, source)["retained_grid_outcomes"], 198)
        before = json.dumps(rows, sort_keys=True)
        primary_before = estimate_tables(rows, plan["test_question_ids"], plan["strengths"], bootstrap_repeats=20)
        selected, cohort = select_hardware_sensitivity(rows, plan, declaration, checkpoint, runtimes)
        self.assertEqual(len(selected), 165)
        self.assertEqual({r["question_id"] for r in selected}, set(declaration["secondary_test_question_ids"]))
        self.assertTrue(all(sum(r["question_id"] == qid for r in selected) == 33 for qid in cohort["question_ids"]))
        self.assertEqual(sum(r["direction"] == "baseline" for r in selected), 5)
        self.assertEqual(sum(r["status"] == "truncated" for r in selected), 1)
        self.assertEqual(sum(r["status"] == "invalid_answer" for r in selected), 1)
        self.assertEqual(cohort["correct_answer_counts"], dict(A=0, B=4, C=1, D=0))
        conditions, pairs, decisions = estimate_tables(selected, cohort["question_ids"], plan["strengths"], bootstrap_repeats=20)
        self.assertTrue(all(r["attempts"] == 5 for r in conditions if r["stratum"] == "all"))
        self.assertEqual(len(decisions), 80)
        self.assertTrue(all(r["vector_minus_random"]["question_count"] <= 5 for r in pairs))
        empty = [r for r in conditions if r["stratum"] == "correct_target" and r["target_letter"] in "AD"]
        self.assertTrue(all(r["attempts"] == 0 and r["valid_target_rate"] is None for r in empty))
        one = next(r for r in pairs if r["target_letter"] == "C" and r["stratum"] == "correct_target")
        self.assertEqual(one["common_valid_n"], 1)
        self.assertIn("One eligible question", one["vector_minus_random"]["precision_warning"])
        self.assertEqual(json.dumps(rows, sort_keys=True), before)
        self.assertEqual(primary_before, estimate_tables(rows, plan["test_question_ids"], plan["strengths"], bootstrap_repeats=20))
        with tempfile.TemporaryDirectory() as directory:
            write_report(Path(directory), conditions, pairs, cohort=cohort)
            report = (Path(directory) / "REPORT.md").read_text()
            self.assertIn("There are 5 held-out question clusters and 165 retained grid outcomes", report)
            self.assertIn("5-question cluster resamples", report)
            self.assertIn("six-question/198-outcome primary analysis remains unchanged", report)
            self.assertIn("All steering vectors were fitted on T4", report)

    def test_rejects_partial_grid_changed_membership_late_declaration_and_wrong_runtime(self):
        rows, _, plan, _, declaration, checkpoint, runtimes = hardware_fixture()
        cases = [
            (rows[:-1], plan, declaration, checkpoint, runtimes),
            (rows[33:], plan, declaration, checkpoint, runtimes),
            (rows, plan, dict(declaration, secondary_exclude_question_ids=plan["test_question_ids"][:2]), checkpoint, runtimes),
            (rows, plan, dict(declaration, secondary_test_question_ids=plan["test_question_ids"][:-1]), checkpoint, runtimes),
            (rows, plan, dict(declaration, frozen_at_utc=rows[8]["started_at"]), checkpoint, runtimes),
            (rows, plan, declaration, checkpoint, []),
            (rows, plan, declaration, checkpoint, [dict(runtimes[0], gpu_name="Tesla T4")]),
            (rows, plan, declaration, checkpoint, [dict(runtimes[0], captured_at="2026-11-10T12:00:01+00:00")]),
        ]
        for index, arguments in enumerate(cases):
            with self.subTest(case=index):
                with self.assertRaises(ValueError):
                    select_hardware_sensitivity(*arguments)
        altered = deepcopy(rows)
        altered[0]["content"] = "Changed archived result"
        with self.assertRaisesRegex(ValueError, "checkpoint outcomes changed"):
            select_hardware_sensitivity(altered, plan, declaration, checkpoint, runtimes)

    def test_published_declaration_bytes_match_fixed_hash(self):
        path = Path(__file__).resolve().parents[1] / "docs/archive/pilot-v1/phase3-l4-resume-addendum.json"
        self.assertEqual(sha256(path), HARDWARE_DECLARATION_SHA256)


@unittest.skipUnless(importlib.util.find_spec("matplotlib"), "matplotlib is optional")
class ReportTests(unittest.TestCase):
    def test_report_and_four_panel_plot_do_not_mutate_tables_or_make_labels(self):
        rows, _, plan, _ = fixture()
        conditions, pairs, _ = estimate_tables(rows, plan["test_question_ids"], plan["strengths"], bootstrap_repeats=20)
        before = json.dumps([conditions, pairs], sort_keys=True)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            write_report(out, conditions, pairs)
            write_plot(out, conditions)
            self.assertEqual({p.name for p in out.iterdir()}, {"REPORT.md", "all_attempt_target_yield.png"})
            self.assertGreater((out / "all_attempt_target_yield.png").stat().st_size, 1000)
            self.assertIn("Target-rate difference (all common-valid)", (out / "REPORT.md").read_text())
        self.assertEqual(json.dumps([conditions, pairs], sort_keys=True), before)


if __name__ == "__main__":
    unittest.main()
