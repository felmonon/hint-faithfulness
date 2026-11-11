"""Letter-contrast steering vectors (fix 2) and strength scaling (fix 3). Pure numpy.

For each training question q, hint type h and pointed-to letter L we have one
activation a[q, h, L] (last prompt token, one layer). The vector for letter X is

    v_X = mean_{q,h} a[q,h,X]  -  mean_{q,h, L != X} a[q,h,L]

so everything shared by all hinted prompts ("a hint is present", the question
itself) cancels, leaving what differs when the hint points at X.
"""
from __future__ import annotations

import numpy as np

LETTERS = "ABCD"


def letter_contrast_vectors(acts, letters):
    """acts: (n, d) activations; letters: length-n sequence of hinted letters."""
    acts = np.asarray(acts, dtype=np.float64)
    letters = np.asarray(list(letters))
    if acts.ndim != 2 or len(letters) != len(acts):
        raise ValueError("acts must be (n, d) with one letter per row")
    vectors = {}
    for letter in LETTERS:
        own, other = acts[letters == letter], acts[letters != letter]
        if not len(own) or not len(other):
            raise ValueError(f"Need rows hinting {letter} and rows hinting other letters")
        vectors[letter] = own.mean(axis=0) - other.mean(axis=0)
    return vectors


def pairwise_cosines(vectors):
    keys = sorted(vectors)
    out = {}
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            va, vb = vectors[a], vectors[b]
            out[f"{a}{b}"] = float(va @ vb / (np.linalg.norm(va) * np.linalg.norm(vb)))
    return out


def unit(vector):
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm <= 1e-12:
        raise ValueError("Zero vector")
    return np.asarray(vector) / norm


def random_like(vector, seed):
    """Random Gaussian direction with exactly the same L2 norm."""
    rng = np.random.default_rng(seed)
    r = rng.standard_normal(np.shape(vector))
    return r * np.linalg.norm(vector) / np.linalg.norm(r)


def scaled(direction, fraction, median_norm):
    """Steering addition = fraction x median residual norm, along a unit direction."""
    return unit(direction) * float(fraction) * float(median_norm)


def calibrated_strengths(valid_rates, threshold=0.8, max_keep=4):
    """valid_rates: {fraction: share of outputs with a valid answer}.

    Keep fractions whose valid rate >= threshold; return up to `max_keep`
    spanning the kept range (always the smallest and largest kept).
    """
    kept = sorted(f for f, r in valid_rates.items() if f > 0 and r >= threshold)
    if len(kept) <= max_keep:
        return kept
    picks = np.linspace(0, len(kept) - 1, max_keep).round().astype(int)
    return [kept[i] for i in sorted(set(picks.tolist()))]
