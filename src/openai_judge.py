"""Direct OpenAI Responses API judge; never used as a reasoning-trace subject."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import urllib.error
import urllib.request

from .common import append_jsonl, read_jsonl, stable_hash, utc_now
from .providers import BudgetExceededError, ledger_state

DEFAULT_MODEL = "gpt-4.1-mini-2025-04-14"
# Standard rates verified 2026-11-09. These are estimates, not an account cap.
# This model is scheduled to shut down on 2027-01-14; no silent replacement.
PRICES = {DEFAULT_MODEL: {"input": .40 / 1_000_000, "output": 1.60 / 1_000_000}}
VERDICT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "mentions_hint": {"type": "boolean"}, "relies_on_hint": {"type": "boolean"},
        "only_final_check": {"type": "boolean"}, "evidence": {"type": "string"},
        "explanation": {"type": "string"},
    },
    "required": ["mentions_hint", "relies_on_hint", "only_final_check", "evidence", "explanation"],
}


class OpenAIJudgeClient:
    """Single-writer, resumable paid calls with durable pre-request reservations."""
    def __init__(self, budget_usd=2.0, spent_usd=0.0, timeout=180, ledger_path=None):
        self.key = os.environ.get("OPENAI_API_KEY")
        if not self.key:
            raise RuntimeError("OPENAI_API_KEY is not configured; complete secure key setup before judging")
        if not math.isfinite(budget_usd) or budget_usd <= 0:
            raise ValueError("budget_usd must be finite and positive")
        self.budget_usd, self.spent_usd, self.timeout = budget_usd, spent_usd, timeout
        self.ledger_path = Path(ledger_path) if ledger_path else None
        self.pending, self.completed = {}, {}
        if self.ledger_path:
            if self.ledger_path.exists():
                entries = read_jsonl(self.ledger_path)
                if not entries or entries[0].get("backend") != "openai":
                    raise ValueError("Billing journal belongs to another backend; use a separate output file")
                self.spent_usd, self.pending = ledger_state(self.ledger_path)
                self.completed = {e["request_key"]: e["response"] for e in entries
                                  if e.get("event") == "settle" and "response" in e}
            else:
                append_jsonl(self.ledger_path, {"event": "opening_balance", "backend": "openai",
                                               "delta_usd": spent_usd, "at": utc_now()})

    def complete(self, messages, model=DEFAULT_MODEL, max_tokens=800, temperature=0,
                 top_p=1, top_k=None, reasoning=False, request_key=None):
        if model not in PRICES:
            raise ValueError(f"Unsupported/unpriced OpenAI judge model {model!r}; choose the documented pinned snapshot")
        if reasoning or top_k is not None:
            raise ValueError("OpenAI backend labels saved traces only; it does not expose raw reasoning or use top_k")
        if not isinstance(max_tokens, int) or max_tokens < 16:
            raise ValueError("max_tokens must be an integer of at least 16")
        payload = {"model": model, "input": messages, "max_output_tokens": max_tokens,
                   "temperature": temperature, "top_p": top_p, "store": False,
                   "service_tier": "default",
                   "text": {"format": {"type": "json_schema", "name": "hint_reliance_verdict",
                                        "strict": True, "schema": VERDICT_SCHEMA}}}
        request_key = request_key or stable_hash(payload)
        if request_key in self.completed:
            saved = self.completed[request_key]
            if saved.get("request_parameters") != payload:
                raise ValueError("Saved request key has different parameters; use a new output file")
            return saved
        if request_key in self.pending:
            raise RuntimeError("A prior OpenAI request remains pending in the billing journal; reconcile its charge before retrying")
        prices = PRICES[model]
        # UTF-8 bytes overcount ordinary text tokens; include schema and framing.
        prompt_bound = len(json.dumps(messages, ensure_ascii=False).encode()) + len(json.dumps(VERDICT_SCHEMA).encode()) + 1024
        reservation = prompt_bound * prices["input"] + max_tokens * prices["output"]
        if self.spent_usd + reservation > self.budget_usd:
            raise BudgetExceededError(f"OpenAI budget guard: next call could exceed ${self.budget_usd:.2f}; no request sent")
        if self.ledger_path:
            append_jsonl(self.ledger_path, {"event": "reserve", "request_key": request_key,
                                          "delta_usd": reservation, "at": utc_now()})
        self.pending[request_key] = reservation
        self.spent_usd += reservation
        request = urllib.request.Request("https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode(), headers={"Authorization": "Bearer " + self.key,
                                                       "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"OpenAI HTTP {exc.code}; not retried. Check account access/billing; the journal retains its reservation.") from None
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError("OpenAI connection failed or timed out; not retried because the request may have been billed") from None
        if raw.get("error") or not isinstance(raw.get("output"), list):
            raise RuntimeError("OpenAI returned no usable response; retain the journal and check account status")
        text, refused = [], False
        for item in raw["output"]:
            if item.get("type") != "message":
                continue
            for part in item.get("content", []):
                if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    text.append(part["text"])
                elif part.get("type") == "refusal":
                    refused = True
        status = raw.get("status")
        finish_reason = "refusal" if refused else "stop" if status == "completed" else "length" if status == "incomplete" else "error"
        usage = raw.get("usage") or {}
        token_counts = [usage.get("input_tokens"), usage.get("output_tokens")]
        valid_usage = all(type(n) is int and n >= 0 for n in token_counts)
        # Deliberately ignore cached-input discounts: conservative usage estimate.
        estimated_cost = (token_counts[0] * prices["input"] + token_counts[1] * prices["output"]) if valid_usage else reservation
        result = {"content": "".join(text), "reasoning": "", "finish_reason": finish_reason,
                  "usage": usage, "raw_response": raw, "request_parameters": payload,
                  "resolved_model": raw.get("model"), "provider": "openai",
                  "cost_usd": estimated_cost, "cost_is_estimate": True,
                  "pricing_verified_on": "2026-11-09", "pricing_usd_per_token": prices}
        if self.ledger_path:
            append_jsonl(self.ledger_path, {"event": "settle", "request_key": request_key,
                                          "delta_usd": estimated_cost - reservation,
                                          "response": result, "at": utc_now()})
        self.pending.pop(request_key, None)
        self.completed[request_key] = result
        self.spent_usd += estimated_cost - reservation
        return result
