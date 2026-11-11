# Phase 2–3 implementation checks

**Final update, November 11 UTC:** Both real pilot extensions completed. Phase 3 now has 198 audited retained outputs, with unchanged eight/28-row prefixes and both primary/secondary numerical analyses. See the [Phase 3 report](PHASE3_PILOT_REPORT.md) and [final audit](../results/pilot-20-phase3-v1/artifact_audit/audit.md). The latest software suite passed 152 tests. The entries below are preserved historical software/execution checkpoints, not current GPU blockers. Human validation and the larger two-model study remain absent.

**Historical checkpoint, November 10 UTC:** Real Phase 2 has completed on the pinned Qwen3-1.7B checkpoint, with [raw artifacts](../artifacts/pilot-20-phase2-v1/), exact source hashes, runtime metadata, and the [frozen plan](../artifacts/pilot-20-phase2-v1/plan.json). Phase 3 is **blocked by Colab GPU usage limits** after loss of the earlier runtime. Its [archived checkpoint](../artifacts/pilot-20-phase3-checkpoint-0430/) preserves eight records; 190 grid positions lack archived outcomes, and later original attempts are unknown. The [resume protocol](archive/pilot-v1/PHASE3_RESUME_PROTOCOL.md) preserves the [separate frozen plan](../artifacts/pilot-20-phase3-v1/plan.json), vectors, and retained rows. The synthetic checks below remain historical software evidence, not substitutes for model measurements.

The local suite at that checkpoint passed **97 tests** with `python3.12 -m unittest discover -s tests -q` on November 10 UTC, including seven offline Phase 3 analyzer tests. The earlier 36-test checkpoint below is retained as history. Passing the expanded suite does not imply that the 198-position model sweep completed.

Checked November 9, 2026 (America/Edmonton). These are **software checks with synthetic fixtures**, not model experiment results. No reported rate here is evidence about Qwen or reasoning faithfulness. No actual model checkpoint was loaded by these checks.

`python3 -m unittest discover -s tests -q` passed all 36 tests present at this checkpoint. The 15 tests in `tests/test_interventions.py` cover:

- Exact token-preserving 0%, partial, and 100% cuts; final-answer exclusion; incomplete thinking and pre-thinking text rejection.
- Rejection of mock data, mixed models/revisions, invalid outcomes, and duplicate baseline weighting.
- Question-group separation across train and test, and question-cluster counting in uncertainty estimates.
- Tiny PyTorch decoder hooks: the captured vectors precede final normalization; hooks are removed; steering touches prediction positions without mutating original tensors.
- Synthetic end-to-end early answering and probe analysis: 24 fixture records, 5 cuts each, 3 artificial activation layers. JSONL, manifests, NPZ arrays, and both charts serialize successfully. Temporary outputs are deleted after testing.
- Steering answer-change denominators and preservation of human labels when additional responses arrive after a resumed run. The test’s manual label is explicitly a fixture, not a human research judgment.

Both Phase 2 and Phase 3 CLI help commands pass. The Python cells in the four Colab notebooks compile after treating notebook shell commands as shell commands; the notebooks have not been executed in Colab.

## Historical validation status at the checkpoint

The real small-model pilot, full retained-trace AI review, and Phase 2 execution are now complete. The [Phase 2 report](PHASE2_PILOT_REPORT.md) and [numerical audit](../results/pilot-20-phase2-v1/audit.md) verify checkpoint identity, FP16 runtime, token boundaries, arrays, grouped splits, predictions, and statistics. They do not supply independent human labels or an independent GPU replication.

Phase 3 cannot currently continue because Colab reports that a GPU connection is unavailable due to usage limits. The verified checkpoint contains all four fitted target vectors and random controls, plus eight records covering only part of one question. The remaining 190 grid positions require a retained continuation outcome; their earlier attempt history is unknown. No completed steering result is available. Recovery must preserve failed outputs, original/new runtime provenance, and compare attrition/common-valid pairs before interpreting steering. AI explanation review may be reported separately; it cannot become human validation.

The implementation intentionally reports answer agreement and linear decodability as proxies. Neither proves that an internal answer was already irrevocably settled; an unreported activation intervention does not establish deliberate concealment.
