# Verified 28-row Phase 3 checkpoint

This is an incomplete checkpoint, not a completed steering experiment. It preserves eight original T4 rows plus 20 rows from the first L4 continuation. All 28 rows belong to one question; 170 positions remain without archived outcomes. Later attempts after both lost runtimes are unknown.

The snapshot was captured at 2026-11-10T11:10:25.384475+00:00, saved in Drive at 11:10:53.105 UTC, and downloaded/verified at 2026-11-11T00:36:17.391699+00:00. The saved notebook SHA-256 is `422d9a13a683f910e28e48f25ae6b3b069f0b778477cb9d5f8c54aa939567efa`.

- `steering.jsonl` is the unchanged, readable 28-row payload, including invalid/truncated responses.
- `snapshot.json` preserves the full structured snapshot with 20 explicitly named gzip/base64 payloads, raw/compressed hashes and byte counts. It includes original vectors, manifests, frozen plans, original/first-resume runtimes, setup and logs. Decompression must verify both hashes and safe relative paths before writing to a new destination.
- `acquisition-provenance.json` records the saved notebook and payload identities. It is an acquisition record, not proof of scientific validity.
- `checksums.sha256` covers this archive's files without rewriting any payload.

Read the [second recovery protocol](../../docs/PHASE3_SECOND_RESUME_PROTOCOL.md) before using this checkpoint. The original [eight-row archive](../pilot-20-phase3-checkpoint-0430/) remains unchanged. Neither checkpoint supports an efficacy or explanation-faithfulness estimate. Human validation remains absent.
