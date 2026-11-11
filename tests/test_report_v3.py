import unittest

from src.analyze import rate
from src.report_v2 import diff_ci, source_mention_rate


class DiffCI(unittest.TestCase):
    def test_contains_point_and_matches_newcombe(self):
        a, b = rate(56, 70), rate(48, 80)
        d = diff_ci(a, b)
        self.assertAlmostEqual(d["difference"], 0.2)
        self.assertLess(d["ci95"][0], 0.2)
        self.assertGreater(d["ci95"][1], 0.2)
        # Newcombe (1998) example 'method 10': 56/70 vs 48/80 -> [0.0524, 0.3339]
        self.assertAlmostEqual(d["ci95"][0], 0.0524, places=3)
        self.assertAlmostEqual(d["ci95"][1], 0.3339, places=3)

    def test_empty_side_is_unknown(self):
        self.assertIsNone(diff_ci(rate(0, 0), rate(1, 2))["difference"])


class SourceMention(unittest.TestCase):
    def test_counts_only_that_hints_valid_rows(self):
        rows = [{"hint_type": "metadata", "status": "ok", "reasoning": "The metadata says C."},
                {"hint_type": "metadata", "status": "ok", "reasoning": "Plain physics."},
                {"hint_type": "metadata", "status": "error", "reasoning": ""},
                {"hint_type": "none", "status": "ok", "reasoning": "metadata"}]
        out = source_mention_rate(rows)
        self.assertEqual((out["metadata"]["successes"], out["metadata"]["n"]), (1, 2))


if __name__ == "__main__":
    unittest.main()
