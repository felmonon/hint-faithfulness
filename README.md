# Does the model say what changed its answer?

A complete Python implementation of the supplied hint-faithfulness project: hint experiments, a checked judge, early answering, layer probes, and optional activation steering.

[![Open the real 20-question pilot in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/felmonon/hint-faithfulness/blob/main/notebooks/00_real_pilot_20.ipynb)

**Research pilot:** read the [frozen protocol](docs/PILOT_PROTOCOL.md), [reproducibility guide](docs/REPRODUCIBILITY.md), and [data license](DATA_LICENSE.md). The 20-question Colab notebook saves 100 real Qwen3 responses in `artifacts/pilot-20-qwen3-1.7b/`, including failures and runtime provenance. It requires no API key. Results will be added after execution; the synthetic demonstration below is not evidence about a model.

**Status: implementation and software checks, not completed research.** The frozen dataset contains 150 real MMLU questions across 57 subjects. Files in `data/demo/` and `results/demo/` use explicitly synthetic test responses. No live model findings, human labels, or publication claims have been invented.

## Start here

Use the notebooks in `notebooks/` for a Colab workflow. Start with `01_local_phase1.ipynb` on a GPU, then `04_judge_and_analysis.ipynb` for the API comparison and labeling. Use notebooks 02 and 03 when you reach the internal experiments. Upload the supplied project ZIP and run cells in order. Read the complete pilot responses before continuing to the full sample. The command-line equivalent is below.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m src.doctor --catalog
```

Run commands from this folder. Python 3.11 or 3.12 is recommended. The primary GPU route uses plain Hugging Face Transformers and PyTorch; TransformerLens is not required.

## Phase 1: collect and inspect

The question file is already prepared. To create an independent sample, use a new output path:

```bash
python -m src.prepare --count 150 --output data/questions-new.jsonl
```

The sample and local Qwen checkpoint are pinned to exact Hugging Face revisions. One random **wrong** option is assigned per question before any run, then reused for both models and all three hints. Every question receives two unhinted runs and three hinted runs. Sampling settings and prompts are saved with each result.

Read `LOG.md` and record your predictions before collecting live responses. Run the small-model pilot on a GPU:

```bash
python -m src.run --backend local --model Qwen/Qwen3-1.7B --limit 20 --output data/runs/small.jsonl
python -m src.transcripts --input data/runs/small.jsonl --output results/small-pilot-review.md
```

The pilot produces 100 responses. Inspect all of them for answer parsing, complete thinking blocks, and unexpected prompt behavior. If the 4,096-token allowance causes frequent truncation, choose a larger allowance and a **new output path**, then rerun both models with the same limit. Do not silently discard difficult questions.

For the large model, configure `OPENROUTER_API_KEY` privately in your terminal or a Colab secret. The code reads it from the environment and never saves it. Do not paste the key into a notebook cell, this chat, or a data file.

```bash
python -m src.run --backend openrouter --model deepseek/deepseek-r1-0528 --limit 20 --budget-usd 8 --output data/runs/large.jsonl
python -m src.transcripts --input data/runs/large.jsonl --output results/large-pilot-review.md
```

After reviewing both pilots, repeat the two run commands with `--limit 150`. Existing records are retained and skipped. Each complete model condition contains 750 responses. Changing settings requires a new output file. Failed calls are preserved and never automatically retried; diagnose them before starting a documented replacement run.

At setup, the public OpenRouter catalog listed `deepseek/deepseek-r1-0528` with reasoning support, but neither Qwen3-1.7B nor Qwen3-4B. The small model therefore runs on a GPU directly. The large model's listed token prices implied approximately $6.60 for the **maximum completion tokens alone** at 750 × 4,096 tokens; prompt tokens and judging add cost. Prices and availability can change. The $8 collection and $2 judging guards apply separately per output file. Requests cap the provider's token prices at the catalog rates; if no provider meets them, the request fails. These guards are not a global account cap. Provider routing and model updates can still change behavior. [OpenRouter model catalog](https://openrouter.ai/api/v1/models), [provider price caps](https://openrouter.ai/docs/guides/routing/provider-selection)

Keep each `.billing.jsonl` beside its output file when moving or resuming API work. It saves the reservation before sending a request and caches completed responses. Interrupted calls without a confirmed response remain reserved and cannot be silently repeated. Check the charge in your provider account, then use `python -m src.billing --help` to record reconciliation. This does not erase failed research records. Run only one writer per output file.

## Judge and chart

Export a blinded sample, read the traces, and fill `faithful` with `true` or `false` in the CSV. Keep uncertain rows blank; do not invent human labels.

```bash
python -m src.judge export --input data/runs/small.jsonl --input data/runs/large.jsonl --out-dir results/manual-review --count 30
python -m src.judge run --input data/runs/small.jsonl --input data/runs/large.jsonl --output data/judgments/judge.jsonl --model qwen/qwen3-30b-a3b-instruct-2507 --budget-usd 2
python -m src.judge validate --judgments data/judgments/judge.jsonl --labels results/manual-review/labels.csv --manifest results/manual-review/manifest.json --output results/judge-validation.json --held-out
python -m src.analyze --input data/runs/small.jsonl --input data/runs/large.jsonl --judgments data/judgments/judge.jsonl --validation results/judge-validation.json --out-dir results/phase1
```

The default judge is `qwen/qwen3-30b-a3b-instruct-2507`, listed at setup with low token prices. Smoke-test its structured response before judging all switches. It shares a model family with the small model, so human validation and possible judge-family bias remain relevant. `--held-out` is an assertion that these labels were **not** used to tune the rubric. If you revise the rubric after inspecting disagreement, freeze it and export a fresh, disjoint validation sample. At least 30 valid paired labels and 90% agreement are required; inspect the confusion matrix too. See `docs/LABELING.md`.

The report includes uptake, overall baseline disagreement, spontaneous switches to the assigned hint, missingness, Wilson intervals, and a paired bootstrap difference. Faithfulness stays pending when coverage or judge validation is insufficient. Low switch counts are reported; reaching 50 is not guaranteed by 150 questions.

## Phases 2 and 3

Reuse the exact local model, checkpoint, prompts, token IDs, and valid responses. Colab notebooks provide the full commands. Early answering scores A–D after 0%, 25%, 50%, 75%, and 100% of the saved thinking tokens. Probes train on 70% of **questions**, with all variants of a question kept together, and test on the remaining 30%. Training-only scaling, majority and shuffled-label controls, and wrong-answer/resisted-hint subsets are included.

```bash
python -m src.phase2 early --records data/runs/small.jsonl --out-dir results/phase2/early
python -m src.phase2 probe --records data/runs/small.jsonl --out-dir results/phase2/probe
python -m src.phase3 --help
```

Optional steering uses separate vector-building and evaluation questions, zero-strength and random-direction controls, raw saved outputs, plots, and a blank explanation-label sheet. It does not automatically treat a model's silence about injected activations as deliberate concealment. The optional introspection follow-up from the brief is left as a further experiment, not claimed as implemented evidence.

## What to read and ship

- `docs/METHODS.md`: definitions, sources, departures from the papers, and inference limits.
- `LOG.md`: predictions, observations, and the eight-week schedule.
- `docs/WRITEUP_TEMPLATE.md`: a publication structure to fill only after results exist.
- `docs/VERIFICATION.md`: what was actually checked and what still needs live access.
- `results/demo/`: a labeled synthetic pipeline demonstration, unsuitable for scientific conclusions.

The original brief encouraged hand-written experiment loops. You explicitly chose the complete implementation. Treat this as reference code: read the loops before running them, and disclose AI assistance in the eventual write-up. Publishing to your blog or social accounts is a separate action after the results and text are reviewed.
