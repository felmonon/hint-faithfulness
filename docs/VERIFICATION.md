# What was actually verified

Prepared November 9, 2026, America/Edmonton.

## Completed

- Downloaded the pinned `cais/mmlu` dataset and saved **150 unique questions across 57 subjects**, with two or three questions per subject, fixed wrong hints, and a reproducibility manifest.
- Checked the public model catalog. The selected large model and low-cost judge were present; the two proposed small models were absent. See `environment.json` for model IDs, listed prices, package versions, and environment capabilities.
- Ran `python3.12 -m unittest discover -s tests -q`: **73 tests passed** after the direct OpenAI judge, artifact audit, and separate post hoc format diagnostic were added. These check denominators, uncertainty, incomplete responses, label validation, question-level train/test separation, token cuts, residual and steering hooks, artifact serialization, durable billing recovery, backend identity after interruptions, frozen-pilot integrity, and conservative format recovery without modifying original evidence.
- Ran the complete synthetic Phase 1 pilot: 20 questions × five conditions = **100 explicitly synthetic responses**. Rerunning found zero remaining requests and preserved the records. Analysis generated a chart/report; review export produced 30 blank label rows.
- Inspected the generated demonstration chart. Its title explicitly says synthetic software check; faithfulness remains pending because no human validation exists.
- Loaded the **real pinned Qwen3 tokenizer**, without downloading pretrained weights. Thinking delimiters and A–D are single tokens. Tested the local adapter with an actual Qwen3 architecture using **tiny random weights**; four-token generation completed and was correctly classified as truncated. This caught and fixed a Transformers 5 return-type incompatibility.
- Ran synthetic end-to-end Phase 2 checks with 24 fixture records and three artificial activation layers. Early-answer/probe tables, arrays, manifests, and plots serialized successfully; temporary fixture outputs were removed. See `PHASE2_3_VERIFICATION.md`.
- Parsed the Colab notebooks and compiled their Python cells with notebook shell lines handled separately. Published notebook outputs are empty.
- Launched the real 20-question Qwen pilot on a Colab Tesla T4 using frozen source `fe4de16013bf9e3e9a9d66abd5b47401becbe24a`. Colab setup checks passed and real response collection began. Completion and final artifact verification are still pending.

## Still pending

- **Completed pretrained-model pilot:** Qwen collection is in progress on Colab. Final response counts, transcript review, and the full evidence archive must be verified before reporting completion. DeepSeek inference has not been performed. The setup Mac has 8 GB shared memory and no CUDA GPU; it is not the collection machine.
- **API execution:** `OPENROUTER_API_KEY` is not configured here. No paid inference or judge calls were made. HTTP behavior, budget limits, and interrupted-request recovery were tested with simulated responses; live provider behavior still needs a pilot.
- **Human work:** personal predictions, pilot transcript review, and at least 30 actual blind labels. Blank labels are intentional. A tuned judge needs a separate held-out check.
- **Scientific deliverables:** real uptake/faithfulness charts, three supported examples, early-answer/probe findings, optional steering findings, and a final public write-up. The template and demonstration are not substitutes for those results.

The public code repository is [felmonon/hint-faithfulness](https://github.com/felmonon/hint-faithfulness). Research conclusions remain pending the completed evidence and appropriate validation. No social posting or calendar scheduling occurred.
