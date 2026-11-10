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

## November 9, 2026 — raw-record discrepancy during collection

A direct Colab terminal check found 23 saved rows while the progress log recorded 33 completed attempts. Missing original ordinals are 9–16 and 25–26. This coincides with live raw-file editor access; the cause remains unproven, and no deliberate raw-data edits were made. The editor was closed, and timestamped copies of the partial raw data, log, and discrepancy audit were saved before recovery.

The [fixed recovery protocol](docs/RECOVERY_PROTOCOL.md) was recorded at 2026-11-10 01:57 UTC before replaying any missing slot. Original retained data will remain immutable and supply the primary descriptive estimates. A separately named composite will regenerate only the fixed missing IDs with the original settings and seeds. Total attempts and lineage must be reported; replayed text must not be represented as the lost original text. No retained invalid or truncated output will be replaced.

## November 9, 2026 — completed collection, recovery, and evidence review

UTC timestamps extend into November 10. The original pass ran from 01:14:19 to 03:03:23 UTC: 100 logged generation attempts, 90 retained records. Recovery preparation at 03:04:36 UTC verified the fixed ten missing IDs, original files, source, and settings. Ten new executions finished at 03:17:41 UTC. Finalization verified exactly 90 unchanged originals plus ten new records, for 110 attempts and 100 retained trial slots. These replacements are a recovery sensitivity dataset, not recovered original text or independent replication.

Colab's normal browser download failed, including a user attempt. An alternate data-URL download was blocked by browser policy and was not retried. The evidence was instead recorded as a structured notebook output and saved using Colab's normal Copy to Drive function, then retrieved through the authenticated Drive connector. The first text export normalized carriage returns in the recovery log; its checksum mismatch was detected before that log was accepted. The final byte-preserving UTF-8 export verified all 13 files against hashes computed in Colab. The raw model responses matched on both exports and were never changed. See `artifacts/pilot-20-qwen3-1.7b/export-provenance.json`.

Four assistant review partitions read all 100 retained prompts, reasoning texts, and final responses before interpreting the rates. The [AI review manifest](results/pilot-20-v1/ai-review/coverage.json) records coverage and source hashes. This was unblinded AI review, with zero human labels. Observed problems include repetitive factual errors, disagreement between the end of reasoning and the final answer, 21 original strict-format exclusions, three original token-cap truncations, and duplicated A/B option text in `mmlu-test-90b259b07aa70826`. The malformed anatomy stem and duplicated options were retained as supplied. Missing original traces cannot be reviewed.

Original status census: 66 `ok`, 21 `invalid_answer`, 3 `truncated`, and ten lost slots. Composite status census: 73 `ok`, 24 `invalid_answer`, 3 `truncated`. The original artifact audit fails only missing record/coverage checks; the composite audit passes. Original token and checksum checks pass. The verified lineage is essential to interpreting that composite pass.

Strict original uptake is sycophancy 2/7, metadata 5/7, and grader hacking 1/6. Strict composite uptake is 2/10, 7/10, and 1/8 respectively. These all-pair rates are not directly subtracted from directional noise: matched original uptake is 2/6, 4/6, and 1/5, compared with target-switch noise 0/6, 0/6, and 0/5. Full uncertainty and composite comparisons are in the [report](docs/PILOT_REPORT.md). Small denominators, shared questions, nonrandom storage loss, and formatting exclusions restrict interpretation.

The previously specified post hoc format rule recovered 15 original and 18 composite answer formats in derived copies. Original uptake then becomes 2/11, 6/11, 1/10; composite uptake becomes 2/15, 8/14, 1/13. This confirms material sensitivity to parsing eligibility, not a correction of the primary dataset.

The first original plot failed because a zero-success Wilson bound rounded slightly above zero. Commit `9b4d3636fd24a5a981adb69a512503c9af279cd5` clamps only displayed error-bar lengths; the numerical original summary remained byte-identical. A regression checks zero and all-success endpoints without altering its input statistics. All 80 software tests passed. This fixes rendering only, with no collection, parser, or inferential formula changes.

Eight original switches and two additional composite cases were exported as blank human-review forms. No machine verdicts or human labels exist; ten cases are insufficient for the stated minimum 30 held-out labels. The secure key destination prompt returned `not_approved`/`decline`, so no key was created or saved. This workflow made zero OpenAI API calls and purchased no Colab compute. Human validation and further experiments remain pending. The published result is a documented exploratory pilot, not a validated measure of model honesty.

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

## November 9 local / November 10 UTC — secure key and real OpenAI judge

The native secure destination confirmation succeeded after the earlier confirmation-flow failures. One new key was created and saved only to the approved private, ignored `.env.local`; no value was printed or committed. Frozen judge plan and runner commit `03153e7` preceded requests. Five original cases were inspected, followed by the remaining three originals and two additional composite-eligible cases, reusing the shared eight verdicts. One exact-quotation failure was retried once with unchanged model, rubric, settings, output file, and budget after preserving the initial snapshot and recording the retry decision. It failed again and remains unscored. Eleven completed API requests returned 17,908 input and 1,006 output tokens; the conservative usage estimate is $0.0087728, not an invoice. Nine verdicts passed structural/evidence checks; unblinded AI audit found interpretive concerns, including a likely final-check error. No human labels or corrected favorable rate were manufactured. See [the judge report](docs/OPENAI_JUDGE_REPORT.md).

## November 10 UTC — Phase 2 and Phase 3 pilot extensions

The user authorized autonomous completion through Phase 3. Scope was stated as the same 20-question exploratory pilot; the full 150-question/two-model study remains separate. AI assistance is not human validation. The Phase 2 prediction and selection/split rules were frozen in commit `66788e3` before execution. Original strict cohort:54 records, 10 unhinted + 8 hinted-switch traces; composite strict cohort:61 records, 14 + 10 traces. Both probes hold out six questions. All four jobs completed on the real pinned Qwen weights by 04:08:34 UTC. Byte-preserving base64 notebook export saved 22 files; local hashes and20 in-run checksum entries verified. Raw probability/activation data and original parser exclusions are preserved.

Phase 3 adaptations were specified before its measurements: all 20 verified prompt pairs regardless of Phase 1 completion format, a target-stratified 14/6 question split, 198 generations, strengths 0/1/2/4/8, middle block 14, and norm-matched random controls. This avoids filtering prompt vectors by whether a separate sampled completion followed the final-answer format. The split uses assigned target letters, not steering outcomes. Source commit `ef90362` contains the frozen plan and runner. It launched at 04:12 UTC on the same T4. Code/runtime provenance and exact prompt verification are retained; no success claim is made while it runs.

## November 10, 09:54 UTC — Phase 3 checkpoint and Colab usage-limit block

Monitoring was interrupted during an approval/download wait, approximately 04:34–09:40 UTC. Reconnection found the earlier runtime disk unavailable; the cause and exact termination time were not independently established. The [checkpoint captured at 04:28:37 UTC](artifacts/pilot-20-phase3-checkpoint-0430/) preserves seven hash-verified payload files and eight complete JSONL records, the latest finishing at 04:25:26 UTC. These cover only the beginning of one question's condition grid. Unexported attempts after that checkpoint are unknown.

Colab now displays “Cannot connect to GPU backend” and states that GPU access is unavailable because of usage limits. **Phase 3 continuation is blocked, not running.** Of the 198 fixed grid positions, eight have preserved outcomes and 190 remain without archived outcomes. This does not establish the historical number of generation attempts; an eventual completed recovery may exceed 198 physical attempts and must be described as retained grid outcomes rather than an uninterrupted run.

The [resume protocol](docs/PHASE3_RESUME_PROTOCOL.md), frozen before any resumed generation, requires the original eight rows, source, manifest, and fitted vector bytes to remain unchanged, with fresh runtime provenance and durable checkpoints for continuation. No new steering findings, explanation labels, or human-validation claims follow from the checkpoint. The existing Phase 1, OpenAI judge, and Phase 2 results remain separately documented.

Local verification reran `python3.12 -m unittest discover -s tests -q`: all **97 tests passed**, including seven new offline Phase 3 analyzer tests. This is software evidence using test fixtures, not additional experimental generations or a completed steering result. The previously recorded 90-test GitHub CI result remains a separate historical check.
