import os
import unittest
from unittest import mock

from src.providers import OpenRouterClient


class EffortPin(unittest.TestCase):
    def client(self, supported):
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test"}), \
             mock.patch.object(OpenRouterClient, "models", staticmethod(lambda: [
                 {"id": "x/m", "supported_parameters": supported, "pricing": {"prompt": "0", "completion": "0"}}])):
            return OpenRouterClient(budget_usd=1.0)

    def test_effort_on_model_without_dial_raises_before_any_call(self):
        c = self.client(["reasoning"])
        with mock.patch("urllib.request.urlopen") as net:
            with self.assertRaisesRegex(ValueError, "reasoning_effort"):
                c.complete([{"role": "user", "content": "q"}], "x/m", reasoning_effort="high")
            net.assert_not_called()


if __name__ == "__main__":
    unittest.main()
