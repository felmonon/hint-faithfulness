# Raw-record loss and a fixed recovery plan

Recorded at 2026-11-10 01:57 UTC, during the original collection and before any recovery generation. This is a post-start protocol deviation, not a preregistration of the original experiment.

## Observed discrepancy

The collection log recorded 33 completed attempts while a direct terminal read found 23 unique response rows. Ten completed trial slots were absent. Their ordinals coincide with two periods when the live JSONL was opened in Colab's file editor for inspection. Stale editor saving is a possible cause, but it has not been established. There were no deliberate raw-data edits. The editor has been closed, and further checks use the terminal rather than opening the live response file in an editor.

A timestamped copy of the partial response file, the partial collection log, and a machine-readable discrepancy audit was saved in the run's `recovery/` directory. The original collection continues with the same code, checkpoint, prompts, seeds, decoding settings, and planned trial order. No response has yet been regenerated under this recovery plan.

## Missing slots fixed before recovery

Ordinals refer to the frozen, seeded 100-trial order. The list below was reconstructed from the original design and compared with saved record IDs. It does not select cases according to whether a hint worked.

| Original ordinal | Record ID | Question ID | Condition | Baseline repeat | Seed |
|---:|---|---|---|---:|---:|
| 9 | 56eb54c340a8fab1fdc084f8 | mmlu-test-0f51211333c17165 | none | 0 | 1024990475 |
| 10 | 9401acc6eb1ba91c6fd0f593 | mmlu-test-8b4f293c1edb7375 | grader_hacking | — | 569702602 |
| 11 | 72b0eb898a913ea07c61bf45 | mmlu-test-e3ab4dd2cecf9d2b | none | 0 | 1983849706 |
| 12 | 1e7982bf8dd33ea4edb4b098 | mmlu-test-0cb9c2dea70b4fc0 | none | 0 | 312206386 |
| 13 | 21c4733d63a33222e277ca87 | mmlu-test-832083e11f4100df | metadata | — | 1032810747 |
| 14 | c7aca6252fe59b3745dba582 | mmlu-test-b52f3c79d8bc9171 | sycophancy | — | 1025473198 |
| 15 | e82036ed9c984233febd9438 | mmlu-test-2d952f29adab145f | grader_hacking | — | 353586365 |
| 16 | 3655610b6c73cdb9613c2b14 | mmlu-test-8b4f293c1edb7375 | none | 0 | 537672015 |
| 25 | d2f3a52213ca8cda500eb816 | mmlu-test-ffa1ffbde5071c93 | sycophancy | — | 849685368 |
| 26 | 30fa7eb2bc600f9270a4a4e0 | mmlu-test-734e02d9073e986d | none | 1 | 282530575 |

## Preservation and recovery rule

1. Let the original 100-attempt collection finish. Preserve its response file, log, manifests, and runtime metadata unchanged, including all retained invalid or truncated responses. Verify the actual final missing-ID set before replay; document any additional discrepancy separately rather than silently expanding this list.
2. Analyze the retained original records first. Count absent slots explicitly. Their absence limits paired comparisons and is not proven independent of response behavior.
3. Create a separately named recovery composite by copying the retained original records and their runner manifest. Use the frozen collection source, model revision, GPU precision, prompts, and original per-trial seeds to generate only the ten missing slots. The resumable runner skips every retained record, including failures. Retain a separate recovery log and runtime record.
4. Verify that all copied original records are unchanged, every regenerated ID belongs to this fixed list, and the composite contains each planned slot once. Keep a lineage manifest identifying each row as retained original or recovery generation. A reused seed does not prove that a regenerated response equals the lost response.
5. Publish original-only estimates as the primary integrity record and the completed composite as a separate recovery analysis. Apply the frozen strict parser to both. The previously specified formatting diagnostic, if run, remains another explicitly post hoc analysis and cannot redefine either raw dataset.

Report planned slots, original generation attempts, retained original rows, recovery generation attempts, and composite rows separately. If the final loss remains ten rows, completing 100 unique slots will require 110 generation attempts in total. No missing original text, token IDs, timestamps, or human labels may be reconstructed from guesses. The progress log preserves original statuses but cannot replace lost full responses.

The pilot can still document engineering behavior and descriptive outcomes. It must not be presented as an uninterrupted, intact 100-response original run. Human validation and any broader faithfulness conclusion remain separate requirements.
