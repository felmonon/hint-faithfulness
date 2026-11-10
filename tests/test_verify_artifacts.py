"""In-memory fixtures test integrity checks; none are experimental evidence."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.common import read_jsonl, stable_hash, write_jsonl
from src.local_model import MODEL_REVISION
from src.run import make_trials
from src.verify_artifacts import CLOSE_THINK, MODEL, PARAMETERS, audit_files, audit_records

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = ROOT / "data/questions.jsonl"


class ArtifactAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.questions = read_jsonl(QUESTIONS_PATH)
        cls.question_manifest = json.loads(QUESTIONS_PATH.with_suffix(".jsonl.manifest.json").read_text())
        all_trials = make_trials(cls.questions, MODEL, "local", PARAMETERS)
        cls.manifest = {"experiment_id": all_trials[0]["experiment_id"], "model": MODEL,
                        "backend": "local", "revision": MODEL_REVISION, "provider": None,
                        "parameters": PARAMETERS, "questions_sha256": stable_hash(cls.questions), "device": "cuda",
                        "prompts_sha256": stable_hash([trial["messages"] for trial in all_trials])}
        cls.fixture_rows = [{**trial, "reasoning": "Test-only reasoning.", "content": "Answer: (A)",
                             "answer": "A", "status": "ok", "finish_reason": "stop", "complete_thinking": True,
                             "usage": {"prompt_tokens": 4, "completion_tokens": 5},
                             "prompt_token_ids": [1, 2, 151667, 198],
                             "generated_token_ids": [27, 28, CLOSE_THINK, 17, 151645],
                             "reasoning_token_ids": [27, 28], "model_revision": MODEL_REVISION,
                             "dtype": "torch.float16", "device": "cuda:0",
                             "started_at": "2026-11-10T01:00:00+00:00", "finished_at": "2026-11-10T01:00:01+00:00"}
                            for trial in all_trials[:100]]

    def setUp(self):
        self.rows = copy.deepcopy(self.fixture_rows)

    def audit(self, **kwargs):
        return audit_records(self.rows, kwargs.get("questions", self.questions),
                             kwargs.get("manifest", self.manifest), kwargs.get("questions_manifest", self.question_manifest))

    @staticmethod
    def codes(report):
        return {item["code"] for item in report["failures"]}

    def test_complete_pilot_reconstructed_from_full_parent_sample(self):
        report = self.audit()
        self.assertTrue(report["ok"], report["failures"])
        self.assertTrue(report["collection_complete"])
        self.assertEqual(report["status_counts"], {"ok": 100})
        self.assertEqual(report["token_records_checked"], 100)
        short_trials = make_trials(self.questions[:20], MODEL, "local", PARAMETERS)
        self.assertNotEqual(self.rows[0]["record_id"], short_trials[0]["record_id"])
        self.assertEqual(self.rows, self.fixture_rows)  # Audit never mutates inputs.

    def test_missing_duplicate_and_wrong_question_cannot_count_as_complete(self):
        self.rows[-1] = copy.deepcopy(self.rows[0])
        report = self.audit()
        self.assertFalse(report["collection_complete"])
        self.assertIn("record_set", self.codes(report))
        self.assertIn("question_coverage", self.codes(report))
        self.rows = copy.deepcopy(self.fixture_rows)
        self.rows.pop()
        self.assertFalse(self.audit()["collection_complete"])

    def test_trial_and_model_metadata_tampering_is_detected(self):
        for field, value, code in [("prompt", "altered prompt", "trial_fields"),
                                   ("seed", 2, "trial_fields"),
                                   ("synthetic", True, "real_local_model"),
                                   ("backend", "openai", "real_local_model"),
                                   ("model_revision", "main", "model_revision"),
                                   ("dtype", "torch.float32", "runtime_precision")]:
            with self.subTest(field=field):
                self.rows = copy.deepcopy(self.fixture_rows)
                self.rows[0][field] = value
                self.assertIn(code, self.codes(self.audit()))

    def test_manifest_and_frozen_questions_are_bound_to_protocol(self):
        for field, value in [("prompts_sha256", "0" * 64), ("revision", "main"),
                             ("parameters", {**PARAMETERS, "max_tokens": 8192})]:
            with self.subTest(field=field):
                report = self.audit(manifest={**self.manifest, field: value})
                self.assertIn("run_manifest", self.codes(report))
        changed = copy.deepcopy(self.questions)
        changed[0]["question"] += " altered"
        self.assertIn("frozen_questions", self.codes(self.audit(questions=changed)))
        self.assertIn("question_manifest", self.codes(self.audit(questions_manifest={**self.question_manifest, "sample_sha256": "0" * 64})))

    def test_timestamps_and_answer_status_consistency(self):
        for field, value, code in [("started_at", "2026-11-10T01:00:02+00:00", "timestamps"),
                                   ("started_at", "2026-11-10T01:00:00", "timestamps"),
                                   ("finished_at", "not a date", "timestamps"),
                                   ("answer", "B", "response_status"),
                                   ("status", "truncated", "response_status")]:
            with self.subTest(field=field, value=value):
                self.rows = copy.deepcopy(self.fixture_rows)
                self.rows[0][field] = value
                self.assertIn(code, self.codes(self.audit()))

    def test_exact_token_arrays_and_counts(self):
        cases = [("reasoning_token_ids", [28], "reasoning_tokens"),
                 ("generated_token_ids", [27, 28, CLOSE_THINK, 17, 99], "token_termination"),
                 ("prompt_token_ids", [True, 2, 3, 4], "token_schema"),
                 ("usage", {"prompt_tokens": 8, "completion_tokens": 5}, "token_counts"),
                 ("complete_thinking", False, "thinking_boundary")]
        for field, value, code in cases:
            with self.subTest(field=field):
                self.rows = copy.deepcopy(self.fixture_rows)
                self.rows[0][field] = value
                self.assertIn(code, self.codes(self.audit()))
        self.rows = copy.deepcopy(self.fixture_rows)
        self.rows[1]["prompt_token_ids"][0] = 900
        self.assertIn("prompt_token_consistency", self.codes(self.audit()))
        self.rows = copy.deepcopy(self.fixture_rows)
        del self.rows[0]["reasoning_token_ids"]
        self.assertIn("token_schema", self.codes(self.audit()))

    def test_missing_tokens_are_explicit_warning_not_invented_evidence(self):
        for field in ("prompt_token_ids", "generated_token_ids", "reasoning_token_ids"):
            del self.rows[0][field]
        report = self.audit()
        self.assertTrue(report["ok"], report["failures"])
        self.assertEqual(report["token_records_checked"], 99)
        self.assertIn("tokens_absent", {item["code"] for item in report["warnings"]})

    def test_truncation_incomplete_thinking_and_exception_are_attrition(self):
        self.rows[0].update(reasoning="Unclosed test reasoning.", content="", answer=None, status="truncated",
                            finish_reason="length", complete_thinking=False, generated_token_ids=[27] * 4096,
                            reasoning_token_ids=[27] * 4096, usage={"prompt_tokens": 4, "completion_tokens": 4096})
        self.rows[1].update(reasoning="Unclosed test reasoning.", content="", answer=None, status="incomplete_thinking",
                            finish_reason="stop", complete_thinking=False, generated_token_ids=[27, 151645],
                            reasoning_token_ids=[27, 151645], usage={"prompt_tokens": 4, "completion_tokens": 2})
        self.rows[2].update(reasoning="", content="", answer=None, status="error", error_type="RuntimeError",
                            finish_reason=None, usage={})
        for field in ("prompt_token_ids", "generated_token_ids", "reasoning_token_ids", "model_revision", "dtype", "device", "complete_thinking"):
            del self.rows[2][field]
        report = self.audit()
        self.assertTrue(report["ok"], report["failures"])
        self.assertTrue(report["collection_complete"])
        self.assertEqual(report["status_counts"], {"error": 1, "incomplete_thinking": 1, "ok": 97, "truncated": 1})
        self.assertIn("response_attrition", {item["code"] for item in report["warnings"]})

    def write_fixture_files(self, directory):
        records = directory / "responses.jsonl"
        write_jsonl(records, self.rows)
        manifest = records.with_suffix(".jsonl.manifest.json")
        manifest.write_text(json.dumps(self.manifest) + "\n")
        checksums = directory / "checksums.json"
        checksums.write_text(json.dumps({file.name: hashlib.sha256(file.read_bytes()).hexdigest()
                                        for file in (records, manifest)}))
        return records, manifest, checksums

    def test_original_checksums_verified_without_writes_and_tampering_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records, manifest, checksums = self.write_fixture_files(root)
            before = {path: path.read_bytes() for path in root.iterdir()}
            report = audit_files(records, QUESTIONS_PATH)
            self.assertTrue(report["ok"], report["failures"])
            self.assertEqual(report["checksums"]["status"], "verified")
            self.assertEqual(before, {path: path.read_bytes() for path in root.iterdir()})
            records.write_bytes(records.read_bytes() + b"\n")  # Valid JSONL, different raw bytes.
            report = audit_files(records, QUESTIONS_PATH)
            self.assertIn("checksum_mismatch", self.codes(report))
            checksums.write_text(json.dumps({"../outside.txt": "0" * 64}))
            self.assertIn("checksum_entry", self.codes(audit_files(records, QUESTIONS_PATH)))
            checksums.write_text(json.dumps({manifest.name: hashlib.sha256(manifest.read_bytes()).hexdigest()}))
            self.assertIn("checksum_core_coverage", self.codes(audit_files(records, QUESTIONS_PATH)))

    def test_cli_returns_json_nonzero_for_incomplete_or_malformed_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            records, _, checksums = self.write_fixture_files(Path(directory))
            checksums.unlink()
            write_jsonl(records, self.rows[:1])
            result = subprocess.run([sys.executable, "-m", "src.verify_artifacts", "--records", str(records),
                                     "--questions", str(QUESTIONS_PATH)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            report = json.loads(result.stdout)
            self.assertFalse(report["collection_complete"])
            self.assertEqual(report["checksums"]["status"], "absent")
            records.write_text('{"interrupted":')
            report = audit_files(records, QUESTIONS_PATH)
            self.assertIn("input_read", self.codes(report))


if __name__ == "__main__":
    unittest.main()
