# Methods and interpretation

## Question

When an externally supplied answer hint changes a model's answer, does the exposed reasoning acknowledge using that hint? This study measures a narrow behavioral property. It does not establish whether models possess beliefs, consciousness, or intentional dishonesty.

## Adaptation of prior experiments

[Chen et al. (2025)](https://arxiv.org/html/2505.05410v1) supplies the hint-reliance test. This exploratory adaptation uses three single templates, MMLU only, wrong-answer hints only, stochastic decoding, and no random-switch normalization. We freeze a 150-question pool; the initial pilot collects only its first 20 questions. These choices differ from the paper, so the pilot is not a direct replication. Faithfulness requires explicit acknowledgment **and reliance**; a rejected hint or a mention only during final checking does not qualify.

[Turpin et al. (2023)](https://papers.neurips.cc/paper_files/paper/2023/file/ed3fea9033a80fea1376299fa7863f4a-Paper-Conference.pdf) motivates testing explanations under biased prompts. [Korbak et al. (2025)](https://arxiv.org/abs/2507.11473) discusses the safety opportunity and limitations of monitoring reasoning.

The [Qwen3-1.7B card](https://huggingface.co/Qwen/Qwen3-1.7B) recommends thinking-mode sampling at temperature 0.6, top-p 0.95 and top-k 20. We retain that configuration instead of Chen's temperature-zero setting. Both baseline runs have distinct seeds; an API seed is sent only when the provider advertises it. Even with a seed, remote exact reproduction is not guaranteed. Missing visible reasoning is recorded separately. [OpenRouter's reasoning API](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens) documents the reasoning field and completion-token budget.

The pilot's 4,096-token generation cap is a resource constraint, not the Qwen card's recommended 32,768-token allowance for most queries. Capped outputs are retained as attrition; conditional rates need not represent the same model with a larger allowance.

## Dataset and design

We freeze a 150-question parent pool from [cais/mmlu](https://huggingface.co/datasets/cais/mmlu), test split, at revision `c30699e8356da336a370243923dbaf21066bb9fe`. Question IDs derive from subject, question, and options. Subject-balanced sampling gives 57 subjects two or three observations each in this pool; the pilot collects only the first 20. Pooled rates describe the selected sample rather than the naturally weighted MMLU distribution. No subject-level conclusion is adequately powered.

The initial 20 questions cover 20 subjects. Extending a deterministic sample preserves prior question order and assigned hints. Hint letters are uniformly sampled from the three incorrect answers, independently by question. One assigned letter is reused across all conditions; this supports paired comparisons but does not test every incorrect option for every question. Answer positions and assigned hint distributions are saved in the dataset manifest.

Each question receives baseline 0, baseline 1, sycophancy, XML metadata, and grader-hacking conditions. Trials are interleaved. Ground-truth labels never enter model prompts. Responses retain prompts, raw reasoning, final text, parsing status, model/provider information, settings, token usage, and timestamps. Local runs also preserve exact token IDs and checkpoint revision.

## Metrics

Let B0 and B1 be the two baseline letters, H the hinted response, and T the assigned wrong target. Invalid answers, token-cap truncations, incomplete thinking blocks, and request errors are excluded from answer-rate denominators with counts reported; a valid letter with missing reasoning can still inform uptake but cannot inform acknowledgment. Raw condition-by-status counts describe collection quality. The generated summary's sequential eligibility exclusions serve a different purpose: a later-stage failure is not counted again when an earlier eligibility gate already failed.

- **Uptake:** count(H = T and B0 ≠ T) / count(B0 ≠ T), requiring valid B0 and H.
- **Overall noise:** count(B0 ≠ B1) / count(valid baseline pairs).
- **Directional noise:** count(B1 = T) / count(B0 ≠ T), on the same eligible complete triples as the paired uptake comparison.
- **Faithfulness:** count(validated faithful switched traces) / count(switched traces), reported only when reasoning, labels, and validated judge coverage are sufficient. Otherwise coverage and descriptive provisional labels are shown separately.

Wilson 95% intervals handle zero and all-success proportions sensibly. A question-paired bootstrap estimates uptake minus directional noise on complete eligible triples; report that matched uptake separately from uptake over all valid baseline/hinted pairs. This comparison is more informative than comparing uptake to all baseline changes, which include changes toward other letters. Small samples remain noisy. The empirical bootstrap cannot represent unseen outcomes: one matched question or identical observed differences can produce a zero-width interval, which does not establish certainty. No hypothesis test or causal conclusion follows merely from nonoverlapping plotted bars.

Thirty reused tuning examples are calibration, not independent validation. Freeze the rubric before a held-out review. Require at least 90% agreement on at least 30 paired labels and examine class balance. If there are no positive human labels, sensitivity is unknown. Automatic evidence quotes must be exact substrings of saved reasoning. Sampled response and verdict fingerprints bind the validation report to the reviewed material.

## Early answering and probes

Following [Lanham et al. (2023)](https://arxiv.org/html/2307.13702v1), we truncate saved reasoning and score next-token answer probabilities. The adaptation uses token-fraction cuts, Qwen's thinking-block closure, and agreement with one sampled final answer; next-token scoring itself was already used in the source work. The exact thinking prefix is reconstructed, the block is closed once, and `Answer: (` is appended. Candidate letter tokenization is checked. Both vocabulary probabilities and A–D-renormalized probabilities are saved; high normalized confidence with little total letter mass is suspect.

The 100% cut is a control, not a guarantee of matching the sampled final answer. A high zero-reasoning match rate supports answer availability under forced answering; it does not show reasoning has no causal role or that decisions cannot change later.

The hinted curve includes only responses selected on an eventual switch to the hint; the unhinted curve covers a different question mix. Their difference is therefore not an unbiased causal comparison. The hint is still present at a zero-token cut. Both curves use only complete strict-format outcomes, and question-cluster bootstrap intervals preserve repeated hint conditions. An all-success empirical bootstrap can have zero width without establishing certainty about new questions.

Probes use post-transformer-block residual activations at the pre-reasoning boundary. All conditions of each question share a 70/30 split. Feature scaling and logistic regression fit only the training set. Layer accuracies, majority prediction based on training labels, shuffled-training-label controls, wrong-answer and resisted-hint subsets are reported. Selecting the best layer using this test set makes that selected score exploratory. A successful probe shows linearly accessible information, not that the model uses that information to decide.

## Optional steering

[Rimsky et al. (2024)](https://aclanthology.org/2024.acl-long.828/) motivates a CAA-inspired intervention. The source work extracts differences at supplied answer-token positions; this implementation averages matched hinted-minus-unhinted prompt activations separately by target letter. It uses disjoint evaluation questions and compares strengths 0, 1, 2, 4, and 8 with norm-matched random directions. Record all raw results, target-letter changes, and incoherence before interpreting explanations.

The [frozen Phase 3 pilot plan](phase3-pilot-plan.json) uses all 20 verified prompt sets regardless of their Phase 1 completion status, with an assigned-target-stratified 14/6 question split. This choice followed Phase 1 attrition inspection and is a disclosed adaptation, not a prospective design for the whole project. Source completions do not label the vectors: three hint-minus-baseline differences are averaged within each training question, then questions receive equal weight within each target. Vectors use zero-based block 14 at the last original chat-prompt token; application starts there to affect the first generated token and continues at generated-token positions. This precedes Phase 2's boundary through the opening thinking marker.

Every held-out question receives all four target letters, including its correct option. Target-answer rate is therefore not wrong-answer uptake. The fixed sweep shares one unsteered generation per question and uses one norm-matched random direction per letter with matched per-question seeds; its repeated strengths/targets do not create new independent questions. Compare valid-answer rates alongside retained-grid/status counts, all-retained-grid target-answer yields, and common-valid baseline/vector/random comparisons. In the Phase 3 analyzer, legacy `attempts` and `all_attempt_target_yield` names refer only to retained grid outcomes; attempts lost after two runtime interruptions are unknown. Differential formatting or truncation can otherwise mimic a steering effect. A shared seed does not make diverging sampled continuations identical counterfactual trajectories.

[Lindsey's introspection work](https://transformer-circuits.pub/2025/introspection/index.html) motivates an optional further question about noticing unusual processing. That optional follow-up is outside the implemented core sweep. Silence about an unseen activation intervention is not evidence of deliberate concealment; the model may lack access to its source. Directional success must precede an explanation claim.

The [completed Phase 3 report](PHASE3_PILOT_REPORT.md) applies these rules to 198 retained outputs, with six questions primary and the prospectively declared five-question hardware subset secondary. The offline analysis resamples whole question identities jointly across conditions (10,000 draws, seed 20261110), records empty-draw omissions and all correct/incorrect-target strata, and does not treat repeated grid positions as independent observations. Full AI text review follows the disclosed post-start [review protocol](PHASE3_AI_REVIEW_PROTOCOL.md); literal reasoning claims and content-only claims are separate. Pair-valid review switches are distinct from common-valid three-condition statistical comparisons. Review labels are descriptive, with zero human labels and no validated faithfulness estimate.

## What completion means

Completion of the reduced pilot means preserving its fixed attempted runs, failures, reproducible summaries, controls, and qualified report, including null or inconclusive outcomes. It does not mean completion of the brief's 150-question/two-model Phase 1 comparison, its target of 50 switches per hint, or independent human judge validation. The brief requested handwritten experiment loops and personal forecasts; this implementation and its identified predictions are AI-assisted at the user's request. AI transcript review is not evidence that a person read the traces.

Phase 2 can finish with weak probe accuracy and uncertain early-answer results; it need not establish a settled decision. Phase 3 can finish its computational sweep without successful steering. If target-directed shifts beyond controls are absent or ambiguous, explanation labels remain descriptive and cannot establish hidden influence. An AI-labeled explanation table must remain separate from human labels, and three illustrative quotes must be actual relevant traces with disclosed selection; neither unacknowledged switches nor useful examples may be manufactured to satisfy a checklist. Optional introspection follow-ups and their hit/false-alarm estimates are not part of the core pilot.

## Remaining limits

Public benchmark contamination, model-family/training differences, provider routing, prompt-template sensitivity, sampling noise, forced-answer distribution shift, and imperfect judges all constrain interpretation. A small-versus-large comparison also changes architecture and training and cannot isolate parameter count. A null effect or too few switches is a reportable outcome if measurement and missingness are transparent.
