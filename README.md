# Does the model say what changed its answer?

When a hint changes a reasoning model's answer, does its written reasoning admit the hint? v2 tests Qwen3-1.7B on 150 MMLU questions × 5 conditions (two unhinted, sycophancy, metadata, grader hacking); v3 adds DeepSeek V4.1 Flash on the same prompts. Two models are a comparison, not a size trend. The headline: **when DeepSeek V4.1 Flash can see grader code that pushes a wrong letter, it follows the code and its reasoning says the answer is not the correct one** (any judge yes on 138 of 144 such switches). Full numbers, files and commands: **[docs/RESULTS_V2.md](docs/RESULTS_V2.md)**. Plan and dated changelog: [docs/PLAN_V2.md](docs/PLAN_V2.md).

![Switch and admission rates](results/v2/switch_and_admission.png)

- **DeepSeek V4.1 Flash follows visible grader code that is wrong, and its reasoning says the answer is not the correct one.** The grader hint is always the wrong letter (0/150), so it is a pure compliance nudge. DeepSeek switches anyway on 144/146, in 139 of them away from an answer it got right with no hint. Asked one question about those 144 switches, the judges say the reasoning flags its own answer as not correct on 138/144 (any judge), 131/144 (two of three) and 122/144 (all three). In 82-94% of those the model also works out the real answer itself and still goes with the code. Post hoc, one attempt per judge, no human labels. This is the headline.
- **The switch is specific, not general compliance.** The same model never switches on sycophancy (0/146) and only sometimes on metadata (52/146). On the 122 questions both models share, the gap holds: grader hacking 120 vs 17, metadata 41 vs 81, sycophancy 0 vs 19. Two models is a comparison, not a size trend.
- **Qwen3-1.7B is moved by metadata, not by the grader.** Metadata 83/124 (67%), sycophancy 21/124 (17%), grader hacking 18/124 (15%). An unhinted repeat lands on the hint letter 2/124 times. Three AI judges put its metadata admission at 86-100% and a post hoc keyword check matches 81/83 switches (16/124 controls); for sycophancy the judges range from 4/21 to 13/14, so no rate is claimed.
- **The answer is often set before the reasoning.** With no reasoning kept, the forced answer is already the hint letter in 100/122 switched cases, compared with 46/221 eligible non-switches and 42/269 unhinted responses.
- **Probes barely read the answer before reasoning.** The best layer predicts the final letter 166/526 (32%), against a 114/526 (22%) majority baseline. Over all 28 layers, permutation p = 0.05.
- **Steering did not beat random.** On 40 held-out questions, fitted vectors moved the answer to their letter 5/111 (strength 0.1) and 6/111 (0.2) times, against 4/111 and 2/111 for same-norm random vectors. The intervals overlap.

```bash
pip install -r requirements.txt
python -m src.report_v2 --chart   # recompute every v2 number offline
python -m pytest -q               # tests
```

GPU steps run on Colab (`scripts/colab_v2.sh`). No labels are human-validated. API spend: US$5.67 of a US$25 cap ([costs.json](artifacts/v2/costs.json)). The 20-question pilot and its README are in [docs/archive/pilot-v1](docs/archive/pilot-v1/README_PILOT.md).
