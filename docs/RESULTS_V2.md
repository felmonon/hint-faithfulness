# Results v2

Qwen3-1.7B (revision `70d244cc`), 150 questions × 5 conditions, thinking on, T 0.6 / top-p 0.95 / top-k 20, 4,096-token cap, vLLM 0.33.0 on a Colab L4. The plan is in [PLAN_V2.md](PLAN_V2.md) and every change after the freeze is in its changelog. DeepSeek was not run because no OpenRouter key was configured.

Every rate below is k/n with a 95% Wilson interval. Recompute everything offline with:

```bash
python -m src.report_v2 --chart
```

This writes `results/v2/report.json` and `results/v2/switch_and_admission.png`. The JSON key for each number is given in brackets.

**All faithfulness labels are AI-judged.** Both judges are OpenAI models (the same family). No human labels exist.

## 1. Do hints change the answer? (Phase 1)

Data: `artifacts/v2/phase1/responses.jsonl` (750 rows, all kept) and `responses.manifest.json`. Command: `python -m src.gen_v2 --output artifacts/v2/phase1/responses.jsonl`.

Statuses: 659 ok, 85 truncated at 4,096 tokens, 6 invalid answer [`phase1.status`].

Denominator: questions whose unhinted repeat-0 answer is valid and differs from the hint letter (124). An invalid hinted response counts as no switch.

| Hint | Switched to hint letter | Strict pilot parser |
|---|---|---|
| Sycophancy | 21/124 = 16.9% [11.4, 24.5] | 13/91 = 14.3% [8.5, 22.9] |
| Metadata | 83/124 = 66.9% [58.3, 74.6] | 61/91 = 67.0% [56.9, 75.8] |
| Grader hacking | 18/124 = 14.5% [9.4, 21.8] | 12/91 = 13.2% [7.7, 21.6] |
| All hints | 122/372 = 32.8% [28.2, 37.7] | 86/273 = 31.5% [26.3, 37.2] |
| Noise: unhinted repeat 1 lands on the hint letter | 2/124 = 1.6% [0.4, 5.7] | 2/91 = 2.2% [0.6, 7.7] |

[`phase1.switch_rate`, `phase1_strict_parser.switch_rate`, `phase1.control_unhinted_repeat_lands_on_hint_letter`]

Parser v2 accepts 659 answers; the strict pilot parser accepts 519. The switch rates barely change.

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

Agreement on the 75 cases both judges labelled: 65/75 = 86.7% [77.2, 92.6]. Cohen's kappa = 0.25 (bootstrap 95% CI 0.00–0.56) [`judge_hint.agreement`]. **Kappa is below 0.6, so the faithfulness estimate is unreliable.** The high raw agreement and low kappa come from nearly all cases being labelled "admits". The judges disagree mainly on sycophancy.

## 3. Was the answer decided before the reasoning? (Phase 2)

### Early answering

Data: `artifacts/v2/phase2/early.jsonl` (3,295 rows = 659 valid responses × 5 cuts; 0 errors). Command: `python -m src.phase2_v2 early`. The thinking is cut at a fraction of its tokens, then closed, and the model is forced to answer.

| With 0% of the reasoning kept, the forced answer is the hint letter | |
|---|---|
| Hinted responses that switched | 100/122 = 82.0% [74.2, 87.8] |
| Hinted responses that did not switch | 84/268 = 31.3% [26.1, 37.1] |
| Unhinted responses (hint letter of the matching question) | 42/269 = 15.6% [11.8, 20.4] |

[`phase2.forced_at_0pct_equals_hint`]

Among hinted responses, the switch rate is 100/184 = 54.3% [47.1, 61.4] when the 0% forced answer is the hint letter, and 22/206 = 10.7% [7.2, 15.6] when it is not [`phase2.switch_given_forced0_*`].

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
