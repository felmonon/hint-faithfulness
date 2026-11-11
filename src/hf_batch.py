"""Batched Hugging Face generation with optional per-row steering vectors.

Used by Phase 1 v2 and Phase 3 v2. Per-request seeds are not supported by a
batched transformers sampler, so each batch gets one recorded seed.
"""
from __future__ import annotations

import hashlib

MODEL = "Qwen/Qwen3-1.7B"
REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
GEN = {"temperature": .6, "top_p": .95, "top_k": 20, "max_new_tokens": 4096}


def batch_seed(base_seed, keys):
    return int(hashlib.sha256(f"{base_seed}:{'|'.join(keys)}".encode()).hexdigest()[:8], 16) % (2 ** 31)


class HFRunner:
    def __init__(self, device="cuda"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
        self.model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REVISION, torch_dtype=torch.float16,
                                                          attn_implementation="sdpa").to(device).eval()
        self.device = torch.device(device)
        eos = self.model.generation_config.eos_token_id
        self.eos = set([eos] if isinstance(eos, int) else eos)
        self.pad = self.tok.pad_token_id if self.tok.pad_token_id is not None else min(self.eos)
        self.steer = None  # (layer, tensor[B, d]) while generating a steered batch
        self.layers = self.model.model.layers
        self._hooked = set()
        self.info = {"backend": "transformers-batched", "torch": torch.__version__,
                     "transformers": __import__("transformers").__version__, "dtype": "float16",
                     "attn_implementation": "sdpa", "gpu": torch.cuda.get_device_name(0) if device == "cuda" else device}

    def prompt_ids(self, messages):
        return self.tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, enable_thinking=True,
                                        return_dict=False)

    def _hook(self, layer):
        if layer in self._hooked:
            return

        def hook(_module, _inputs, output):
            if self.steer is None or self.steer[0] != layer:
                return output
            hidden = output[0] if isinstance(output, (tuple, list)) else output
            hidden = hidden + self.steer[1][:, None, :].to(hidden.dtype)
            if isinstance(output, tuple):
                return (hidden, *output[1:])
            if isinstance(output, list):
                return [hidden, *output[1:]]
            return hidden
        self.layers[layer].register_forward_hook(hook)
        self._hooked.add(layer)

    def generate(self, prompts, seed, steer_layer=None, steer_vectors=None):
        """prompts: list of token-id lists. steer_vectors: (B, d) array or None.

        Adds steer_vectors[i] to the residual stream after block steer_layer at
        every position (prompt and generated) of row i. Returns per-row dicts.
        """
        torch = self.torch
        width = max(len(p) for p in prompts)
        ids = torch.full((len(prompts), width), self.pad, dtype=torch.long)
        mask = torch.zeros((len(prompts), width), dtype=torch.long)
        for i, p in enumerate(prompts):
            ids[i, width - len(p):] = torch.tensor(p)
            mask[i, width - len(p):] = 1
        if steer_vectors is not None:
            self._hook(steer_layer)
            self.steer = (steer_layer, torch.tensor(steer_vectors, dtype=torch.float32, device=self.device))
        try:
            torch.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
            with torch.inference_mode():
                out = self.model.generate(input_ids=ids.to(self.device), attention_mask=mask.to(self.device),
                                          do_sample=True, pad_token_id=self.pad, **GEN)
        finally:
            self.steer = None
        rows = []
        for i in range(len(prompts)):
            generated = out[i, width:].tolist()
            stop = next((j for j, t in enumerate(generated) if t in self.eos), None)
            if stop is None:
                rows.append({"generated": generated, "finish_reason": "length"})
            else:
                rows.append({"generated": generated[:stop + 1], "finish_reason": "stop"})
        return rows
