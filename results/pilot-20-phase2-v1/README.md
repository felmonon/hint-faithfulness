# Real Phase 2 pilot results

The [report](../../docs/PHASE2_PILOT_REPORT.md) presents early-answer cuts, every probe layer, controls, uncertainty, and limitations. These are real Qwen3-1.7B forward passes on the existing 20-question pilot. The original90 cohort is primary; the composite100 cohort adds recovery records and is an overlapping sensitivity analysis. This is not the full 150-question/two-model study.

## Evidence index

All exported evidence is preserved under [`artifacts/pilot-20-phase2-v1`](../../artifacts/pilot-20-phase2-v1/). This results directory provides navigation without duplicating the raw files.

| Evidence | Original90, primary | Composite100, sensitivity |
|---|---|---|
| Early-answer row-level scores and probabilities | [90 rows](../../artifacts/pilot-20-phase2-v1/original90/early_results.jsonl) | [120 rows](../../artifacts/pilot-20-phase2-v1/composite100/early_results.jsonl) |
| Early-answer summary with question-cluster intervals | [10 group/cut rows](../../artifacts/pilot-20-phase2-v1/original90/early_summary.jsonl) | [10 group/cut rows](../../artifacts/pilot-20-phase2-v1/composite100/early_summary.jsonl) |
| Early-answer manifest | [Manifest](../../artifacts/pilot-20-phase2-v1/original90/early_manifest.json) | [Manifest](../../artifacts/pilot-20-phase2-v1/composite100/early_manifest.json) |
| Early-answer plot | [PNG](../../artifacts/pilot-20-phase2-v1/original90/early_answering.png) | [PNG](../../artifacts/pilot-20-phase2-v1/composite100/early_answering.png) |
| Per-layer held-out probe predictions | [560 rows](../../artifacts/pilot-20-phase2-v1/original90/probe_predictions.jsonl) | [588 rows](../../artifacts/pilot-20-phase2-v1/composite100/probe_predictions.jsonl) |
| Probe summaries, controls, subsets, intervals | [28 layers](../../artifacts/pilot-20-phase2-v1/original90/probe_summary.jsonl) | [28 layers](../../artifacts/pilot-20-phase2-v1/composite100/probe_summary.jsonl) |
| Probe manifest and exact train/test question IDs | [Manifest](../../artifacts/pilot-20-phase2-v1/original90/probe_manifest.json) | [Manifest](../../artifacts/pilot-20-phase2-v1/composite100/probe_manifest.json) |
| Saved residual activations, labels, IDs, split indices | [54 × 28 × 2,048 NPZ](../../artifacts/pilot-20-phase2-v1/original90/probe_activations.npz) | [61 × 28 × 2,048 NPZ](../../artifacts/pilot-20-phase2-v1/composite100/probe_activations.npz) |
| Probe plot | [PNG](../../artifacts/pilot-20-phase2-v1/original90/probe_accuracy.png) | [PNG](../../artifacts/pilot-20-phase2-v1/composite100/probe_accuracy.png) |

The NPZ files contain `activations` (saved as float32 after FP16 inference), `train_indices`, `test_indices`, `record_ids`, `answers`, and `question_ids`. Use `numpy.load(path, allow_pickle=False)`. The 560/588 prediction rows are 28 layers applied to 20/21 held-out prompt records, not that many independent questions. Both tests contain six question identities.

Shared provenance: [frozen plan](../../docs/phase2-pilot-plan.json), [in-run plan copy](../../artifacts/pilot-20-phase2-v1/plan.json), [runtime and installed packages](../../artifacts/pilot-20-phase2-v1/runtime.json), [execution log](../../artifacts/pilot-20-phase2-v1/execution.log), [20 in-run checksums](../../artifacts/pilot-20-phase2-v1/checksums.sha256), and [22-file export hashes and provenance](../../artifacts/pilot-20-phase2-v1/export-provenance.json). All hashes were independently verified after export. The two source files and their hashes are recorded in the plan; [Phase 1 provenance](../../docs/PILOT_REPORT.md) explains the recovery incident.

## Reproduce without overwriting the evidence

The executed code was [`66788e3444a43f1cc87422313ad6b1f7b72a6114`](https://github.com/felmonon/hint-faithfulness/tree/66788e3444a43f1cc87422313ad6b1f7b72a6114). On a CUDA GPU in a **new checkout** of that commit, install the [pilot requirements](../../requirements-pilot.txt), verify the source SHA256s against the plan, and run:

```bash
python -m pip install -r requirements-pilot.txt
python -u scripts/run_phase2_pilot.py
```

The runner loads the pinned model once, checks the source hashes, runs both early-answer and probe analyses for each cohort, and records runtime, manifests, and checksums. It refuses to run if `artifacts/pilot-20-phase2-v1` already exists. Keep the published evidence intact; use a new checkout rather than deleting it. The captured runtime identifies the actual CUDA Torch build, which the requirements file deliberately leaves to the GPU host; matching Python packages alone does not reproduce the GPU environment.

To place rerun outputs elsewhere, the equivalent individual commands are:

```bash
python -m src.phase2 early --device cuda --seed 20261109 --records artifacts/pilot-20-qwen3-1.7b/responses.jsonl --out-dir results/phase2-reproduction/original90
python -m src.phase2 probe --device cuda --seed 20261109 --records artifacts/pilot-20-qwen3-1.7b/responses.jsonl --out-dir results/phase2-reproduction/original90
python -m src.phase2 early --device cuda --seed 20261109 --records artifacts/pilot-20-qwen3-1.7b/recovery-composite/responses.jsonl --out-dir results/phase2-reproduction/composite100
python -m src.phase2 probe --device cuda --seed 20261109 --records artifacts/pilot-20-qwen3-1.7b/recovery-composite/responses.jsonl --out-dir results/phase2-reproduction/composite100
```

These commands reload the model per process and produce the result files/manifests, but do not replace the runner's separate runtime and source-hash checks. Model inference is required to recompute activations and early-answer probabilities; reading the saved summaries, predictions, and arrays requires no API key or new inference. GPU/package changes can affect floating-point scores, so compare recorded settings and numerical outputs, not only file hashes from a new execution.

For a read-only integrity check of the preserved in-run files:

```bash
cd artifacts/pilot-20-phase2-v1
shasum -a 256 -c checksums.sha256
```

The export-provenance file additionally hashes the execution log and checksum file itself. Early-answer agreement is with a sampled final letter, and the switched subset was selected on its eventual outcome. Probe accuracy measures linear decodability on a tiny held-out question set. Neither is a human-validated faithfulness measure; see the report before interpreting the plots.
