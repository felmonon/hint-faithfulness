# Completed Phase 3 pilot

All **198 retained outcomes** are published with a passed saved-artifact audit. There are six held-out question identities, not 198 independent observations. The data do **not** establish target-directed steering beyond random controls. Only 74 outputs have strict valid final answers; 25 are invalid and 99 are truncated. No vector condition exceeds its matched random control on target-answer yield per retained grid cell in either cohort. See the [full report](../../docs/PHASE3_PILOT_REPORT.md).

| Material | Location | Scope |
|---|---|---|
| Raw evidence | [Final artifacts](../../artifacts/pilot-20-phase3-v1/) | Exact prompts/tokens/text, vectors, statuses, runtime lineage, blank human-label sheet and completion inventory |
| Acquisition | [Original notebook and checks](../../artifacts/pilot-20-phase3-acquisition-v1/) | Two identical final 38-file exports, full notebook preserved, 13 earlier acquired-prefix histories |
| Integrity audit | [Audit](artifact_audit/audit.md), [machine-readable details](artifact_audit/audit.json) | All 198 rows, 100 source prompts, both byte prefixes, code/vector hashes and timestamp-based runtime attribution |
| Six-question primary | [Analysis](paired_sensitivity/REPORT.md) | All targets/strengths, failures, correct/incorrect strata, common-valid contrasts and question-bootstrap intervals |
| Declared five-question sensitivity | [Analysis](hardware_sensitivity_five_questions/REPORT.md) | Excludes the entire mixed-runtime question; overlapping subset, not an independent replication |
| Numerical interpretation | [Complete tables and findings](NUMERICAL_FINDINGS.md) | Every marginal and paired comparison, with denominators and prediction assessment |
| Descriptive AI review | [Review workspace](ai-review/) | Frozen source/partition identity, complete-text annotations, context checks and separate counts; zero human labels |
| Publication inventory | [Manifest](publication-manifest.json) | File hashes at publication; excludes itself to avoid a circular hash |

The 8 T4 +20 first-L4 +170 later-L4 retained lineage does not establish total historical attempts: later unarchived work after two interruptions is unknown. All original eight and subsequent 28 records, including failures, are byte-preserved. The T4-fitted vectors are reused throughout. Runtime attribution comes from timestamps and metadata rather than per-record hardware attestation.

The steering interpretation gate is unmet/inconclusive. Text categories remain unblinded AI descriptions, not evidence of awareness, concealment, human accuracy or validated faithfulness. Human labels, the larger two-model experiment and the optional introspection follow-up remain absent.

Reproduce the audit and analyses using [the offline commands](../../docs/REPRODUCIBILITY.md#phase-3-full-audit-and-primarysecondary-analyses), always writing to a new output directory. No GPU or API key is needed for saved-data analysis. The audit needs the cached pinned tokenizer but loads no model weights. Annotation reproduction verifies the saved AI judgments; it does not recreate human labels or prove semantic comprehension.
