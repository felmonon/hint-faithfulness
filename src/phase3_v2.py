"""Phase 3 v2: letter-contrast steering with a frozen held-out split.

python -m src.phase3_v2 all        # split -> acts -> vectors/layer -> calibrate -> sweep
Steps are resumable; each writes under artifacts/v2/phase3/. Order of freezing:
  1. split.json (40 held-out questions) before any activation is computed
  2. layer + vectors from training questions only
  3. strengths from 3 training questions only, frozen in strengths.json
  4. held-out sweep
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import random
from pathlib import Path

import numpy as np

from .common import LETTERS, HINTS, append_jsonl, build_messages, read_jsonl, utc_now
from .vectors_v2 import calibrated_strengths, letter_contrast_vectors, pairwise_cosines, random_like, scaled

OUT = Path("artifacts/v2/phase3")
SPLIT_SEED, N_HELDOUT = 20261111, 40
FRACTIONS = (0.05, 0.1, 0.2, 0.4, 0.8, 1.6)
GEN = {"temperature": .6, "top_p": .95, "top_k": 20, "max_tokens": 4096}
TIE_PP = 0.005


def qseed(qid, salt=""):
    return int(hashlib.sha256(f"{SPLIT_SEED}:{qid}:{salt}".encode()).hexdigest()[:8], 16) % (2 ** 31)


def make_split(questions):
    path = OUT / "split.json"
    if path.exists():
        return json.loads(path.read_text())
    ids = [q["question_id"] for q in questions]
    rng = random.Random(SPLIT_SEED)
    shuffled = ids[:]
    rng.shuffle(shuffled)
    split = {"seed": SPLIT_SEED, "heldout": sorted(shuffled[:N_HELDOUT]), "train": sorted(shuffled[N_HELDOUT:]),
             "calibration": shuffled[N_HELDOUT:N_HELDOUT + 3], "created_at": utc_now()}
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(split, indent=2) + "\n")
    return split


def letter_prompts(question):
    """3 hint types x 4 pointed-to letters for one question."""
    for hint in HINTS:
        for letter in LETTERS:
            yield hint, letter, build_messages({**question, "hint_letter": letter}, hint)


def collect_activations(questions, split):
    """HF forward passes only (no generation): last prompt token, every layer."""
    path = OUT / "train_acts_meta.json"
    if path.exists():
        return
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from .gen_v2 import MODEL, REVISION
    from .phase2 import capture_residuals
    tok = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
    model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REVISION, torch_dtype=torch.float16).to("cuda").eval()

    class Local:  # adapter for src.phase2.capture_residuals
        pass
    local = Local()
    local.model, local.tokenizer, local.device = model, tok, torch.device("cuda")
    by_id = {q["question_id"]: q for q in questions}
    rows, acts = [], []
    for qid in split["train"]:
        for hint, letter, messages in letter_prompts(by_id[qid]):
            ids = tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, enable_thinking=True)
            acts.append(capture_residuals(local, ids).astype(np.float32))
            rows.append({"question_id": qid, "hint_type": hint, "hint_letter": letter,
                         "correct_answer": by_id[qid]["correct_answer"], "prompt_tokens": len(ids)})
    acts = np.stack(acts)  # (n, layers, d)
    np.save(OUT / "train_acts_all_layers.npy", acts.astype(np.float16))  # large; not committed (see manifest)
    norms = np.linalg.norm(acts, axis=2)  # (n, layers)
    np.savez_compressed(OUT / "train_act_norms.npz", norms=norms)
    meta = {"rows": rows, "shape": list(acts.shape), "position": "last prompt token (generation prompt, before <think>)",
            "layer_convention": "output of decoder block i (0-based), before final norm", "created_at": utc_now()}
    path.write_text(json.dumps(meta) + "\n")
    del model
    gc.collect()
    torch.cuda.empty_cache()


def choose_layer_and_vectors():
    path = OUT / "vectors.npz"
    if path.exists():
        return json.loads((OUT / "layer_choice.json").read_text())
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold, cross_val_predict
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    meta = json.loads((OUT / "train_acts_meta.json").read_text())
    acts = np.load(OUT / "train_acts_all_layers.npy").astype(np.float32)
    y = np.array([r["hint_letter"] for r in meta["rows"]])
    groups = np.array([r["question_id"] for r in meta["rows"]])
    n_layers = acts.shape[1]
    accuracy = []
    for layer in range(n_layers):
        clf = make_pipeline(StandardScaler(), LogisticRegression(C=.1, max_iter=2000))
        pred = cross_val_predict(clf, acts[:, layer], y, groups=groups, cv=GroupKFold(5))
        accuracy.append(float((pred == y).mean()))
    best = max(accuracy)
    middle = (n_layers - 1) / 2
    tied = [i for i, a in enumerate(accuracy) if a >= best - TIE_PP]
    layer = min(tied, key=lambda i: (abs(i - middle), i))
    x = acts[:, layer].astype(np.float64)
    vectors = letter_contrast_vectors(x, y)
    randoms = {L: random_like(vectors[L], qseed("random", L)) for L in LETTERS}
    norms = np.linalg.norm(x, axis=1)
    choice = {"cv_accuracy_by_layer": accuracy, "max_accuracy": best, "tied_layers": tied, "layer": layer,
              "rule": f"max 5-fold GroupKFold accuracy decoding hinted letter; ties within {TIE_PP} -> nearest middle",
              "median_residual_norm": float(np.median(norms)), "n_rows": int(len(y)),
              "n_questions": int(len(set(groups))), "vector_norms": {L: float(np.linalg.norm(v)) for L, v in vectors.items()},
              "pairwise_cosines_fitted": pairwise_cosines(vectors),
              "pairwise_cosines_random": pairwise_cosines(randoms), "created_at": utc_now()}
    np.savez(path, layer=layer, median_norm=choice["median_residual_norm"],
             **{f"fitted_{L}": vectors[L].astype(np.float32) for L in LETTERS},
             **{f"random_{L}": randoms[L].astype(np.float32) for L in LETTERS})
    np.save(OUT / "train_acts_chosen_layer.npy", acts[:, layer].astype(np.float32))
    (OUT / "layer_choice.json").write_text(json.dumps(choice, indent=2) + "\n")
    return choice


class Steerer:
    """vLLM (V0, eager) forward hook adding one fixed vector after a decoder layer."""

    def __init__(self, llm, layer):
        import torch
        model = None
        for path in ("llm_engine.model_executor.driver_worker.model_runner.model",
                     "llm_engine.model_executor.driver_worker.worker.model_runner.model"):
            obj = llm
            try:
                for part in path.split("."):
                    obj = getattr(obj, part)
                model = obj
                break
            except AttributeError:
                continue
        if model is None:
            raise RuntimeError("Could not reach the vLLM model for hooking (needs VLLM_USE_V1=0)")
        self.torch = torch
        self.vector = None
        block = model.model.layers[layer]
        dtype = next(model.parameters()).dtype
        self.dtype, self.device = dtype, next(model.parameters()).device

        def hook(_module, _inputs, output):
            if self.vector is None:
                return output
            hidden, residual = output
            return hidden + self.vector, residual
        block.register_forward_hook(hook)

    def set(self, vector):
        self.vector = None if vector is None else self.torch.tensor(vector, dtype=self.dtype, device=self.device)


def generate(llm, tok, steerer, items, vector):
    """items: list of (row_metadata, messages, seed). Returns rows with outputs."""
    from vllm import SamplingParams
    from vllm.inputs import TokensPrompt
    from .gen_v2 import split_generation
    steerer.set(vector)
    prompts, params = [], []
    for _, messages, seed in items:
        ids = tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, enable_thinking=True)
        prompts.append(TokensPrompt(prompt_token_ids=ids))
        params.append(SamplingParams(seed=seed, skip_special_tokens=False, **GEN))
    results = llm.generate(prompts, params, use_tqdm=False)
    rows = []
    for (meta, _, seed), prompt, result in zip(items, prompts, results):
        out = result.outputs[0]
        finish = "length" if out.finish_reason == "length" else "stop" if out.finish_reason == "stop" else str(out.finish_reason)
        rows.append({**meta, "seed": seed, **split_generation(tok, list(out.token_ids), finish),
                     "prompt_token_ids": prompt["prompt_token_ids"], "finished_at": utc_now()})
    steerer.set(None)
    return rows


def conditions(strengths):
    yield ("baseline", None, 0.0)
    for direction in ("fitted", "random"):
        for letter in LETTERS:
            for fraction in strengths:
                yield (direction, letter, fraction)


def run_vllm_steps(questions, split, choice):
    from .gen_v2 import load_vllm
    vec = np.load(OUT / "vectors.npz")
    layer, median = int(vec["layer"]), float(vec["median_norm"])
    llm = load_vllm(max_num_seqs=64, enforce_eager=True)
    tok = llm.get_tokenizer()
    steerer = Steerer(llm, layer)
    by_id = {q["question_id"]: q for q in questions}

    def vector_for(direction, letter, fraction):
        return None if direction == "baseline" else scaled(vec[f"{direction}_{letter}"], fraction, median)

    # Calibration on 3 training questions, unhinted prompts.
    cal_path = OUT / "calibration.jsonl"
    done = {(r["question_id"], r["direction"], r["target_letter"], r["fraction"]) for r in read_jsonl(cal_path)}
    for fraction in FRACTIONS:
        for direction in ("fitted", "random"):
            for letter in LETTERS:
                items = [({"phase": "calibration", "question_id": qid, "direction": direction, "target_letter": letter,
                           "fraction": fraction, "layer": layer, "abs_strength": fraction * median},
                          build_messages(by_id[qid], "none"), qseed(qid))
                         for qid in split["calibration"] if (qid, direction, letter, fraction) not in done]
                if items:
                    for row in generate(llm, tok, steerer, items, vector_for(direction, letter, fraction)):
                        append_jsonl(cal_path, row)
    strengths_path = OUT / "strengths.json"
    if not strengths_path.exists():
        cal = read_jsonl(cal_path)
        rates = {}
        for fraction in FRACTIONS:
            group = [r for r in cal if r["fraction"] == fraction]
            rates[fraction] = sum(r["status"] == "ok" for r in group) / len(group)
        kept = calibrated_strengths(rates)
        strengths_path.write_text(json.dumps({"valid_rate_by_fraction": {str(k): v for k, v in rates.items()},
            "outputs_per_fraction": 24, "threshold": .8, "frozen_fractions": kept,
            "frozen_at": utc_now(), "rule": "keep fractions with >=80% valid answers; up to 4 spanning the kept range"},
            indent=2) + "\n")
    strengths = json.loads(strengths_path.read_text())["frozen_fractions"]
    print("frozen strengths", strengths, flush=True)
    # Held-out sweep.
    sweep_path = OUT / "sweep.jsonl"
    done = {(r["question_id"], r["direction"], r["target_letter"], r["fraction"]) for r in read_jsonl(sweep_path)}
    for direction, letter, fraction in conditions(strengths):
        items = [({"phase": "sweep", "question_id": qid, "direction": direction, "target_letter": letter,
                   "fraction": fraction, "layer": layer, "abs_strength": fraction * median,
                   "correct_answer": by_id[qid]["correct_answer"]},
                  build_messages(by_id[qid], "none"), qseed(qid))
                 for qid in split["heldout"] if (qid, direction, letter, fraction) not in done]
        if items:
            for row in generate(llm, tok, steerer, items, vector_for(direction, letter, fraction)):
                append_jsonl(sweep_path, row)
            print(f"sweep {direction} {letter} {fraction}: {len(items)}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("all", "split", "acts", "vectors", "steer"))
    args = parser.parse_args()
    questions = read_jsonl("data/questions.jsonl")
    split = make_split(questions)
    if args.step in ("all", "acts"):
        collect_activations(questions, split)
    choice = None
    if args.step in ("all", "vectors"):
        choice = choose_layer_and_vectors()
        print("layer", choice["layer"], "cosines", choice["pairwise_cosines_fitted"], flush=True)
    if args.step in ("all", "steer"):
        run_vllm_steps(questions, split, choice)


if __name__ == "__main__":
    main()
