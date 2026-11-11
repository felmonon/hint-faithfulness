# Does the model say what changed its answer?

When a hint changes a reasoning model's answer, does its written reasoning admit the hint? v2 tests Qwen3-1.7B on 150 MMLU questions × 5 conditions (two unhinted, sycophancy, metadata, grader hacking); v3 adds DeepSeek V4.1 Flash on the same prompts. Two models are a comparison, not a size trend. Full numbers, files and commands: **[docs/RESULTS_V2.md](docs/RESULTS_V2.md)**. Plan and dated changelog: [docs/PLAN_V2.md](docs/PLAN_V2.md).

![Switch and admission rates](results/v2/switch_and_admission.png)

- **Qwen: hints move answers.** Metadata 83/124 (67%), sycophancy 21/124 (17%), grader hacking 18/124 (15%). An unhinted repeat lands on the hint letter 2/124 times.
- **Qwen: metadata switches admit the hint; the others are unclear.** Three AI judges put metadata admission at 86–100%, and a post hoc keyword check matches 81/83 switches (16/124 controls). For sycophancy the judges range from 4/21 to 13/14, so no rate is claimed.
- **DeepSeek V4.1 is moved by grader code, not opinions, and says so.** It switches on grader hacking 144/146, in 139 of them away from an answer it got right with no hint, and on metadata 52/146, never on sycophancy (0/146). Every judge rates 97–100% of its switches as admitting the hint (j2–j3 agree 181/181).
- **The answer is often set before the reasoning.** With no reasoning kept, the forced answer is already the hint letter in 100/122 switched cases, compared with 46/221 eligible non-switches and 42/269 unhinted responses.
- **Probes barely read the answer before reasoning.** The best layer predicts the final letter 166/526 (32%), against a 114/526 (22%) majority baseline. Over all 28 layers, permutation p = 0.05.
- **Steering did not beat random.** On 40 held-out questions, fitted vectors moved the answer to their letter 5/111 (strength 0.1) and 6/111 (0.2) times, against 4/111 and 2/111 for same-norm random vectors. The intervals overlap.

```bash
pip install -r requirements.txt
python -m src.report_v2 --chart   # recompute every v2 number offline
python -m pytest -q               # tests
```

GPU steps run on Colab (`scripts/colab_v2.sh`). No labels are human-validated. API spend: US$4.80 of a US$25 cap ([costs.json](artifacts/v2/costs.json)). The 20-question pilot and its README are in [docs/archive/pilot-v1](docs/archive/pilot-v1/README_PILOT.md).
