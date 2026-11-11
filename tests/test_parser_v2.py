import json
import unittest
from collections import Counter
from pathlib import Path

from src.parser_v2 import parse_answer_strict, parse_answer_v2, response_status_v2

PILOT = Path(__file__).resolve().parents[1] / "artifacts/pilot-20-qwen3-1.7b/responses.jsonl"


class PilotEndings(unittest.TestCase):
    def test_all_21_pilot_invalid_endings_parse(self):
        rows = [json.loads(line) for line in PILOT.open()]
        invalid = [r for r in rows if r["status"] == "invalid_answer"]
        self.assertEqual(len(invalid), 21)
        rules = Counter()
        for row in invalid:
            self.assertIsNone(parse_answer_strict(row["content"]))
            parsed = parse_answer_v2(row["content"])
            self.assertIn(parsed["answer"], list("ABCD"), row["content"][-120:])
            rules[parsed["rule"]] += 1
        # 12 option-text + 3 bold Markdown -> line declarations; 6 LaTeX -> boxed.
        self.assertEqual(rules, Counter({"line_declaration": 15, "boxed": 6}))

    def test_v2_agrees_with_strict_wherever_strict_parses(self):
        rows = [json.loads(line) for line in PILOT.open()]
        for row in rows:
            strict = parse_answer_strict(row["content"])
            if strict:
                parsed = parse_answer_v2(row["content"])
                self.assertEqual(parsed["answer"], strict)
                self.assertEqual(parsed["rule"], "strict_terminal")


class Rules(unittest.TestCase):
    def check(self, text, letter, rule):
        parsed = parse_answer_v2(text)
        self.assertEqual((parsed["answer"], parsed["rule"]), (letter, rule), text)

    def test_examples_from_brief(self):
        self.check("Answer: (B) Ectopic pregnancy", "B", "line_declaration")
        self.check("blah\n\n$$\\boxed{D}$$", "D", "boxed")
        self.check("### Final Answer:\n$$\n\\text{Answer: } \\boxed{A}\n$$", "A", "boxed")
        self.check("**Answer:** (B)", "B", "line_declaration")
        self.check("**Answer: (B)**", "B", "line_declaration")
        self.check("Reasoning...\nAnswer: (C)", "C", "strict_terminal")

    def test_bare_letters(self):
        self.check("Final answer: D", "D", "line_declaration")
        self.check("Answer: C.", "C", "line_declaration")
        # A bare letter that begins a word is not a declaration.
        self.check("Answer: A good option is unclear.", None, "none")

    def test_conflicting_declarations_rejected(self):
        for text in ("Answer: (A)\nAnswer: (B)", "\\boxed{A}\n\nAnswer: (C)",
                     "**Answer:** (B) 125\n\n$$\\boxed{D}$$", "Final Answer: (A)\nAnswer: (D) foo"):
            parsed = parse_answer_v2(text)
            self.assertIsNone(parsed["answer"], text)
            self.assertEqual(parsed["rule"], "conflict")
            self.assertGreater(len(parsed["letters"]), 1)

    def test_repeated_same_letter_is_fine(self):
        self.check("Answer: (A) foo\n\n\\boxed{A}", "A", "boxed+line_declaration")

    def test_no_answer(self):
        for text in ("", None, "I think it's (B) but not sure", "- **(D)** Context-free, true"):
            self.assertIsNone(parse_answer_v2(text)["answer"])

    def test_status(self):
        self.assertEqual(response_status_v2("r", "Answer: (B) x", "stop"), "ok")
        self.assertEqual(response_status_v2("r", "Answer: (B) x", "length"), "truncated")
        self.assertEqual(response_status_v2("r", "nothing", "stop"), "invalid_answer")
        self.assertEqual(response_status_v2("", "Answer: (B)", "stop"), "missing_reasoning")
        self.assertEqual(response_status_v2("r", "", "stop", complete_thinking=False), "incomplete_thinking")


if __name__ == "__main__":
    unittest.main()
