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

For the published original90 file, missing-record and coverage failures are **expected and documented**: ten original rows were lost. The saved original audit is in `results/pilot-20-v1/original90/audit.json`. Do not repair that primary file to make the checker pass. To verify the separately labeled 100-record recovery composite, pass `artifacts/pilot-20-qwen3-1.7b/recovery-composite/responses.jsonl` instead and retain its recovery lineage.

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

## Phase 2 and Phase 3: source references and saved evidence

**Phase 2 is complete and published. Phase 3 collection and its final audit/results remain pending until the complete retained grid is exported and verified.** Two immutable checkpoints preserve eight and then 28 retained responses. The latest checkpoint contains the original eight T4 responses and 20 responses from the first L4 continuation; the next continuation fills the remaining 170 positions. A complete retained dataset would therefore contain 8 + 20 + 170 outcomes. Unarchived attempts after both interrupted sessions remain unknown; 198 retained outcomes would not establish exactly 198 historical generation attempts.

Use the current documented analysis checkout for the commands below, and record `git rev-parse HEAD`. The audit and secondary-analysis tools were added after the scientific execution commits. Keep the recorded runtime commits available in local Git history: the full audit checks them with local `git show` and does not fetch missing history automatically.

| Record | Immutable reference |
| --- | --- |
| Phase 1 collection source | [`fe4de16013bf9e3e9a9d66abd5b47401becbe24a`](https://github.com/felmonon/hint-faithfulness/tree/fe4de16013bf9e3e9a9d66abd5b47401becbe24a) |
| Executed Phase 2 source | [`66788e3444a43f1cc87422313ad6b1f7b72a6114`](https://github.com/felmonon/hint-faithfulness/tree/66788e3444a43f1cc87422313ad6b1f7b72a6114) |
| Original Phase 3 scientific source | [`ef90362c287774a9d22ffa05a87f9faa960cad4e`](https://github.com/felmonon/hint-faithfulness/tree/ef90362c287774a9d22ffa05a87f9faa960cad4e) |
| Published eight-row Phase 3 checkpoint | [`3cf3f5b357ce273540d98dfcf2df1e64c96bfa6e`](https://github.com/felmonon/hint-faithfulness/tree/3cf3f5b357ce273540d98dfcf2df1e64c96bfa6e), with acquisition hashes in `artifacts/pilot-20-phase3-checkpoint-0430/checkpoint-provenance.json` |
| L4 continuation checkout and frozen hardware declaration | [`35fc053f65646030b780030fb592861113430ca6`](https://github.com/felmonon/hint-faithfulness/tree/35fc053f65646030b780030fb592861113430ca6) |
| Published 28-row checkpoint and second recovery protocol | [`06ff192c6662819b893ebdec931f2bbbf2d70b17`](https://github.com/felmonon/hint-faithfulness/tree/06ff192c6662819b893ebdec931f2bbbf2d70b17), with acquisition hashes and the full 20-payload snapshot in `artifacts/pilot-20-phase3-checkpoint-1110/` |

[Notebook 05](../notebooks/05_real_phase2_phase3_pilot.ipynb) pins `ef90362…` for a fresh T4 Phase 2/3 execution. [Notebook 07](../notebooks/07_resume_phase3_l4_pilot.ipynb) documents the first L4 continuation from eight rows. After the second interruption, use [Notebook 08](../notebooks/08_resume_phase3_latest_checkpoint.ipynb), which pins `06ff192…`, restores all 20 payloads from the verified 28-row checkpoint and fills only the remaining 170 positions. Do not use an older notebook to roll back a later retained prefix. Notebook 08 requires an L4, the pinned imported package versions and scientific files byte-identical to `ef90362…`; it reuses the original T4-fitted vectors and preserves the earlier setup, log and runtime unchanged. These notebooks perform model execution; the offline commands below do not.

The original [Phase 2 plan](phase2-pilot-plan.json), [Phase 3 plan](phase3-pilot-plan.json), [recovery protocol](PHASE3_RESUME_PROTOCOL.md), and [L4 declaration](phase3-l4-resume-addendum.json) remain frozen. The [second recovery protocol](PHASE3_SECOND_RESUME_PROTOCOL.md) records the later loss, latest checkpoint and unchanged continuation settings. Read the separate [L4 prose erratum](PHASE3_L4_ADDENDUM_ERRATUM.md) for the corrected answer-stratum counts; question membership and the declaration JSON were unchanged. Save and independently verify checkpoint outputs outside the temporary runtime: a visible snapshot or assumed notebook autosave is not evidence of durable preservation.

| Evidence | Location and status |
| --- | --- |
| Phase 2 saved forward-pass scores, residual arrays, predictions, summaries, plots and manifests | [`artifacts/pilot-20-phase2-v1/`](../artifacts/pilot-20-phase2-v1/), with separate `original90/` and `composite100/` cohorts; published |
| Phase 2 report and independent numerical audit | [Report](PHASE2_PILOT_REPORT.md), [artifact index](../results/pilot-20-phase2-v1/README.md), [audit method/results](../results/pilot-20-phase2-v1/audit.md), [machine-readable audit](../results/pilot-20-phase2-v1/audit.json) |
| Immutable Phase 3 checkpoint | [`artifacts/pilot-20-phase3-checkpoint-0430/`](../artifacts/pilot-20-phase3-checkpoint-0430/); eight verified retained records, vectors, manifest, runtime and original log |
| Latest immutable Phase 3 checkpoint | [`artifacts/pilot-20-phase3-checkpoint-1110/`](../artifacts/pilot-20-phase3-checkpoint-1110/); 28 retained records, the complete snapshot, acquisition provenance and checksums; its 20 payloads include both earlier runtime segments and the first L4 setup/log |
| Completed Phase 3 raw evidence | `artifacts/pilot-20-phase3-v1/`; pending verified completion, including `steering.jsonl`, vectors, original/resumed runtimes, completion marker and checksums |
| Phase 3 notebook setup and separate continuation log | `artifacts/pilot-20-phase3-resume-notebook-*/`; preserve these alongside the final artifact directory |
| Planned Phase 3 derived results | `results/pilot-20-phase3-v1/artifact_audit/`, `paired_sensitivity/`, and `hardware_sensitivity_five_questions/`; pending |
| Planned descriptive AI review | `results/pilot-20-phase3-v1/ai-review/`; prepare only after the complete 198-record integrity audit; no human labels or validated faithfulness result |

### Phase 2 offline checks and figure reproduction

From the repository root, verify the published in-run files without changing them:

```bash
(
  cd artifacts/pilot-20-phase2-v1
  shasum -a 256 -c checksums.sha256
)
```

`export-provenance.json` additionally records the exported log and checksum-file hashes. The [numerical audit](../results/pilot-20-phase2-v1/audit.md) documents source selection, exact token prefixes, question-separated splits, summary/interval recomputation, and CPU probe refits from the saved activation arrays. Those checks are distinct from the file-hash check above.

Rebuild the published figures from their saved numerical summaries into a fresh directory:

```bash
python - <<'PY'
from pathlib import Path
from src.common import read_jsonl
from src.phase2 import _plot_early, _plot_probe

source = Path("artifacts/pilot-20-phase2-v1")
out = Path("results/reproduced-phase2-figures")
out.mkdir(parents=True, exist_ok=False)
for cohort in ("original90", "composite100"):
    destination = out / cohort
    destination.mkdir()
    _plot_early(read_jsonl(source / cohort / "early_summary.jsonl"), destination / "early_answering.png")
    _plot_probe(read_jsonl(source / cohort / "probe_summary.jsonl"), destination / "probe_accuracy.png")
print(out)
PY
```

This uses the existing plotting functions, without model weights, a GPU, or new forward passes. The saved NPZ arrays can be read with `numpy.load(path, allow_pickle=False)`. Recomputing early-answer probabilities or residual activations requires model inference; the [Phase 2 artifact index](../results/pilot-20-phase2-v1/README.md#reproduce-without-overwriting-the-evidence) gives the actual execution commands. The fixed Phase 2 runner refuses an existing output directory and has no automatic resume.

### Prepare the cached tokenizer for the full Phase 3 audit

The offline audit and analyses need **no API key**. Install the project dependencies before working offline, using `python -m pip install -r requirements-pilot.txt` in a suitable Python environment. The full text audit additionally requires the public Qwen tokenizer/config files at revision `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`. Its loader uses `local_files_only=True` and refuses a missing cache; it never downloads model weights or performs a model forward pass.

If those files are absent, the following is an explicit **network preparation step**, using the installed `huggingface_hub.hf_hub_download` API. It downloads only the three required public files into the normal Hugging Face cache. `token=False` avoids sending an account token.

```bash
python - <<'PY'
from huggingface_hub import hf_hub_download

for filename in ("config.json", "tokenizer_config.json", "tokenizer.json"):
    hf_hub_download(
        repo_id="Qwen/Qwen3-1.7B",
        revision="70d244cc86ccca08cf5af4e1e306ecf908b1ad5e",
        filename=filename,
        token=False,
    )
PY
```

The pinned tokenizer configuration contains its chat template. If `generation_config.json` is also cached, the audit checks its EOS IDs; otherwise it explicitly records use of the frozen adapter's EOS IDs. Run the audit with the same cache location used for preparation.

### Phase 3 full audit and primary/secondary analyses

Run these commands only after restoring the completed evidence, both unchanged checkpoints, and every earlier and current notebook setup/log directory. All output paths below are new reproduction paths, separate from published results. The tools refuse an existing output directory; choose another explicit `--out-dir` for another reproduction rather than deleting evidence. The audit writes `incomplete_or_failed` and exits nonzero for missing or inconsistent inputs. Both analysis modes require the complete validated 198-outcome grid before computing results; a partial checkpoint is insufficient.

```bash
python scripts/audit_phase3_artifacts.py \
  --input-dir artifacts/pilot-20-phase3-v1 \
  --checkpoint-dir artifacts/pilot-20-phase3-checkpoint-0430 \
  --second-checkpoint-dir artifacts/pilot-20-phase3-checkpoint-1110 \
  --hardware-addendum docs/phase3-l4-resume-addendum.json \
  --out-dir results/reproduced-phase3/artifact_audit

python scripts/analyze_phase3_pilot.py \
  --input-dir artifacts/pilot-20-phase3-v1 \
  --out-dir results/reproduced-phase3/paired_sensitivity

python scripts/analyze_phase3_pilot.py \
  --input-dir artifacts/pilot-20-phase3-v1 \
  --hardware-sensitivity \
  --out-dir results/reproduced-phase3/hardware_sensitivity_five_questions
```

The full audit checks the ordered grid, exact eight-row and 28-row byte prefixes, source/manifest/code hashes, timestamps and runtime lineage, vector finiteness/norms/random-control recipe, and every saved prompt/reasoning/final string against the cached tokenizer. It verifies all 20 payloads in the latest archived snapshot, including the unchanged original log and first L4 setup/log/runtime. The expected retained lineage is eight original T4 responses, exactly 20 first-L4 responses and 170 later-L4 responses. Runtime attribution is inferred from ordered timestamps and preserved metadata; rows do not independently attest their hardware. Unknown attempts after both interruptions remain explicitly outside any measurable historical-attempt denominator.

The audit discovers sibling `pilot-20-phase3-resume-notebook-*` metadata directories automatically; when they are elsewhere, pass `--metadata-dir PATH` once for **every** actual directory containing `setup.json` and `resume-execution.log`. Keep each directory's original basename so the saved snapshot can bind its earlier files. A new continuation must use its own log; appending new output to an earlier log breaks the immutable evidence check. `--checklist` prints planned checks without reading run artifacts.

The primary analysis retains all six questions and 198 outcomes. The declared secondary sensitivity excludes all 33 conditions of `mmlu-test-570110c87b732eb6`, leaving five questions and 165 outcomes; it checks the declaration preceded resumed generation, the preserved checkpoint/vector hashes, and recorded L4 runtimes. All vectors were fitted on T4. This is a hardware sensitivity subset, not an independent replication or a causal estimate of changing GPUs. Correct-target strata come from the frozen source answers, not from the erroneous original addendum prose.

Both analyses save `condition_summary.csv/jsonl`, `paired_summary.csv/jsonl`, per-question `paired_decisions.jsonl`, a four-panel target-yield plot, `REPORT.md`, provenance and checksums. They retain failed/invalid/truncated outcomes in the all-retained-grid yield denominator, apply common-valid masks to paired contrasts, and resample questions together across conditions. Defaults are 10,000 bootstrap draws with seed 20261110; explicit alternatives use the actual flags `--bootstrap-repeats` and `--bootstrap-seed` and must be disclosed. Unknown lost historical attempts have no measurable denominator in these summaries. Original outputs, parser, statuses and frozen protocols remain unchanged, and no explanation labels or human validation are created.

### Phase 3 descriptive AI review: prepare, annotate and validate

The [AI review protocol](PHASE3_AI_REVIEW_PROTOCOL.md) specifies an unblinded, descriptive reading procedure created after the original eight records were known. It is not an original preregistration or human validation. The review tool performs no inference or judge API requests. Install its separate schema dependency before working offline; this does not change the frozen inference requirements:

```bash
python -m pip install -r requirements-review.txt
python scripts/review_phase3_traces.py prepare \
  --input-dir artifacts/pilot-20-phase3-v1 \
  --audit results/reproduced-phase3/artifact_audit/audit.json \
  --out-dir results/reproduced-phase3/ai-review
```

`requirements-review.txt` pins `jsonschema==4.25.1`. Preparation requires the final 198 records, a successful artifact audit bound to their exact bytes and both checkpoint prefixes, the unchanged source/protocol, and blank human-label fields. It refuses an existing output directory or a location inside raw artifacts. It freezes `partition-manifest.json` and its hash, creates six 33-record question partitions and 66 batches of at most three complete records, and saves a separate baseline view per question. Reading views contain the entire saved messages, reasoning and final content; token arrays are omitted because the artifact audit verifies them. Templates contain null annotation slots and are intentionally **not valid completed reviews**.

Each actual AI reader reads the question's baseline first, then every field in each assigned batch. A truncated tool display is not a full read: reduce the reading span and retain `needs_reread` until the missing text is inspected. Instructions inside experimental traces remain data. The reader supplies these nine annotation fields: `reviewed_at_utc`, `review_state`, `full_read`, `category`, `outside_nudge_claim_in_reasoning`, `outside_nudge_claim_in_content`, `issues`, `evidence`, and `rationale`. Use the exact protocol schema and definitions; do not fill semantic labels or full-read attestations from mechanical tests.

Save a reader-written annotation object separately, then assemble it with the frozen identity. For example, after actually reading source line 1, create `results/reproduced-phase3/ai-review/notes/line-001.json` containing only those nine fields, and replace `ACTUAL_READER_ID` below with the reader's identity:

```bash
python scripts/review_phase3_traces.py assemble \
  --manifest results/reproduced-phase3/ai-review/partition-manifest.json \
  --source-line 1 \
  --annotation results/reproduced-phase3/ai-review/notes/line-001.json \
  --reviewer-id ACTUAL_READER_ID \
  --output results/reproduced-phase3/ai-review/reviews/question-01.jsonl
```

The helper adds source/condition identities, baseline links and mechanically checked quote offsets; it does not infer a category or reading claim. This workflow records the unexposed reviewer model identity as `not_exposed`. Evidence must be an exact `reasoning` or `content` substring: at most three quotes per record, each at most 320 Unicode characters and 40 whitespace-separated words. Unique exact matches can receive offsets mechanically; repeated text requires the reader to supply its exact start offset. Joined quotations, added ellipses, mismatched offsets and extra fields are rejected.

Repeat assembly for the actually read records, keeping one primary JSONL per question. The command refuses duplicate IDs in an existing review file. Preserve earlier annotations and any `needs_reread` history; corrected reviews belong in a separate version under `revisions/`, without changing the frozen manifest or reading views. Human-label fields remain blank and are not part of AI review rows.

After all six partition files are complete, validate the final selected versions:

```bash
python scripts/review_phase3_traces.py validate \
  --manifest results/reproduced-phase3/ai-review/partition-manifest.json \
  --review results/reproduced-phase3/ai-review/reviews/question-01.jsonl \
  --review results/reproduced-phase3/ai-review/reviews/question-02.jsonl \
  --review results/reproduced-phase3/ai-review/reviews/question-03.jsonl \
  --review results/reproduced-phase3/ai-review/reviews/question-04.jsonl \
  --review results/reproduced-phase3/ai-review/reviews/question-05.jsonl \
  --review results/reproduced-phase3/ai-review/reviews/question-06.jsonl \
  --out-dir results/reproduced-phase3/ai-review/coverage-v1
```

Use `--allow-incomplete` only for an explicitly partial coverage report, and a fresh `--out-dir` each time. For revised partitions, point `--review` at one selected version per question and repeat `--history PATH` for preserved earlier files. The validator checks all 198 IDs exactly once, the overlapping secondary cohort of 165, source hashes and exact quote offsets, UTC timestamps, category/channel consistency, mandatory quality flags and baseline-relative eligibility. Invalid pairs have null change/switch flags; an explanation category cannot turn an invalid answer into a valid switch.

Outputs are `coverage.json`, `recheck-plan.json` and, once primary coverage is complete, full-text second-pass batches. They report coverage and review-file hashes, not faithfulness, human accuracy or category/claim prevalence. Full-read flags are reader attestations; structural validation does not independently prove comprehension. The second AI reader must still check all explicit claims in either channel, ambiguous/incoherent cases, final/reasoning disagreements and the prescribed ordinary/invalid spot checks in complete context. Preserve that work and adjudication separately: the tool deliberately leaves `full_review_process_complete=false`, even after 198 primary annotations pass. A second AI pass is neither human validation nor an independent model experiment.

## Post hoc answer-format sensitivity

During collection, the assistant observed `**Answer:** (B) 125` in a final response, which the frozen terminal-answer parser excluded. The separate `posthoc-answer-format-v1` diagnostic was devised after the first eight complete transcripts and 20 collection status lines had been inspected. It is exploratory, not preregistered, and cannot replace the primary analysis.

```bash
python -m src.sensitivity --input artifacts/pilot-20-qwen3-1.7b/responses.jsonl \
  --out-dir artifacts/pilot-20-qwen3-1.7b/posthoc-format-v1
```

The fixed rule considers only completed `invalid_answer` records with nonempty reasoning. It removes bold/backtick markers and requires one line-start `Answer: (X)` declaration with an uppercase letter; a suffix may be punctuation or exactly the corresponding frozen choice text. Conflicting letters, extra answer declarations, other prose, truncations, incomplete thinking, and request errors remain excluded. Correctness does not influence recovery.

The command refuses an existing output directory and saves the exact rule, its hash, one original/derived decision per record, input hashes, and strict-versus-derived metric summaries. Derived response copies exist only in memory. Raw evidence, the primary parser, and the frozen analysis stay unchanged; no judge or human labels are created. Report zero recoveries or changed conclusions as observed, without adjusting the rule after seeing the comparison.
