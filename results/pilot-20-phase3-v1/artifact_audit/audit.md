# Phase 3 retained-artifact audit

Status: **passed_with_documented_limits**.

AI-assisted integrity review; no human validation, new inference, or explanation labels.

All 198 retained grid outcomes, the exact eight-row and 28-row byte prefixes, immutable checkpoint files, and frozen scientific source passed verification. Every saved response was independently decoded using the cached pinned tokenizer. Historical total attempts remain unknown.

Checked 100 source prompts and 198 response traces. No model weights were loaded.

Checklist:

- Verify completed inventory and seven archived checkpoint hashes.
- Bind source, manifest, plan, vectors and frozen scientific code to the checkpoint.
- Require exact eight-row and 28-row checkpoint byte prefixes and all 198 planned IDs in original order.
- Validate every grid row, seed, source link, strict parser, token boundary and termination.
- Independently retokenize all source prompts and decode all generated traces using cached pinned files.
- Verify finite float32 vectors, training counts, norm-matched seeded random controls.
- Check sequential UTC timestamps and original/resumed runtime segments; disclose inferred attribution.
- Rehash inputs after auditing; keep historical attempt count unknown and human validation absent.

Runtime attribution is inferred from timestamps; full segments, environment differences and checksums are in `audit.json`. A successful audit establishes saved-artifact consistency, not steering efficacy or honesty.

- Eight preserved T4 outcomes, 20 first-L4 outcomes and 170 later-L4 outcomes form the primary dataset; only the first question spans both GPUs. The five-question sensitivity was declared before retained resumed generation.
- Runtime environment differs from original in runtime-resume-2026-11-10T10-39-08.868091+00-00.json; see explicit hardware/software deltas.
- Runtime environment differs from original in runtime-resume-2026-11-11T00-54-40.487123+00-00.json; see explicit hardware/software deltas.

- Consistency and hashes do not independently prove that inference occurred.
- Unknown unarchived attempts after both interruptions preclude an exact total historical attempt count.
- Runtime assignment is inferred from timestamps; package/driver differences are disclosed, not erased.
- No new model forward pass, vector refit, explanation labeling, or statistical claim is performed.
- Original distribution metadata lists two NumPy versions; it does not identify the imported version by itself.
