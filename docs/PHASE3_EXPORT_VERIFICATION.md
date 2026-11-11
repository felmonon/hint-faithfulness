# Verify a saved Phase 3 Colab export offline

The [acquisition verifier](../scripts/verify_phase3_colab_export.py) checks a downloaded Notebook 08 copy or its standalone structured snapshot JSON **outside Colab**. It extracts and preserves an exact source copy plus the checked payloads in a new directory. This fills the gap between displaying a checkpoint in Colab and checking its saved bytes locally. It requires only Python's standard library, the repository reference files, and the downloaded evidence; no API key, network, GPU, tokenizer, or model execution is used.

Notebook 08 verifies and produces snapshots inside the temporary runtime. The separate [completed-artifact audit](../scripts/audit_phase3_artifacts.py) requires all 198 retained outcomes and checks tokens, text, scientific settings and runtime lineage. The acquisition verifier accepts retained prefixes from 28 through 198 and **does not replace that final audit**. Its `acquisition_checks_passed` result concerns preservation and transport. Even a producer-marked complete export receives `full_scientific_audit_passed: false` until audited separately.

## Inputs and checks

The notebook reference is pinned by exact byte SHA-256 to commit `cef711f2da01e9b1799b9f6e238737652cb0a460`; the restored 28-row checkpoint remains `06ff192c6662819b893ebdec931f2bbbf2d70b17`, and scientific source remains `ef90362c287774a9d22ffa05a87f9faa960cad4e`. The tool never executes notebook cells. For a downloaded notebook, every cell's type/source must match the reference, allowing only the documented `COPIED_TO_DRIVE` boolean change. Exactly one structured `application/json` snapshot is required; the tool does not choose among multiple outputs. Standalone JSON lacks notebook cells, so provenance explicitly records that their equality was not checked.

Checks cover compressed and decoded sizes/hashes, the exact expected payload set, unchanged earlier evidence, both frozen eight-row and 28-row byte prefixes, the ordered grid prefix and condition identities, separate L4 setup/log/runtime records, and chronology. The new setup must retain the fixed source/declaration/restoration identities, clean tracked tree, CUDA/L4 and imported package settings; its runner runtime must match except for capture time. A claimed complete export additionally needs all 198 positions, the completion marker, and a complete non-self-referential artifact checksum inventory. These checks do not assess generated reasoning, assign labels, repair statuses, count unarchived attempts, or authenticate a caller's claimed Drive metadata.

For **every already acquired later prefix**, supply `--prior-jsonl` explicitly. Each must be unchanged at the start of the new raw file, so rollback or replacement is rejected. No personal backup folder is searched automatically. When none is supplied, the report clearly limits its checks to the frozen eight/28-row checkpoints; it does not claim that every prior acquisition was compared.

## Example

From the repository root, replace the example paths with your downloaded file, previously verified raw prefix, and a fresh destination whose parent exists:

```bash
python scripts/verify_phase3_colab_export.py /path/to/downloaded-notebook.ipynb \
  --prior-jsonl /path/to/previously-verified/steering.jsonl \
  --out-dir /path/to/new-acquisition
```

Repeat `--prior-jsonl` for additional earlier acquisitions. A standalone snapshot `.json` uses the same command. Optional `--expected-bytes NUMBER`, `--expected-sha256 HEX`, and `--source-modified-at UTC_TIMESTAMP` bind externally recorded download metadata. The metadata is recorded as caller supplied, not independently authenticated. `--project /path/to/hint-faithfulness` selects another checkout containing the exact pinned reference and frozen archives.

The output contains:

- `source-export.ipynb` or `source-export.json`: the exact downloaded bytes; the input is neither moved nor modified.
- `snapshot.json`: a deterministically serialized extracted snapshot, with its own hash distinct from the original download hash.
- `payloads/artifacts/…` and `payloads/docs/…`: verified experiment evidence, preserving its relative layout.
- `acquisition-provenance.json`: verification time, source name/bytes/hash, supplied metadata, reference/tool hashes, snapshot capture time, payload hashes, and exact prior-prefix check scope.
- `checksums.sha256`: hashes of the saved source, snapshot, provenance and payloads; it excludes itself. `verification-complete.json` is written last and binds the inventory hash. It is an acquisition marker, not a scientific-completion certificate.

All validation precedes extraction. The tool rejects unsafe payload paths, symlink paths, writes beneath repository raw artifacts, and **every existing output directory**, including a partial result. Writes are staged in an exclusively created destination. If saving fails, preserve the partial directory as evidence and choose a fresh destination; it must not be treated as verified without a valid final marker and matching inventory. Inputs are limited to 256 MiB; each decoded payload is limited to 64 MiB and total decoded payloads to 256 MiB. These bounds cover this fixed pilot's exports, not arbitrary datasets.

## After acquisition

Keep each acquired bundle immutable and preserve its provenance. A partial prefix is useful recovery evidence but cannot enter the completed analysis. Once a complete export is acquired, run the [full audit and analyses](REPRODUCIBILITY.md#phase-3-full-audit-and-primarysecondary-analyses) on its extracted artifact directory, supplying both checkpoint directories and the separate setup/log directories as required by the audit CLI. A successful acquisition does not certify a full trace read, human validation, steering efficacy, or an exact historical inference count.

The live operational backup helper is deliberately unchanged. This portable verifier is a separately reviewed publication tool; it does not modify the experiment, notebook, frozen protocols, or acquisition history.
