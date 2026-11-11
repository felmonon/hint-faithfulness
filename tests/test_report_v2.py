import unittest

from src.report_v2 import early_switch_analysis, kappa


class KappaTest(unittest.TestCase):
    def test_perfect_and_chance(self):
        self.assertEqual(kappa([1, 0, 1, 0], [1, 0, 1, 0]), 1.0)
        self.assertAlmostEqual(kappa([1, 1, 0, 0], [1, 0, 1, 0]), 0.0)

    def test_known_value(self):
        # 2x2 table [[20,5],[10,15]]: po=.7, pe=.5 -> kappa=.4
        a = [1] * 25 + [0] * 25
        b = [1] * 20 + [0] * 5 + [1] * 10 + [0] * 15
        self.assertAlmostEqual(kappa(a, b), 0.4)

    def test_constant_labels_undefined(self):
        self.assertIsNone(kappa([1, 1], [1, 1]))



def _resp(q, hint, answer, hint_letter="B", repeat=None):
    return {"record_id": f"{q}-{hint}-{repeat}", "experiment_id": "e", "model": "m", "question_id": q,
            "hint_type": hint, "baseline_repeat": repeat, "hint_letter": hint_letter, "answer": answer,
            "status": "ok" if answer else "invalid_answer"}


def _early(resp, forced):
    return {"record_id": resp["record_id"], "hint_type": resp["hint_type"], "hint_letter": resp["hint_letter"],
            "fraction": 0.0, "forced_answer": forced, "final_answer": resp["answer"], "status": "ok"}


class EarlyEligibilityTest(unittest.TestCase):
    def test_ineligible_hinted_kept_out_of_switch_split(self):
        # q1 eligible (baseline A != hint B): switches. q2 eligible: does not switch.
        # q3 ineligible (baseline already B): hinted answer B is NOT a switch and must not be "not switched".
        responses = [_resp("q1", "none", "A", repeat=0), _resp("q1", "metadata", "B"),
                     _resp("q2", "none", "A", repeat=0), _resp("q2", "metadata", "A"),
                     _resp("q3", "none", "B", repeat=0), _resp("q3", "metadata", "B")]
        forced = {"q1": "B", "q2": "A", "q3": "B"}
        early = [_early(r, forced[r["question_id"]] if r["hint_type"] != "none" else "A") for r in responses]
        out = early_switch_analysis(early, responses)
        groups = out["forced_at_0pct_equals_hint"]
        self.assertEqual((groups["switched_hinted"]["successes"], groups["switched_hinted"]["n"]), (1, 1))
        self.assertEqual((groups["not_switched_hinted"]["successes"], groups["not_switched_hinted"]["n"]), (0, 1))
        self.assertEqual((groups["ineligible_hinted"]["successes"], groups["ineligible_hinted"]["n"]), (1, 1))
        self.assertEqual((out["switch_given_forced0_hint"]["successes"], out["switch_given_forced0_hint"]["n"]), (1, 1))
        self.assertEqual((out["switch_given_forced0_not_hint"]["successes"], out["switch_given_forced0_not_hint"]["n"]), (0, 1))


if __name__ == "__main__":
    unittest.main()
