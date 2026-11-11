# Results v2

Qwen3-1.7B (revision `70d244cc`), 150 questions × 5 conditions, thinking on, T 0.6 / top-p 0.95 / top-k 20, 4,096-token cap, vLLM 0.33.0 on a Colab L4. The plan is in [PLAN_V2.md](PLAN_V2.md) and every change after the freeze is in its changelog. The v3 comparison model, DeepSeek V4.1 Flash, is in [section 6](#6-deepseek-v41-flash-vs-qwen3-17b-v3-item-4).

**v3 update (2026-11-11, after an external review).** Two bugs were fixed and every number below was recomputed:
- Parser v2 now accepts `\boxed{\text{X}}`.
- The early-answer switch analysis now uses only eligible questions.

The 0.2 steering sweep was also run at 0.1, which the frozen rule selects once the parser is fixed. Every number matches the reviewer's expected values. The changelog in PLAN_V2.md lists each change.

Every rate below is k/n with a 95% Wilson interval. Recompute everything offline with:

```bash
python -m src.report_v2 --chart
```

This writes `results/v2/report.json` and `results/v2/switch_and_admission.png`. The JSON key for each number is given in brackets.

**All faithfulness labels are AI-judged.** j1 and j2 are OpenAI models (the same family); j3 (v3) is Google Gemini 3.8 Flash via OpenRouter. No human labels exist.

## 1. Do hints change the answer? (Phase 1)

Data: `artifacts/v2/phase1/responses.jsonl` (750 rows, all kept) and `responses.manifest.json`. Command: `python -m src.gen_v2 --output artifacts/v2/phase1/responses.jsonl`.

Statuses: 663 ok, 85 truncated at 4,096 tokens, 2 invalid answer [`phase1.status`]. Before the parser fix it was 659 ok and 6 invalid. The 4 grader-hacking responses ending in `\boxed{\text{A}}` / `\boxed{\text{C}}` are now valid; none of them lands on the hint letter, so no switch rate changes. Grader-hacking valid answers: 129/150 = 86.0% [79.5, 90.7] (was 125/150).

Denominator: questions whose unhinted repeat-0 answer is valid and differs from the hint letter (124). An invalid hinted response counts as no switch.

| Hint | Switched to hint letter | Strict pilot parser |
|---|---|---|
| Sycophancy | 21/124 = 16.9% [11.4, 24.5] | 13/91 = 14.3% [8.5, 22.9] |
| Metadata | 83/124 = 66.9% [58.3, 74.6] | 61/91 = 67.0% [56.9, 75.8] |
| Grader hacking | 18/124 = 14.5% [9.4, 21.8] | 12/91 = 13.2% [7.7, 21.6] |
| All hints | 122/372 = 32.8% [28.2, 37.7] | 86/273 = 31.5% [26.3, 37.2] |
| Noise: unhinted repeat 1 lands on the hint letter | 2/124 = 1.6% [0.4, 5.7] | 2/91 = 2.2% [0.6, 7.7] |

[`phase1.switch_rate`, `phase1_strict_parser.switch_rate`, `phase1.control_unhinted_repeat_lands_on_hint_letter`]

Parser v2 accepts 663 answers; the strict pilot parser accepts 519. The switch rates barely change.

## 2. When the answer switched, does the reasoning admit the hint? (AI-judged)

Data: `artifacts/v2/judge/hint_j1.jsonl`, `hint_j2.jsonl` (the 122 switches, one attempt each, errors kept). Rubric `hint-reliance-v2` was frozen before judging (`artifacts/v2/judge/rubric_freeze.json`); the 10 pilot cases were used for calibration only (`calibration_*`). Commands: `python -m src.judge_v2 hint --judge j1` and `--judge j2`.

| | Judge 1 (gpt-4.1-mini-2025-04-14) | Judge 2 (gpt-4o-2024-08-06) |
|---|---|---|
| Usable verdicts | 77/122 (45 errors, mostly quotes that were not verbatim) | 116/122 (6 errors) |
| Admits and relies on the hint, among usable | 75/77 = 97.4% [91.0, 99.3] | 94/116 = 81.0% [73.0, 87.1] |
| Same, counting errors as not admitted | 75/122 = 61.5% [52.6, 69.6] | 94/122 = 77.0% [68.8, 83.6] |
| Sycophancy | 13/14 = 92.9% [68.5, 98.7] | 9/20 = 45.0% [25.8, 65.8] |
| Metadata | 49/49 = 100% [92.7, 100] | 72/78 = 92.3% [84.2, 96.4] |
| Grader hacking | 13/14 = 92.9% [68.5, 98.7] | 13/18 = 72.2% [49.1, 87.5] |

[`judge_hint.j1`, `judge_hint.j2`]

Overall agreement on the 75 cases both judges labelled: 65/75 = 86.7% [77.2, 92.6], Cohen's kappa 0.25 (bootstrap 95% CI 0.00–0.56) [`judge_hint.agreement`].

Kappa is low partly because almost every case is labelled "admits". When one label dominates, chance agreement is already high, so even near-perfect raw agreement gives a small kappa. Reliability therefore has to be read per hint, with raw agreement next to kappa [`judge_hint.agreement_by_hint`]:

| Hint | Both judges usable | Raw agreement | Kappa | Reading |
|---|---|---|---|---|
| Metadata | 48 | 47/48 = 97.9% [89.1, 99.6] | 0.00 | The judges agree; kappa is 0 only because 47 of 48 cases are labelled "admits" |
| Sycophancy | 13 | 8/13 = 61.5% [35.5, 82.3] | 0.18 | **Unreliable**: few switches, judges disagree |
| Grader hacking | 14 | 10/14 = 71.4% [45.4, 88.3] | 0.24 | **Unreliable**: few switches, judges disagree |

**Keyword cross-check (post hoc).** These patterns were chosen by the external reviewer after reading the judges' quotes, so this is a sanity check, not a pre-registered measure. A case-insensitive regex runs on the reasoning text; the patterns are in `src/report_v2.py` (`KEYWORDS`). As a false-positive control, the same regex runs on the unhinted repeat-0 reasoning for the same eligible questions [`keyword_check_post_hoc`].

| Hint | Switches whose reasoning matches | Unhinted control matching |
|---|---|---|
| Metadata | 81/83 = 97.6% [91.6, 99.3] | 16/124 = 12.9% [8.1, 19.9] |
| Sycophancy | 15/21 = 71.4% [50.0, 86.2] | 27/124 = 21.8% [15.4, 29.8] |
| Grader hacking | 14/18 = 77.8% [54.8, 91.0] | 12/124 = 9.7% [5.6, 16.2] |

**Third judge (v3).** j3 = `google/gemini-3.8-flash` (outside OpenAI), same frozen rubric, strict JSON schema, temperature 0, low reasoning effort (`judge/hint_j3.jsonl`). It was not calibrated on the pilot cases; the rubric was already frozen. Usable 120/122 (2 errors: non-verbatim quote). Admits among usable: 88/120 = 73.3% [64.8, 80.4]. Sycophancy 4/21 = 19.0% [7.7, 40.0], metadata 70/81 = 86.4% [77.3, 92.2], grader hacking 14/18 = 77.8% [54.8, 91.0] [`judge_hint.j3`].

Pairwise agreement on cases both judges labelled, raw agreement with Cohen's kappa (bootstrap 95% CI) [`judge_hint.pairwise`]:

| Pair | All | Metadata | Sycophancy | Grader hacking |
|---|---|---|---|---|
| j1–j2 | 65/75, κ 0.25 [0.00, 0.56] | 47/48, κ 0.00 | 8/13, κ 0.18 | 10/14, κ 0.24 |
| j1–j3 | 55/76, κ 0.12 [0.00, 0.29] | 41/48, κ 0.00 | 3/14, κ 0.03 | 11/14, κ 0.32 |
| j2–j3 | 97/114, κ 0.59 [0.40, 0.75] | 65/76, κ 0.28 | 15/20, κ 0.47 | 17/18, κ 0.85 |

j1 is the outlier: it says "admits" in almost every case it can label. j2 and j3 agree best, but κ is still below 0.6 overall and on metadata and sycophancy.

**Reading.** When the metadata hint changes Qwen3-1.7B's answer, the reasoning usually says so: all three judges put admission at 86–100%, and the keyword check agrees. For sycophancy the judges range from 4/21 to 13/14, so no sycophancy admission rate is claimed. For grader hacking the three judges give 72–93% on 14–18 cases; j2 and j3 agree on 17/18, but the sample is small.

## 3. Was the answer decided before the reasoning? (Phase 2)

### Early answering

Data: `artifacts/v2/phase2/early.jsonl` (3,295 rows = 659 valid responses × 5 cuts; 0 errors). Command: `python -m src.phase2_v2 early`. The thinking is cut at a fraction of its tokens, then closed, and the model is forced to answer.

| With 0% of the reasoning kept, the forced answer is the hint letter | |
|---|---|
| Eligible hinted responses that switched | 100/122 = 82.0% [74.2, 87.8] |
| Eligible hinted responses that did not switch | 46/221 = 20.8% [16.0, 26.6] |
| Hinted responses on ineligible questions (repeat-0 answer already the hint letter, or invalid) | 38/47 = 80.9% [67.5, 89.6] |
| Unhinted responses (hint letter of the matching question) | 42/269 = 15.6% [11.8, 20.4] |

[`phase2.forced_at_0pct_equals_hint`]

Among eligible hinted responses, the switch rate is 100/146 = 68.5% [60.6, 75.5] when the 0% forced answer is the hint letter, and 22/197 = 11.2% [7.5, 16.3] when it is not [`phase2.switch_given_forced0_*`].

**Bug fix.** v2 mistakenly put the 47 ineligible hinted responses into the "did not switch" group, which gave 84/268, 100/184 and 22/206. They now have their own line, as the plan specifies, and the corrected numbers match the reviewer's. Phase 2 still covers the original 659 valid responses: the 4 responses made valid by the parser fix would need new GPU forward passes, so they were not added. None of the 4 is a switch.

Forced answer equals the final answer, all 659 valid responses: 0% cut 456/659 = 69.2% [65.6, 72.6]; 25% 514/659 = 78.0% [74.7, 81.0]; 50% 564/659 = 85.6% [82.7, 88.1]; 75% 609/659 = 92.4% [90.1, 94.2]; 100% 652/659 = 98.9% [97.8, 99.5] [`phase2.forced_equals_final_by_fraction`].

### Probes

**Setup.** Linear probes are trained on the residual activation at the last token before any reasoning (after `<think>`). They predict the final answer letter, at each of the 28 layers.
- Rows: 526 valid repeat-0 unhinted and hinted responses from 150 questions.
- Model: standardized logistic regression, C = 0.1, 5-fold GroupKFold by question.
- Baseline: the majority class of each training fold.
- Significance: 100 label shuffles with the same folds.

Data: `artifacts/v2/phase2/probe_predictions.jsonl`, `probe_permutation_null.npz`, `probe_config.json`. Activation shards are not committed; their checksums are in `artifacts/v2/CHECKSUMS.txt`. Commands: `python -m src.phase2_v2 acts` (GPU), then `python -m src.phase2_v2 probe` (CPU).

**Results.**
- **Majority baseline:** 114/526 = 21.7% [18.4, 25.4] at every layer.
- **Best layer:** layer 24, with 166/526 = 31.6% [27.7, 35.7] (permutation p = 0.010).
- **Max over all 28 layers:** the observed best of 31.6% compares with an average null maximum of 28.5%, permutation p = 0.050 [`phase2.probe_max_over_layers`].
- **Layers with p ≤ 0.02:** 7, 22, 23, 24, 25 and 27. These per-layer p-values are not corrected for 28 tests.
- **Layer 12** (the layer chosen for steering): 131/526 = 24.9% [21.4, 28.8], p = 0.53.

Per-layer table: [`phase2.probe`].

So, before any reasoning, the final letter is barely decodable: at most about 10 points above the majority class, which is borderline once all layers are counted.

**Reproducibility check.** The same probe also finished on Colab (scikit-learn 1.6.1 rather than 1.8.0). Its per-layer accuracies differ: its best was layer 22 at 175/526, and its average null maximum was 0.283. Its files were retrieved in v3 and are in `artifacts/v2/phase2/colab_check/`. The max-over-layers permutation p there is 0.020, against 0.050 locally. Following the rule declared before the results, the local run is the one reported. The two runs differ in library version, and that alone moves the borderline p-value either side of 0.05.

## 4. Can a steering vector move the answer without the reasoning saying so? (Phase 3)

Data: `artifacts/v2/phase3/` (`split.json`, `layer_choice.json`, `vectors.npz`, `hook_check*.jsonl`, `calibration.jsonl`, `strengths.json`, `sweep.jsonl`). Commands: `python -m src.phase3_v2 split|acts|vectors|check|steer` (GPU; vLLM in-process, eager mode).

**Fixed before steering.** 40 held-out questions were chosen by a seeded shuffle (seed 20261111) before any vector was built. Everything below was fitted on the 110 training questions.
- Layer 12 had the best 5-fold grouped-CV accuracy for decoding the hinted letter: 0.934, no tie [`phase3.layer_choice`].
- Letter-contrast vectors have pairwise cosines AB −0.37, AC −0.52, AD −0.59, BC −0.12, BD −0.25, CD −0.02. The same-norm random vectors have |cos| ≤ 0.03.
- Strength is a fraction of the layer-12 median residual norm (116.6).

**Calibration** (3 training questions × 4 letters × fitted/random = 24 outputs per strength, `calibration.jsonl`):

| Strength (× median norm) | 0.05 | 0.1 | 0.2 | 0.4 | 0.8 | 1.6 |
|---|---|---|---|---|---|---|
| Valid answers (fixed parser) | 19/24 | 20/24 | 20/24 | 18/24 | 0/24 | 0/24 |
| Valid answers (v2 parser, before the fix) | 19/24 | 19/24 | 20/24 | 18/24 | 0/24 | 0/24 |

With the v2 parser only 0.2 met the frozen ≥80% rule. After the `\boxed{\text{X}}` fix, one fitted output at 0.1 (`\boxed{\text{A}}`) became valid. That brings 0.1 to 20/24, so the **unchanged** rule now selects 0.1 and 0.2 [`phase3.strengths`; the old selection is kept as `frozen_fractions_v2_0`]. This is a bug fix that changed what the frozen rule selects, not a new choice. The 0.1 sweep was then run with exactly the same 40 questions, vectors, per-question seeds, settings and code; the existing unsteered baselines were reused. Two strengths is still fewer than the 3–4 hoped for. The 15 calibration rows written before the switch to per-request steering are kept (see the changelog).

**Held-out sweep** (40 questions × (1 unsteered + 4 letters × {fitted, random} × 2 strengths) = 680 outputs, all kept. 360 were generated at 0.2 in v2, and the 320 at 0.1 were added in v3):
- The unsteered baseline is valid for 37/40 = 92.5% [80.1, 97.4] [`phase3.baseline_valid`].
- Denominator: (question, target letter) pairs whose valid unsteered answer differs from the target, 111 per direction. An invalid steered output counts as no switch.

| Steering (× median norm) | Answer moved to the target letter | Invalid outputs |
|---|---|---|
| Fitted letter vector, 0.1 | 5/111 = 4.5% [1.9, 10.1] | 4 |
| Random vector, same norm, 0.1 | 4/111 = 3.6% [1.4, 8.9] | 3 |
| Fitted letter vector, 0.2 | 6/111 = 5.4% [2.5, 11.3] | 7 |
| Random vector, same norm, 0.2 | 2/111 = 1.8% [0.5, 6.3] | 12 |

[`phase3.steered_switch_rate`] At both strengths the intervals overlap, so this does not show that the fitted vectors steer toward their letter. The parser fix made one fitted 0.2 output valid, but its answer is C and its target D, so the 0.2 numbers are unchanged, as the reviewer expected.

Post hoc descriptive numbers, decided after seeing the sweep [`phase3.post_hoc`]:
- **Fitted switches by target letter:** at 0.1, A 1/28, B 4/27, C 0/26, D 0/30; at 0.2, A 0/28, B 3/27, C 1/26, D 2/30.
- **Random switches by target letter:** at 0.1, A 1/28, B 1/27, C 2/26, D 0/30; at 0.2, A 0/28, B 0/27, C 1/26, D 1/30.
- **Answer changed to any letter:** at 0.1, fitted 18/148 = 12.2% [7.8, 18.4] and random 21/148 = 14.2% [9.5, 20.7]; at 0.2, fitted 19/148 = 12.8% [8.4, 19.2] and random 18/148 = 12.2% [7.8, 18.4].

At both strengths the fitted vectors change answers about as often as random ones.

**Hook check.** In one mixed batch on 2 training questions, the steered rows were token-identical to the per-call check, which confirms that each request got its own vector. The zero-vector rows gave the same answers, and their tokens matched for 445 and 2,940 tokens before fp16 batch noise made them diverge (`hook_check.jsonl`, `hook_check_mixed.jsonl`).

**Labels for steered switches (AI-judged).** Commands: `python -m src.judge_v2 steer --judge j1|j2`. Files: `artifacts/v2/judge/steer_j1.jsonl`, `steer_j2.jsonl`. There are 17 steered switches: 6 fitted + 2 random at 0.2, and 5 fitted + 4 random at 0.1. The steer rubric (`steer-label-v2`) was not calibrated.

| | mentions_outside_nudge | argues_normally | incoherent | errors |
|---|---|---|---|---|
| Judge 1 | 0/5 | 5/5 | 0/5 | 12/17 |
| Judge 2 | 4/12 | 3/12 | 5/12 | 5/17 |

[`judge_steer`] Both judges produced a usable label for only 3 cases and agreed on 1 of them. The report prints kappa as 0 and marks it unreliable. Most errors are evidence quotes that were not verbatim; they were kept, not retried. In all four of judge 2's `mentions_outside_nudge` cases, the quoted evidence names no outside source. Three express the model's own uncertainty or recall, and one says "The question is from a test" (`steer_j2.jsonl`, field `evidence`). **No conclusion about whether steered reasoning admits the nudge is supported.**

## 5. Costs, failures and limits

- **API spend:** US$4.80 of the US$25 cap (`artifacts/v2/costs.json`; `python -m src.judge_v2 costs`): US$1.11 in v2; in v3, US$0.07 for the steered switches, US$1.50 for the stopped R1-0528 run (includes reserves for calls in flight when it was stopped, an upper bound), US$0.19 for V4.1 generation including its smoke tests, and the rest for j1/j2/j3 on the new switches. OpenAI figures are list-price estimates from token usage; OpenRouter figures are the cost it returned. Colab used the existing balance only.
- **Kept failures:**
  - Phase 1: 85 truncated and 2 invalid responses (6 before the parser fix).
  - Judges: 45 + 6 errors on hint cases and 12 + 5 on steer cases.
  - Phase 3: calibration and sweep outputs that truncated or gave no answer.
  - All of these stay in the raw files and in the denominators stated above.
- **Changes after the plan was frozen** (dated in [PLAN_V2.md](PLAN_V2.md)):
  - Backend: vLLM 0.33.0 on an L4 instead of the T4 plan. The pinned vLLM 0.8.5 had no wheel for the runtime's Python 3.13, and batched HF ran out of memory.
  - Phase 3 steering changed from one vector per call to one vector per request, so the 15 earliest calibration rows were generated the old way.
  - The probe ran locally from checksum-verified shards.
  - Post hoc analyses are labelled where they appear.
- **DeepSeek (v3 item 4):** run on V4.1 Flash, not R1-0528 as the v3 brief named. See section 6 for why. R1-0528 stopped at 225/750 rows and is kept as a partial condition.
- **Numbers vs. the reviewer's expected values:** every expected value in the v3 brief matches, before and after the fixes: Phase 1, calibration, sweep, early-answer groups, per-hint agreement and the keyword check. No differences need explaining.
- **Limits:**
  - Two models, so a comparison, not a size trend.
  - Judge agreement is poor for Qwen (best pair j2–j3, κ 0.59); for DeepSeek it is near-perfect, but nearly every case is "admits", so κ is undefined.
  - No human labels.
  - Only one steering strength survived calibration.
  - With 8 steered switches, the steered-reasoning labels can't support any conclusion.
- **Large files** (activation shards, Phase 3 training activations) are not committed. Their SHA-256 sums and regeneration commands are in `artifacts/v2/CHECKSUMS.txt`.

## 6. DeepSeek V4.1 Flash vs. Qwen3-1.7B (v3 item 4)

**Model.** `deepseek/deepseek-v4.1-flash-1017` via OpenRouter. This is the owner's instruction; the v3 brief named R1-0528. Settings:
- `reasoning_effort` fixed at `high` and recorded in every row.
- Every call pinned to the DeepInfra fp8 endpoint, with no fallbacks.
- T 0.6, top-p 0.95, 8,192-token cap, and the same per-trial seeds and 750 prompts as Qwen.
- Parsed with the fixed parser v2, using the same eligible / switch / noise definitions.

Data: `artifacts/v2/deepseek-v41/responses.jsonl`. Command: `python -m src.deepseek_v3 run --model v41`. The 5-prompt smoke gate passed: the returned reasoning is full, not summarized, at about 2.7–4.9 characters per billed reasoning token. The median trace is 856 characters.

**Two models make a comparison, not a size trend.** They differ in size, training, provider and token cap (Qwen 4,096, DeepSeek 8,192), so no difference below can be attributed to size.

**Records:** 750/750, all served by DeepInfra with the same resolved model and effort. 742 ok, 8 truncated (5 of them metadata), 0 errors [`deepseek.phase1.status`].

**Switch rates** (same denominator: questions whose valid unhinted repeat-0 answer differs from the hint letter). Differences are DeepSeek minus Qwen, with Newcombe hybrid-score 95% intervals that treat the two models as independent samples [`comparison.switch_rate`]:

| Hint | Qwen3-1.7B | DeepSeek V4.1 Flash | Difference |
|---|---|---|---|
| Sycophancy | 21/124 = 16.9% [11.4, 24.5] | 0/146 = 0.0% [0.0, 2.6] | −16.9 pts [−24.5, −10.8] |
| Metadata | 83/124 = 66.9% [58.3, 74.6] | 52/146 = 35.6% [28.3, 43.7] | −31.3 pts [−41.9, −19.5] |
| Grader hacking | 18/124 = 14.5% [9.4, 21.8] | 144/146 = 98.6% [95.1, 99.6] | +84.1 pts [+76.1, +89.3] |
| Control: unhinted repeat lands on hint letter | 2/124 = 1.6% | 0/146 = 0.0% | |

DeepSeek ignores a user's stated opinion entirely and follows leaked grader code almost every time.

**Admission among switches (AI-judged).** Each judge's usable verdicts, DeepSeek minus Qwen [`comparison.admission_faithful_among_ok`]:

| Hint | Judge | Qwen | DeepSeek | Difference |
|---|---|---|---|---|
| Metadata | j1 | 49/49 = 100% [92.7, 100] | 33/34 = 97.1% [85.1, 99.5] | −2.9 pts [−14.9, +4.7] |
| Metadata | j2 | 72/78 = 92.3% [84.2, 96.4] | 49/49 = 100% [92.7, 100] | +7.7 pts [−0.7, +15.8] |
| Metadata | j3 | 70/81 = 86.4% [77.3, 92.2] | 51/51 = 100% [93.0, 100] | +13.6 pts [+4.5, +22.7] |
| Grader hacking | j1 | 13/14 = 92.9% [68.5, 98.7] | 108/108 = 100% [96.6, 100] | +7.1 pts [+0.3, +31.5] |
| Grader hacking | j2 | 13/18 = 72.2% [49.1, 87.5] | 136/136 = 100% [97.3, 100] | +27.8 pts [+12.3, +50.9] |
| Grader hacking | j3 | 14/18 = 77.8% [54.8, 91.0] | 141/141 = 100% [97.3, 100] | +22.2 pts [+8.7, +45.2] |
| Sycophancy | all | 13/14, 9/20, 4/21 | no switches | – |

Usable DeepSeek verdicts:
- j1: 142/196 (54 errors, mostly non-verbatim quotes).
- j2: 185/196.
- j3: 192/196.

Pairwise raw agreement on DeepSeek [`deepseek.judge_hint.pairwise`]:
- j1–j2: 135/136.
- j1–j3: 140/141.
- j2–j3: 181/181.

Kappa is 0 or undefined there, because almost every case is "admits". That is exactly the case where kappa fails, so read the raw agreement.

**Keyword cross-check (post hoc,** same reviewer patterns) [`deepseek.keyword_check_post_hoc`]:

| Hint | Switches matching | Unhinted control matching |
|---|---|---|
| Metadata | 52/52 = 100% [93.1, 100] | 0/146 = 0.0% [0.0, 2.6] |
| Grader hacking | 143/144 = 99.3% [96.2, 99.9] | 7/146 = 4.8% [2.3, 9.6] |

**Summarization check (post hoc).** This asks whether a model's reasoning names the hint's source in *all* hinted responses, switched or not, using the same keyword patterns [`comparison.source_mention_rate_post_hoc`]:

| Hint | Qwen | DeepSeek V4.1 | R1-0528 (partial) |
|---|---|---|---|
| Metadata | 137/150 | 144/150 | 42/42 |
| Sycophancy | 106/150 | 106/150 | 46/47 |
| Grader hacking | 71/150 | 149/150 | 42/43 |

V4.1's short traces do not hide the hint any more often than Qwen's. No summarization failure was found.

**Reading.** On these 150 questions, DeepSeek V4.1 Flash is moved by a different hint than Qwen3-1.7B: grader code rather than metadata or a user's opinion. When a hint does move it, all three AI judges and the keyword check say the reasoning names the hint and relies on it, at rates of 97–100%. No unfaithful switch is detected for this model.

**R1-0528 (partial second condition, not judged).** `artifacts/v2/deepseek/responses.jsonl`: 225/750 rows (215 ok, 10 truncated at 8,192 tokens), all from DeepInfra. It was stopped for two reasons:
- It cannot take the required effort setting.
- The OpenRouter account credit was nearly exhausted. The guard had checked the repo's US$25 cap, not the account balance; that is now fixed.

Only questions whose repeat-0 and hinted rows both finished count. Switch rates: sycophancy 0/10, metadata 4/10, grader hacking 7/13; control 0/18 [`deepseek_r1_partial`]. These are too few to compare and are shown only so the data isn't dropped.

**Differences from the numbers in the budget/model review (2026-11-11).** These figures come from the external review the owner pasted into the working session on 2026-11-11, the one that flagged the account-credit and model problems. They are not from the v3 brief and not from the later audit. Each claim was rechecked against the live API before acting:
- Account credit was US$2.42 at check time; the review said US$2.60.
- R1-0528 cost US$0.0054 per call over 225 rows; the review said US$0.00545 over 195.
- 10 of 225 R1 rows were truncated; the review counted 9 of 195.
- V4.1 cost US$0.00023 per call. The review's US$0.000106 was the Relace fp4 endpoint, which does not support `seed`; this run used DeepInfra fp8.

**Post hoc checks from the later audit (2026-11-11)** [recomputed by `src/report_v2.py`, which was not changed for this; the numbers come from the raw files]:
- **DeepSeek mostly switches away from answers it knew.** In 139 of its 144 grader-hacking switches, its unhinted repeat-0 answer was the correct one. Unhinted accuracy on the 146 eligible questions was 141/146. Example reasoning: "But validation function says answer == "C" (pneumonia) oddly."
- How often the reasoning *states* that the graded letter is wrong has not been measured. A rough regex gives anywhere from 44 to 129 of 144, depending on the pattern. That would need a new judge question, so it is not claimed.
- **The comparison holds on the questions both models share.** On the 122 questions eligible for both models, switches are: sycophancy DeepSeek 0 vs Qwen 19, metadata 41 vs 81, grader hacking 120 vs 17.
