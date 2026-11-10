"""Paid-response recovery uses mocked HTTP and temporary journals only."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.common import read_jsonl, write_jsonl
from src.judge import judge_messages, run_judge
from src.openai_judge import DEFAULT_MODEL, OpenAIJudgeClient
from src.providers import OpenRouterClient
from tests.test_analysis import response
from tests.test_openai_judge import api_response


class BackendRecoveryTests(unittest.TestCase):
    catalog = [{"id": model, "supported_parameters": ["reasoning", "seed", "top_k"],
                "pricing": {"prompt": "0.000001", "completion": "0.000002"}}
               for model in ("test/model", "test/other")]
    messages = [{"role": "user", "content": "Public research fixture"}]
    raw = {"choices": [{"message": {"reasoning": "Fixture reasoning", "content": "Answer: (A)"},
                         "finish_reason": "stop"}], "usage": {"cost": .001}}

    def router(self, ledger, budget=1, catalog=None):
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake-test-key"}), patch.object(
                OpenRouterClient, "models", return_value=catalog or self.catalog):
            return OpenRouterClient(budget_usd=budget, ledger_path=ledger)

    def save_router_response(self, ledger, **kwargs):
        client = self.router(ledger)
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(self.raw).encode())):
            return client.complete(self.messages, "test/model", request_key="same-key", **kwargs)

    def test_openai_settlement_cannot_be_recovered_as_openrouter_after_caller_crash(self):
        rows = [dict(r, backend="local", synthetic=False) for r in
                [response("1"), response("1", "metadata", None, "B")]]
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {
                "OPENAI_API_KEY": "fake-openai-key", "OPENROUTER_API_KEY": "fake-router-key"}):
            output = Path(directory) / "judgments.jsonl"
            ledger = output.with_suffix(".jsonl.billing.jsonl")
            with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(api_response()).encode())):
                client = OpenAIJudgeClient(ledger_path=ledger)
                client.complete(judge_messages(rows[1]), model=DEFAULT_MODEL,
                                request_key=f"{rows[1]['record_id']}:attempt:1")
            # Simulate a crash before the caller wrote any judgment file.
            journal_before = ledger.read_bytes()
            with patch("urllib.request.urlopen") as http, patch.object(OpenRouterClient, "models") as catalog:
                with self.assertRaisesRegex(ValueError, "another backend"):
                    run_judge(rows, output, "test/model", backend="openrouter")
            http.assert_not_called()
            catalog.assert_not_called()
            self.assertFalse(output.exists())
            self.assertEqual(ledger.read_bytes(), journal_before)

    def test_new_router_journal_identifies_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "billing.jsonl"
            self.router(ledger)
            self.assertEqual(read_jsonl(ledger)[0]["backend"], "openrouter")

    def test_cached_response_rejects_changed_experiment_parameters_without_charging(self):
        original = {"seed": 12, "provider": "host-one"}
        changes = [dict(messages=[{"role": "user", "content": "Changed trace"}]),
                   dict(model="test/other"), dict(max_tokens=900), dict(temperature=.9),
                   dict(top_p=.8), dict(top_k=5), dict(seed=13), dict(reasoning=False),
                   dict(provider="host-two")]
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "billing.jsonl"
            self.save_router_response(ledger, **original)
            journal_before = ledger.read_bytes()
            for change in changes:
                with self.subTest(change=change):
                    resumed = self.router(ledger)
                    arguments = {"messages": self.messages, "model": "test/model", **original, **change}
                    with patch("urllib.request.urlopen") as http:
                        with self.assertRaisesRegex(ValueError, "different parameters"):
                            resumed.complete(**arguments, request_key="same-key")
                    http.assert_not_called()
                    self.assertEqual(ledger.read_bytes(), journal_before)

    def test_legacy_router_cache_with_verified_provenance_can_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "billing.jsonl"
            first = self.save_router_response(ledger)
            entries = read_jsonl(ledger)
            del entries[0]["backend"]  # Shape written by the original OpenRouter implementation.
            write_jsonl(ledger, entries)
            journal_before = ledger.read_bytes()
            resumed = self.router(ledger)
            with patch("urllib.request.urlopen") as http:
                recovered = resumed.complete(self.messages, "test/model", request_key="same-key")
            http.assert_not_called()
            self.assertEqual(recovered, first)
            self.assertEqual(ledger.read_bytes(), journal_before)

    def test_ambiguous_legacy_journal_is_not_assumed_to_be_router(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "billing.jsonl"
            write_jsonl(ledger, [{"event": "opening_balance", "delta_usd": 0},
                                {"event": "reserve", "request_key": "one", "delta_usd": .01}])
            with self.assertRaisesRegex(ValueError, "no verifiable OpenRouter response"):
                self.router(ledger)

    def test_unmarked_openai_response_does_not_pass_legacy_router_detection(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"OPENAI_API_KEY": "fake-key"}):
            ledger = Path(directory) / "billing.jsonl"
            with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(api_response()).encode())):
                OpenAIJudgeClient(ledger_path=ledger).complete(self.messages, request_key="same-key")
            entries = read_jsonl(ledger)
            del entries[0]["backend"]
            write_jsonl(ledger, entries)
            with self.assertRaisesRegex(ValueError, "without OpenRouter provenance"):
                self.router(ledger)

    def test_paid_cache_remains_recoverable_when_price_or_budget_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "billing.jsonl"
            first = self.save_router_response(ledger)
            changed_catalog = copy.deepcopy(self.catalog)
            for model in changed_catalog:
                model["pricing"]["completion"] = "0.01"
            # Recovery must not reserve a new call, even if the remaining budget
            # or current price would forbid making that call again.
            resumed = self.router(ledger, budget=.0001, catalog=changed_catalog)
            with patch("urllib.request.urlopen") as http:
                recovered = resumed.complete(self.messages, "test/model", request_key="same-key")
            http.assert_not_called()
            self.assertEqual(first, recovered)
            self.assertAlmostEqual(resumed.spent_usd, .001)


if __name__ == "__main__":
    unittest.main()
