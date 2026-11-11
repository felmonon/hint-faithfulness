# Phase 3 infrastructure recovery protocol

Frozen before resumed generation on 2026-11-10 at 09:49 UTC. This document adds incident and recovery provenance; it does not alter the frozen [pilot plan](phase3-pilot-plan.json), its manifest, model, prompts, vectors, split, strengths, scoring, or interpretation rules. The following execution is planned, not asserted complete.

## Incident and limits of preservation

Root reports that a tool approval/download wait prevented monitoring from approximately 04:34 to 09:40 UTC. Reconnection allocated a fresh Tesla T4 runtime with an empty prior working disk. The earlier background Phase 3 process and its unexported files are unavailable. The cause and exact time of runtime termination were not independently established.

The verified notebook/Drive checkpoint captured at **2026-11-10T04:28:37.649111+00:00** preserves seven payload files and **eight complete JSONL records**. Its latest preserved response finished at **04:25:26.353859 UTC**. The checkpoint is archived unchanged at `artifacts/pilot-20-phase3-checkpoint-0430/`, with acquisition details in `checkpoint-provenance.json`. No completion marker for the 198-position sweep exists in that checkpoint.

**Attempts after this checkpoint are unknown.** Some remaining grid positions may already have been attempted, completed, or in progress without a recoverable output. The checkpoint does not establish that only eight physical generations occurred. The resumed dataset will aim for **198 retained, unique grid outcomes: eight preserved plus 190 missing positions**. Its total historical inference-attempt count is unknown and may exceed 198. This is a disclosed infrastructure deviation from the original “Fixed198attempts” stopping text, whose same paragraph explicitly permits exact-manifest infrastructure resume. The frozen plan remains unchanged.

## Checkpoint verification before execution

An AI-assisted, read-only local audit verified the following without loading model weights, making API calls, or performing a model forward pass:

- All seven payload SHA-256 hashes match the acquisition manifest; the saved plan equals the frozen repository plan. The full Phase 1 source hash and the reconstructed Phase 3 manifest match exactly.
- The eight retained IDs are unique and match the first eight entries in the fixed 198-position grid. Their source links, prompts, model revision, layer, per-question seeds, dtype/device, strict answer parsing, termination fields, exact token counts, thinking boundaries and EOS are consistent.
- The pinned, locally cached tokenizer exactly reconstructs all 100 source prompts and decodes all eight saved reasoning/content strings from their token IDs. No answer or trace was repaired.
- `vectors.npz` contains exactly four steering and four random arrays, each finite float32 with shape `(2048,)`. Steering norms equal saved metadata. Random vectors reproduce bit-for-bit from NumPy seed 42 and the stored steering norms. A/B/D norms match exactly; C differs relatively by only 9.23e-8 from float32 normalization.
- The source and split give target training counts A=3, B=3, C=5, D=3. Code weights the three hinted-minus-baseline activations equally within each training question, then weights questions equally within each target group. Held-out questions are excluded. Individual training activations were not stored, so the numeric steering means cannot be independently reconstructed from the checkpoint alone; this audit verifies the recipe, membership, aggregate arrays and random controls.
- `src/phase3.py`, `src/local_model.py`, `src/common.py`, and `scripts/run_phase3_pilot.py` are byte-identical to the recorded original commit `ef90362c287774a9d22ffa05a87f9faa960cad4e`.

| Target | Training questions | Steering norm | Random norm |
| --- | ---: | ---: | ---: |
| A | 3 | 25.739307404 | 25.739307404 |
| B | 3 | 30.513193130 | 30.513193130 |
| C | 5 | 20.666421890 | 20.666419983 |
| D | 3 | 23.183128357 | 23.183128357 |

The checkpoint covers one question and only the first part of its condition grid. It supports preservation checks, not an estimate of steering efficacy or explanation faithfulness. No human validation or new explanation labels are supplied by this audit.

## Fixed resumption procedure

1. Preserve the checkpoint archive. Restore its seven verified payloads into `artifacts/pilot-20-phase3-v1/`; copy the frozen Phase 1 source and scientific code unchanged. Verify all hashes again before launch. In particular, require `vectors.npz` and its exact checkpoint hash: the existing code would otherwise refit vectors if that file were absent. Do not permit that fallback for this recovery.
2. Record the fresh runtime separately and preserve original `runtime.json`. The runner’s `--resume` path creates a timestamped runtime file. Compare core inference packages and hardware against the original Tesla T4, torch 2.14.1+cu130, transformers 5.0.0rc3 and pinned model/tokenizer revision. Record any environment difference explicitly; the manifest does not enforce package/GPU identity and matching seeds do not guarantee byte-identical outputs across environments. The original installed-distribution list contains two NumPy versions; the prior same-runtime post-execution import check reported NumPy 2.2.6. Preserve that distinction.
3. Run the existing foreground runner with `python -u scripts/run_phase3_pilot.py --resume`. Its fixed configuration is the existing plan: CUDA float16/eager attention, Qwen/Qwen3-1.7B revision `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`, layer 14, strengths 0/1/2/4/8, seed 42 with the same per-question seed derivation, temperature 0.6, top-p 0.95, top-k 20 and 4,096 new-token cap. Its underlying Phase 3 invocation retains `--include-invalid-source-outcomes --stratify-targets`.
4. Reuse the checkpoint manifest and vectors. Skip all eight retained record IDs irrespective of answer/status, including invalid or truncated outputs. The first missing condition is question `mmlu-test-570110c87b732eb6`, vector B, strength 8. Preserve raw rows verbatim and append only missing grid positions in the original order. There are 190 planned new calls if this continuation completes without another interruption; that count does not resolve unknown earlier calls.
5. Use foreground execution with automatic recoverable JSON checkpoint updates at intervals of at most ten newly saved records and at completion, including raw rows, manifest, vectors, metadata, plan, runtime provenance and logs. Verify that checkpoints are actually saved outside the transient runtime; an in-memory display alone is not durable. Preserve the original checkpoint and original log rather than overwriting that evidence. Record subsequent acquisitions and hashes.
6. At completion, verify all 198 unique grid positions, unchanged eight-row prefix, unchanged manifest/vector bytes, token/text integrity and preserved original/new runtime records. Run the existing default analysis and the separately reviewed paired/attrition sensitivity analysis. Retain failed/truncated outputs and report their attrition; do not tune strengths, retry a retained failure, select a best strength or generate explanation labels through this recovery.

If another interruption occurs, preserve and validate the latest durable checkpoint before an identical continuation, and add that incident to the lineage. If previously missing outputs are later recovered from the original runtime, archive them separately; do not silently replace checkpoint/continuation selections or choose outputs by their quality. The declared selection is the eight checkpoint rows plus the first durably retained continuation record for each remaining ID.

## Reporting and provenance

Final reporting must distinguish the original eight-row segment from the resumed 190-position segment and state that unarchived earlier attempts are unknown. Use “198 retained grid outcomes” only after validation; do not say “exactly 198 total attempts” or claim an uninterrupted run. Completion counts are not evidence of steering success. The pilot’s existing baseline/random controls, common-valid sensitivity, interpretation gate and absent human validation remain in force.

Checkpoint payload hashes:

| File | SHA-256 |
| --- | --- |
| `manifest.json` | `b6ab6444ac32113f1e00ebf3f1cba43a6344f00ada0b431ff7b4fdc03b74565c` |
| `plan.json` | `5ecc12c4f4d79161de442582f2bea7b89815a0ba06808eb130b00054de52d1f2` |
| `runtime.json` | `46c1201b9755f0ac8f317773cfdff9e82ed5c5ae966ee3528ff88232e59d0b64` |
| `steering.jsonl` | `5bec0702c11667104b6a37a3f15487b19dceb7358f771748e467b346ae63044b` |
| `vector_metadata.json` | `cf3a7ff327d4ef6eb496a0819c8af2539b1d5ee43636db284cbb5266dc0cba20` |
| `vectors.npz` | `9808b154bd3e584c53ba8fe784d3b5d47c67ec131a9c246fe0ca5dfc828e8c57` |
| `execution.log` | `5b580df84a568b4de5ad1f601844354302fdfaaf01e351f31d1e417d015373d9` |

Scientific source hashes, matching original commit `ef90362`:

| File | SHA-256 |
| --- | --- |
| `src/phase3.py` | `57bb529ac9096f8892d3da6253d43b728d7fb562b1c1565a64c5b0691a28fcdc` |
| `src/local_model.py` | `b7a549ace225611660eb0c27ca03ba12cb1d4a180407b7138c1fd223fdb68766` |
| `src/common.py` | `665d1d7866e87dac4afd0cff9e12c7be190a57e6daaa9cb692441e1475cc9d9d` |
| `scripts/run_phase3_pilot.py` | `8e616c5b20f21c01682e215ea2ba0e8b5bf0ed8d145fd529c6497190474ef714` |

Frozen Phase 1 source SHA-256: `ba4c4e897f182048fc97a08d9872f423f01c6531e933d85077ad5ab712b1a2bf`.
