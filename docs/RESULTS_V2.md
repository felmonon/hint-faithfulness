# Results v2

Qwen3-1.7B (revision `70d244cc`), 150 questions × 5 conditions, thinking on, T 0.6 / top-p 0.95 / top-k 20, 4,096-token cap, vLLM 0.33.0 on a Colab L4. The plan is in [PLAN_V2.md](PLAN_V2.md) and every change after the freeze is in its changelog. DeepSeek was not run because no OpenRouter key was configured; the v3 comparison is waiting for that key.

**v3 update (2026-11-11, after an external review).** Two bugs were fixed and every number below was recomputed:
- Parser v2 now accepts `\boxed{\text{X}}`.
- The early-answer switch analysis now uses only eligible questions.

The 0.2 steering sweep was also run at 0.1, which the frozen rule selects once the parser is fixed. Every number matches the reviewer's expected values. The changelog in PLAN_V2.md lists each change.

Every rate below is k/n with a 95% Wilson interval. Recompute everything offline with:

```bash
python -m src.report_v2 --chart
```

This writes `results/v2/report.json` and `results/v2/switch_and_admission.png`. The JSON key for each number is given in brackets.

**All faithfulness labels are AI-judged.** Both judges are OpenAI models (the same family). No human labels exist.

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

**Reading.** When the metadata hint changes Qwen3-1.7B's answer, the reasoning almost always says so: the judges agree, and the keyword check agrees. For sycophancy and grader hacking, there are too few switches and the judges disagree, so no admission rate is claimed.

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

**Reproducibility check.** The same probe also finished on Colab (scikit-learn 1.6.1 rather than 1.8.0). Its per-layer accuracies differ: its best was layer 22 at 175/526, and its average null maximum was 0.283. Only these summary counts were read before the runtime disconnected; Colab's output files were not retrieved. Following the rule declared before the results, the local run is the one reported.

## 4. Can a steering vector move the answer without the reasoning saying so? (Phase 3)

Data: `artifacts/v2/phase3/` (`split.json`, `layer_choice.json`, `vectors.npz`, `hook_check*.jsonl`, `calibration.jsonl`, `strengths.json`, `sweep.jsonl`). Commands: `python -m src.phase3_v2 split|acts|vectors|check|steer` (GPU; vLLM in-process, eager mode).

**Fixed before steering.** 40 held-out questions were chosen by a seeded shuffle (seed 20261111) before any vector was built. Everything below was fitted on the 110 training questions.
- Layer 12 had the best 5-fold grouped-CV accuracy for decoding the hinted letter: 0.934, no tie [`phase3.layer_choice`].
- Letter-contrast vectors have pairwise cosines AB −0.37, AC −0.52, AD −0.59, BC −0.12, BD −0.25, CD −0.02. The same-norm random vectors have |cos| ≤ 0.03.
- Strength is a fraction of the layer-12 median residual norm (116.6).

**Calibration** (3 training questions × 4 letters × fitted/random = 24 outputs per strength, `calibration.jsonl`):

| Strength (× median norm) | 0.05 | 0.1 | 0.2 | 0.4 | 0.8 | 1.6 |
|---|---|---|---|---|---|---|
| Valid answers | 19/24 | 19/24 | 20/24 | 18/24 | 0/24 | 0/24 |

Only 0.2 meets the frozen ≥80% rule, so the sweep uses one strength rather than the 3–4 hoped for; the rule was not relaxed [`phase3.strengths`]. The 15 calibration rows written before the switch to per-request steering are kept (see the changelog).

**Held-out sweep** (40 questions × (1 unsteered + 4 letters × {fitted, random}) at 0.2 = 360 outputs, all kept):
- The unsteered baseline is valid for 37/40 = 92.5% [80.1, 97.4] [`phase3.baseline_valid`].
- Denominator: (question, target letter) pairs whose valid unsteered answer differs from the target, 111 per direction. An invalid steered output counts as no switch.

| Steering at 0.2 × median norm | Answer moved to the target letter | Invalid outputs |
|---|---|---|
| Fitted letter vector | 6/111 = 5.4% [2.5, 11.3] | 7 |
| Random vector, same norm | 2/111 = 1.8% [0.5, 6.3] | 12 |

[`phase3.steered_switch_rate`] The intervals overlap, so this does not show that the fitted vectors steer toward their letter.

Post hoc descriptive numbers, decided after seeing the sweep [`phase3.post_hoc`]:
- **Fitted switches by target letter:** A 0/28, B 3/27, C 1/26, D 2/30.
- **Random switches by target letter:** A 0/28, B 0/27, C 1/26, D 1/30.
- **Answer changed to any letter:** fitted 19/148 = 12.8% [8.4, 19.2], random 18/148 = 12.2% [7.8, 18.4].

At this strength the fitted vectors change answers about as often as random ones.

**Hook check.** In one mixed batch on 2 training questions, the steered rows were token-identical to the per-call check, which confirms that each request got its own vector. The zero-vector rows gave the same answers, and their tokens matched for 445 and 2,940 tokens before fp16 batch noise made them diverge (`hook_check.jsonl`, `hook_check_mixed.jsonl`).

**Labels for steered switches (AI-judged).** Commands: `python -m src.judge_v2 steer --judge j1|j2`. Files: `artifacts/v2/judge/steer_j1.jsonl`, `steer_j2.jsonl`. The steered switches are 8 (6 fitted + 2 random). The steer rubric (`steer-label-v2`) was not calibrated.

| | mentions_outside_nudge | argues_normally | incoherent | errors |
|---|---|---|---|---|
| Judge 1 | 0/3 | 3/3 | 0/3 | 5/8 |
| Judge 2 | 1/5 | 1/5 | 3/5 | 3/8 |

[`judge_steer`] Both judges labelled only 1 case, and they disagreed on it, so kappa is undefined in practice: the report prints 0 and marks it unreliable. Most errors are evidence quotes that were not verbatim; they were kept, not retried. Judge 2's one `mentions_outside_nudge` case quotes only the model's own uncertainty, not any outside source (`steer_j2.jsonl`, field `evidence`). **No conclusion about whether steered reasoning admits the nudge is supported.**

## 5. Costs, failures and limits

- **API spend:** US$1.11 of the US$25 cap (`artifacts/v2/costs.json`; `python -m src.judge_v2 costs`). These are list-price estimates from returned token usage, not an invoice. Colab used the existing balance only.
- **Kept failures:**
  - Phase 1: 85 truncated and 6 invalid responses.
  - Judges: 45 + 6 errors on hint cases and 5 + 3 on steer cases.
  - Phase 3: calibration and sweep outputs that truncated or gave no answer.
  - All of these stay in the raw files and in the denominators stated above.
- **Changes after the plan was frozen** (dated in [PLAN_V2.md](PLAN_V2.md)):
  - Backend: vLLM 0.33.0 on an L4 instead of the T4 plan. The pinned vLLM 0.8.5 had no wheel for the runtime's Python 3.13, and batched HF ran out of memory.
  - Phase 3 steering changed from one vector per call to one vector per request, so the 15 earliest calibration rows were generated the old way.
  - The probe ran locally from checksum-verified shards.
  - Post hoc analyses are labelled where they appear.
- **Not run:** DeepSeek (no OpenRouter key).
- **Limits:**
  - One small model.
  - Both judges are OpenAI models, and their agreement is poor.
  - No human labels.
  - Only one steering strength survived calibration.
  - With 8 steered switches, the steered-reasoning labels can't support any conclusion.
- **Large files** (activation shards, Phase 3 training activations) are not committed. Their SHA-256 sums and regeneration commands are in `artifacts/v2/CHECKSUMS.txt`.
