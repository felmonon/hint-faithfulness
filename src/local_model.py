"""Pinned, unquantized Qwen3 model for all phases. Imports are lazy."""
from __future__ import annotations

from .common import parse_answer, response_status

MODEL_REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"


class LocalModel:
    def __init__(self, model_id="Qwen/Qwen3-1.7B", revision=None, device="auto"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.model_id = model_id
        self.revision = revision or (MODEL_REVISION if model_id == "Qwen/Qwen3-1.7B" else "main")
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = torch.device(device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, revision=self.revision)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, revision=self.revision,
            torch_dtype=torch.float32 if device == "cpu" else torch.float16,
            attn_implementation="eager",
        ).to(self.device).eval()
        self.revision = getattr(self.model.config, "_commit_hash", None) or self.revision
        self.close_think = self.tokenizer.encode("</think>", add_special_tokens=False)
        if len(self.close_think) != 1:
            raise ValueError("This adapter requires a single Qwen </think> token")

    def prompt_ids(self, messages):
        return self.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                                   enable_thinking=True, return_dict=False)

    def generate(self, messages, seed, max_new_tokens=2048, temperature=.6, top_p=.95, top_k=20):
        import torch
        from transformers import set_seed

        set_seed(seed)
        prompt_ids = self.prompt_ids(messages)
        inputs = torch.tensor([prompt_ids], device=self.device)
        with torch.inference_mode():
            generated = self.model.generate(
                input_ids=inputs, attention_mask=torch.ones_like(inputs),
                max_new_tokens=max_new_tokens, do_sample=True,
                temperature=temperature, top_p=top_p, top_k=top_k,
                pad_token_id=self.tokenizer.eos_token_id,
            )[0, len(prompt_ids):].tolist()
        eos = self.model.generation_config.eos_token_id
        eos_ids = [eos] if isinstance(eos, int) else (eos or [])
        finish_reason = "stop" if generated and generated[-1] in eos_ids else "length"
        complete_thinking = self.close_think[0] in generated
        if complete_thinking:
            boundary = generated.index(self.close_think[0])
            opening = self.tokenizer.encode("<think>", add_special_tokens=False)
            start = generated.index(opening[0]) + 1 if len(opening) == 1 and opening[0] in generated[:boundary] else 0
            reasoning_ids, answer_ids = generated[start:boundary], generated[boundary + 1:]
            reasoning = self.tokenizer.decode(reasoning_ids, skip_special_tokens=True)
            content = self.tokenizer.decode(answer_ids, skip_special_tokens=True).strip()
        else:
            reasoning_ids = generated
            reasoning = self.tokenizer.decode(generated, skip_special_tokens=True)
            content = ""
            # Preserve actual EOS vs token-limit termination for attrition analysis.
            # Missing thinking closure is not evidence of an unfaithful explanation.
        status = response_status(reasoning, content, finish_reason)
        if not complete_thinking and finish_reason == "stop":
            status = "incomplete_thinking"
        return {
            "reasoning": reasoning, "content": content, "answer": parse_answer(content),
            "status": status, "finish_reason": finish_reason, "complete_thinking": complete_thinking,
            "usage": {"prompt_tokens": len(prompt_ids), "completion_tokens": len(generated)},
            "prompt_token_ids": prompt_ids, "generated_token_ids": generated,
            "reasoning_token_ids": reasoning_ids, "model_revision": self.revision,
            "dtype": str(self.model.dtype), "device": str(self.device),
        }
