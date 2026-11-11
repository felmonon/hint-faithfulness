# Final Colab evidence acquisition

The unchanged downloaded notebook completed 198 retained grid outcomes. `source-notebook.ipynb` is 3,090,573 bytes with SHA-256 `b9104b848a244de389f24627167eb2a8f51193167f70779d084da950f8b7a5f0`.

It contains two structured final snapshots, in zero-based cells 5 and 6. Both were independently verified and their complete payload dictionaries are identical; only snapshot metadata timestamps differ. `notebook-acquisition.json` records source-cell verification and this selection. The only authorized source normalization was the copied-to-Drive guard. No notebook code was executed during acquisition.

- `foreground-snapshot.json` and `foreground-verification-provenance.json`: foreground-cell final snapshot and its check record.
- `verified-export/`: full independently checked export-cell snapshot, unchanged source JSON, 38 decoded payloads, acquisition provenance and completion/inventory files.
- `continuation-checkpoint-history/`: exact acquisition-provenance records for all 13 externally acquired second-continuation checkpoints (28, 38, …, 148), with notebook hashes and final-prefix comparisons. Full intermediate notebook copies remain in the local evidence backup; they are not duplicated here. Their raw prefixes can be recovered from the final JSONL and verified against the published hashes.
- `checksums.sha256`: original integration inventory; the subsequently added README and checkpoint-history directory are outside that original inventory. The history has its own inventory, and the final publication manifest covers all published evidence.

The portable verifier deliberately refuses to choose among multiple notebook snapshots. The two final snapshots were extracted explicitly and checked separately; the source notebook was preserved. Reproduce the export-cell payload checks with the published standalone JSON:

```bash
python scripts/verify_phase3_colab_export.py \
  artifacts/pilot-20-phase3-acquisition-v1/verified-export/source-export.json \
  --expected-bytes 1521498 \
  --expected-sha256 988c551ac3fbb5e68935aedd03a79ff01bd36f06d2f1f6ecced7d379fd4eb61a \
  --source-modified-at 2026-11-11T07:20:46.878Z \
  --out-dir results/reproduced-final-acquisition
```

This standalone check does not claim source-cell verification; that separate check is recorded in `notebook-acquisition.json` and can be reproduced by comparing all eight cells with the published notebook08, allowing only `COPIED_TO_DRIVE = True` in place of `False`. To reproduce every historical prefix check, reconstruct each prefix from the first N complete lines of the final JSONL, compare its hash with `continuation-checkpoint-history/history.json`, and pass each as `--prior-jsonl`. The frozen eight/28-row prefixes are always checked.

Acquisition proves transport/preservation consistency, not scientific efficacy. The subsequent full token/text/runtime audit is [published separately](../../results/pilot-20-phase3-v1/artifact_audit/audit.md). Its success does not retroactively rewrite the acquisition-time `full_scientific_audit_passed: false` metadata. Unknown attempts after both earlier runtime losses remain unknown.
