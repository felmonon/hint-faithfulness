# Reproducing and auditing a run

This project separates software verification, real model collection, and human interpretation. Passing a test suite proves neither that an external model ran nor that the scientific measurement is valid. The pilot protocol is in [PILOT_PROTOCOL.md](PILOT_PROTOCOL.md); the inference limits are in [METHODS.md](METHODS.md).

## Minimum run record

Every published run needs the following evidence. Mark unavailable fields explicitly; do not substitute a setup-machine report for the actual Colab runtime.

| Artifact | Required content |
|---|---|
| Protocol | Commit containing the frozen design, later deviations, and prediction attribution |
| Execution provenance | Git commit, working-tree changes, exact command, start/end times with timezone |
| Inputs | Question file, source revision, sampling seed, question IDs, assigned targets, and SHA-256 |
| Model | Repository/model ID, resolved checkpoint revision, tokenizer revision, thinking setting, precision |
| Runtime | Python and package versions, operating system, GPU model/memory, CUDA/cuDNN versions |
| Sampling | Temperature, top-p, top-k, token cap, per-trial seeds, trial order, any unsupported API parameters |
| Raw responses | Prompt/messages, reasoning, final content, terminal parsed answer, generation IDs, finish reason, status, timestamps, usage |
| Local token evidence | Exact prompt token IDs, generated token IDs, and thinking token IDs |
| Remote provenance, if used | Requested and resolved model, provider, full response object, request parameters without authorization headers |
| Failures | Attempted count, errors, malformed answers, missing reasoning, incomplete thinking, budget stops, interruptions |
| Analysis | Code commit, command, numerator/denominator tables, exclusion counts, plots, uncertainty method |
| Judge, if used | Model, full rubric/hash, raw verdicts, exact evidence, manually supplied labels, blinded-review manifest, holdout declaration |
| Integrity | File byte hashes and the canonical-object hashes used by the runner |

The runner saves response-level fields, and `src.provenance` captures the execution commit, installed package versions, and GPU runtime. `docs/environment.json` is a **setup-host** diagnostic, not evidence of the machine that generated a future model result. The dedicated [real pilot notebook](../notebooks/00_real_pilot_20.ipynb) saves the actual runtime before collection.

## Minimal collection command

Use the frozen file without reordering it. From a clean checkout of the execution commit:

```bash
python -m pip install -r requirements-pilot.txt
python -m unittest discover -s tests -v
python -m src.provenance --output artifacts/pilot-20-qwen3-1.7b/runtime.json
python -m src.run --backend local --model Qwen/Qwen3-1.7B \
  --revision 70d244cc86ccca08cf5af4e1e306ecf908b1ad5e \
  --questions data/questions.jsonl --limit 20 \
  --seed 20261109 --temperature 0.6 --top-p 0.95 --top-k 20 \
  --max-tokens 4096 --device cuda --output artifacts/pilot-20-qwen3-1.7b/responses.jsonl
python -m src.transcripts --input artifacts/pilot-20-qwen3-1.7b/responses.jsonl \
  --output artifacts/pilot-20-qwen3-1.7b/transcripts.md
python -m src.analyze --input artifacts/pilot-20-qwen3-1.7b/responses.jsonl --out-dir artifacts/pilot-20-qwen3-1.7b/analysis
```

The analysis command works without a judge. Its faithfulness panel remains pending until validated labels exist. The transcript export refuses to replace an existing review file; use a new filename when exporting a later version so annotations are preserved.

The initial 20-question subset produces 100 planned records, not necessarily 100 valid answers. A resume skips recorded outcomes, including failures. Record whether any failed trials were deliberately replaced and keep the original attempts. A different token cap, model, precision, prompt, or question file is a different run; it must not be silently merged with the original.

## Capture the actual runtime

Before collection, save the exact package versions for the run. A safe Python approach uses `importlib.metadata` to list installed package names and versions. Hardware metadata can be obtained from `torch.cuda.get_device_name(0)`, `torch.cuda.get_device_properties(0)`, `torch.version.cuda`, and `torch.backends.cudnn.version()`. Save the Git commit separately using `git rev-parse HEAD`, along with the exact command and any working-tree diff affecting the experiment.

Avoid collecting environment-variable dumps, credential files, package-index configuration, browser sessions, or API headers. None is needed for reproducibility. API keys belong only in local ignored files or the intended secret store. A Colab download should include experiment artifacts and omit credentials and model weight caches.

The broad ranges in `requirements.txt` are compatibility ranges. `requirements-pilot.txt` pins the principal Python packages used for this pilot while retaining the Colab-supplied compatible Torch build. It is not a lock of every transitive dependency. Save the successful runtime's exact versions with `src.provenance`; use those when seeking a close reproduction. Even a fixed checkpoint, seed, and package set may produce numerical differences across GPU types or kernels. Report those differences rather than claiming bit-for-bit determinism.

## Public artifact layout

The dedicated pilot notebook writes a publishable directory:

```text
artifacts/pilot-20-qwen3-1.7b/
  runtime.json                 actual Colab versions, hardware, execution commit
  responses.jsonl              real responses, including unsuccessful records
  responses.jsonl.manifest.json
  collection.log               complete collection stdout/stderr
  checksums.json               byte hashes generated at export
  transcripts.md               complete readable responses
  analysis/
    summary.json               generated metrics and exclusion counts
    phase1.png                 generated chart
    report.md                  generated descriptive report
```

Add a run README, actual status and findings, protocol deviations, and review notes identifying who inspected which records. These are intended artifact names, not a claim that a completed run already exists. The notebook archives them as `pilot-20-results.zip`. Preserve the execution commit recorded in `runtime.json`; a notebook opened from a moving branch is not itself an immutable source reference.

The older general notebooks use `data/runs/` and `data/judgments/`, which `.gitignore` intentionally excludes. Publishing those runs requires an explicit reviewed export. The dedicated pilot's `artifacts/` path avoids that ambiguity. Do not remove the rules that exclude secrets.

Raw traces and their runner manifest should be immutable once published. Make corrections through a new artifact version with a documented reason. Derived tables and figures can be regenerated, but retain the raw inputs, command, and code commit used. A checksum verifies file identity; it does not certify scientific validity.

After exporting the frozen pilot, run the read-only integrity audit from the current documented analysis checkout:

```bash
python -m src.verify_artifacts --records artifacts/pilot-20-qwen3-1.7b/responses.jsonl
```

It prints JSON, checks the exact expected 100 trials, prompt/settings identities, checkpoint metadata, timestamps, token structure, and original export checksums, and exits nonzero on integrity failures. Recorded invalid or truncated responses are reported as attrition rather than removed. The checker does not change evidence, independently prove that inference occurred, or validate scientific interpretations. Record the audit's code commit alongside its output.

## Judge review and audit trail

Human labels are entered by a person and identified as such. Keep blank uncertain cases, human notes, the review export manifest, and a declaration of whether the rubric was frozen before those cases were seen. Model-assisted review can be useful but must be labeled separately. A report based solely on AI labels cannot claim human validation.

If a judge changes, rerun the affected judgments under a new filename and rubric/model identity. Do not overwrite disagreements from a prior judge. Keep response and verdict fingerprints so the validation report can be traced to exactly the judged material. Thirty labels are a minimum operational threshold; report the uncertainty and class balance rather than describing the judge as perfectly reliable.

## Reproducing figures without another model call

For a single published raw-response file:

```bash
python -m src.analyze --input artifacts/RUN_NAME/responses.jsonl --out-dir results/reproduced-RUN_NAME
```

When validated judgments are included, also pass their JSONL and validation report with `--judgments` and `--validation`. To combine model conditions, repeat `--input`; do not put two filenames after one flag. Analysis separates different experiment IDs and rejects mixing real responses with mock data.

The public record must distinguish completed inference, completed transcript review, completed human labeling, and completed judge validation. A partially completed pilot is publishable as a transparent status report; it is not a completed faithfulness result.

## Post hoc answer-format sensitivity

During collection, the assistant observed `**Answer:** (B) 125` in a final response, which the frozen terminal-answer parser excluded. The separate `posthoc-answer-format-v1` diagnostic was devised after the first eight complete transcripts and 20 collection status lines had been inspected. It is exploratory, not preregistered, and cannot replace the primary analysis.

```bash
python -m src.sensitivity --input artifacts/pilot-20-qwen3-1.7b/responses.jsonl \
  --out-dir artifacts/pilot-20-qwen3-1.7b/posthoc-format-v1
```

The fixed rule considers only completed `invalid_answer` records with nonempty reasoning. It removes bold/backtick markers and requires one line-start `Answer: (X)` declaration with an uppercase letter; a suffix may be punctuation or exactly the corresponding frozen choice text. Conflicting letters, extra answer declarations, other prose, truncations, incomplete thinking, and request errors remain excluded. Correctness does not influence recovery.

The command refuses an existing output directory and saves the exact rule, its hash, one original/derived decision per record, input hashes, and strict-versus-derived metric summaries. Derived response copies exist only in memory. Raw evidence, the primary parser, and the frozen analysis stay unchanged; no judge or human labels are created. Report zero recoveries or changed conclusions as observed, without adjusting the rule after seeing the comparison.
