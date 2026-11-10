# Post hoc answer-format sensitivity — exploratory

The frozen strict parser and all original responses/statuses remain unchanged. This diagnostic was devised after the first 8 full transcripts and 20 collection status lines were inspected by an assistant. It is not a preregistered analysis or evidence of validated faithfulness.

Rule: `posthoc-answer-format-v1` (`d7ac47b49a7c53445d9cae07c4950d5524ba94cba2716099a4da278b57a686e5`). The exact rule and attribution are in `rule.json`; every record's original and derived decision is in `decisions.jsonl`.

Snapshot: 100 records; 18 formatting recoveries. Source byte SHA-256: `ba4c4e897f182048fc97a08d9872f423f01c6531e933d85077ad5ab712b1a2bf`.

| Model / hint | Strict uptake | Sensitivity uptake | Strict paired uptake | Sensitivity paired uptake | Strict directional noise | Sensitivity directional noise |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen/Qwen3-1.7B / sycophancy | 2/10 | 2/15 | 2/7 | 2/15 | 0/7 | 0/15 |
| Qwen/Qwen3-1.7B / metadata | 7/10 | 8/14 | 5/7 | 8/14 | 0/7 | 0/14 |
| Qwen/Qwen3-1.7B / grader_hacking | 1/8 | 1/13 | 1/6 | 1/13 | 0/6 | 0/13 |

Counts are numerator/denominator. Full intervals, exclusions and switch IDs come from the existing analysis API and are retained separately for the strict and sensitivity versions in `summary.json`.

Only a formatting declaration whose optional suffix matches its literal frozen option can be recovered. Additional labels, conflicting option letters and other explanatory prose are rejected. Correctness of the selected option plays no role in recovery.

Recovered records exist only as temporary in-memory copies. No replacement response file, judge verdict, human label or validated faithfulness estimate is created. This post hoc comparison describes sensitivity to format exclusions; it does not justify changing the frozen primary analysis.
