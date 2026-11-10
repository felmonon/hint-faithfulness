import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_openai_pilot_judge as wrapper
from src.common import append_jsonl, read_jsonl, write_jsonl


class OpenAIPilotWrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.folder = self.project / "results/pilot-20-openai-v1"
        self.folder.mkdir(parents=True)
        self.output = self.folder / "judgments.jsonl"
        self.ledger = self.output.with_suffix(".jsonl.billing.jsonl")
        self.key = self.project / ".env.local"
        self.key.write_text("OPENAI_API_KEY=sk-fake\n")
        self.key.chmod(0o600)
        ids = [f"record-{i}" for i in range(10)]
        hashes = {}
        for name, relative, count in [("original90", "responses.jsonl", 8),
                                       ("composite100", "recovery-composite/responses.jsonl", 10)]:
            path = self.project / "artifacts/pilot-20-qwen3-1.7b" / relative
            write_jsonl(path, [{"record_id": rid} for rid in ids[:count]])
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.folder / "run-plan.json").write_text(json.dumps({
            "original_eligible_ids": ids[:8], "composite_eligible_ids": ids, "source_sha256": hashes}))

    def fake_judge(self, records, output, **kwargs):
        self.assertEqual(kwargs["backend"], "openai")
        self.assertEqual(kwargs["model"], "gpt-4.1-mini-2025-04-14")
        self.assertEqual(kwargs["budget"], 2.0)
        self.assertFalse(kwargs["retry_errors"])
        existing = read_jsonl(output)
        ids = {row["record_id"] for row in existing}
        if not self.ledger.exists():
            append_jsonl(self.ledger, {"event": "opening_balance", "delta_usd": 0})
        for row in [r for r in records if r["record_id"] not in ids][:kwargs["limit"]]:
            existing.append({"record_id": row["record_id"], "status": "ok"})
            append_jsonl(self.ledger, {"event": "settle", "request_key": row["record_id"], "delta_usd": .001})
        write_jsonl(output, existing)

    def test_stage_limits_idempotent_resume_and_shared_budget(self):
        with patch.object(wrapper, "run_judge", side_effect=self.fake_judge) as judge:
            self.assertEqual(wrapper.execute_stage("smoke", self.project)["completed_unique_verdicts"], 5)
            wrapper.execute_stage("smoke", self.project)
            self.assertEqual(judge.call_count, 1)  # Repeating smoke cannot add three more calls.
            with self.assertRaisesRegex(ValueError, "preceding stage"):
                wrapper.execute_stage("composite", self.project)
            self.assertEqual(wrapper.execute_stage("original", self.project)["completed_unique_verdicts"], 8)
            final = wrapper.execute_stage("composite", self.project)
            self.assertEqual(final["completed_unique_verdicts"], 10)
            self.assertAlmostEqual(final["shared_recorded_or_reserved_usd"], .010)
            self.assertEqual([call.kwargs["limit"] for call in judge.call_args_list], [5, 3, 2])

    def test_error_return_and_pending_journal_stop_without_retry(self):
        def saved_error(records, output, **kwargs):
            append_jsonl(self.ledger, {"event": "opening_balance", "delta_usd": 0})
            write_jsonl(output, [{"record_id": "record-0", "status": "error"}])
        with patch.object(wrapper, "run_judge", side_effect=saved_error) as judge:
            with self.assertRaisesRegex(ValueError, "Saved judge error"):
                wrapper.execute_stage("smoke", self.project)
            with self.assertRaisesRegex(ValueError, "Saved judge error"):
                wrapper.execute_stage("smoke", self.project)
            self.assertEqual(judge.call_count, 1)
        self.output.unlink()
        append_jsonl(self.ledger, {"event": "reserve", "request_key": "record-0", "delta_usd": .1})
        with patch.object(wrapper, "load_approved_key") as loader:
            with self.assertRaisesRegex(ValueError, "Pending"):
                wrapper.execute_stage("smoke", self.project)
            loader.assert_not_called()

    def test_literal_private_file_only_and_symlink_rejected(self):
        self.assertEqual(wrapper.load_approved_key(self.project), "sk-fake")
        self.key.write_text("OPENAI_API_KEY=$(not-executed)\n")
        with self.assertRaisesRegex(ValueError, "syntax"):
            wrapper.load_approved_key(self.project)
        self.key.unlink()
        self.key.symlink_to(self.folder / "run-plan.json")
        with self.assertRaisesRegex(ValueError, "symlink"):
            wrapper.load_approved_key(self.project)


if __name__ == "__main__":
    unittest.main()
