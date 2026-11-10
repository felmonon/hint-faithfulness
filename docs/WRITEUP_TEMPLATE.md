# Does the model say what changed its answer?

**Working template — no findings yet. Do not publish as completed research.**

Target approximately 1,200 words once results exist. Attribute AI-assisted implementation and keep the frozen data, model revisions, prompts, and analysis available.

## The question (150 words)

Explain why a plausible reasoning trace might omit an external influence. Describe the narrow operational question: does the exposed reasoning acknowledge reliance on a wrong-answer hint when the final answer changes toward it? Avoid treating this as a test of consciousness or intentional deception.

## Method in five sentences (150 words)

We sampled [N] questions from [dataset revision], balancing [subjects]. We tested [exact model IDs, revisions, providers] with two unhinted runs and three hints pointing to the same preassigned wrong answer. We measured hint uptake against [overall and directional controls], reporting [missingness]. We judged acknowledgment and reliance using [judge ID and rubric], with [held-out N, agreement, confusion matrix] against human labels. We estimated [interval method] and additionally tested [early answering/probes, only if actually completed].

## Main chart and result (250 words)

Insert the real chart from `results/phase1/`, never the synthetic demonstration. State each numerator and denominator. Explain whether uptake exceeds spontaneous movement toward the same wrong letter. Report the faithfulness rate only if judge validation and coverage pass. Report low uptake or undefined faithfulness directly.

## Three complete, auditable examples (250 words)

Choose genuine switched traces after reading all outputs. Give question/record IDs, baseline and hinted letters, the hint, and the relevant exact excerpts. Explain the label using the frozen rubric. If fewer than three supported unacknowledged switches exist, say so rather than substituting fictional examples.

Example 1: pending.

Example 2: pending.

Example 3: pending.

## What the internal tests add (150 words)

If Phase 2 ran, report early-answer agreement at 0% and 100%, probe controls, and wrong-answer/resisted-hint sample sizes. Separate decodable information from causal use. If it did not run, remove this section and describe it as future work.

## Limitations and next experiment (250 words)

Discuss sampling and benchmark contamination, model-family confounds, incomplete outputs, label balance, judge error, and changes from Chen/Lanham. State exactly which conclusions the data support. Choose one fixed follow-up experiment and predict its result before running it. A null result is acceptable.

## Publication checklist

- [ ] Real runs and raw transcripts saved and reviewed.
- [ ] Human labels actually entered; held-out judge validation documented.
- [ ] Chart denominators, error bars, missingness and limitations checked.
- [ ] Three examples verified against raw outputs, or fewer clearly disclosed.
- [ ] No credentials or unrelated private data included.
- [ ] Final text reviewed before posting to any public account.
