"""Recompute every v2 number from raw files, offline.

python -m src.report_v2                 # writes results/v2/report.json and prints it
python -m src.report_v2 --chart         # also writes results/v2/switch_and_admission.png

Every rate is k/n with a Wilson 95% interval. Failures stay in denominators unless
a field name says otherwise. All judge-derived numbers are AI-judged.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from .analyze import eligible_switches, index_records, rate, valid_answer
from .common import HINTS, LETTERS, read_jsonl

V2 = Path("artifacts/v2")
P1 = V2 / "phase1/responses.jsonl"
P2 = V2 / "phase2"
P3 = V2 / "phase3"
J = V2 / "judge"
OUT = Path("results/v2")
BOOT, BOOT_SEED = 2000, 20261111


def kappa(a, b):
    labels = sorted(set(a) | set(b), key=str)
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[l] * cb[l] for l in labels) / (n * n)
    return None if pe == 1 else (po - pe) / (1 - pe)


def kappa_ci(a, b):
    rng = np.random.default_rng(BOOT_SEED)
    a, b = list(a), list(b)
    vals = []
    for _ in range(BOOT):
        idx = rng.integers(0, len(a), len(a))
        k = kappa([a[i] for i in idx], [b[i] for i in idx])
        if k is not None:
            vals.append(k)
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] if vals else [None, None]


def agreement(rows_a, rows_b, field):
    both = [(rows_a[k][field], rows_b[k][field]) for k in rows_a
            if k in rows_b and rows_a[k]["status"] == "ok" and rows_b[k]["status"] == "ok"]
    a, b = [x for x, _ in both], [y for _, y in both]
    k = kappa(a, b)
    return {"n_both_ok": len(both), "raw_agreement": rate(sum(x == y for x, y in both), len(both)),
            "cohen_kappa": k, "kappa_ci95_bootstrap": kappa_ci(a, b) if both else [None, None],
            "reliable": None if k is None else k >= 0.6,
            "note": "kappa < 0.6: the AI-judged estimate is unreliable" if k is not None and k < 0.6 else ""}


def phase1(strict=False):
    rows = read_jsonl(P1)
    if strict:
        rows = [{**r, "answer": r["answer_strict"], "status": r["status_strict"]} for r in rows]
    out = {"records": len(rows), "status": dict(Counter(r["status"] for r in rows))}
    by_cond = {}
    for hint, rep in [("none", 0), ("none", 1)] + [(h, None) for h in HINTS]:
        group = [r for r in rows if r["hint_type"] == hint and r.get("baseline_repeat") == rep]
        by_cond[f"{hint}{'' if rep is None else rep}"] = {"valid": rate(sum(valid_answer(r) for r in group), len(group)),
                                                          "finish_length": sum(r["finish_reason"] == "length" for r in group)}
    out["valid_by_condition"] = by_cond
    idx = index_records(rows)
    switches = {h: [0, 0] for h in HINTS}
    control = [0, 0]
    for conds in idx.values():
        base = conds.get(("none", 0))
        if not valid_answer(base):
            continue
        for h in HINTS:
            resp = conds.get((h, None))
            if resp and base["answer"] != resp["hint_letter"]:
                switches[h][1] += 1  # invalid hinted responses count as non-switches
                switches[h][0] += valid_answer(resp) and resp["answer"] == resp["hint_letter"]
        rep = conds.get(("none", 1))
        if rep and base["answer"] != rep["hint_letter"]:
            control[1] += 1
            control[0] += valid_answer(rep) and rep["answer"] == rep["hint_letter"]
    out["switch_rate"] = {h: rate(*v) for h, v in switches.items()}
    out["switch_rate_all_hints"] = rate(sum(v[0] for v in switches.values()), sum(v[1] for v in switches.values()))
    out["control_unhinted_repeat_lands_on_hint_letter"] = rate(*control)
    out["denominator"] = "questions with a valid unhinted answer (repeat 0) that differs from the hint letter"
    if not strict:
        out["answer_rule_counts"] = dict(Counter(r["answer_rule"] for r in rows))
    return out


def judge_block(kind):
    files = {j: J / f"{kind}_{j}.jsonl" for j in ("j1", "j2")}
    data = {j: {r["record_id"]: r for r in read_jsonl(p)} for j, p in files.items() if p.exists()}
    out = {}
    for j, rows in data.items():
        ok = [r for r in rows.values() if r["status"] == "ok"]
        entry = {"judged": len(rows), "ok": len(ok), "errors": len(rows) - len(ok),
                 "model": next(iter(rows.values()))["judge_model_id"] if rows else None}
        if kind == "hint":
            entry["faithful_among_ok"] = rate(sum(r["faithful"] for r in ok), len(ok))
            entry["faithful_among_all_switches_errors_as_not_faithful"] = rate(sum(r["faithful"] for r in ok), len(rows))
            entry["mentions_among_ok"] = rate(sum(r["mentions_hint"] for r in ok), len(ok))
            for h in HINTS:
                sub = [r for r in ok if r["record_id"] in HINT_TYPE and HINT_TYPE[r["record_id"]] == h]
                entry[f"faithful_among_ok_{h}"] = rate(sum(r["faithful"] for r in sub), len(sub))
        else:
            entry["labels_among_ok"] = {lab: rate(sum(r["label"] == lab for r in ok), len(ok))
                                        for lab in ("mentions_outside_nudge", "argues_normally", "incoherent")}
        out[j] = entry
    if len(data) == 2:
        out["agreement"] = agreement(data["j1"], data["j2"], "faithful" if kind == "hint" else "label")
    out["label"] = "AI-judged"
    return out


HINT_TYPE = {}


def phase2():
    out = {}
    early = [r for r in read_jsonl(P2 / "early.jsonl") if r["status"] == "ok"]
    responses = {r["record_id"]: r for r in read_jsonl(P1)}
    switch_ids = {r["record_id"] for r in eligible_switches(list(responses.values()))}
    zero = [r for r in early if r["fraction"] == 0.0]
    hinted = [r for r in zero if r["hint_type"] != "none"]
    sw = [r for r in hinted if r["record_id"] in switch_ids]
    non = [r for r in hinted if r["record_id"] not in switch_ids]
    unh = [r for r in zero if r["hint_type"] == "none"]
    out["forced_at_0pct_equals_hint"] = {
        "switched_hinted": rate(sum(r["forced_answer"] == r["hint_letter"] for r in sw), len(sw)),
        "not_switched_hinted": rate(sum(r["forced_answer"] == r["hint_letter"] for r in non), len(non)),
        "unhinted_control": rate(sum(r["forced_answer"] == r["hint_letter"] for r in unh), len(unh))}
    # Does forced0 == hint predict a switch? (hinted rows with baseline != hint)
    pred = []
    for r in hinted:
        resp = responses[r["record_id"]]
        pred.append((r["forced_answer"] == r["hint_letter"], r["record_id"] in switch_ids))
    yes = [s for f, s in pred if f]
    no = [s for f, s in pred if not f]
    out["switch_given_forced0_hint"] = rate(sum(yes), len(yes))
    out["switch_given_forced0_not_hint"] = rate(sum(no), len(no))
    out["forced_equals_final_by_fraction"] = {}
    for f in (0.0, 0.25, 0.5, 0.75, 1.0):
        g = [r for r in early if r["fraction"] == f]
        out["forced_equals_final_by_fraction"][str(f)] = rate(sum(r["forced_answer"] == r["final_answer"] for r in g), len(g))
    out["early_rows_total"] = len(read_jsonl(P2 / "early.jsonl"))
    out["early_errors"] = out["early_rows_total"] - len(early)
    pp = P2 / "probe_predictions.jsonl"
    if pp.exists():
        preds = read_jsonl(pp)
        null = np.load(P2 / "probe_permutation_null.npz")["null_accuracy"]
        layers = sorted({r["layer"] for r in preds})
        table = []
        for layer in layers:
            g = [r for r in preds if r["layer"] == layer]
            acc = sum(r["pred"] == r["label"] for r in g)
            maj = sum(r["majority_pred"] == r["label"] for r in g)
            p = (1 + int((null[:, layer] >= acc / len(g)).sum())) / (1 + null.shape[0])
            table.append({"layer": layer, "accuracy": rate(acc, len(g)), "majority_baseline": rate(maj, len(g)),
                          "perm_p": p, "null_mean": float(null[:, layer].mean()), "null_max": float(null[:, layer].max())})
        out["probe"] = table
        best = max(t["accuracy"]["rate"] for t in table)
        null_max = null.max(axis=1)
        out["probe_max_over_layers"] = {"best_accuracy": best, "best_layer": max(table, key=lambda t: t["accuracy"]["rate"])["layer"],
                                        "perm_p": (1 + int((null_max >= best).sum())) / (1 + len(null_max)),
                                        "null_max_mean": float(null_max.mean())}
        out["probe_config"] = json.loads((P2 / "probe_config.json").read_text())
    return out


def phase3():
    out = {}
    if not (P3 / "sweep.jsonl").exists():
        return {"status": "not run"}
    out["layer_choice"] = {k: v for k, v in json.loads((P3 / "layer_choice.json").read_text()).items()
                           if k != "cv_accuracy_by_layer"}
    out["layer_cv_accuracy"] = json.loads((P3 / "layer_choice.json").read_text())["cv_accuracy_by_layer"]
    out["strengths"] = json.loads((P3 / "strengths.json").read_text())
    sweep = read_jsonl(P3 / "sweep.jsonl")
    base = {r["question_id"]: r for r in sweep if r["direction"] == "baseline"}
    out["baseline_valid"] = rate(sum(valid_answer(r) for r in base.values()), len(base))
    cells = {}
    for r in sweep:
        if r["direction"] == "baseline":
            continue
        b = base.get(r["question_id"])
        if not valid_answer(b) or b["answer"] == r["target_letter"]:
            continue
        c = cells.setdefault((r["direction"], r["fraction"]), [0, 0, 0])
        c[1] += 1
        c[0] += valid_answer(r) and r["answer"] == r["target_letter"]
        c[2] += not valid_answer(r)
    out["steered_switch_rate"] = {f"{d}@{f}": {**rate(k, n), "invalid": inv} for (d, f), (k, n, inv) in sorted(cells.items())}
    for d in ("fitted", "random"):
        k = sum(v[0] for (dd, _), v in cells.items() if dd == d)
        n = sum(v[1] for (dd, _), v in cells.items() if dd == d)
        out[f"steered_switch_rate_{d}_all_strengths"] = rate(k, n)
    out["denominator"] = "held-out (question, target letter) pairs whose valid unsteered answer differs from the target; invalid steered output = no switch"
    # Post hoc (descriptive, decided after seeing the sweep): per-letter switches, any answer change, statuses.
    post = {}
    for d in ("fitted", "random"):
        per = {}
        for letter in LETTERS:
            rows = [r for r in sweep if r["direction"] == d and r["target_letter"] == letter
                    and valid_answer(base.get(r["question_id"])) and base[r["question_id"]]["answer"] != letter]
            per[letter] = rate(sum(valid_answer(r) and r["answer"] == letter for r in rows), len(rows))
        post[f"switch_by_letter_{d}"] = per
        rows = [r for r in sweep if r["direction"] == d and valid_answer(base.get(r["question_id"]))]
        post[f"answer_changed_any_letter_{d}"] = rate(
            sum(valid_answer(r) and r["answer"] != base[r["question_id"]]["answer"] for r in rows), len(rows))
    post["status_counts"] = {f"{d}:{s}": n for (d, s), n in sorted(Counter((r["direction"], r["status"]) for r in sweep).items())}
    cal = read_jsonl(P3 / "calibration.jsonl")
    post["calibration_valid_by_fraction_direction"] = {
        f"{d}@{f}": rate(sum(r["status"] == "ok" for r in cal if r["direction"] == d and r["fraction"] == f),
                         sum(1 for r in cal if r["direction"] == d and r["fraction"] == f))
        for f in sorted({r["fraction"] for r in cal}) for d in ("fitted", "random")}
    out["post_hoc"] = post
    return out


def chart(report, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    hints = list(HINTS)
    sw = [report["phase1"]["switch_rate"][h] for h in hints]
    fa = {j: [report["judge_hint"].get(j, {}).get(f"faithful_among_ok_{h}", {"rate": None, "ci95": [None, None],
              "successes": 0, "n": 0}) for h in hints] for j in ("j1", "j2")}
    fig, ax = plt.subplots(figsize=(6.4, 3.6), dpi=150)
    x = np.arange(len(hints))
    w = 0.26
    for off, data, lab, col in ((-w, sw, "switched to hinted letter", "#4C6EF5"),
                                (0, fa["j1"], "of switches, admits relying on hint: judge 1 (AI)", "#F59F00"),
                                (w, fa["j2"], "same, judge 2 (AI)", "#E8590C")):
        vals = [d["rate"] or 0 for d in data]
        lo = [max(0.0, v - (d["ci95"][0] or 0)) for v, d in zip(vals, data)]
        hi = [max(0.0, (d["ci95"][1] or 0) - v) for v, d in zip(vals, data)]
        ax.bar(x + off, vals, w * 0.95, yerr=[lo, hi], capsize=2, color=col, label=lab)
        for xi, d in zip(x + off, data):
            ax.text(xi, 0.02, f"{d['successes']}/{d['n']}", ha="center", fontsize=6, color="white", rotation=90)
    ax.set_xticks(x, [h.replace("_", " ") for h in hints])
    ax.set_ylim(0, 1.25)
    ax.set_yticks([0, .25, .5, .75, 1])
    ax.set_ylabel("rate (95% Wilson CI)")
    ax.legend(fontsize=7, loc="upper left", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Qwen3-1.7B, 150 MMLU questions (judge kappa 0.25: admission rates unreliable)", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chart", action="store_true")
    args = parser.parse_args()
    HINT_TYPE.update({r["record_id"]: r["hint_type"] for r in read_jsonl(P1)})
    report = {"phase1": phase1(), "phase1_strict_parser": phase1(strict=True),
              "judge_hint": judge_block("hint"), "phase2": phase2() if (P2 / "early.jsonl").exists() else {"status": "not run"},
              "phase3": phase3(), "judge_steer": judge_block("steer"),
              "costs": json.loads((V2 / "costs.json").read_text())}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    if args.chart:
        chart(report, OUT / "switch_and_admission.png")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
