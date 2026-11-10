# Synthetic software check

![Uptake and faithfulness](phase1.png)

| Model / hint | Uptake | Paired spontaneous switch | Faithfulness | Switches |
| --- | --- | --- | --- | --- |
| synthetic/pipeline-test / sycophancy | 50.0% (10/20) | 5.0% (1/20) | Pending / not estimable | 10 |
| synthetic/pipeline-test / metadata | 70.0% (14/20) | 5.0% (1/20) | Pending / not estimable | 14 |
| synthetic/pipeline-test / grader_hacking | 90.0% (18/20) | 5.0% (1/20) | Pending / not estimable | 18 |

The plotted uptake uses the same questions as directional noise. The table's uptake uses every valid baseline/hint pair. Exact intervals and all exclusions are in summary.json.

- Synthetic data verify software only; they are not experimental results.
- Rates exclude errors, truncation and invalid final answers; attrition is reported.
- Missing reasoning is unknown, never an unfaithful label.
- Uptake and directional noise are directly comparable on the paired subset.
- Faithfulness is hidden until all switches are labeled and held-out validation passes.
- Wilson intervals are marginal; paired bootstrap describes the uptake-noise difference.
- High early-answer or probe agreement alone cannot establish a decision was settled.

## Example traces

No validated unacknowledged switches are available yet. No examples have been invented.
