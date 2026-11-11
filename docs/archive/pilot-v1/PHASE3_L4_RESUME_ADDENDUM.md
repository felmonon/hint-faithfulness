# Phase 3 L4 hardware recovery addendum

Frozen at **2026-11-10T10:33:27+00:00**, before any resumed generation. This is an infrastructure amendment after the original eight T4 records were already available; it is not an original preregistration. The original pilot plan, recovery protocol, and scientific source remain unchanged. Machine-readable declarations are in `phase3-l4-resume-addendum.json`.

Paid Colab credits were confirmed in the interface. Allocation of the requested T4 failed with “No backend with GPU available.” A CPU fallback began dependency setup only; the notebook's CUDA/T4 guard prevented restoration or inference. An L4 GPU runtime was subsequently connected. The continuation is permitted on **NVIDIA L4**, with actual GPU, driver, Python, CUDA and package versions recorded before inference. The preflight refuses any other GPU. Availability motivated this change, not observed steering success.

The continuation preserves the original eight rows byte for byte, the exact saved vectors and manifest, the pinned Qwen model/tokenizer revision, all prompts, split, strengths, sampling settings, seeds, dtype, eager attention, strict parser, and interpretation gate. It fills only the 190 missing positions. No retained invalid or truncated output is retried. Unknown unarchived earlier attempts remain unknown.

Hardware and software differences can change floating-point calculations and sampled outputs despite identical seeds. The original eight outcomes are all from question `mmlu-test-570110c87b732eb6`; its remaining 25 conditions will therefore span T4 and L4. The other five questions' 165 conditions will all be generated on L4 if this continuation completes. All vectors were fitted on the original T4 and will be reused, not refitted.

## Analysis declared before continuation

The **primary analysis retains all six held-out questions and all 198 retained grid outcomes**, with the previously specified baseline/random controls, every strength, attrition, common-valid comparisons and question-level bootstrap. No outcome-based condition or question selection is introduced.

A **secondary hardware sensitivity analysis excludes the entire mixed-runtime question** `mmlu-test-570110c87b732eb6`, leaving the five questions listed in the JSON declaration and 165 grid outcomes. It repeats the same target/strength, correct versus incorrect target, common-valid, all-retained-outcome and question-bootstrap summaries. Exclusion applies to every condition for that question, including the baseline; it cannot be chosen separately by result. This sensitivity does not replace the six-question primary analysis, isolate a causal hardware effect, restore missing historic attempts, or validate the T4-fitted vectors on L4 independently. With only five questions it is still severely underpowered. No second GPU replication is planned.

The first original question has correct answer C; its exclusion leaves correct-answer counts A=0, B=4, C=0, D=1. Correct-target A/C strata are undefined; D has one question. Report empty cells and single-question uncertainty plainly. AI-assisted review remains separate from absent independent human validation.

Notebook `07_resume_phase3_l4_pilot.ipynb` records this declaration and its hash in the new setup metadata and snapshots. The original T4 recovery notebook remains historical. Final reporting must disclose both segments and this amendment regardless of results.
