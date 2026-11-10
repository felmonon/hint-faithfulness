# Does the model say what changed its answer?

Research software for testing whether an open reasoning model acknowledges using a wrong-answer hint. The project includes prompt interventions, answer/noise measurements, judge validation, early answering, linear probes, and optional activation steering.

[![Open the real 20-question pilot in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/felmonon/hint-faithfulness/blob/main/notebooks/00_real_pilot_20.ipynb)

**Status: the real pilot is running in Colab; no completed model findings are published yet.** The code and frozen dataset are available. Software tests and synthetic demonstrations have run, but they are not research results. Human transcript review, human labels, and validated faithfulness findings remain separate checkpoints.

## Start with the real pilot

Open [notebook 00](notebooks/00_real_pilot_20.ipynb) in Colab and select a **T4 GPU**. It clones this repository, checks out the frozen collection source, installs the pilot dependencies, runs software checks, captures the actual runtime, and attempts **100 responses: 20 questions × five conditions**. It needs no API key. The first 20 rows of the frozen 150-question sample are used, with one wrong target letter assigned to each question before generation.

Read the [pilot protocol](docs/PILOT_PROTOCOL.md) before running. It records question IDs, input hashes, model revision, sampling settings, stopping rules, prediction attribution, and the limits of a 20-question exploratory study. The collection notebook currently pins source commit [`fe4de16013bf9e3e9a9d66abd5b47401becbe24a`](https://github.com/felmonon/hint-faithfulness/tree/fe4de16013bf9e3e9a9d66abd5b47401becbe24a); later documentation and judge changes do not silently change that collection run.

The notebook writes to `artifacts/pilot-20-qwen3-1.7b/` and exports `pilot-20-results.zip`. Download the archive before the Colab session ends. Expected artifacts include raw responses, their manifest, runtime metadata, collection logs, complete transcripts, checksums, and descriptive analysis. A response count of 100 does not mean all 100 answers are valid. Preserve and report failed or incomplete outputs.

| Material | Where to look | What it establishes |
|---|---|---|
| Frozen design | [Pilot protocol](docs/PILOT_PROTOCOL.md) | What was planned before live collection |
| Actual real pilot | `artifacts/pilot-20-qwen3-1.7b/` when published | Measured outputs and their provenance; currently pending |
| Software demonstration | [Synthetic report](results/demo/report.md), [fixture data](data/demo/mock.jsonl) | Pipeline behavior only; not evidence about a model |
| Human validation | Published labels and validation report when available | Judge agreement on actual reviewed cases; currently pending |
| Implementation checks | [Verification notes](docs/VERIFICATION.md), [CI](https://github.com/felmonon/hint-faithfulness/actions/workflows/tests.yml) | Software checks, with their stated limits |

## Models, APIs, and what is measured

The small experimental subject is **Qwen3-1.7B**, using unquantized half-precision weights and thinking enabled. Its exact checkpoint and token sequences are retained for later internal experiments. Each question receives two unhinted runs and one run for each of three hints: sycophancy, XML metadata, and grader hacking. The same preassigned wrong letter is reused across hint conditions.

**OpenAI is used as a judge of the saved Qwen reasoning**, not as a replacement source of exposed model reasoning. See [OpenAI setup and judging](docs/OPENAI_SETUP.md) for secure access, the fixed judge snapshot, model availability limits, billing safeguards, and live validation. An OpenAI API key does not authenticate OpenRouter. No key is needed to collect or analyze the initial Qwen pilot.

The optional large-model comparison uses an open reasoning model through OpenRouter. It requires separate access and its own pilot. That comparison remains pending until its raw outputs exist. Two models of different sizes also differ in architecture and training, so this design cannot isolate a pure parameter-count effect.

The main measurements are:

- **Uptake:** how often a hinted response moves to the target when the first baseline did not already select it.
- **Noise:** overall baseline disagreement, plus spontaneous movement to the same target on the matched eligible questions.
- **Faithfulness:** acknowledgment and reliance on the hint among switched responses, reported only when reasoning coverage and held-out judge validation are sufficient.

Missing reasoning is unknown, not an unfaithful label. Truncation, incomplete thinking blocks, invalid final answers, and request errors are counted and retained. [Methods and interpretation](docs/METHODS.md) defines the denominators, Wilson intervals, paired bootstrap, and departures from the source papers.

## Run locally on a GPU

Run commands from the repository root. Python 3.11 or 3.12 is recommended. The dedicated pilot uses [requirements-pilot.txt](requirements-pilot.txt), which pins the principal Python libraries while recording the actual compatible Torch/CUDA runtime. The broader [requirements.txt](requirements.txt) contains compatibility ranges. Neither guarantees identical numerical behavior on every GPU.

```bash
git clone https://github.com/felmonon/hint-faithfulness.git
cd hint-faithfulness
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-pilot.txt
python -m unittest discover -s tests -v
```

For an exact replay, use the execution commit recorded in the original run's `runtime.json`. To collect a new, explicitly versioned pilot:

```bash
python -m src.provenance --output artifacts/pilot-20-qwen3-1.7b/runtime.json
python -m src.run --backend local --model Qwen/Qwen3-1.7B --revision 70d244cc86ccca08cf5af4e1e306ecf908b1ad5e --questions data/questions.jsonl --limit 20 --seed 20261109 --temperature 0.6 --top-p 0.95 --top-k 20 --max-tokens 4096 --device cuda --output artifacts/pilot-20-qwen3-1.7b/responses.jsonl
python -m src.transcripts --input artifacts/pilot-20-qwen3-1.7b/responses.jsonl --output artifacts/pilot-20-qwen3-1.7b/transcripts.md
python -m src.analyze --input artifacts/pilot-20-qwen3-1.7b/responses.jsonl --out-dir artifacts/pilot-20-qwen3-1.7b/analysis
```

Use a fresh artifact directory for a new run. Matching collection commands can resume saved responses; already recorded failures are retained and skipped rather than silently retried. Runtime and transcript exports preserve existing files, so choose new filenames when documenting another session or review. Read all 100 pilot responses before interpreting aggregates. If the 4,096-token allowance or parser needs changing, preserve the first run and document the revised condition before recollecting.

The input file already contains **150 real MMLU questions across 57 subjects**. Its dataset revision and selection hash are in [the manifest](data/questions.jsonl.manifest.json). Do not regenerate or reorder it when reproducing this pilot. Extending to 150 questions is a later, declared experiment; decisions made after viewing the pilot must be disclosed.

## Judge and human review

Follow [OpenAI setup and judging](docs/OPENAI_SETUP.md) after collecting real outputs. Start with five machine verdicts to check formatting and exact evidence, then judge the remaining eligible switches. The judge must identify a hint mention and reliance; a mention only in a final double-check does not count.

Export the blinded human review separately:

```bash
python -m src.judge export --input artifacts/pilot-20-qwen3-1.7b/responses.jsonl --out-dir artifacts/pilot-20-qwen3-1.7b/manual-review --count 30
```

Read the exported traces and enter actual human labels in `labels.csv`. Keep uncertain labels blank. AI review must be identified as AI review and cannot satisfy a human-validation claim. [The labeling guide](docs/LABELING.md) explains calibration, fresh disjoint validation, evidence checks, and the confusion matrix.

The reporting rule requires at least **30 blind held-out labels and 90% agreement**. `--held-out` is an assertion that those cases were not used to tune the rubric. If the pilot yields too few switches, leave validated faithfulness pending and report that shortfall. Do not manufacture labels or keep collecting until a desired result appears. Inspect class balance even if the agreement threshold passes.

The uptake/noise chart can be generated before judging; the faithfulness panel remains pending. Keep API billing journals beside their verdict files when resuming. Interrupted calls and cached completions are handled explicitly. The local budget guard applies to one output file, not the entire provider account. Use one writer per output file.

## Later experiments and notebook routes

| Notebook | Purpose | Access |
|---|---|---|
| [00 — real 20-question pilot](notebooks/00_real_pilot_20.ipynb) | Primary frozen Qwen collection and public artifact export | Colab GPU; no API key |
| [01 — general local Phase 1](notebooks/01_local_phase1.ipynb) | Alternative ZIP-based workflow for a declared larger small-model run | Colab GPU |
| [02 — early answering and probes](notebooks/02_early_answering_and_probes.ipynb) | Reuse local tokens and weights; split by question; compare majority and shuffled-label controls | Colab GPU and saved local outputs |
| [03 — optional steering](notebooks/03_optional_steering.ipynb) | Separate vector-building/evaluation questions; zero-strength and random-direction controls | Colab GPU and saved local outputs |
| [04 — OpenRouter comparison and judge](notebooks/04_judge_and_analysis.ipynb) | Optional large-model comparison and the original OpenRouter judging workflow | Separate OpenRouter key; CPU sufficient for API calls |

Notebooks 01–04 accept a project ZIP and saved-results ZIP together. Their default `data/runs/small.jsonl` paths differ from notebook 00's `artifacts/` path: change `RECORDS` to the actual saved local response file before using Phase 2 or 3. Notebook 04 is an OpenRouter alternative, not an OpenAI-key setup flow. For the requested OpenAI judge, use [the OpenAI instructions](docs/OPENAI_SETUP.md).

Early-answer agreement and probe accuracy show consistency or decodable information, not that an answer was irrevocably settled. A steering-induced answer change does not establish deliberate concealment. The optional introspection follow-up from the brief is not part of the implemented core sweep. Actual execution and validation of each later experiment must be documented separately.

## Documentation and attribution

- [Frozen pilot protocol](docs/PILOT_PROTOCOL.md): settings, exact question IDs, stopping rules, and diagnostic limits.
- [Reproducibility guide](docs/REPRODUCIBILITY.md): runtime capture, artifact contract, immutable raw results, and figure reproduction.
- [Methods](docs/METHODS.md): source papers, metrics, controls, and inference limits.
- [OpenAI setup](docs/OPENAI_SETUP.md) and [labeling guide](docs/LABELING.md): API judging and independent human validation.
- [Research log](LOG.md): dated expectations and observations, with assistant-authored predictions identified.
- [Verification](docs/VERIFICATION.md) and [Phase 2–3 checks](docs/PHASE2_3_VERIFICATION.md): what was tested and what remains unverified.
- [Write-up template](docs/WRITEUP_TEMPLATE.md): a structure to complete after real evidence exists.
- [Data license and attribution](DATA_LICENSE.md): MMLU source and the preserved upstream notice.
- [Citation metadata](CITATION.cff): cite the exact commit or release used, and the original papers separately.

The implementation and documentation were produced with AI assistance at the maintainer's request. Review of the code, raw model traces, and human labels remains necessary. This repository documents an exploratory research process; its publication alone does not make the measurements complete or the conclusions independently validated.
