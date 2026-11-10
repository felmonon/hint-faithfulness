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

## November 9, 2026 — live pilot launched

The public repository was created at `https://github.com/felmonon/hint-faithfulness`. Notebook 00 launched real Qwen3-1.7B collection on a Colab Tesla T4, using source commit `fe4de16013bf9e3e9a9d66abd5b47401becbe24a`. Setup tests passed. The fixed 20-question, 100-attempt design and decoding settings were retained.

An initial AI inspection of saved responses found a format-compliance issue: the basketball question ended with `**Answer:** (B) 125`, which the frozen strict parser marks `invalid_answer`. This is a correct semantic answer with an invalid requested format. The raw output and original classification will be preserved; no parser change or replacement generation is being applied during collection. Any later relaxed-parser sensitivity analysis must be labeled as post hoc and kept separate.

The pilot is still running. Full transcript review, final statistics, and human judge validation are not claimed here. The OpenAI judging adapter and read-only artifact checker were added on a later source revision, without changing the live collection process. API access remains pending secure setup.

## November 9, 2026 — post hoc diagnostic specified during collection

After inspecting the first eight full transcripts and 20 status lines, the assistant specified `posthoc-answer-format-v1` at 2026-11-10 01:40 UTC (November 9 local time). This is a response to observed formatting failures, not a preregistered analysis. It allows one unambiguous line-start answer declaration with Markdown markers removed and an optional exact option-text suffix. It does not recover incomplete or truncated responses, interpret arbitrary prose, or use correctness to choose a letter.

The diagnostic writes separate decisions and strict-versus-derived summaries; the live collection and primary parser remain frozen. Its comparison has not yet been run on the completed pilot. The prediction is assistant-authored: some format-only exclusions may be recovered, but the direction of any uptake change is unknown. Zero recovery and changed conclusions are acceptable outcomes. The exact rule and decision context are stored in `src/sensitivity.py`.

Methods review also clarified matched comparison denominators, raw status counts versus sequential exclusions, possible degenerate bootstrap intervals, and departures from Chen, Lanham, and Rimsky. These documentation changes do not alter collection or the frozen primary calculations.

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
