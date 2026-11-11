# Descriptive AI review counts

Counts of source-bound annotations; no human labels or validated faithfulness score.

## primary six questions

| Category | All | Baseline | Vector | Random |
|---|---:|---:|---:|---:|
| ordinary_reasoning | 100 | 6 | 46 | 48 |
| explicit_outside_nudge_claim | 0 | 0 | 0 | 0 |
| incoherent | 90 | 0 | 47 | 43 |
| ambiguous | 0 | 0 | 0 | 0 |
| empty | 8 | 0 | 3 | 5 |

| Category | Vector target switches | Random target switches | Other vector changes | Other random changes |
|---|---:|---:|---:|---:|
| Eligible records | 2 | 3 | 3 | 5 |
| ordinary_reasoning | 2 | 3 | 3 | 5 |
| explicit_outside_nudge_claim | 0 | 0 | 0 | 0 |
| incoherent | 0 | 0 | 0 | 0 |
| ambiguous | 0 | 0 | 0 | 0 |
| empty | 0 | 0 | 0 | 0 |

All quality flags, claim-channel counts, correct/incorrect-target strata, denominators and record IDs are in `summary.json`; `record_summary.csv` preserves every record.

## secondary five questions

| Category | All | Baseline | Vector | Random |
|---|---:|---:|---:|---:|
| ordinary_reasoning | 79 | 5 | 36 | 38 |
| explicit_outside_nudge_claim | 0 | 0 | 0 | 0 |
| incoherent | 79 | 0 | 41 | 38 |
| ambiguous | 0 | 0 | 0 | 0 |
| empty | 7 | 0 | 3 | 4 |

| Category | Vector target switches | Random target switches | Other vector changes | Other random changes |
|---|---:|---:|---:|---:|
| Eligible records | 2 | 3 | 3 | 5 |
| ordinary_reasoning | 2 | 3 | 3 | 5 |
| explicit_outside_nudge_claim | 0 | 0 | 0 | 0 |
| incoherent | 0 | 0 | 0 | 0 |
| ambiguous | 0 | 0 | 0 | 0 |
| empty | 0 | 0 | 0 | 0 |

All quality flags, claim-channel counts, correct/incorrect-target strata, denominators and record IDs are in `summary.json`; `record_summary.csv` preserves every record.

The separate context-check record must accompany these primary-annotation counts. This script does not establish second-reader completion or adjudicate semantic disagreements.
