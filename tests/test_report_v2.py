import unittest

from src.report_v2 import kappa


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


if __name__ == "__main__":
    unittest.main()
