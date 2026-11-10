"""Download a pinned MMLU test split and sample in subject-balanced rounds."""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from .common import LETTERS, stable_hash, utc_now, write_jsonl

DATASET_REVISION = "c30699e8356da336a370243923dbaf21066bb9fe"


def sample_questions(rows, count, seed=20261109):
    if count <= 0 or count > len(rows):
        raise ValueError("Count must be positive and no larger than the dataset")
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        groups[row["subject"]].append((index, row))
    subjects = sorted(groups)
    rng = random.Random(seed)
    rng.shuffle(subjects)
    for subject in subjects:
        rng.shuffle(groups[subject])
    selected = []
    # Round-robin gives each subject 2 or 3 questions for a 150-question run.
    # The first 20 cover 20 different subjects; expanding preserves all prior rows.
    for round_index in range(max(map(len, groups.values()))):
        for subject in subjects:
            if round_index >= len(groups[subject]):
                continue
            index, row = groups[subject][round_index]
            correct = LETTERS[int(row["answer"])]
            question_id = "mmlu-test-" + stable_hash({"subject": subject, "question": row["question"], "choices": row["choices"]})[:16]
            wrong_rng = random.Random(int(stable_hash([seed, question_id, "wrong-option"])[:16], 16))
            selected.append({
                "question_id": question_id, "subject": subject,
                "question": row["question"], "choices": list(row["choices"]),
                "correct_answer": correct,
                "hint_letter": wrong_rng.choice([x for x in LETTERS if x != correct]),
                "dataset": "cais/mmlu", "dataset_config": "all", "split": "test",
                "source_index": index, "sampling_seed": seed,
            })
            if len(selected) == count:
                if len({q['question_id'] for q in selected}) != count:
                    raise ValueError("Duplicate question content in sample; change sampling policy explicitly")
                return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=150)
    parser.add_argument("--seed", type=int, default=20261109)
    parser.add_argument("--revision", default=DATASET_REVISION)
    parser.add_argument("--output", default="data/questions.jsonl")
    args = parser.parse_args()
    if Path(args.output).exists():
        parser.error("Output already exists; choose a new path to preserve the frozen sample")
    from datasets import load_dataset
    dataset = load_dataset("cais/mmlu", "all", split="test", revision=args.revision)
    selected = sample_questions(dataset, args.count, args.seed)
    for row in selected:
        row["dataset_revision"] = args.revision
    write_jsonl(args.output, selected)
    manifest = {"created_at": utc_now(), "count": len(selected), "revision": args.revision,
                "seed": args.seed, "dataset": "cais/mmlu", "split": "test",
                "sample_sha256": stable_hash(selected),
                "subjects": dict(sorted(Counter(x["subject"] for x in selected).items())),
                "answer_counts": dict(Counter(x["correct_answer"] for x in selected)),
                "hint_counts": dict(Counter(x["hint_letter"] for x in selected))}
    Path(args.output + ".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Saved {len(selected)} questions across {len(manifest['subjects'])} subjects to {args.output}")


if __name__ == "__main__":
    main()
