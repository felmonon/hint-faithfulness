import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.common import read_jsonl
from src.judge import run_judge
from src.openai_judge import DEFAULT_MODEL, OpenAIJudgeClient
from src.providers import BudgetExceededError
from tests.test_analysis import response


VERDICT = {"mentions_hint": False, "relies_on_hint": False, "only_final_check": False,
           "evidence": "", "explanation": "No explicit reliance."}


def api_response(status="completed", refusal=False):
    content = [{"type": "refusal", "refusal": "Refused"}] if refusal else [
        {"type": "output_text", "text": json.dumps(VERDICT)}]
    return {"id": "resp_test", "status": status, "model": DEFAULT_MODEL,
            "output": [{"type": "message", "content": content}],
            "usage": {"input_tokens": 100, "output_tokens": 50}}


class OpenAIJudgeTests(unittest.TestCase):
    messages = [{"role": "system", "content": "Label this trace."},
                {"role": "user", "content": "Research fixture."}]

    def client(self, ledger=None, budget=2):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "fake-test-credential"}):
            return OpenAIJudgeClient(budget_usd=budget, ledger_path=ledger)

    def test_structured_request_and_usage_accounting(self):
        client = self.client()
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(api_response()).encode())) as call:
            result = client.complete(self.messages, request_key="one")
        request = call.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
        payload = json.loads(request.data)
        self.assertFalse(payload["store"])
        self.assertEqual(payload["model"], DEFAULT_MODEL)
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(payload["service_tier"], "default")
        self.assertNotIn("reasoning", payload)
        self.assertEqual(json.loads(result["content"]), VERDICT)
        self.assertEqual(result["finish_reason"], "stop")
        self.assertAlmostEqual(client.spent_usd, .00012)
        self.assertNotIn("fake-test-credential", json.dumps(result))

    def test_budget_stops_before_request(self):
        client = self.client(budget=.000001)
        with patch("urllib.request.urlopen") as call:
            with self.assertRaises(BudgetExceededError):
                client.complete(self.messages)
        call.assert_not_called()

    def test_timeout_reservation_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "billing.jsonl"
            client = self.client(ledger)
            with patch("urllib.request.urlopen", side_effect=TimeoutError) as call:
                with self.assertRaisesRegex(RuntimeError, "timed out"):
                    client.complete(self.messages, request_key="one")
            self.assertEqual(call.call_count, 1)
            resumed = self.client(ledger)
            self.assertGreater(resumed.spent_usd, 0)
            with patch("urllib.request.urlopen") as call:
                with self.assertRaisesRegex(RuntimeError, "remains pending"):
                    resumed.complete(self.messages, request_key="one")
            call.assert_not_called()

    def test_completion_cache_survives_caller_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "billing.jsonl"
            with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(api_response()).encode())):
                first = self.client(ledger).complete(self.messages, request_key="one")
            resumed = self.client(ledger)
            with patch("urllib.request.urlopen") as call:
                second = resumed.complete(self.messages, request_key="one")
            call.assert_not_called()
            self.assertEqual(first, second)
            self.assertAlmostEqual(resumed.spent_usd, .00012)
            with self.assertRaisesRegex(ValueError, "different parameters"):
                resumed.complete(self.messages, max_tokens=200, request_key="one")

    def test_refusal_and_incomplete_do_not_become_valid_judgments(self):
        for status, refusal, finish in [("completed", True, "refusal"), ("incomplete", False, "length")]:
            with self.subTest(finish=finish), patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(api_response(status, refusal)).encode())):
                result = self.client().complete(self.messages)
            self.assertEqual(result["finish_reason"], finish)

    def test_never_substitutes_an_unpriced_or_reasoning_model(self):
        client = self.client()
        with patch("urllib.request.urlopen") as call:
            with self.assertRaisesRegex(ValueError, "Unsupported/unpriced"):
                client.complete(self.messages, model="another-model")
            with self.assertRaisesRegex(ValueError, "does not expose raw reasoning"):
                client.complete(self.messages, reasoning=True)
        call.assert_not_called()

    def test_rejects_another_backends_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "billing.jsonl"
            ledger.write_text('{"event":"opening_balance","delta_usd":0}\n')
            with self.assertRaisesRegex(ValueError, "another backend"):
                self.client(ledger)

    def test_judge_integration_qualifies_model_and_resumes(self):
        rows = [response("1"), response("1", "metadata", None, "B")]
        # Unit fixtures mimic local record metadata; every HTTP call is mocked.
        rows = [dict(row, backend="local", synthetic=False) for row in rows]
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"OPENAI_API_KEY": "fake-test-credential"}):
            path = Path(directory) / "judgments.jsonl"
            with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(api_response()).encode())):
                run_judge(rows, path, DEFAULT_MODEL, backend="openai")
            verdict = read_jsonl(path)[0]
            self.assertEqual(verdict["judge_model"], "openai:" + DEFAULT_MODEL)
            self.assertEqual(verdict["status"], "ok")
            self.assertFalse(verdict["faithful"])
            with patch("urllib.request.urlopen") as call:
                result = run_judge(rows, path, DEFAULT_MODEL, backend="openai")
            call.assert_not_called()
            self.assertEqual(result["calls"], 0)
            with self.assertRaisesRegex(ValueError, "fresh output file"):
                run_judge(rows, path, DEFAULT_MODEL, backend="openrouter")


if __name__ == "__main__":
    unittest.main()
