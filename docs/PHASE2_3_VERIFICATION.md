# Phase 2–3 implementation checks

**Later live checkpoint, November 10 UTC:** Real Phase 2 has completed on the pretrained Qwen3-1.7B checkpoint, with [raw artifacts](../artifacts/pilot-20-phase2-v1/), exact source hashes, runtime metadata, and the [frozen plan](phase2-pilot-plan.json). Phase 3 is running under its [separate frozen plan](phase3-pilot-plan.json). The synthetic checks below remain historical software evidence, not substitutes for these model measurements. The expanded software suite now passes 90 tests.

Checked November 9, 2026 (America/Edmonton). These are **software checks with synthetic fixtures**, not model experiment results. No reported rate here is evidence about Qwen or reasoning faithfulness. No actual model checkpoint was loaded by these checks.

`python3 -m unittest discover -s tests -q` passed all 36 tests present at this checkpoint. The 15 tests in `tests/test_interventions.py` cover:

- Exact token-preserving 0%, partial, and 100% cuts; final-answer exclusion; incomplete thinking and pre-thinking text rejection.
- Rejection of mock data, mixed models/revisions, invalid outcomes, and duplicate baseline weighting.
- Question-group separation across train and test, and question-cluster counting in uncertainty estimates.
- Tiny PyTorch decoder hooks: the captured vectors precede final normalization; hooks are removed; steering touches prediction positions without mutating original tensors.
- Synthetic end-to-end early answering and probe analysis: 24 fixture records, 5 cuts each, 3 artificial activation layers. JSONL, manifests, NPZ arrays, and both charts serialize successfully. Temporary outputs are deleted after testing.
- Steering answer-change denominators and preservation of human labels when additional responses arrive after a resumed run. The test’s manual label is explicitly a fixture, not a human research judgment.

Both Phase 2 and Phase 3 CLI help commands pass. The Python cells in the four Colab notebooks compile after treating notebook shell commands as shell commands; the notebooks have not been executed in Colab.

## Current validation status

The real small-model pilot, full retained-trace AI review, and Phase 2 execution are now complete. The [Phase 2 report](PHASE2_PILOT_REPORT.md) and [numerical audit](../results/pilot-20-phase2-v1/audit.md) verify checkpoint identity, FP16 runtime, token boundaries, arrays, grouped splits, predictions, and statistics. They do not supply independent human labels or an independent GPU replication.

Phase 3 is running with all four target letters represented in its training split, exact source prompt checks, separate held-out questions, and norm-matched random directions. Completion must preserve failed outputs and compare attrition/common-valid pairs before interpreting steering. AI explanation review may be reported separately; it cannot become human validation.

The implementation intentionally reports answer agreement and linear decodability as proxies. Neither proves that an internal answer was already irrevocably settled; an unreported activation intervention does not establish deliberate concealment.
