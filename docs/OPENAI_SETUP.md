# OpenAI as the judge

OpenAI labels the reasoning text saved from the open-model experiment. It is **not** a substitute experimental subject: the OpenAI API does not expose its raw reasoning tokens. Reasoning summaries cannot be scored as if they were the full underlying trace. [Official reasoning documentation](https://developers.openai.com/api/docs/guides/reasoning)

## Access and model

Create the project key through the secure OpenAI Platform setup flow, save it only to the explicitly confirmed private destination, and expose it to the judging process as `OPENAI_API_KEY`. The code does not create keys, read unrelated credential stores, or print the key. In Colab, retrieve it from an authorized Colab Secret into the environment; never include its value in a cell, notebook output, repository, or raw results. An OpenAI key does not authenticate OpenRouter.

This pilot uses the fixed snapshot **`gpt-4.1-mini-2025-04-14`** as a low-cost judge without a separate reasoning step. The documented standard price checked November 9, 2026 is **$0.40 per million input tokens and $1.60 per million output tokens**. The model is deprecated and scheduled to shut down **January 14, 2027**. It is still listed before that date, but actual access must be tested with the project key. The implementation refuses unpriced models and never silently replaces the judge. If migration becomes necessary, record a new judge identity, rerun calibration, and perform fresh held-out validation. [Model and pricing](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [shutdown schedule](https://developers.openai.com/api/docs/deprecations)

## Run after real collection

With the key privately configured in the process environment:

```bash
python -m src.judge run \
  --backend openai \
  --model gpt-4.1-mini-2025-04-14 \
  --input artifacts/pilot-20-qwen3-1.7b/responses.jsonl \
  --output artifacts/pilot-20-qwen3-1.7b/judgments-openai.jsonl \
  --budget-usd 2 --limit 5
```

Inspect the first five machine verdicts for response format and exact evidence matching. Then repeat without `--limit 5` to judge all eligible switches. This does not enter or replace any human labels. The validation procedure in [LABELING.md](LABELING.md) is still required; the pilot may contain fewer than 30 switches, in which case the requested held-out threshold cannot yet be met.

Judgments use an identity such as `openai:gpt-4.1-mini-2025-04-14`; OpenRouter identities use `openrouter:<model-id>`. Reusing an output file with another backend, model, or rubric is rejected. Legacy machine-verdict files without qualified identities should be preserved and replaced by a separately documented new run, not silently mixed.

## Request, billing, and reproducibility

The adapter calls `POST /v1/responses` with the pinned model, `store: false`, standard service tier, temperature 0, an 800-token default output limit, and a strict JSON schema for the five rubric fields. The validator independently checks booleans and exact evidence substrings. Refusals and incomplete responses are errors, never unfaithful labels. `store: false` disables storage for later response retrieval; it is not a claim of zero retention under all account policies. [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)

The local $2 guard reserves a conservative estimated charge before each call. A neighboring `.billing.jsonl` durably saves reservations and completed responses. Keep it with the verdict file during transfer or resumption. An interrupted call remains reserved and blocks retries until its charge is reconciled; a saved completion is reused if the caller stopped before writing the verdict. Use one writer per output file. Estimates use the documented token rates and intentionally ignore cached-input discounts; the journal is not an account-wide provider-enforced spending cap.

The raw response, exact request parameters, token usage, backend/model identity, and rubric hash are saved. No credentials are saved. Automated tests use mock HTTP responses only. No live OpenAI request or scientific judge validation is implied by those tests.
