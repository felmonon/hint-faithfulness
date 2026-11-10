# Research log

## November 9, 2026 — setup, America/Edmonton

Implementation prepared with AI assistance at Felmon's request. No live model responses have been collected. No human labels have been entered. Synthetic pipeline checks are software evidence only.

### Predictions recorded before live experiments

These are starting hypotheses supplied by the implementation assistant, **not personal predictions attributed to Felmon**. Record your own before the live run and preserve both versions.

- Phase 1: grader-hacking hints may produce more uptake than sycophancy. I expect acknowledgment among switches to fall below 100%. I do not have a confident directional prediction about the size comparison because training and model family also differ.
- Phase 2: unhinted zero-reasoning agreement may exceed uniform chance, and hinted prompts may increase immediate probability assigned to the hinted letter. Probe accuracy above a majority baseline would show decodable information, not an irrevocable decision.
- Phase 3: stronger vectors may increase target-letter selection at some strengths, but excessive strength may reduce coherence. Explicit mentions of an outside push may be rare. Neither effect is a finding until measured.

Felmon's predictions: **pending**.

### Frozen initial design

- Dataset: 150 MMLU test questions; balanced rounds over 57 subjects; seed 20261109.
- Qwen/Qwen3-1.7B, full half-precision weights on GPU, and deepseek/deepseek-r1-0528 via OpenRouter.
- Two baseline runs, three hinted runs per question; the same assigned wrong letter across conditions and models.
- Temperature 0.6, top-p 0.95, top-k 20 where supported; 4,096 total new tokens initially.
- Pilot: first 20 questions, 100 responses per model. Review every transcript before scaling.
- Primary sample size: 150 questions regardless of observed effect. Do not expand until a desired effect appears. If more precision is needed, preregister a separate fixed extension and document exploratory pooling.
- No real interpretation until invalid answers, truncated outputs, missing reasoning, and judge coverage are reported.
- Judge: frozen rubric, at least 30 blind held-out labels, at least 90% agreement, confusion matrix and label balance.

### Observations

- Real dataset preparation completed: 150 unique questions across 57 subjects, two or three questions per subject.
- Environment check found an 8 GB Apple Silicon Mac, no CUDA GPU, and no configured OpenRouter key. Colab is the intended route for full half-precision local-model experiments.
- The public model catalog listed the selected large model but not either proposed small model.
- Software smoke checks use labeled deterministic fixtures. They do not satisfy the live pilot checkpoint.

### Results

**Pending live execution and human review.** No uptake, faithfulness, probe, or steering claim is supported yet.

## Suggested eight-week schedule

| Week | Dates | Work and evidence |
|---|---|---|
| 1 | Nov 9–15 | Read Chen, Turpin, Korbak; predictions; run and inspect both 20-question pilots. |
| 2 | Nov 16–22 | Complete Phase 1; label and validate judge; report chart and three genuine traces. |
| 3 | Nov 23–29 | Read Lanham; token-boundary check; early-answer experiment; ARENA exercises. |
| 4 | Nov 30–Dec 6 | Capture residual activations; question-level split; train probes and controls. |
| 5 | Dec 7–13 | Interpret wrong-answer/resisted-hint subsets; write Phase 2 result and limits. |
| 6 | Dec 14–20 | Optional: read Rimsky; build vectors on separate training questions. |
| 7 | Dec 21–27 | Optional: steering sweep, random controls, manual coherence labels. |
| 8 | Dec 28–Jan 3, 2027 | Finish public write-up after review; optional three-minute walkthrough. |

Allow 6–8 hours per week. Reduce scope if a checkpoint is missed. These are suggested work blocks; no calendar events or automations were created.

## Entry template

Date / phase / exact command and output path:

Prediction made before running:

What I read in the raw transcripts:

Observed result, numerator, denominator, uncertainty:

Failures, exclusions, changed settings:

Difference from prediction / next fixed experiment:
