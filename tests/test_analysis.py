import copy
import unittest

from src.analyze import (eligible_switches, rate, response_fingerprint, summarize,
                         validation_matches, verdict_fingerprint)


def response(qid, hint="none", repeat=0, answer="A", target="B", status="ok", reasoning="Work."):
    return {"record_id": f"{qid}-{hint}-{repeat}", "question_id": qid, "experiment_id": "exp",
            "model": "test-model", "backend": "mock", "synthetic": True, "subject": "test",
            "correct_answer": "D", "hint_type": hint, "hint_letter": target,
            "baseline_repeat": repeat, "answer": answer, "status": status,
            "reasoning": reasoning, "prompt": "Question and hint", "content": f"Answer: ({answer})"}


def judgment(row, faithful=False):
    return {"record_id": row["record_id"], "judge_model": "judge", "rubric_version": "test-v1",
            "rubric_hash": "rubric-hash", "status": "ok", "faithful": faithful,
            "mentions_hint": faithful, "relies_on_hint": faithful, "only_final_check": False,
            "response_hash": response_fingerprint(row)}


class AnalysisTests(unittest.TestCase):
    def test_empty_and_extreme_intervals(self):
        self.assertIsNone(rate(0, 0)["rate"])
        self.assertEqual(rate(0, 0)["ci95"], [None, None])
        self.assertGreater(rate(0, 10)["ci95"][1], 0)
        self.assertLess(rate(10, 10)["ci95"][0], 1)

    def test_conditional_denominator_and_paired_directional_noise(self):
        rows = []
        for qid, base, second, hinted in [("1", "A", "B", "B"), ("2", "A", "A", "B"),
                                          ("3", "B", "A", "B"), ("4", "A", "C", "C")]:
            rows += [response(qid, answer=base), response(qid, repeat=1, answer=second),
                     response(qid, "sycophancy", None, hinted)]
        summary = summarize(rows)["summaries"][0]
        # HINTS are sorted insertion order; explicitly find our condition.
        summary = next(x for x in summarize(rows)["summaries"] if x["hint_type"] == "sycophancy")
        self.assertEqual(summary["uptake"]["n"], 3)
        self.assertAlmostEqual(summary["uptake"]["rate"], 2 / 3)
        self.assertAlmostEqual(summary["directional_noise"]["rate"], 1 / 3)
        self.assertAlmostEqual(summary["overall_baseline_disagreement"]["rate"], 3 / 4)
        self.assertAlmostEqual(summary["uptake_minus_directional_noise"]["difference"], 1 / 3)
        self.assertEqual(summary["attrition"]["baseline_already_target"], 1)
        self.assertEqual(len(eligible_switches(rows)), 2)

    def test_missing_reasoning_is_not_false_and_truncation_is_excluded(self):
        rows = [response("1"), response("1", repeat=1),
                response("1", "metadata", None, "B", status="missing_reasoning", reasoning=""),
                response("2"), response("2", repeat=1),
                response("2", "metadata", None, "B", status="truncated")]
        summary = next(x for x in summarize(rows)["summaries"] if x["hint_type"] == "metadata")
        self.assertEqual(summary["uptake"]["n"], 1)
        self.assertEqual(summary["uptake"]["rate"], 1)
        self.assertEqual(summary["attrition"]["invalid_hinted_response"], 1)
        self.assertEqual(summary["judge_coverage"]["missing_reasoning"], 1)
        self.assertEqual(summary["provisional_labeled_faithfulness"]["n"], 0)
        self.assertIsNone(summary["faithfulness"]["rate"])

    def test_invalid_second_baseline_only_excludes_paired_comparison(self):
        rows = [response("1"), response("1", repeat=1, answer=None, status="error"),
                response("1", "metadata", None, "B")]
        summary = next(x for x in summarize(rows)["summaries"] if x["hint_type"] == "metadata")
        self.assertEqual(summary["uptake"]["n"], 1)
        self.assertEqual(summary["paired_uptake"]["n"], 0)
        self.assertIsNone(summary["directional_noise"]["rate"])

    def test_duplicate_conflicts_and_real_mock_mixing_are_rejected(self):
        row = response("1")
        conflicting = dict(row, answer="C")
        with self.assertRaisesRegex(ValueError, "Conflicting duplicate"):
            summarize([row, conflicting])
        real = dict(response("2"), backend="local", synthetic=False)
        with self.assertRaisesRegex(ValueError, "synthetic"):
            summarize([row, real])

    def test_validation_is_bound_to_exact_verdicts(self):
        judgments = {str(i): judgment(response(str(i))) for i in range(30)}
        # Keys in the index must match actual record IDs.
        judgments = {r["record_id"]: r for r in judgments.values()}
        validation = {"passed": True, "held_out": True,
                      "verdict_fingerprints": {key: verdict_fingerprint(row) for key, row in judgments.items()}}
        self.assertTrue(validation_matches(validation, judgments))
        changed = copy.deepcopy(judgments)
        next(iter(changed.values()))["faithful"] = True
        self.assertFalse(validation_matches(validation, changed))
        validation["held_out"] = False
        self.assertFalse(validation_matches(validation, judgments))

    def test_faithfulness_requires_full_coverage(self):
        rows, verdicts = [], []
        for i in range(30):
            current = response(str(i), "metadata", None, "B")
            rows += [response(str(i)), response(str(i), repeat=1), current]
            verdicts.append(judgment(current, i % 2 == 0))
        validation = {"passed": True, "held_out": True, "judge_model": "judge", "rubric_version": "test-v1",
                      "rubric_hash": "rubric-hash",
                      "verdict_fingerprints": {r["record_id"]: verdict_fingerprint(r) for r in verdicts}}
        summary = next(x for x in summarize(rows, verdicts, validation)["summaries"] if x["hint_type"] == "metadata")
        self.assertEqual(summary["faithfulness"]["rate"], .5)
        new_switch = response("extra", "metadata", None, "B")
        rows += [response("extra"), response("extra", repeat=1), new_switch]
        summary = next(x for x in summarize(rows, verdicts, validation)["summaries"] if x["hint_type"] == "metadata")
        self.assertIsNone(summary["faithfulness"]["rate"])
        self.assertEqual(summary["provisional_labeled_faithfulness"]["rate"], .5)


if __name__ == "__main__":
    unittest.main()
