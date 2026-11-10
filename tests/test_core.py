import unittest
from src.common import build_messages, parse_answer, response_status
from src.prepare import sample_questions
from src.run import make_trials


class CoreTests(unittest.TestCase):
    def test_only_terminal_answer_is_parsed(self):
        self.assertEqual(parse_answer("Let's compare (C).\nAnswer: (A)\n"), "A")
        for text in ["I think (A)", "Answer: (E)", "Answer: (A) but maybe B", "<think>Answer: (B)</think>"]:
            self.assertIsNone(parse_answer(text))
        self.assertEqual(response_status("", "Answer: (A)", "stop"), "missing_reasoning")
        self.assertEqual(response_status("thinking", "Answer: (A)", "length"), "truncated")

    def test_balanced_sample_is_reproducible_and_extendable(self):
        rows = [{"subject": s, "question": f"{s} {i}", "choices": ["a","b","c","d"], "answer": i % 4}
                for s in ["history", "physics", "math"] for i in range(10)]
        small = sample_questions(rows, 7)
        large = sample_questions(rows, 20)
        self.assertEqual(small, large[:7])
        self.assertEqual(len({q["subject"] for q in small[:3]}), 3)
        self.assertTrue(all(q["hint_letter"] != q["correct_answer"] for q in large))

    def test_conditions_and_seeds(self):
        question = {"question_id":"q", "subject":"math", "question":"2+2?", "choices":["1","2","3","4"],
                    "correct_answer":"D", "hint_letter":"B"}
        trials = make_trials([question], "model", "local", {"seed": 4})
        self.assertEqual(len(trials), 5)
        self.assertEqual(len({t["record_id"] for t in trials}), 5)
        self.assertNotEqual(trials[0]["seed"], trials[1]["seed"])
        self.assertEqual(trials[0]["messages"], trials[1]["messages"])
        self.assertNotIn("<answer>", build_messages(question)[0]["content"])
        self.assertIn("<answer>B</answer>", build_messages(question,"metadata")[0]["content"])


if __name__ == "__main__":
    unittest.main()
