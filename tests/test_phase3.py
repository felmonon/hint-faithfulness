"""Prompt-cohort and split invariants; no model downloads or inference."""
import importlib.util
import json
import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from src.common import HINTS, read_jsonl, write_jsonl
from src.phase3 import (load_records, paired_prompts, prompt_ids,
                        summarize, target_stratified_split, write_review_and_plot)


def record(qid="q0", hint="none", repeat=0, **changes):
    row = {"record_id": f"{qid}-{hint}-{repeat}", "question_id": qid,
           "hint_type": hint, "baseline_repeat": repeat, "hint_letter": "B",
           "backend": "local", "synthetic": False, "experiment_id": "e",
           "model": "Qwen/test", "model_revision": "pinned", "status": "ok",
           "answer": "A", "messages": [{"role": "user", "content": "Question?"}],
           "prompt_token_ids": [1, 2], "reasoning": "Test fixture"}
    row.update(changes)
    return row


class PromptCohortTests(unittest.TestCase):
    def test_opt_in_preserves_invalid_outcomes_without_making_them_valid(self):
        rows = [record(), record(hint="metadata", repeat=None, status="invalid_answer", answer=None),
                record(hint="sycophancy", repeat=None, status="truncated", answer=None),
                record(hint="grader_hacking", repeat=None, status="incomplete_thinking", answer=None)]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.jsonl"
            write_jsonl(path, rows)
            before = path.read_bytes()
            strict, identity = load_records(path)
            selected, expanded = load_records(path, include_invalid_source_outcomes=True)
            self.assertEqual(strict, rows[:1])
            self.assertEqual(selected, rows)
            self.assertEqual(identity["complete_source_records"], 1)
            self.assertEqual(expanded["selected_source_records"], 4)
            self.assertEqual(expanded["source_cohort_rule"], "verified_local_prompts_regardless_of_source_outcome_v1")
            self.assertEqual(identity["source_file_sha256"], expanded["source_file_sha256"])
            self.assertEqual(paired_prompts(selected, require_complete=True)[2], ["q0"])
            generated = [dict(r, direction="baseline", target_letter=None, strength=0) for r in selected[1:]]
            self.assertTrue(all(item["valid"] == 0 for item in summarize(generated, [0, 1])))
            self.assertEqual(path.read_bytes(), before)

    def test_opt_in_does_not_bypass_identity_or_token_requirements(self):
        cases = [{"backend": "mock"}, {"synthetic": True}, {"synthetic": None},
                 {"model_revision": "other"}, {"experiment_id": "other"},
                 {"prompt_token_ids": []}, {"prompt_token_ids": [True]},
                 {"prompt_token_ids": [-1]}, {"messages": []}]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.jsonl"
            for changes in cases:
                with self.subTest(changes=changes):
                    write_jsonl(path, [record(), record(qid="q1", status="invalid_answer", answer=None, **changes)])
                    with self.assertRaises(ValueError):
                        load_records(path, include_invalid_source_outcomes=True)
            write_jsonl(path, [record(), record()])
            with self.assertRaisesRegex(ValueError, "Duplicate source record"):
                load_records(path, include_invalid_source_outcomes=True)
        with self.assertRaisesRegex(ValueError, "chat template"):
            prompt_ids(SimpleNamespace(prompt_ids=lambda messages: [1, 9]), record())

    def test_complete_cohort_rejects_missing_or_duplicate_condition(self):
        rows = [record()] + [record(hint=hint, repeat=None) for hint in HINTS]
        self.assertEqual(paired_prompts(rows[:-1])[2], ["q0"])
        with self.assertRaisesRegex(ValueError, "all three hints"):
            paired_prompts(rows[:-1], require_complete=True)
        with self.assertRaisesRegex(ValueError, "Duplicate source question/condition"):
            paired_prompts(rows + [dict(rows[-1], record_id="different-id")], require_complete=True)
        with self.assertRaisesRegex(ValueError, "same assigned letter"):
            paired_prompts([dict(rows[0], hint_letter="A"), *rows[1:]], require_complete=True)


class StratifiedSplitTests(unittest.TestCase):
    def test_frozen_pilot_split_uses_targets_and_keeps_question_groups_disjoint(self):
        questions = read_jsonl(Path(__file__).resolve().parents[1] / "data/questions.jsonl")[:20]
        targets = {q["question_id"]: q["hint_letter"] for q in questions}
        train, test = target_stratified_split(list(reversed(targets)), targets, seed=42)
        self.assertEqual(test, sorted([
            "mmlu-test-570110c87b732eb6", "mmlu-test-6d8b16a1326c1729",
            "mmlu-test-7e21219e263a9975", "mmlu-test-8b4f293c1edb7375",
            "mmlu-test-a0a2bb85e6f09020", "mmlu-test-d25a1d54046e0bd5"]))
        self.assertEqual(Counter(targets[q] for q in train), dict(A=3, B=3, C=5, D=3))
        self.assertEqual(Counter(targets[q] for q in test), dict(A=1, B=1, C=3, D=1))
        self.assertFalse(set(train) & set(test))
        self.assertEqual(set(train + test), set(targets))
        self.assertEqual((train, test), target_stratified_split(list(targets) * 3, targets, seed=42))

    def test_rare_target_is_retained_in_training_or_split_refuses(self):
        targets = dict(zip([f"q{i}" for i in range(8)], "ABBCCDDD"))
        train, test = target_stratified_split(list(targets), targets)
        self.assertIn("q0", train)
        self.assertNotIn("q0", test)
        with self.assertRaisesRegex(ValueError, "reserve training"):
            target_stratified_split(list("abcd"), dict(zip("abcd", "ABCD")))


@unittest.skipUnless(importlib.util.find_spec("numpy"), "numpy optional dependency missing")
class VectorWeightTests(unittest.TestCase):
    def test_question_means_have_equal_weight_and_test_questions_are_never_captured(self):
        import numpy as np
        from unittest.mock import patch
        from src.phase3 import fit_vectors
        bases = {qid: record(qid=qid, value=0) for qid in ("a1", "a2", "b", "c", "d", "heldout")}
        hints = {"a1": [record(hint_letter="A", value=value) for value in (2, 4, 6)],
                 "a2": [record(hint_letter="A", value=10)]}
        hints.update({q: [record(hint_letter=q.upper(), value=2)] for q in "bcd"})
        hints["heldout"] = [record(hint_letter="A", value=1000)]
        captured = []

        def activation(_local, _block, row):
            captured.append(row)
            return np.array([row["value"], row["value"]], dtype="float32")

        with patch("src.phase3.last_activation", side_effect=activation):
            vectors, controls, counts = fit_vectors(None, None, bases, hints, ["a1", "a2", "b", "c", "d"], 42)
        np.testing.assert_array_equal(vectors["A"], [7, 7])
        self.assertEqual(counts, dict(A=2, B=1, C=1, D=1))
        self.assertFalse(any(r["question_id"] == "heldout" or r["value"] == 1000 for r in captured))
        for letter in "ABCD":
            self.assertAlmostEqual(float(np.linalg.norm(vectors[letter])), float(np.linalg.norm(controls[letter])), places=5)


@unittest.skipUnless(importlib.util.find_spec("matplotlib"), "matplotlib optional dependency missing")
class PlotRoundoffTests(unittest.TestCase):
    def test_zero_and_all_success_rates_plot_without_changing_intervals(self):
        rows = [dict(record(qid=f"q{i}"), direction="baseline", target_letter=None, strength=0)
                for i in range(3)]
        summaries = summarize(rows, [0, 1])
        before = json.dumps(summaries, sort_keys=True)
        with TemporaryDirectory() as directory:
            out = Path(directory)
            write_review_and_plot(out, rows, summaries)
            self.assertGreater((out / "steering_rates.png").stat().st_size, 1000)
        self.assertEqual(json.dumps(summaries, sort_keys=True), before)


if __name__ == "__main__":
    unittest.main()
