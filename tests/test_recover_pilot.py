"""In-memory/scratch fixtures only; no inference or experimental evidence."""
import copy
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from scripts import recover_pilot as recovery

ROOT = Path(__file__).resolve().parents[1]


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / "frozen-project"
        (self.project / ".git").mkdir(parents=True)
        (self.project / ".git/HEAD").write_text(recovery.SOURCE_REVISION + "\n")
        for name in (*recovery.SOURCE_HASHES, "data/questions.jsonl"):
            target = self.project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        _, self.trials, self.manifest = recovery.verify_project(self.project)
        self.original = self.project / "artifacts/pilot-20-qwen3-1.7b"
        self.original.mkdir(parents=True)
        self.composite = self.original / "recovery-composite"
        missing = set(recovery.MISSING_BY_ORDINAL.values())
        self.rows = [self.result(trial) for trial in self.trials if trial["record_id"] not in missing]
        self.write_rows(self.original / recovery.RAW_NAME, self.rows)
        (self.original / recovery.MANIFEST_NAME).write_text(json.dumps(self.manifest) + "\n")
        (self.original / "collection.log").write_text("".join(
            f"[{n}/100] {trial['question_id']} {trial['hint_type']} -> ok\n" for n, trial in enumerate(self.trials, 1)))
        (self.original / "runtime.json").write_text(json.dumps({"git_commit": recovery.SOURCE_REVISION}))

    @staticmethod
    def result(trial, started="2026-11-10T01:00:00+00:00"):
        return {**copy.deepcopy(trial), "status": "ok", "reasoning": "TEST FIXTURE ONLY.",
                "content": "Answer: (A)", "answer": "A", "finish_reason": "stop", "complete_thinking": True,
                "model_revision": recovery.MODEL_REVISION, "dtype": "torch.float16", "device": "cuda",
                "started_at": started, "finished_at": started}

    @staticmethod
    def write_rows(path, rows):
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def append_recovery(self, prep, timestamp=None):
        started = timestamp or (datetime.fromisoformat(prep["prepared_at"]) + timedelta(seconds=1)).isoformat()
        missing = set(recovery.MISSING_BY_ORDINAL.values())
        appended = [self.result(trial, started) for trial in self.trials if trial["record_id"] in missing]
        with (self.composite / recovery.RAW_NAME).open("a") as handle:
            handle.write("".join(json.dumps(row) + "\n" for row in appended))
        return appended

    def test_prepare_and_finalize_preserve_bytes_and_identify_new_generations(self):
        original_bytes = {path.name: path.read_bytes() for path in self.original.iterdir() if path.is_file()}
        prep = recovery.prepare(self.project)
        self.assertEqual((self.composite / recovery.RAW_NAME).read_bytes(), original_bytes[recovery.RAW_NAME])
        self.append_recovery(prep)
        lineage = recovery.finalize(self.project)
        self.assertEqual(lineage["counts"], {"original_attempts": 100, "preserved_original_rows": 90,
                                            "recovery_attempts": 10, "composite_rows": 100, "total_generation_attempts": 110})
        self.assertEqual(sum(row["origin"] == "retained_original" for row in lineage["records"]), 90)
        regenerated = {row["record_id"] for row in lineage["records"] if row["origin"] == "recovery_generation"}
        self.assertEqual(regenerated, set(recovery.MISSING_BY_ORDINAL.values()))
        self.assertEqual(original_bytes, {path.name: path.read_bytes() for path in self.original.iterdir() if path.is_file()})
        self.assertIn("do not establish equality", lineage["notice"])
        with self.assertRaisesRegex(ValueError, "already exists"):
            recovery.finalize(self.project)

    def test_unexpected_loss_or_duplicate_is_rejected_before_writing(self):
        wrong = self.rows[:-1] + [self.result(self.trials[8])]
        self.write_rows(self.original / recovery.RAW_NAME, wrong)
        with self.assertRaisesRegex(ValueError, "fixed ten"):
            recovery.prepare(self.project)
        self.assertFalse(self.composite.exists())
        self.write_rows(self.original / recovery.RAW_NAME, self.rows[:-1] + [self.rows[0]])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            recovery.prepare(self.project)

    def test_prepare_refuses_existing_directory_incomplete_log_and_changed_source(self):
        self.composite.mkdir()
        with self.assertRaisesRegex(ValueError, "already exists"):
            recovery.prepare(self.project)
        self.composite.rmdir()
        log = self.original / "collection.log"
        log.write_text("\n".join(log.read_text().splitlines()[:-1]) + "\n")
        with self.assertRaisesRegex(ValueError, "100 completed"):
            recovery.prepare(self.project)
        self.assertFalse(self.composite.exists())
        (self.project / "src/run.py").write_text("# altered\n")
        with self.assertRaisesRegex(ValueError, "Frozen source differs"):
            recovery.prepare(self.project)

    def test_original_edits_after_prepare_are_rejected(self):
        prep = recovery.prepare(self.project)
        self.append_recovery(prep)
        raw = self.original / recovery.RAW_NAME
        raw.write_bytes(raw.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Original evidence changed"):
            recovery.finalize(self.project)
        self.assertFalse((self.composite / "lineage.json").exists())

    def test_replacing_retained_row_or_using_old_recovery_timestamp_is_rejected(self):
        prep = recovery.prepare(self.project)
        appended = self.append_recovery(prep)
        changed = copy.deepcopy(self.rows)
        changed[0]["reasoning"] = "A replacement would corrupt the original lineage."
        self.write_rows(self.composite / recovery.RAW_NAME, changed + appended)
        with self.assertRaisesRegex(ValueError, "byte prefix"):
            recovery.finalize(self.project)
        self.write_rows(self.composite / recovery.RAW_NAME, self.rows)
        self.append_recovery(prep, timestamp="2026-11-10T01:00:00+00:00")
        with self.assertRaisesRegex(ValueError, "precede preparation"):
            recovery.finalize(self.project)
        self.assertFalse((self.composite / "lineage.json").exists())

    def test_source_head_and_manifest_changes_are_rejected(self):
        (self.project / ".git/HEAD").write_text("0" * 40 + "\n")
        with self.assertRaisesRegex(ValueError, "fe4"):
            recovery.prepare(self.project)
        (self.project / ".git/HEAD").write_text(recovery.SOURCE_REVISION + "\n")
        changed = {**self.manifest, "parameters": {**recovery.PARAMETERS, "max_tokens": 8192}}
        (self.original / recovery.MANIFEST_NAME).write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, "manifest differs"):
            recovery.prepare(self.project)


if __name__ == "__main__":
    unittest.main()
