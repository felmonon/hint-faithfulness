import unittest

import numpy as np

from src.vectors_v2 import (calibrated_strengths, letter_contrast_vectors, pairwise_cosines,
                            random_like, scaled)


class LetterContrast(unittest.TestCase):
    def synthetic(self, seed=0, d=64, questions=30):
        rng = np.random.default_rng(seed)
        hint_present = rng.standard_normal(d) * 5          # shared by every hinted prompt
        letter_dirs = {L: rng.standard_normal(d) for L in "ABCD"}
        acts, letters = [], []
        for _ in range(questions):
            q = rng.standard_normal(d) * 3                  # question content
            for _h in range(3):
                for L in "ABCD":
                    acts.append(q + hint_present + letter_dirs[L] + .1 * rng.standard_normal(d))
                    letters.append(L)
        return np.array(acts), letters, letter_dirs

    def test_cancels_shared_hint_component(self):
        acts, letters, dirs = self.synthetic()
        vectors = letter_contrast_vectors(acts, letters)
        mean_dir = np.mean(list(dirs.values()), axis=0)
        for L, v in vectors.items():
            expected = dirs[L] - (sum(dirs.values()) - dirs[L]) / 3
            self.assertGreater(np.dot(v, expected) / np.linalg.norm(v) / np.linalg.norm(expected), .99)
            # The shared "hint present" offset is gone.
            self.assertLess(abs(np.dot(v, mean_dir)) / np.linalg.norm(v) / np.linalg.norm(mean_dir), .5)

    def test_exact_formula(self):
        acts = np.array([[1., 0], [3, 0], [0, 2], [0, 4], [5, 5], [7, 7], [-1, -1], [1, 1]])
        letters = list("AABBCCDD")
        v = letter_contrast_vectors(acts, letters)
        np.testing.assert_allclose(v["A"], acts[:2].mean(0) - acts[2:].mean(0))
        np.testing.assert_allclose(v["D"], acts[6:].mean(0) - acts[:6].mean(0))

    def test_letter_vectors_are_not_all_alike(self):
        # Contrast vectors of four letters sum to zero-ish and have negative mean cosine.
        acts, letters, _ = self.synthetic(seed=1)
        cos = pairwise_cosines(letter_contrast_vectors(acts, letters))
        self.assertEqual(len(cos), 6)
        self.assertLess(np.mean(list(cos.values())), 0)

    def test_missing_letter_rejected(self):
        with self.assertRaises(ValueError):
            letter_contrast_vectors(np.ones((3, 2)), list("ABC"))


class Scaling(unittest.TestCase):
    def test_random_same_norm(self):
        v = np.arange(10.)
        r = random_like(v, 3)
        self.assertAlmostEqual(np.linalg.norm(r), np.linalg.norm(v))
        self.assertLess(abs(r @ v) / np.linalg.norm(v) ** 2, .9)

    def test_scaled_norm(self):
        self.assertAlmostEqual(np.linalg.norm(scaled(np.array([3., 4]), .25, 80)), 20)

    def test_calibration_rule(self):
        rates = {0.02: 1, 0.05: .95, 0.1: .9, 0.2: .85, 0.4: .8, 0.8: .1}
        self.assertEqual(calibrated_strengths(rates), [0.02, 0.05, 0.2, 0.4])
        self.assertEqual(calibrated_strengths({0.1: .9, 0.2: .5}), [0.1])
        self.assertEqual(calibrated_strengths({0.1: .5}), [])


if __name__ == "__main__":
    unittest.main()
