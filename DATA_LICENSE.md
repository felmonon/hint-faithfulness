# Data provenance and licensing

## MMLU questions

`data/questions.jsonl` contains a 150-question subset of the test split from [cais/mmlu on Hugging Face](https://huggingface.co/datasets/cais/mmlu). The source dataset card identifies its license as MIT. The original [hendrycks/test repository license](https://github.com/hendrycks/test/blob/master/LICENSE) is the MIT License, copyright 2020 Dan Hendrycks. Its notice is preserved verbatim in [third_party/MMLU_LICENSE.txt](third_party/MMLU_LICENSE.txt).

The source revision is `c30699e8356da336a370243923dbaf21066bb9fe`. The dataset manifest records selection, subject distribution, seed, and canonical sample hash. The project adds question IDs and assigned incorrect hint letters; it does not claim authorship of the underlying questions.

Please cite the original MMLU work when using the questions: [Measuring Massive Multitask Language Understanding](https://arxiv.org/abs/2009.03300), Hendrycks and colleagues, published at ICLR 2021. Attribution to this implementation is additional to, not a replacement for, attribution to MMLU.

## Generated experiment artifacts

Model response records, judgment files, and reports are separate from the source questions. They retain source question IDs and model provenance. Their presence is not evidence that an API provider or model author endorses this work. The original model's license and any relevant API terms remain separate from the MMLU license.

`data/demo/` and `results/demo/` contain software fixtures explicitly identified as synthetic. They are not model experiment observations. Human labels, if later supplied, must retain their actual provenance.

## Project code

The MMLU MIT notice applies to the upstream material; it does not by itself assign a license to this project's original code, documentation, or newly generated artifacts. Any repository-level license chosen by the maintainer governs those original components separately. Preserve upstream notices when redistributing the sample.
