"""Phase 2 v2: early answering on every valid response, and grouped-CV probes.

python -m src.phase2_v2 all          # early + acts (GPU) then probe (CPU)
python -m src.phase2_v2 probe        # CPU only, from saved activation shards
Outputs under artifacts/v2/phase2/.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .common import LETTERS, append_jsonl, read_jsonl, utc_now

RESPONSES = Path("artifacts/v2/phase1/responses.jsonl")
OUT = Path("artifacts/v2/phase2")
FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)
SEED, FOLDS, SHUFFLES, C = 20261111, 5, 100, 0.1
SHARD_LAYERS = 7


def valid_rows():
    rows = read_jsonl(RESPONSES)
    return [r for r in rows if r.get("status") == "ok" and r.get("answer") in list(LETTERS)]


def load_local():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from .gen_v2 import MODEL, REVISION

    class Local:
        pass
    local = Local()
    local.tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
    local.model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REVISION, torch_dtype=torch.float16).to("cuda").eval()
    local.device = torch.device("cuda")
    return local


def run_early(local, rows):
    from .phase2 import candidate_probabilities, cut_input
    path = OUT / "early.jsonl"
    done = {(r["record_id"], r["fraction"]) for r in read_jsonl(path)}
    for index, row in enumerate(rows, 1):
        for fraction in FRACTIONS:
            if (row["record_id"], fraction) in done:
                continue
            base = {"record_id": row["record_id"], "question_id": row["question_id"], "hint_type": row["hint_type"],
                    "baseline_repeat": row.get("baseline_repeat"), "hint_letter": row["hint_letter"],
                    "final_answer": row["answer"], "fraction": fraction}
            try:
                ids, kept, total = cut_input(row, local.tokenizer, fraction)
                raw, normalized = candidate_probabilities(local, ids)
                forced = max(normalized, key=normalized.get)
                append_jsonl(path, {**base, "status": "ok", "kept_tokens": kept, "reasoning_tokens": total,
                                    "probs_raw": raw, "probs": normalized, "forced_answer": forced})
            except ValueError as error:
                append_jsonl(path, {**base, "status": "error", "error": str(error)})
        if index % 50 == 0:
            print(f"early {index}/{len(rows)}", flush=True)


def probe_rows(rows):
    # Baseline repeat 1 is a repeat of the same prompt; keep repeat 0 plus hinted.
    return [r for r in rows if r["hint_type"] != "none" or r.get("baseline_repeat") == 0]


def run_acts(local, rows):
    from .phase2 import capture_residuals, thinking_layout
    meta_path = OUT / "probe_meta.json"
    if meta_path.exists():
        return
    rows = probe_rows(rows)
    acts = []
    for row in rows:
        prefix, _, _ = thinking_layout(row, local.tokenizer)
        acts.append(capture_residuals(local, prefix).astype(np.float16))
    acts = np.stack(acts)
    for start in range(0, acts.shape[1], SHARD_LAYERS):
        np.savez_compressed(OUT / f"probe_acts_layers_{start:02d}-{min(start + SHARD_LAYERS, acts.shape[1]) - 1:02d}.npz",
                            acts=acts[:, start:start + SHARD_LAYERS], first_layer=start)
    meta_path.write_text(json.dumps({"rows": [{"record_id": r["record_id"], "question_id": r["question_id"],
        "hint_type": r["hint_type"], "hint_letter": r["hint_letter"], "answer": r["answer"]} for r in rows],
        "shape": list(acts.shape), "position": "last token of prompt + generated <think> (before any reasoning)",
        "dtype": "float16", "created_at": utc_now()}) + "\n")


def load_probe_acts():
    shards = sorted(OUT.glob("probe_acts_layers_*.npz"))
    return np.concatenate([np.load(s)["acts"] for s in shards], axis=1).astype(np.float32)


def fold_predictions(x, y, groups):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    pred = np.empty(len(y), dtype=object)
    majority = np.empty(len(y), dtype=object)
    folds = np.empty(len(y), dtype=int)
    for k, (train, test) in enumerate(GroupKFold(FOLDS).split(x, y, groups)):
        clf = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=2000))
        clf.fit(x[train], y[train])
        pred[test] = clf.predict(x[test])
        values, counts = np.unique(y[train], return_counts=True)
        majority[test] = values[np.argmax(counts)]
        folds[test] = k
    return pred, majority, folds


def run_probe():
    from joblib import Parallel, delayed
    meta = json.loads((OUT / "probe_meta.json").read_text())
    x = load_probe_acts()
    y = np.array([r["answer"] for r in meta["rows"]])
    groups = np.array([r["question_id"] for r in meta["rows"]])
    n_layers = x.shape[1]
    observed = Parallel(n_jobs=-1)(delayed(fold_predictions)(x[:, layer], y, groups) for layer in range(n_layers))
    rng = np.random.default_rng(SEED)
    perms = [rng.permutation(len(y)) for _ in range(SHUFFLES)]

    def perm_acc(layer, order):
        pred, _, _ = fold_predictions(x[:, layer], y[order], groups)
        return float((pred == y[order]).mean())
    null = Parallel(n_jobs=-1)(delayed(perm_acc)(layer, order) for order in perms for layer in range(n_layers))
    null = np.array(null).reshape(SHUFFLES, n_layers)
    with (OUT / "probe_predictions.jsonl").open("w") as handle:
        for layer, (pred, majority, folds) in enumerate(observed):
            for i, row in enumerate(meta["rows"]):
                handle.write(json.dumps({"layer": layer, "record_id": row["record_id"], "question_id": row["question_id"],
                                         "fold": int(folds[i]), "label": y[i], "pred": pred[i],
                                         "majority_pred": majority[i]}) + "\n")
    np.savez(OUT / "probe_permutation_null.npz", null_accuracy=null, seed=SEED, shuffles=SHUFFLES)
    (OUT / "probe_config.json").write_text(json.dumps({"folds": FOLDS, "cv": "GroupKFold by question_id",
        "model": f"StandardScaler + LogisticRegression(C={C}, lbfgs, max_iter=2000)", "target": "final answer letter",
        "shuffles": SHUFFLES, "permutation": "labels permuted across rows, same grouped folds", "seed": SEED,
        "n_rows": int(len(y)), "n_questions": int(len(set(groups))), "created_at": utc_now()}, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("all", "early", "acts", "probe"))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = valid_rows()
    if args.step in ("all", "early", "acts"):
        local = load_local()
        if args.step in ("all", "early"):
            run_early(local, rows)
        if args.step in ("all", "acts"):
            run_acts(local, rows)
        del local
    if args.step in ("all", "probe"):
        run_probe()


if __name__ == "__main__":
    main()
