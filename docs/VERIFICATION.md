# What was actually verified

Prepared November 9, 2026, America/Edmonton.

## Completed

- Downloaded the pinned `cais/mmlu` dataset and saved **150 unique questions across 57 subjects**, with two or three questions per subject, fixed wrong hints, and a reproducibility manifest.
- Checked the public model catalog. The selected large model and low-cost judge were present; the two proposed small models were absent. See `environment.json` for model IDs, listed prices, package versions, and environment capabilities.
- Ran `python3 -m unittest discover -s tests -q`: **39 tests passed**. These check denominators, uncertainty, incomplete responses, label validation, question-level train/test separation, token cuts, residual and steering hooks, artifact serialization, and durable billing recovery.
- Ran the complete synthetic Phase 1 pilot: 20 questions × five conditions = **100 explicitly synthetic responses**. Rerunning found zero remaining requests and preserved the records. Analysis generated a chart/report; review export produced 30 blank label rows.
- Inspected the generated demonstration chart. Its title explicitly says synthetic software check; faithfulness remains pending because no human validation exists.
- Loaded the **real pinned Qwen3 tokenizer**, without downloading pretrained weights. Thinking delimiters and A–D are single tokens. Tested the local adapter with an actual Qwen3 architecture using **tiny random weights**; four-token generation completed and was correctly classified as truncated. This caught and fixed a Transformers 5 return-type incompatibility.
- Ran synthetic end-to-end Phase 2 checks with 24 fixture records and three artificial activation layers. Early-answer/probe tables, arrays, manifests, and plots serialized successfully; temporary fixture outputs were removed. See `PHASE2_3_VERIFICATION.md`.
- Parsed the four Colab notebooks and compiled their Python cells with notebook shell lines handled separately. Saved notebook outputs are empty.

## Still pending

- **Pretrained model inference:** no real Qwen or DeepSeek study run has been performed. This host has 8 GB shared memory and no CUDA GPU. Colab notebooks are supplied for the half-precision GPU run; actual Colab execution and full checkpoint memory behavior remain untested.
- **API execution:** `OPENROUTER_API_KEY` is not configured here. No paid inference or judge calls were made. HTTP behavior, budget limits, and interrupted-request recovery were tested with simulated responses; live provider behavior still needs a pilot.
- **Human work:** personal predictions, pilot transcript review, and at least 30 actual blind labels. Blank labels are intentional. A tuned judge needs a separate held-out check.
- **Scientific deliverables:** real uptake/faithfulness charts, three supported examples, early-answer/probe findings, optional steering findings, and a final public write-up. The template and demonstration are not substitutes for those results.

The implementation is ready for live validation. The research conclusions are not yet available. No external publishing, social posting, or calendar scheduling occurred.
