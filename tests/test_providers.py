import io
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from src.providers import OpenRouterClient


class ProviderTests(unittest.TestCase):
    catalog = [{"id": "test/model", "supported_parameters": ["reasoning", "seed", "top_k"],
                "pricing": {"prompt": "0.000001", "completion": "0.000002"}}]

    def client(self, budget=1, ledger=None):
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "fake-test-key"}), patch.object(OpenRouterClient, "models", return_value=self.catalog):
            return OpenRouterClient(budget_usd=budget, ledger_path=ledger)

    def test_extracts_reasoning_and_accounts_cost(self):
        raw = {"choices": [{"message": {"reasoning": "test reasoning", "content": "Answer: (C)"}, "finish_reason": "stop"}],
               "usage": {"cost": .001}, "provider": "test-provider", "model": "test/model"}
        client = self.client()
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(raw).encode())) as request:
            result = client.complete([{"role":"user", "content":"q"}], "test/model", seed=12)
        payload = json.loads(request.call_args.args[0].data)
        self.assertEqual(payload["reasoning"], {"enabled": True, "exclude": False})
        self.assertEqual(payload["seed"], 12)
        self.assertEqual(payload["provider"]["max_price"], {"prompt": 1.0, "completion": 2.0, "request": 0.0})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["answer"], "C")
        self.assertAlmostEqual(client.spent_usd, .001)
        self.assertNotIn("fake-test-key", json.dumps(result))

    def test_budget_prevents_request(self):
        client = self.client(.000001)
        with patch("urllib.request.urlopen") as request:
            with self.assertRaisesRegex(RuntimeError, "Budget guard"):
                client.complete([{"role":"user", "content":"q"}], "test/model")
        request.assert_not_called()

    def test_incomplete_output_not_silent_failure_of_faithfulness(self):
        raw = {"choices": [{"message": {"reasoning": "still thinking", "content": ""}, "finish_reason": "length"}], "usage": {}}
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(raw).encode())):
            result = self.client().complete([{"role":"user", "content":"q"}], "test/model")
        self.assertEqual(result["status"], "truncated")
        self.assertIsNone(result["answer"])

    def test_timeout_is_reserved_and_not_retried(self):
        client = self.client()
        with patch("urllib.request.urlopen", side_effect=TimeoutError) as request:
            with self.assertRaises(RuntimeError):
                client.complete([{"role":"user", "content":"q"}], "test/model")
        self.assertEqual(request.call_count, 1)
        self.assertGreater(client.spent_usd, 0)

    def test_interrupted_request_reservation_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "billing.jsonl"
            client = self.client(ledger=ledger)
            with patch("urllib.request.urlopen", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    client.complete([{"role":"user", "content":"q"}], "test/model", request_key="trial-1")
            resumed = self.client(ledger=ledger)
            self.assertGreater(resumed.spent_usd, 0)
            with patch("urllib.request.urlopen") as request:
                with self.assertRaisesRegex(RuntimeError, "remains pending"):
                    resumed.complete([{"role":"user", "content":"q"}], "test/model", request_key="trial-1")
            request.assert_not_called()

    def test_completed_response_survives_caller_crash_without_rebilling(self):
        raw = {"choices": [{"message": {"reasoning": "test", "content": "Answer: (A)"}, "finish_reason": "stop"}],
               "usage": {"cost": .001}}
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "billing.jsonl"
            with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(raw).encode())):
                first = self.client(ledger=ledger).complete([{"role":"user", "content":"q"}], "test/model", request_key="trial-1")
            resumed = self.client(ledger=ledger)
            with patch("urllib.request.urlopen") as request:
                second = resumed.complete([{"role":"user", "content":"q"}], "test/model", request_key="trial-1")
            self.assertEqual(first, second)
            self.assertAlmostEqual(resumed.spent_usd, .001)
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
