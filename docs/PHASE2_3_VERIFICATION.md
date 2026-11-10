# Phase 2–3 implementation checks

Checked November 9, 2026 (America/Edmonton). These are **software checks with synthetic fixtures**, not model experiment results. No reported rate here is evidence about Qwen or reasoning faithfulness. No actual model checkpoint was loaded by these checks.

`python3 -m unittest discover -s tests -q` passed all 36 tests present at this checkpoint. The 15 tests in `tests/test_interventions.py` cover:

- Exact token-preserving 0%, partial, and 100% cuts; final-answer exclusion; incomplete thinking and pre-thinking text rejection.
- Rejection of mock data, mixed models/revisions, invalid outcomes, and duplicate baseline weighting.
- Question-group separation across train and test, and question-cluster counting in uncertainty estimates.
- Tiny PyTorch decoder hooks: the captured vectors precede final normalization; hooks are removed; steering touches prediction positions without mutating original tensors.
- Synthetic end-to-end early answering and probe analysis: 24 fixture records, 5 cuts each, 3 artificial activation layers. JSONL, manifests, NPZ arrays, and both charts serialize successfully. Temporary outputs are deleted after testing.
- Steering answer-change denominators and preservation of human labels when additional responses arrive after a resumed run. The test’s manual label is explicitly a fixture, not a human research judgment.

Both Phase 2 and Phase 3 CLI help commands pass. The Python cells in the four Colab notebooks compile after treating notebook shell commands as shell commands; the notebooks have not been executed in Colab.

## Remaining validation

Run the real small-model pilot, inspect raw traces, and then execute Phase 2 on those saved local token sequences. Confirm model revision, numerical precision, token boundaries, context limits, and GPU memory behavior on the actual runtime. The saved manifests record the relevant identities and precision. Phase 3 additionally needs all four target letters represented in its training split, successful held-out steering beyond random-direction controls, and actual human explanation labels.

The implementation intentionally reports answer agreement and linear decodability as proxies. Neither proves that an internal answer was already irrevocably settled; an unreported activation intervention does not establish deliberate concealment.
