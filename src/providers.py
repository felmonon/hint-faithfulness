"""OpenRouter HTTP client with visible reasoning and an explicit spend ceiling."""
from __future__ import annotations

import json
import os
import math
import urllib.error
import urllib.request
from pathlib import Path

from .common import append_jsonl, parse_answer, read_jsonl, response_status, stable_hash, utc_now


class BudgetExceededError(RuntimeError):
    """No request was sent because its estimate would exceed the file budget."""


def ledger_state(path):
    spent, pending = 0.0, {}
    for entry in read_jsonl(path):
        spent += entry["delta_usd"]
        if entry["event"] == "reserve":
            pending[entry["request_key"]] = entry["delta_usd"]
        elif entry["event"] == "settle":
            pending.pop(entry["request_key"], None)
    return spent, pending


class OpenRouterClient:
    def __init__(self, budget_usd=10.0, spent_usd=0.0, timeout=180, ledger_path=None):
        self.key = os.environ.get("OPENROUTER_API_KEY")
        if not self.key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured. Set it in your terminal; never put it in data or source files.")
        if not math.isfinite(budget_usd) or budget_usd <= 0:
            raise ValueError("budget_usd must be positive")
        self.budget_usd, self.spent_usd, self.timeout = budget_usd, spent_usd, timeout
        self.ledger_path = Path(ledger_path) if ledger_path else None
        self.pending = {}
        self.completed = {}
        if self.ledger_path:
            if self.ledger_path.exists():
                self.spent_usd, self.pending = ledger_state(self.ledger_path)
                self.completed = {entry["request_key"]: entry["response"] for entry in read_jsonl(self.ledger_path)
                                  if entry.get("event") == "settle" and "response" in entry}
            else:
                append_jsonl(self.ledger_path, {"event": "opening_balance", "delta_usd": spent_usd, "at": utc_now()})
        self.catalog = {m["id"]: m for m in self.models()}

    @staticmethod
    def models():
        with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30) as response:
            return json.load(response)["data"]

    def complete(self, messages, model, max_tokens=2048, temperature=.6, top_p=.95,
                 top_k=20, seed=None, reasoning=True, provider=None, request_key=None):
        # A crash after durable completion but before the caller saves its row
        # reuses the already paid response rather than paying a second time.
        if request_key and request_key in self.completed:
            return self.completed[request_key]
        entry = self.catalog.get(model)
        if entry is None:
            raise ValueError(f"Model {model} is absent from the current OpenRouter catalog")
        supported = entry.get("supported_parameters", [])
        if reasoning and "reasoning" not in supported:
            raise ValueError(f"{model} does not advertise reasoning support")
        # Bytes plus per-message overhead is deliberately conservative, not a bill.
        prompt_bound = sum(len(m["content"].encode()) + 64 for m in messages)
        prices = entry.get("pricing", {})
        upper_cost = prompt_bound * float(prices.get("prompt", 0)) + max_tokens * float(prices.get("completion", 0)) + float(prices.get("request", 0))
        if self.spent_usd + upper_cost > self.budget_usd:
            raise BudgetExceededError(f"Budget guard: next call could exceed ${self.budget_usd:.2f}. Recorded/reserved spend ${self.spent_usd:.4f}.")
        payload = {"model": model, "messages": messages, "max_tokens": max_tokens,
                   "temperature": temperature, "top_p": top_p,
                   "provider": {"require_parameters": True, "allow_fallbacks": False,
                                "max_price": {"prompt": float(prices.get("prompt", 0)) * 1_000_000,
                                              "completion": float(prices.get("completion", 0)) * 1_000_000,
                                              "request": float(prices.get("request", 0))}}}
        if top_k is not None and "top_k" in supported:
            payload["top_k"] = top_k
        if seed is not None and "seed" in supported:
            payload["seed"] = seed
        if provider:
            payload["provider"]["order"] = [provider]
        if reasoning:
            payload["reasoning"] = {"enabled": True, "exclude": False}
        request_key = request_key or stable_hash(payload)
        if request_key in self.pending:
            raise RuntimeError("A prior request remains pending in the billing journal. Reconcile its charge before retrying (python -m src.billing --help).")
        request = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(payload).encode(), headers={"Authorization": "Bearer " + self.key,
                                                       "Content-Type": "application/json"})
        # Reserve before sending. No blind retries: timeouts may already be billed.
        if self.ledger_path:
            append_jsonl(self.ledger_path, {"event": "reserve", "request_key": request_key,
                         "delta_usd": upper_cost, "at": utc_now()})
        self.pending[request_key] = upper_cost
        self.spent_usd += upper_cost
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"OpenRouter HTTP {exc.code}; request not retried. Check account/provider status.") from None
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError("OpenRouter connection failed or timed out; request not retried because it may have been billed.") from None
        if "error" in raw or not raw.get("choices"):
            raise RuntimeError("OpenRouter returned no completion; inspect account/provider status")
        choice = raw["choices"][0]
        message = choice.get("message", {})
        reasoning_text = message.get("reasoning") or ""
        content = message.get("content") or ""
        if not isinstance(reasoning_text, str):
            reasoning_text = ""
        if not isinstance(content, str):
            content = ""
        finish_reason = choice.get("finish_reason")
        cost = raw.get("usage", {}).get("cost")
        charged = float(cost) if isinstance(cost, (int, float)) and cost >= 0 else upper_cost
        result = {"reasoning": reasoning_text, "content": content, "answer": parse_answer(content),
                "status": response_status(reasoning_text, content, finish_reason),
                "finish_reason": finish_reason, "usage": raw.get("usage", {}),
                "cost_usd": charged, "cost_is_estimate": not isinstance(cost, (int, float)),
                "provider": raw.get("provider"), "resolved_model": raw.get("model"),
                "request_parameters": payload, "raw_response": raw}
        if self.ledger_path:
            append_jsonl(self.ledger_path, {"event": "settle", "request_key": request_key,
                         "delta_usd": charged - upper_cost, "response": result, "at": utc_now()})
        self.completed[request_key] = result
        self.pending.pop(request_key, None)
        self.spent_usd += charged - upper_cost
        return result
