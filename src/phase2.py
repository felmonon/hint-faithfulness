"""Token-preserving early answering and question-held-out residual-stream probes.

Run with ``python -m src.phase2 early|probe --records ... --out-dir ...``.
Only a single completed local-model experiment is accepted; no synthetic results.
"""
from __future__ import annotations

import argparse
import inspect
import json
from collections import Counter
from pathlib import Path

from .common import LETTERS, append_jsonl, read_jsonl, stable_hash, write_jsonl

FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)


def select_local_records(rows):
    if not rows:
        raise ValueError("No experiment records were found")
    if any(r.get("backend") != "local" for r in rows):
        raise ValueError("Phase 2 requires local records; API and mock traces cannot identify exact weights/tokens")
    for field in ("model", "experiment_id"):
        values = {r.get(field) for r in rows}
        if len(values) != 1 or not next(iter(values)):
            raise ValueError(f"Records must identify exactly one nonempty {field}")
    revisions = {r.get("model_revision") for r in rows if r.get("model_revision")}
    if len(revisions) != 1 or any(r.get("status") == "ok" and not r.get("model_revision") for r in rows):
        raise ValueError("Records must identify exactly one nonempty model_revision for usable generations")
    valid = [r for r in rows if r.get("status") == "ok" and r.get("answer") in list(LETTERS)]
    # Baseline repetition 1 measures stochastic noise; do not double-weight the
    # identical prompt in the probe or the baseline early-answer curve.
    valid = [r for r in valid if r.get("hint_type") != "none" or r.get("baseline_repeat") == 0]
    keys = [(r["question_id"], r["hint_type"]) for r in valid]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate question/condition rows; provide one experiment file")
    if not valid:
        raise ValueError("No complete, parseable local records remain")
    return valid


def single_token(tokenizer, text):
    ids = tokenizer.encode(text, add_special_tokens=False)
    if len(ids) != 1 or tokenizer.decode(ids, skip_special_tokens=False) != text:
        raise ValueError(f"Expected one exact token for {text!r}; use sequence scoring for this tokenizer")
    return ids[0]


def thinking_layout(row, tokenizer):
    """Return exact prefix through <think>, thinking tokens, and close token.

    The opening marker may be generated (Qwen3) or already in the template.
    Neither decoded/re-encoded thinking nor final-answer tokens enter a cut.
    """
    prompt = row.get("prompt_token_ids")
    generated = row.get("generated_token_ids")
    if not isinstance(prompt, list) or not isinstance(generated, list):
        raise ValueError("Exact prompt_token_ids and generated_token_ids are required")
    opening = single_token(tokenizer, "<think>")
    closing = single_token(tokenizer, "</think>")
    if opening in generated:
        start = generated.index(opening) + 1
        if tokenizer.decode(generated[:start - 1], skip_special_tokens=False).strip():
            raise ValueError("Content before the thinking marker would leak into the pre-reasoning probe")
        prefix = prompt + generated[:start]
    else:
        open_positions = [i for i, token in enumerate(prompt) if token == opening]
        if not open_positions or closing in prompt[open_positions[-1] + 1:]:
            raise ValueError("No unclosed thinking block at the assistant boundary")
        prefix, start = list(prompt), 0
    try:
        stop = generated.index(closing, start)
    except ValueError as exc:
        raise ValueError("Incomplete thinking block cannot be used for early answering") from exc
    reasoning = generated[start:stop]
    if not reasoning:
        raise ValueError("Empty reasoning trace")
    return prefix, reasoning, closing


def cut_input(row, tokenizer, fraction):
    if not 0 <= fraction <= 1:
        raise ValueError("Fraction must lie between zero and one")
    prefix, reasoning, closing = thinking_layout(row, tokenizer)
    count = int(len(reasoning) * fraction)
    suffix = tokenizer.encode("\n\nAnswer: (", add_special_tokens=False)
    return prefix + reasoning[:count] + [closing] + suffix, count, len(reasoning)


def _check_length(local, ids):
    maximum = getattr(local.model.config, "max_position_embeddings", None)
    if maximum and len(ids) > maximum:
        raise ValueError(f"{len(ids)} input tokens exceed model context {maximum}; do not silently truncate")


def candidate_probabilities(local, ids):
    import torch

    _check_length(local, ids)
    candidates = [single_token(local.tokenizer, letter) for letter in LETTERS]
    inputs = torch.tensor([ids], device=local.device)
    kwargs = {"input_ids": inputs, "attention_mask": torch.ones_like(inputs), "use_cache": False}
    # Avoid allocating sequence_length x vocabulary logits where supported.
    params = inspect.signature(local.model.forward).parameters
    if "logits_to_keep" in params:
        kwargs["logits_to_keep"] = 1
    elif "num_logits_to_keep" in params:
        kwargs["num_logits_to_keep"] = 1
    with torch.inference_mode():
        logits = local.model(**kwargs).logits[0, -1].float()
        raw = torch.softmax(logits, dim=-1)[candidates]
        normalized = torch.softmax(logits[candidates], dim=-1)
    return dict(zip(LETTERS, raw.cpu().tolist())), dict(zip(LETTERS, normalized.cpu().tolist()))


def capture_residuals(local, ids):
    """Post-block residuals at the last token, before final model RMSNorm.

    Layer 0 means the output of the first decoder block, not embeddings.
    Hooks avoid HF hidden_states' architecture-dependent final-normalization
    convention. Only the last-position vector is retained per layer.
    """
    import numpy as np
    import torch

    _check_length(local, ids)
    backbone = getattr(local.model, "model", None)
    layers = getattr(backbone, "layers", None)
    if layers is None:
        raise ValueError("This implementation requires Qwen-style model.model.layers")
    captured = [None] * len(layers)
    handles = []
    for index, layer in enumerate(layers):
        def hook(_module, _args, output, index=index):
            hidden = output[0] if isinstance(output, tuple) else output
            captured[index] = hidden[0, -1].detach().float().cpu().numpy().copy()
        handles.append(layer.register_forward_hook(hook))
    try:
        inputs = torch.tensor([ids], device=local.device)
        with torch.inference_mode():
            backbone(input_ids=inputs, attention_mask=torch.ones_like(inputs), use_cache=False)
    finally:
        for handle in handles:
            handle.remove()
    if any(value is None for value in captured):
        raise ValueError("Some decoder layers were not observed")
    return np.stack(captured)


def question_split(question_ids, seed=20261109, test_size=0.3):
    """Split identities first: all conditions of a question stay together."""
    import numpy as np

    unique = sorted(set(question_ids))
    if len(unique) < 4:
        raise ValueError("Need at least four questions for a meaningful train/test split")
    rng = np.random.default_rng(seed)
    rng.shuffle(unique)
    n_test = max(1, min(len(unique) - 1, int(round(len(unique) * test_size))))
    test_questions = set(unique[:n_test])
    train = np.array([i for i, q in enumerate(question_ids) if q not in test_questions])
    test = np.array([i for i, q in enumerate(question_ids) if q in test_questions])
    return train, test


def clustered_interval(successes, groups, seed=20261109, repeats=1000):
    """Percentile bootstrap over questions, preserving repeated conditions."""
    import numpy as np

    if not len(successes):
        return {"rate": None, "low": None, "high": None, "n": 0, "questions": 0}
    successes = np.asarray(successes, dtype=float)
    groups = np.asarray(groups)
    unique = sorted(set(groups.tolist()))
    counts = np.array([sum(groups == group) for group in unique])
    wins = np.array([successes[groups == group].sum() for group in unique])
    rng = np.random.default_rng(seed)
    sampled = rng.integers(len(unique), size=(repeats, len(unique)))
    rates = wins[sampled].sum(axis=1) / counts[sampled].sum(axis=1)
    # Fewer than two question clusters cannot support an uncertainty estimate.
    low, high = np.quantile(rates, [0.025, 0.975]) if len(unique) > 1 else (float("nan"), float("nan"))
    return {"rate": float(successes.mean()), "low": float(low) if len(unique) > 1 else None,
            "high": float(high) if len(unique) > 1 else None, "n": len(successes), "questions": len(unique)}


def early_selection(rows):
    baselines = {r["question_id"]: r for r in rows if r["hint_type"] == "none"}
    selected = []
    for row in rows:
        if row["hint_type"] == "none":
            selected.append((row, "unhinted"))
        else:
            base = baselines.get(row["question_id"])
            if base and base["answer"] != row["hint_letter"] and row["answer"] == row["hint_letter"]:
                selected.append((row, "hinted_switch"))
    return selected


def _write_manifest(out, rows, args, extra=None):
    manifest = {"model": rows[0]["model"], "model_revision": rows[0]["model_revision"],
                "experiment_id": rows[0]["experiment_id"], "selected_records_sha256": stable_hash(rows),
                "source_records": getattr(args, "source_count", None), "selected_records": len(rows),
                "source_status_counts": getattr(args, "source_status_counts", {}),
                "source_dtypes": sorted({r.get("dtype", "unknown") for r in rows}),
                "command": args.command, "seed": args.seed,
                "interpretation": "Answer agreement and linear decodability are proxies, not proof of a settled decision.",
                **(extra or {})}
    (out / f"{args.command}_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def run_early(local, rows, out, args):
    selected = early_selection(rows)
    if not selected:
        raise ValueError("No baseline or valid hinted-switch traces")
    path = out / "early_results.jsonl"
    if path.exists():
        raise ValueError(f"{path} exists; choose a fresh output directory")
    results = []
    for index, (row, group) in enumerate(selected, 1):
        for fraction in FRACTIONS:
            ids, shown, total = cut_input(row, local.tokenizer, fraction)
            raw, normalized = candidate_probabilities(local, ids)
            prediction = max(normalized, key=normalized.get)
            result = {"record_id": row["record_id"], "question_id": row["question_id"],
                      "group": group, "hint_type": row["hint_type"], "fraction": fraction,
                      "shown_reasoning_tokens": shown, "total_reasoning_tokens": total,
                      "final_answer": row["answer"], "prediction": prediction,
                      "matches_final": prediction == row["answer"],
                      "probabilities": raw, "conditional_letter_probabilities": normalized,
                      "letter_probability_mass": sum(raw.values())}
            append_jsonl(path, result)
            results.append(result)
        print(f"Early answering: {index}/{len(selected)} traces", flush=True)
    summary = []
    for group in ("unhinted", "hinted_switch"):
        for fraction in FRACTIONS:
            subset = [r for r in results if r["group"] == group and r["fraction"] == fraction]
            summary.append({"group": group, "fraction": fraction,
                            **clustered_interval([r["matches_final"] for r in subset],
                                                 [r["question_id"] for r in subset], args.seed)})
    write_jsonl(out / "early_summary.jsonl", summary)
    _plot_early(summary, out / "early_answering.png")
    _write_manifest(out, rows, args, {"fractions": FRACTIONS, "selected_traces": len(selected),
                                    "intervention_dtype": str(local.model.dtype),
                                    "interval": "95% percentile bootstrap, resampling questions"})


def _plot_early(summary, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for group, label in (("unhinted", "Unhinted"), ("hinted_switch", "Hinted switches")):
        points = [p for p in summary if p["group"] == group and p["rate"] is not None]
        if points:
            ax.plot([p["fraction"] * 100 for p in points], [p["rate"] for p in points], "o-", label=label)
            if all(p["low"] is not None for p in points):
                ax.fill_between([p["fraction"] * 100 for p in points], [p["low"] for p in points],
                                [p["high"] for p in points], alpha=.15)
    ax.set(xlabel="Reasoning tokens retained (%)", ylabel="Matches original final answer", ylim=(0, 1.03),
           title="Early answering: agreement after forced thinking closure")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_probe(local, rows, out, args):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if (out / "probe_activations.npz").exists():
        raise ValueError("Probe artifacts already exist; choose a fresh output directory")
    question_ids = [r["question_id"] for r in rows]
    train, test = question_split(question_ids, args.seed)
    y = np.array([r["answer"] for r in rows])
    if len(set(y[train])) < 2:
        raise ValueError("Training outcomes have fewer than two classes; collect more questions")
    activations = []
    for index, row in enumerate(rows, 1):
        prefix, _, _ = thinking_layout(row, local.tokenizer)
        activations.append(capture_residuals(local, prefix))
        print(f"Probe activations: {index}/{len(rows)} prompts", flush=True)
    x = np.stack(activations)  # example, decoder block, residual coordinate
    np.savez_compressed(out / "probe_activations.npz", activations=x, train_indices=train, test_indices=test,
                        record_ids=np.array([r["record_id"] for r in rows]), answers=y,
                        question_ids=np.array(question_ids))
    majority = Counter(y[train]).most_common(1)[0][0]
    shuffled_y = np.random.default_rng(args.seed).permutation(y[train])
    test_rows = [rows[i] for i in test]
    test_questions = [r["question_id"] for r in test_rows]
    correct = np.array([r["correct_answer"] for r in test_rows])
    wrong = np.array([r["answer"] != r["correct_answer"] for r in test_rows])
    resisted = np.array([r["hint_type"] != "none" and r["answer"] != r["hint_letter"] for r in test_rows])
    baseline = clustered_interval(y[test] == majority, test_questions, args.seed)
    summaries, predictions = [], []
    for layer in range(x.shape[1]):
        fit = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000, random_state=args.seed))
        control = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000, random_state=args.seed))
        fit.fit(x[train, layer], y[train])
        control.fit(x[train, layer], shuffled_y)
        predicted = fit.predict(x[test, layer])
        shuffled = control.predict(x[test, layer])
        summaries.append({"layer": layer, "test": clustered_interval(predicted == y[test], test_questions, args.seed),
                          "shuffled_training_labels": clustered_interval(shuffled == y[test], test_questions, args.seed),
                          "train_majority_test": baseline, "majority_letter": majority,
                          "wrong_model_answer": clustered_interval((predicted == y[test])[wrong],
                                                                    np.array(test_questions)[wrong], args.seed),
                          "wrong_correct_answer": clustered_interval((predicted == correct)[wrong],
                                                                      np.array(test_questions)[wrong], args.seed),
                          "resisted_hint_model_answer": clustered_interval((predicted == y[test])[resisted],
                                                                            np.array(test_questions)[resisted], args.seed)})
        predictions.extend({"record_id": row["record_id"], "question_id": row["question_id"], "layer": layer,
                            "answer": row["answer"], "correct_answer": row["correct_answer"],
                            "hint_type": row["hint_type"], "hint_letter": row["hint_letter"],
                            "predicted_answer": str(predicted[j]), "shuffled_prediction": str(shuffled[j])}
                           for j, row in enumerate(test_rows))
    write_jsonl(out / "probe_summary.jsonl", summaries)
    write_jsonl(out / "probe_predictions.jsonl", predictions)
    _plot_probe(summaries, out / "probe_accuracy.png")
    _write_manifest(out, rows, args, {"train_questions": sorted(set(np.array(question_ids)[train])),
                                    "intervention_dtype": str(local.model.dtype),
                                    "test_questions": sorted(set(np.array(question_ids)[test])),
                                    "train_examples": len(train), "test_examples": len(test),
                                    "layer_definition": "zero-based post-decoder-block residual, before final RMSNorm",
                                    "position": "last token of the exact assistant prefix through <think>",
                                    "regularization_C": 1.0, "scaling": "fit on training examples only",
                                    "interval": "95% percentile bootstrap, resampling test questions",
                                    "limitation": "One shuffled-label control; no hyperparameter or best-layer selection on test data"})


def _plot_probe(summary, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    layers = [s["layer"] for s in summary]
    for key, label in (("test", "Probe"), ("shuffled_training_labels", "Shuffled training labels")):
        ax.plot(layers, [s[key]["rate"] for s in summary], label=label)
    if all(s["test"]["low"] is not None for s in summary):
        ax.fill_between(layers, [s["test"]["low"] for s in summary], [s["test"]["high"] for s in summary], alpha=.15)
    ax.axhline(summary[0]["train_majority_test"]["rate"], ls="--", color="gray", label="Training majority on test")
    ax.axhline(.25, ls=":", color="black", label="Uniform four-way chance")
    ax.set(xlabel="Decoder block (zero based)", ylabel="Held-out answer prediction accuracy", ylim=(0, 1.03),
           title="Answer information before thinking text")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("early", "probe"))
    parser.add_argument("--records", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=20261109)
    args = parser.parse_args(argv)
    source = read_jsonl(args.records)
    args.source_count = len(source)
    args.source_status_counts = dict(Counter(r.get("status", "missing") for r in source))
    rows = select_local_records(source)
    from .local_model import LocalModel
    local = LocalModel(rows[0]["model"], revision=rows[0]["model_revision"], device=args.device)
    if local.revision != rows[0]["model_revision"]:
        raise ValueError("Loaded revision differs from the Phase 1 records")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if args.command == "early":
        run_early(local, rows, out, args)
    else:
        run_probe(local, rows, out, args)


if __name__ == "__main__":
    main()
