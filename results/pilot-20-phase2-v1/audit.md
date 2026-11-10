# Independent Phase 2 artifact audit

AI-assisted saved-artifact audit by `/root/method_review`, 2026-11-10. This is a separate numeric and code review, not human validation or an independent model run. Frozen run: `66788e3444a43f1cc87422313ad6b1f7b72a6114`. Full evidence, source hashes, question IDs, all layer curves, and tolerances are in [audit.json](audit.json).

**Result: all checked saved calculations reproduce; no split or prefix leakage was found.** The saved plan equals `docs/phase2-pilot-plan.json`; current `src/phase2.py` equals the frozen source. All 20 entries in the run checksum file and both source-data hashes match. Raw artifacts were unchanged.

## Selection and probe inputs

| Check | Original 90, primary | Composite 100, sensitivity |
|---|---:|---:|
| Strictly eligible examples | 54 | 61 |
| Eligible questions | 19 | 19 |
| Train examples / questions | 34 / 13 | 40 / 13 |
| Test examples / questions | 20 / 6 | 21 / 6 |
| Residual array shape | 54 × 28 × 2,048 | 61 × 28 × 2,048 |
| Saved prediction rows | 560 | 588 |

Every NPZ index is unique, in range, and part of a complete train/test partition; no question crosses the split. Both splits contain all four answer classes. The seeded question split, selected record order, labels, and manifests reproduce exactly. The estimator fits scaling and labels on training examples only, including its shuffled-label control.

All stored residual values are finite float32 values exactly representable in float16. Hooks capture each decoder block's last-token output, before the final normalization. Re-tokenization using the pinned, locally cached Qwen tokenizer matches every selected saved prompt. Every probe prefix contains that prompt plus only the opening `<think>` token: no substantive generated reasoning or final answer. Prompt hints and answer options remain legitimate but potentially predictive input features.

## Recomputed early-answering curves

Each cell reports matches to the trace's sampled final answer, not accuracy against the correct answer. Fractions refer to retained reasoning tokens.

| Cohort and selected group | 0% | 25% | 50% | 75% | 100% |
|---|---:|---:|---:|---:|---:|
| Original, unhinted: 10 traces / 10 questions | 5/10 | 8/10 | 9/10 | 9/10 | 10/10 |
| Original, hinted switches: 8 traces / 5 questions | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| Composite, unhinted: 14 traces / 14 questions | 9/14 | 12/14 | 13/14 | 13/14 | 14/14 |
| Composite, hinted switches: 10 traces / 7 questions | 9/10 | 9/10 | 10/10 | 9/10 | 10/10 |

All 210 fraction rows have the expected token cuts, argmax predictions, and match flags. All 20 summary rows and their 1,000-draw question-cluster bootstrap intervals reproduce within 1e-12. Candidate probabilities are finite and bounded; total A–D probability mass is at least 0.999998034. Reported masses exceed one in some rows by at most 8.97e-8, consistent with float32 summation roundoff. Conditional probabilities agree with renormalized full-vocabulary probabilities within 8.97e-8; no raw values were adjusted.

## Probe reproduction and limits

Refitting the frozen estimator recipe reproduces **all 2,296 held-out predictions**, counting normal and shuffled-label models across both cohorts and 28 layers, with no fit warnings. All layer/subgroup counts, accuracies, majority controls, and question-bootstrap intervals also reproduce. Across layers, original probe accuracy is 25–30% versus shuffled 30–60%; composite accuracy is 19.0–28.6% versus shuffled 9.5–42.9%. These are descriptive ranges, not selected best-layer results or evidence of robust decoding. Both wrong-answer subsets contain nine examples over four questions; resisted-hint subsets contain eight examples over four questions.

The CPU refit uses scikit-learn 1.8.0 and SciPy 1.16.3, matching recorded versions, plus NumPy 2.2.6. Local Python, operating system, and Torch differ from the GPU run. Original runtime metadata lists both NumPy 1.26.4 and 2.2.6. Root separately reports that a read-only import check in the same Colab runtime at 04:18 UTC returned NumPy 2.2.6 and scikit-learn 1.8.0, with no intervening dependency installation. This is supplementary post-run evidence, not a change to the original metadata. No GPU forward pass was repeated; float32 storage cannot restore precision lost in float16 inference. Fitted coefficients were not saved, so prediction reproduction uses refitting.

Strict completion/parsing filters create selection limits. Hinted switches are selected using observed outcomes and cover a different question mix, so their early-answering curve cannot be treated as a randomized causal contrast. Only six test questions and one shuffled control support the probe comparisons; bootstrap intervals condition on this fit and selected cohort. Decoding a sampled answer would not establish a settled internal decision or dishonesty.

All 54 shared residual arrays and all 90 shared early-answering rows are exactly equal across cohorts. The composite is overlapping recovery sensitivity analysis, not an independent replication.
