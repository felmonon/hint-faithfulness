"""Intervention invariants with tiny fixtures, never downloaded model weights."""
import importlib.util
import unittest
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory

from src.phase2 import cut_input, early_selection, select_local_records, thinking_layout


class Tokenizer:
    tokens = {"<think>": [10], "</think>": [11], "\n\nAnswer: (": [20, 21],
              "A": [30], "B": [31], "C": [32], "D": [33]}

    def encode(self, text, add_special_tokens=False):
        return self.tokens[text]

    def decode(self, ids, skip_special_tokens=False):
        return "".join({10: "<think>", 11: "</think>", 30: "A", 31: "B", 32: "C", 33: "D",
                        99: "leaked answer", 9: "\n"}.get(i, "x") for i in ids)


def row(**changes):
    result = {"record_id": "r", "question_id": "q1", "model": "Qwen/test", "model_revision": "pinned",
              "experiment_id": "e", "backend": "local", "status": "ok", "answer": "A", "correct_answer": "A",
              "hint_type": "none", "baseline_repeat": 0, "hint_letter": "B",
              "prompt_token_ids": [1, 2], "generated_token_ids": [10, 41, 42, 43, 44, 11, 30, 99]}
    result.update(changes)
    return result


class TokenCutTests(unittest.TestCase):
    def test_cut_retains_exact_tokens_and_never_answer(self):
        ids, shown, total = cut_input(row(), Tokenizer(), .5)
        self.assertEqual(ids, [1, 2, 10, 41, 42, 11, 20, 21])
        self.assertEqual((shown, total), (2, 4))
        self.assertNotIn(99, ids)

    def test_zero_and_full_cut(self):
        self.assertEqual(cut_input(row(), Tokenizer(), 0)[0], [1, 2, 10, 11, 20, 21])
        self.assertEqual(cut_input(row(), Tokenizer(), 1)[0], [1, 2, 10, 41, 42, 43, 44, 11, 20, 21])

    def test_template_can_already_open_thinking(self):
        r = row(prompt_token_ids=[1, 2, 10, 9], generated_token_ids=[41, 42, 11, 99])
        self.assertEqual(thinking_layout(r, Tokenizer()), ([1, 2, 10, 9], [41, 42], 11))

    def test_rejects_incomplete_thinking(self):
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            thinking_layout(row(generated_token_ids=[10, 41, 42]), Tokenizer())

    def test_rejects_leakage_before_thinking_marker(self):
        with self.assertRaisesRegex(ValueError, "leak"):
            thinking_layout(row(generated_token_ids=[99, 10, 41, 11]), Tokenizer())


class SelectionTests(unittest.TestCase):
    def test_rejects_mock_mixed_model_and_mixed_revision(self):
        for changes in ({"backend": "mock"}, {"model": "another"}, {"model_revision": "different"}):
            with self.assertRaises(ValueError):
                select_local_records([row(), row(question_id="q2", **changes)])

    def test_invalid_and_noise_repeat_excluded(self):
        selected = select_local_records([row(), row(question_id="q2", status="truncated", answer=None),
                                         row(baseline_repeat=1)])
        self.assertEqual(len(selected), 1)

    def test_only_target_switches_enter_hinted_curve(self):
        rows = [row(), row(hint_type="metadata", answer="B", baseline_repeat=None),
                row(hint_type="sycophancy", answer="C", baseline_repeat=None)]
        selected = early_selection(select_local_records(rows))
        self.assertEqual([group for _, group in selected], ["unhinted", "hinted_switch"])


class SteeringSelectionTests(unittest.TestCase):
    def test_changed_answer_denominator_excludes_baseline_already_target(self):
        from src.phase3 import summarize
        rows = [dict(row(question_id="q1", answer="B"), direction="baseline", target_letter=None, strength=0),
                dict(row(question_id="q2", answer="A"), direction="baseline", target_letter=None, strength=0),
                dict(row(question_id="q1", answer="B"), direction="vector", target_letter="B", strength=1),
                dict(row(question_id="q2", answer="B"), direction="vector", target_letter="B", strength=1)]
        summaries = summarize(rows, [0, 1])
        observed = next(r for r in summaries if r["target_letter"] == "B" and r["direction"] == "vector" and r["strength"] == 1)
        self.assertEqual((observed["valid"], observed["eligible_pairs"], observed["switch_count"]), (2, 1, 1))


@unittest.skipUnless(importlib.util.find_spec("numpy"), "numpy optional dependency is not installed")
class SplitTests(unittest.TestCase):
    def test_question_groups_never_leak(self):
        from src.phase2 import question_split
        questions = [f"q{i}" for i in range(10) for _ in range(4)]
        train, test = question_split(questions, seed=7)
        self.assertFalse({questions[i] for i in train} & {questions[i] for i in test})
        self.assertEqual(len(test), 12)
        self.assertEqual((train.tolist(), test.tolist()), tuple(x.tolist() for x in question_split(questions, seed=7)))

    def test_cluster_interval_counts_questions_not_condition_rows(self):
        from src.phase2 import clustered_interval
        result = clustered_interval([True, True, False, False], ["q1", "q1", "q2", "q2"], repeats=100)
        self.assertEqual((result["n"], result["questions"], result["rate"]), (4, 2, .5))


@unittest.skipUnless(importlib.util.find_spec("torch") and importlib.util.find_spec("numpy"),
                     "torch/numpy optional dependencies are not installed")
class ResidualTests(unittest.TestCase):
    def test_steering_only_changes_prediction_positions(self):
        import torch
        from src.phase3 import steering_hook
        vector = torch.tensor([2.0, 3.0])
        hook = steering_hook(vector, 2, prompt_length=3)
        original = torch.zeros(1, 3, 2)
        changed = hook(None, None, original)
        self.assertTrue(torch.equal(changed[0, :2], original[0, :2]))
        self.assertEqual(changed[0, -1].tolist(), [4.0, 6.0])
        self.assertEqual(original.sum().item(), 0.0)
        cached = hook(None, None, torch.zeros(1, 1, 2))
        self.assertEqual(cached[0, 0].tolist(), [4.0, 6.0])

    def test_hooks_capture_pre_final_norm_and_are_removed(self):
        import torch
        from src.phase2 import capture_residuals

        class Add(torch.nn.Module):
            def __init__(self, amount):
                super().__init__()
                self.amount = amount
            def forward(self, hidden):
                return hidden + self.amount

        class Backbone(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.layers = torch.nn.ModuleList([Add(1), Add(3)])
            def forward(self, input_ids, attention_mask, use_cache):
                hidden = input_ids.float().unsqueeze(-1)
                for layer in self.layers:
                    hidden = layer(hidden)
                return hidden * 100

        backbone = Backbone()
        local = SimpleNamespace(device="cpu", model=SimpleNamespace(model=backbone,
                                 config=SimpleNamespace(max_position_embeddings=100)))
        states = capture_residuals(local, [8, 2])
        self.assertEqual(states[:, 0].tolist(), [3.0, 6.0])
        self.assertTrue(all(len(layer._forward_hooks) == 0 for layer in backbone.layers))


@unittest.skipUnless(all(importlib.util.find_spec(name) for name in ("numpy", "sklearn", "matplotlib")),
                     "Analysis dependencies are not installed")
class SyntheticPipelineTests(unittest.TestCase):
    def test_early_and_probe_artifacts_serialize(self):
        import contextlib
        import io
        import json
        import numpy as np
        from unittest.mock import patch
        from src.phase2 import run_early, run_probe

        rows = []
        for i in range(12):
            answer, hint = "ABCD"[i % 4], "ABCD"[(i + 1) % 4]
            for j in range(2):
                rows.append(row(record_id=f"{i}-{j}", question_id=f"q{i}", answer=answer if j == 0 else hint,
                                correct_answer=answer, hint_letter=hint, hint_type="none" if j == 0 else "metadata",
                                baseline_repeat=0 if j == 0 else None, prompt_token_ids=[100 + i, 50 + j]))
        local = SimpleNamespace(tokenizer=Tokenizer(), model=SimpleNamespace(dtype="synthetic-fixture"))
        def fake_capture(_local, ids):
            return np.random.default_rng(sum(ids)).normal(size=(3, 8))
        with TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            out = Path(directory)
            with patch("src.phase2.candidate_probabilities", return_value=(dict.fromkeys("ABCD", .1), dict.fromkeys("ABCD", .25))):
                run_early(local, rows, out, SimpleNamespace(command="early", seed=42))
            with patch("src.phase2.capture_residuals", side_effect=fake_capture):
                run_probe(local, rows, out, SimpleNamespace(command="probe", seed=42))
            self.assertTrue((out / "early_answering.png").stat().st_size > 1000)
            self.assertTrue((out / "probe_accuracy.png").stat().st_size > 1000)
            self.assertEqual(len((out / "early_results.jsonl").read_text().splitlines()), 120)
            with np.load(out / "probe_activations.npz", allow_pickle=False) as arrays:
                self.assertEqual(arrays["activations"].shape, (24, 3, 8))
            manifest = json.loads((out / "probe_manifest.json").read_text())
            self.assertFalse(set(manifest["train_questions"]) & set(manifest["test_questions"]))

    def test_resumed_steering_review_preserves_labels_and_adds_new_cases(self):
        import csv
        from src.phase3 import summarize, write_review_and_plot

        rows = [dict(row(record_id="base1", question_id="q1", answer="A"), direction="baseline", target_letter=None, strength=0),
                dict(row(record_id="base2", question_id="q2", answer="A"), direction="baseline", target_letter=None, strength=0),
                dict(row(record_id="switch1", question_id="q1", answer="B"), direction="vector", target_letter="B", strength=1)]
        with TemporaryDirectory() as directory:
            out = Path(directory)
            write_review_and_plot(out, rows, summarize(rows, [0, 1]))
            labels = out / "explanation_labels.csv"
            with labels.open(newline="") as stream:
                saved = list(csv.DictReader(stream))
            saved[0].update(human_label="ordinary_argument", notes="Human fixture label; not research evidence")
            with labels.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(saved[0]))
                writer.writeheader()
                writer.writerows(saved)
            rows.append(dict(row(record_id="switch2", question_id="q2", answer="C"), direction="vector", target_letter="C", strength=1))
            write_review_and_plot(out, rows, summarize(rows, [0, 1]))
            with labels.open(newline="") as stream:
                restored = list(csv.DictReader(stream))
            self.assertEqual(len(restored), 2)
            self.assertEqual(restored[0]["human_label"], "ordinary_argument")
            self.assertEqual(restored[1]["human_label"], "")


if __name__ == "__main__":
    unittest.main()
