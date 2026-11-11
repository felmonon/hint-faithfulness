# Factual erratum to the Phase 3 L4 addendum

Recorded **2026-11-10T10:37:08+00:00**, before resumed generation. This is a correction to the explanatory prose in the [L4 addendum](PHASE3_L4_RESUME_ADDENDUM.md), frozen at 10:33:27 UTC and published in commit `35fc053f65646030b780030fb592861113430ca6`. The original frozen document and [JSON declaration](phase3-l4-resume-addendum.json) remain unchanged. The coordinator reported that resumed inference had not begun: the runtime preflight stopped on imported-package mismatches, which were being corrected.

## Corrected factual statement

The mixed-runtime question `mmlu-test-570110c87b732eb6` has stored dataset `correct_answer` **D**, not C. Excluding that question leaves **A=0, B=4, C=1, D=0**, not A=0, B=4, C=0, D=1. In the five-question sensitivity analysis, correct-target A and D strata are therefore undefined, and correct-target C contains only one question before any outcome attrition. The six-question primary distribution remains A=0, B=4, C=1, D=1.

## Evidence checked

All eight [checkpoint records](../artifacts/pilot-20-phase3-checkpoint-0430/steering.jsonl) identify this same question and carry `correct_answer: "D"`. The checkpoint baseline record is `45cef91658d0fc9eed16ed7b813ecb6504e647558c8d1aacf7065193750103f5`, linked to source record `039add433d7dcceca32559ba`. That baseline-0 source record in the [frozen Phase 1 recovery composite](../artifacts/pilot-20-qwen3-1.7b/recovery-composite/responses.jsonl) also gives D and subject `high_school_european_history`.

The JSON declaration already excludes the correct question identity. Reading its five retained question IDs against the source baseline records gives:

| Retained question ID | Stored correct-answer letter |
|---|---|
| `mmlu-test-6d8b16a1326c1729` | B |
| `mmlu-test-7e21219e263a9975` | B |
| `mmlu-test-8b4f293c1edb7375` | C |
| `mmlu-test-a0a2bb85e6f09020` | B |
| `mmlu-test-d25a1d54046e0bd5` | B |

SHA-256 identities verified when preparing this correction:

| File | SHA-256 |
|---|---|
| Checkpoint `steering.jsonl` | `5bec0702c11667104b6a37a3f15487b19dceb7358f771748e467b346ae63044b` |
| Frozen recovery-composite `responses.jsonl` | `ba4c4e897f182048fc97a08d9872f423f01c6531e933d85077ad5ab712b1a2bf` |
| `phase3-l4-resume-addendum.json` | `b9c9afeeddc099297bfd3eb1c9652590afea97ffcf4be03a4c2ad16ef9716607` |

## Effect on execution and analysis

This corrects a transposed letter/count statement only. It changes no question membership, source label, prompt, vector, split, model, sampling setting, retained record, or planned generation. The primary analysis still retains six questions/198 grid outcomes; the predeclared secondary still excludes the entire same question and retains five questions/165 outcomes. The fixed machine-readable declaration remains the execution reference. Final reporting must use the corrected strata counts and cite this erratum alongside the preserved original addendum. No new model inference, outcome-based selection, or human labeling was used to make the correction.
