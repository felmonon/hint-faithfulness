# OpenAI judge results: 20-question pilot

Real calls to `openai:gpt-4.1-mini-2025-04-14` produced **9 accepted verdicts for 10 cases**, after **11 completed requests** including one unsuccessful identical-settings retry. Human validation is absent. Validated faithfulness stays null; machine-label fractions are provisional.

Read the [judge report](../../docs/OPENAI_JUDGE_REPORT.md) and [AI audit](ai-audit.md) before interpreting the numbers. Original90 is primary; composite100 overlaps it and adds two eligible cases.

| Artifact | Contents |
|---|---|
| [run-plan.json](run-plan.json) | Frozen judge identity, rubric, settings, source hashes, case list, and $2 cap |
| [initial-attempts.jsonl](initial-attempts.jsonl) | First ten responses, including the initial rejected quotation |
| [retry-plan.json](retry-plan.json) | One additional identical-settings attempt, declared before retry |
| [judgments.jsonl](judgments.jsonl) | Final state: nine accepted verdicts and the rejected retry, with raw API responses |
| [billing journal](judgments.jsonl.billing.jsonl) and [costs.json](costs.json) | Eleven settled requests; $0.0087728 usage-based estimate, not an invoice |
| [ai-audit.jsonl](ai-audit.jsonl) and [audit narrative](ai-audit.md) | Unblinded AI review of all ten cases; no human labels or corrected aggregate |
| [original90 analysis](original90/summary.json) and [chart](original90/phase1.png) | Eight accepted judgments; provisional positives: sycophancy1/2, metadata4/5, grader1/1 |
| [composite100 analysis](composite100/summary.json) and [chart](composite100/phase1.png) | Nine accepted judgments; positives:1/2,5/6,1/1; one metadata case unscored |
| [analysis-provenance.json](analysis-provenance.json) | Exact commands, source/input/output hashes, and no-validation declaration |

The original eight verdicts are reused in the composite; these are not eighteen independently judged cases. Combine the initial/current snapshots by `(record_id, attempt)`, not by counting every line. The latest failed-case cost includes its earlier attempt; costs.json avoids that duplication.

From the project root, regenerate the derived tables and charts locally:

```bash
python3 -m src.analyze --input artifacts/pilot-20-qwen3-1.7b/responses.jsonl --judgments results/pilot-20-openai-v1/judgments.jsonl --out-dir results/pilot-20-openai-v1/original90
python3 -m src.analyze --input artifacts/pilot-20-qwen3-1.7b/recovery-composite/responses.jsonl --judgments results/pilot-20-openai-v1/judgments.jsonl --out-dir results/pilot-20-openai-v1/composite100
```

These commands make no model calls and supply no human-validation artifact. They overwrite derived analysis files, not source responses or judge snapshots. Preserve the present output hashes before changing analysis code. For cost reproduction, sum unique-attempt input tokens ×0.40/1,000,000 plus output tokens ×1.60/1,000,000, then reconcile each request against reserve+settle in the journal.

The [original pilot report](../../docs/PILOT_REPORT.md) explains the ten lost original traces, separately regenerated trial slots, strict answer-format exclusions, and limitations of the underlying Qwen sample.
