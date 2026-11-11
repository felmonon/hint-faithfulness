# Phase 3 second infrastructure recovery

Frozen **2026-11-11T00:40:20+00:00**, before second-continuation inference. This supplements the original [recovery protocol](PHASE3_RESUME_PROTOCOL.md) and [L4 amendment](PHASE3_L4_RESUME_ADDENDUM.md), including its [factual erratum](PHASE3_L4_ADDENDUM_ERRATUM.md). It changes no scientific condition, source prompt, fitted vector, scoring rule, question membership, or analysis gate.

## Observed incident and preservation limits

The first L4 continuation started at 2026-11-10T10:39:09.719017 UTC. Its latest externally saved snapshot was captured at **2026-11-10T11:10:25.384475+00:00** and saved in Drive at **11:10:53.105 UTC**. It contains **28 retained rows**, all from the first held-out question: eight preserved original T4 rows followed by 20 new L4 rows. The last retained row finished at **11:10:24.978264 UTC** (random direction C, strength 4).

On resumed inspection around **2026-11-11 00:37 UTC**, Colab displayed Reconnect rather than an executing session. Reconnection supplied a fresh L4 runtime with an empty prior working disk. The interval between the last saved snapshot and this inspection was not continuously observed. The exact disconnection/termination time, cause, and any later progress are unknown. A completed 198-position run cannot be inferred from elapsed time, and later outputs cannot be reconstructed from its progress counter. The latest Drive bytes still contained only the 28-row snapshot. Acquisition at **2026-11-11T00:36:17.391699+00:00** independently verified its saved bytes and all 20 payloads.

**Unarchived attempts after both interrupted sessions remain unknown.** The original T4 loss and the later L4 loss must both be disclosed. An eventual 198-row retained dataset does not establish exactly 198 historical generations; missing positions may have been attempted previously without recoverable output. No recorded failure or truncation is to be retried or replaced.

## Immutable input and continuation

The new archive is `artifacts/pilot-20-phase3-checkpoint-1110/`. `snapshot.json` preserves the complete structured `phase3-recovery-snapshot-v1` object extracted from the saved notebook. Its gzip/base64 payloads are independently checked against compressed/raw sizes and SHA-256 values. `steering.jsonl` is the exact readable 28-row payload; `acquisition-provenance.json` records the original notebook hash, Drive timestamps, and payload identities. The archive includes its own checksum inventory.

| Archived file | SHA-256 |
| --- | --- |
| `snapshot.json` | `92adcb34894143f73f63f74965862d1c895dd7041b2f81e568fbb86c1991b81a` |
| `steering.jsonl` | `54f5e311d8e6ceed08629f4bb39f4f0de3b5e7b6a337f74cef2e7812fed73507` |
| `acquisition-provenance.json` | `f7aaab4e4a3290f511034a87f115dacf61135ed4058bf7d3812d55dea22ba57f` |
| Source saved notebook | `422d9a13a683f910e28e48f25ae6b3b069f0b778477cb9d5f8c54aa939567efa` |

1. Restore only this verified 28-row prefix into a new dedicated checkout. Preserve every named original checkpoint, prior runtime, prior setup file and prior continuation log. Reject unsafe paths, unknown payloads, checksum failures and conflicting existing bytes. Never restore only the earlier eight-row checkpoint when this later archive exists.
2. Require an L4 CUDA runtime and the pinned imported inference packages. Record the actual new hardware/software identity separately. Keep the model revision, FP16/eager attention, seed derivation, all strengths, sampling settings, 4,096-token cap and exact saved vector bytes unchanged. Verify the scientific files against original commit `ef90362c287774a9d22ffa05a87f9faa960cad4e` before inference.
3. Resume the unchanged foreground runner with `--resume`, preserving the entire 28-row byte prefix and skipping all retained IDs regardless of status. The first missing position is **question `mmlu-test-570110c87b732eb6`, random direction C, strength 8**. There are **170 missing grid positions**: five remaining conditions for that question plus all 33 conditions for each of the other five held-out questions.
4. Create a new setup directory/log and a new timestamped runtime record. Snapshots must include both prior and new metadata/logs, all resumed-runtime records, and the unchanged earlier evidence. Capture at 28 initially, after each ten new completed rows (38, 48, …), on interruption, and at 198 after full verification. Save outside the transient VM and independently verify each acquired checkpoint; a displayed update alone is not durable.
5. At completion, verify all 198 unique ordered grid IDs, both exact eight-row and 28-row byte prefixes, all immutable vectors/manifests/source identities, every saved token/text sequence, both interrupted-session lineages, and the final checksum inventory. If another interruption occurs, recover the latest verified prefix rather than restarting from 28 or eight.

## Analysis and reporting remain fixed

The primary analysis still contains six held-out questions and 198 retained grid outcomes. The predeclared secondary sensitivity still excludes the entire first mixed-runtime question and contains five questions/165 outcomes. All vectors remain those fitted on the original T4. The primary retained lineage is eight T4 rows, 20 rows from the first L4, and up to 170 rows from the second L4 if this continuation completes. These are infrastructure segments, not independent replications. Package/hardware differences must be disclosed even when nominal settings agree.

Publish controls, all strengths, attrition, common-valid paired contrasts, question-level uncertainty, and descriptive AI-only review under the existing interpretation gate. Preserve blank human-label fields. Do not turn successful preservation or completion into a claim of steering efficacy, awareness, deliberate concealment, or validated faithfulness.
