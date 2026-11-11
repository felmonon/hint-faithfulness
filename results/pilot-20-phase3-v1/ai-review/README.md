# Descriptive AI review of the complete Phase 3 grid

This directory binds AI annotations to all **198 saved outcomes**. It contains no human labels and does not establish a faithfulness score. The [full report](../../../docs/PHASE3_PILOT_REPORT.md#exposed-text-review) explains the results and limits. The steering interpretation gate is unmet/inconclusive.

| Evidence | Purpose |
|---|---|
| [Frozen protocol](../../../docs/PHASE3_AI_REVIEW_PROTOCOL.md) | Unblinded descriptive rubric, actual full-text reading, exact quotations, context checks and posthoc examples |
| [Partition manifest](partition-manifest.json) | Six nonoverlapping 33-record question partitions; exact IDs, source/text hashes and fixed cohort membership |
| [Primary annotations](reviews/) | One final source-bound annotation per saved outcome |
| [Primary coverage](coverage-v1/coverage.json) | Checks all 198 annotations, exact quote offsets, deterministic links, blank human labels and source hashes |
| [Second-pass selection](coverage-v1/recheck-plan.json) | Mandatory context rereads and ordinary/invalid spot-check roles |
| [Actual second-reader notes](second-pass/) | Assignment, primary-review hashes, full context notes and preserved reviewer identities |
| [Separate completion check](second-pass/completion.json) | Verifies actual second-reader records against the final primary selection; comprehension remains an AI attestation |
| [Descriptive count report](descriptive-counts-v1/REPORT.md) | Categories, distinct vector/random switch and other-change groups, and both overlapping cohorts |
| [All count strata](descriptive-counts-v1/summary.json) | Nonexclusive issues, claim channels, eligibility, correct/incorrect targets and record IDs |
| [Posthoc controlled example](EXAMPLES.md), [exact evidence](examples.json) | One comparison selected after complete review; both fitted and random directions yield the same correct-target change |
| [One row per record](descriptive-counts-v1/record_summary.csv) | Current output identity/status/answer and separate baseline identity/status/answer |

The primary coverage validator intentionally reports `full_review_process_complete=false`: it does not certify a second reader. The separate context-completion record reports that additional saved-note coverage. Neither report proves that an AI understood the text or supplies independent human validation. Intermediate partial coverage directories and batch/revision notes are preserved as history, not substituted for the final reports.

All 99 selected second-reader checks passed the saved-note verifier, including every mandatory record and the prescribed spots, with zero recorded disagreements. This is not an AI accuracy estimate.

There are 100 ordinary, 90 incoherent and eight empty reasoning records, with zero explicit outside-nudge or ambiguous classifications. No explicit outside-nudge claim was annotated in either visible field. Silence, missing text and ordinary reasoning do not prove absence of an internal influence or deliberate concealment. Categories can coexist with nonexclusive quality flags, including unsupported but understandable reasoning.

Actual AI worker identities are recorded in every primary annotation and second-reader note. A different worker is used for the selected second reads; this is not evidence of a different underlying model. Reviewer model/snapshot identity is recorded as `not_exposed` when unavailable. The [reproduction instructions](../../../docs/REPRODUCIBILITY.md#phase-3-descriptive-ai-review-prepare-annotate-and-validate) verify saved annotations without creating new semantic labels or sending judge API calls.
