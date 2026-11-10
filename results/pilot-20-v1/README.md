# Real 20-question pilot: evidence and reproduction

Read the [research report](../../docs/PILOT_REPORT.md) first. This is actual Qwen3-1.7B output collected on a Colab Tesla T4 on November 10, 2026 UTC (November 9 in America/Edmonton). It is not the synthetic demonstration.

## What is preserved

- [Original evidence](../../artifacts/pilot-20-qwen3-1.7b/): 100 logged attempts, 90 retained original responses, exact token IDs, prompts, runtime, and manifest.
- [Incident snapshot](../../artifacts/pilot-20-qwen3-1.7b/recovery/): the 23-record snapshot when 33 attempts had been logged, its log, and the discrepancy audit.
- [Recovery composite](../../artifacts/pilot-20-qwen3-1.7b/recovery-composite/): the original 90 records unchanged, followed by ten new executions of the missing slots. The [lineage](../../artifacts/pilot-20-qwen3-1.7b/recovery-composite/lineage.json) identifies each origin and records 110 total generation attempts. This is not an independent replication.
- [Export provenance](../../artifacts/pilot-20-qwen3-1.7b/export-provenance.json): SHA-256 hashes computed in Colab and checked locally for all 13 evidence files. Colab's browser download failed; a notebook copy with a structured JSON evidence output was saved to Drive and retrieved through the authenticated Drive connector. UTF-8 decoding preserved the final exported bytes, including log carriage returns. No credentials were included.
- [Quality census](quality-census.json): mutually exclusive raw statuses and storage missingness by condition. Token totals cover retained records only; the ten lost original texts and their exact token usage remain unavailable.
- [AI review and coverage](ai-review/coverage.json): all 90 originals and ten recovery generations were read in full. These unblinded AI notes are neither human annotations nor validated judge results.
- [Original analysis](original90/strict/report.md) and [recovery analysis](composite100/strict/report.md), with machine-readable summaries and plots. The three original truncations and all strict-format failures are preserved.
- Separate [original format sensitivity](original90/posthoc-format-v1/report.md) and [composite format sensitivity](composite100/posthoc-format-v1/report.md). The rule was fixed after some original outputs had been observed and is explicitly post hoc; it changes derived copies only.
- Blank human-review forms: [eight original switches](original90/human-review/) and [two additional composite switches](composite100/human-review-additional/). Ten unique cases fall short of the protocol's minimum 30 held-out labels. There are zero human labels and zero OpenAI judge calls.

## Integrity interpretation

The [original audit](original90/audit.json) intentionally reports `ok=false`: the fixed ten missing records cause only `record_set` and `question_coverage` failures. Its token and checksum checks pass. The [composite audit](composite100/audit.json) reports `ok=true` for 100 unique planned records. An internally consistent composite is not evidence of an uninterrupted original run; read the lineage and [recovery protocol](../../docs/RECOVERY_PROTOCOL.md).

Original and composite checksum manifests cover separate scopes. The original manifest excludes the composite subtree. These local manifests were created after the independently recorded Colab hashes were verified. The derived-results checksum manifest excludes itself. Hashes establish consistency of the preserved evidence, not independent proof of inference or scientific validity.

Collection source: `fe4de16013bf9e3e9a9d66abd5b47401becbe24a`. Recovery helper source: `febad78c36fe3c8e0b77b3e720a56c780b2d481d`, executed outside the frozen checkout. Analysis/plot source: `9b4d3636fd24a5a981adb69a512503c9af279cd5`. The [plot diagnostic](diagnostics/plot-failure-febad78.json) records a floating-point display fix; the original summary remained byte-identical. No statistical formula, parser, or collection setting changed for that fix.

## Reproduce without a GPU or API key

Use Python 3.11/3.12 with the repository dependencies. Run from a checkout containing the published evidence. Choose a new output directory; the commands below never modify the raw inputs. A fresh `results/pilot-20-reproduction` directory must not already exist.

```bash
mkdir results/pilot-20-reproduction
python -m src.verify_artifacts --records artifacts/pilot-20-qwen3-1.7b/responses.jsonl
# Expected exit 1 for the two documented original missingness failures.
python -m src.verify_artifacts --records artifacts/pilot-20-qwen3-1.7b/recovery-composite/responses.jsonl
# Expected exit 0 for the recovery composite.
python -m src.analyze --input artifacts/pilot-20-qwen3-1.7b/responses.jsonl --out-dir results/pilot-20-reproduction/original90-strict
python -m src.analyze --input artifacts/pilot-20-qwen3-1.7b/recovery-composite/responses.jsonl --out-dir results/pilot-20-reproduction/composite100-strict
python -m src.sensitivity --input artifacts/pilot-20-qwen3-1.7b/responses.jsonl --out-dir results/pilot-20-reproduction/original90-format
python -m src.sensitivity --input artifacts/pilot-20-qwen3-1.7b/recovery-composite/responses.jsonl --out-dir results/pilot-20-reproduction/composite100-format
```

Do not combine original and composite as repeated `--input` arguments: they share 90 observations. Exact audit timestamps and figure binary bytes may differ across environments; compare the rates, counts, source hashes, and documented failures. The human-review export commands used `--count 30 --seed 42`; the additional composite export excluded `original90/human-review/manifest.json` to avoid duplicate cases. No labels were filled automatically.

The [complete original transcripts](original90/transcripts.md) and [complete composite transcripts](composite100/transcripts.md) preserve all reasoning and final text. Their blank annotation prompts remain blank; completed AI notes are in the separate `ai-review` directory.

## Costs and remaining work

The Colab account displayed free resources and zero compute units; this workflow purchased no compute. OpenAI API usage and charges from this workflow are zero. Codex chat/account credit usage is not exposed here. Secure OpenAI key creation remains incomplete because its local destination prompt returned `not_approved`; no key was created or saved. Human validation, additional models, the full 150-question experiment, and actual activation/probe/steering runs remain future work.
