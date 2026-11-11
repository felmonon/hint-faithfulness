"""Synthetic transport fixtures only; no model, API, or actual outcome review."""
from copy import deepcopy
import base64
from datetime import datetime, timedelta, timezone
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import verify_phase3_colab_export as export


def encoded(value):
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def pack(raw):
    compressed = gzip.compress(raw, mtime=0)
    return {"encoding": "gzip+base64", "bytes": len(raw), "sha256": export.sha(raw),
            "compressed_bytes": len(compressed), "compressed_sha256": export.sha(compressed),
            "base64": base64.b64encode(compressed).decode()}


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.project = self.root / "project"
        self.project.mkdir()
        self.reference = {"cells": [{"cell_type": "code", "source": ["# Synthetic notebook fixture\n"], "outputs": []}
                                    for _ in range(8)]}
        self.plan = {"strengths": [0, 1, 2, 4, 8], "test_question_ids": [f"synthetic-q{i}" for i in range(6)]}
        self.manifest = {"synthetic": True, **self.plan}
        conditions = [("baseline", None, 0.0)] + [(d, letter, float(s)) for d in ("vector", "random")
                      for letter in "ABCD" for s in [1, 2, 4, 8]]
        self.rows = []
        for q in self.plan["test_question_ids"]:
            for d, letter, strength in conditions:
                ordinal = len(self.rows)
                day = 1 if ordinal < 8 else 2 if ordinal < 28 else 3
                start = datetime(2020, 1, day, tzinfo=timezone.utc) + timedelta(seconds=ordinal * 2 + 1)
                self.rows.append({"record_id": export.stable_hash([export.stable_hash(self.manifest), q, d, letter, strength]),
                    "question_id": q, "direction": d, "target_letter": letter, "strength": strength,
                    "started_at": start.isoformat(), "finished_at": (start + timedelta(seconds=1)).isoformat(),
                    "synthetic": True, "reasoning": "Synthetic test-only field"})
        self.prefix = lambda n: b"".join(encoded(row) for row in self.rows[:n])
        self.old_setup = "artifacts/pilot-20-phase3-resume-notebook-20200102T000000.000000Z/setup.json"
        self.new_setup = "artifacts/pilot-20-phase3-resume-notebook-20200103T000000.000000Z/setup.json"
        self.old_runtime = export.RUN + "runtime-resume-2020-01-02T00-00-00.000000+00-00.json"
        self.new_runtime = export.RUN + "runtime-resume-2020-01-03T00-00-00.000000+00-00.json"
        original_name = "artifacts/pilot-20-phase3-checkpoint-0430/steering.jsonl"
        self.old = {export.RUN + "steering.jsonl": self.prefix(28), export.RUN + "manifest.json": encoded(self.manifest),
            export.RUN + "plan.json": encoded(self.plan), original_name: self.prefix(8),
            self.old_setup: encoded({"synthetic": True}),
            self.old_setup.replace("setup.json", "resume-execution.log"): b"Synthetic prior log\n",
            self.old_runtime: encoded({"gpu_name": "NVIDIA L4", "captured_at": "2020-01-02T00:00:00+00:00"}),
            "docs/phase3-l4-resume-addendum.json": encoded({"synthetic": True})}
        for name in export.PROTOCOLS:
            target = self.project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"Synthetic protocol fixture: " + name.encode())
        target = self.project / original_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.prefix(8))
        self.publication = {"snapshot.json": encoded({"synthetic": True}), "steering.jsonl": self.prefix(28),
                            "acquisition-provenance.json": encoded({"synthetic": True}),
                            "README.md": b"Synthetic checkpoint", "checksums.sha256": b"Synthetic inventory"}
        self.constants = {"EXPECTED_SNAPSHOT_FILES": {name: {"sha256": export.sha(raw), "bytes": len(raw)}
                                                       for name, raw in self.old.items()},
            "LATEST_PUBLICATION_HASHES": {name: export.sha(raw) for name, raw in self.publication.items()},
            "SECOND_PROTOCOL_SHA256": export.sha((self.project / "docs/PHASE3_SECOND_RESUME_PROTOCOL.md").read_bytes()),
            "ADDENDUM_SHA256": export.sha(self.old["docs/phase3-l4-resume-addendum.json"]),
            "EXPECTED_IMPORTED_VERSIONS": {"synthetic_test_package": "0", "torch": "synthetic-torch"}}
        self.reference_patch = patch.object(export, "load_reference", return_value=(self.reference, self.constants))
        self.reference_patch.start()
        self.addCleanup(self.reference_patch.stop)

    def snapshot(self, count=38, complete=False):
        files = {**self.old, **{export.CHECKPOINT + name: raw for name, raw in self.publication.items()},
                 **{name: (self.project / name).read_bytes() for name in export.PROTOCOLS}}
        files[export.RUN + "steering.jsonl"] = self.prefix(count)
        runtime = {"gpu_name": "NVIDIA L4", "captured_at": "2020-01-03T00:00:00+00:00",
            "git_commit": export.CHECKPOINT_COMMIT, "git_tracked_changes": "", "cuda_available": True,
            "torch_version": "synthetic-torch", "cuda_version": "13.0", "gpu_memory_bytes": 23 * 1024**3}
        files[self.new_setup] = encoded({"runtime": runtime,
            "imported_versions": self.constants["EXPECTED_IMPORTED_VERSIONS"], "restored_retained_records": 28,
            "planned_missing_positions": 170, "second_resume_protocol_sha256": self.constants["SECOND_PROTOCOL_SHA256"],
            "checkpoint_commit": export.CHECKPOINT_COMMIT, "scientific_commit": export.SCIENTIFIC_COMMIT,
            "hardware_addendum_path": "docs/phase3-l4-resume-addendum.json",
            "hardware_addendum_sha256": self.constants["ADDENDUM_SHA256"], "hardware_addendum": {"synthetic": True},
            "second_resume_protocol_path": "docs/PHASE3_SECOND_RESUME_PROTOCOL.md",
            "restored_checkpoint_path": export.CHECKPOINT.rstrip("/"), "retained_original_records": 8,
            "restored_publication_sha256": self.constants["LATEST_PUBLICATION_HASHES"],
            "restored_payload_sha256": {name: item["sha256"] for name, item in self.constants["EXPECTED_SNAPSHOT_FILES"].items()}})
        files[self.new_setup.replace("setup.json", "resume-execution.log")] = b"Synthetic current log\n"
        if count > 28:
            files[self.new_runtime] = encoded(runtime)
        if complete:
            files.update({export.RUN + name: b"Synthetic final artifact\n" for name in export.FINAL - {"checksums.sha256"}})
            files[export.RUN + "completion.json"] = encoded({"status": "complete_fixed_sweep", "records": 198})
            files[export.RUN + "checksums.sha256"] = "".join(f"{export.sha(raw)}  {name[len(export.RUN):]}\n"
                for name, raw in sorted(files.items()) if name.startswith(export.RUN)).encode()
        return {"schema": "phase3-recovery-snapshot-v1", "checkpoint_commit": export.CHECKPOINT_COMMIT,
            "scientific_commit": export.SCIENTIFIC_COMMIT, "retained_records": count, "complete_verified": complete,
            "original_retained_records": 8, "restored_checkpoint_records": 28,
            "restored_snapshot_sha256": self.constants["LATEST_PUBLICATION_HASHES"]["snapshot.json"],
            "second_resume_protocol_sha256": self.constants["SECOND_PROTOCOL_SHA256"],
            "captured_at_utc": "2020-01-04T00:00:00+00:00", "files": {name: pack(raw) for name, raw in files.items()}}

    def notebook(self, snap):
        document = deepcopy(self.reference)
        document["cells"][5]["outputs"] = [{"data": {"application/json": snap}}]
        return document

    def run_export(self, document, name="result", **kwargs):
        source = self.root / (name + ".json")
        source.write_bytes(encoded(document))
        return export.verify_export(source, self.root / name, self.project, **kwargs)

    def reject(self, snap, pattern=None):
        with self.assertRaises(ValueError) if pattern is None else self.assertRaisesRegex(ValueError, pattern):
            self.run_export(snap)
        self.assertFalse((self.root / "result").exists(), "Validation failure must precede extraction")

    def test_notebook_and_json_preserve_exact_inputs_and_explicit_prior_scope(self):
        prior = self.root / "verified-028.jsonl"
        prior.write_bytes(self.prefix(28))
        snap = self.snapshot()
        result = self.run_export(self.notebook(snap), prior_paths=[prior])
        self.assertTrue(result["notebook_cells_checked"])
        self.assertEqual(result["checks"]["supplied_prior_prefixes"][0]["records"], 28)
        self.assertEqual((self.root / "result/source-export.ipynb").read_bytes(), (self.root / "result.json").read_bytes())
        marker = json.loads((self.root / "result/verification-complete.json").read_text())
        self.assertFalse(marker["full_scientific_audit_passed"])
        second = self.run_export(snap, name="standalone")
        self.assertFalse(second["notebook_cells_checked"])
        self.assertEqual(second["checks"]["supplied_prior_prefixes"], [])
        for line in (self.root / "result/checksums.sha256").read_text().splitlines():
            digest, name = line.split("  ", 1)
            self.assertEqual(export.sha((self.root / "result" / name).read_bytes()), digest)
            self.assertNotEqual(name, "checksums.sha256")
        before = (self.root / "result/acquisition-provenance.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "fresh directory"):
            export.verify_export(self.root / "result.json", self.root / "result", self.project)
        self.assertEqual(before, (self.root / "result/acquisition-provenance.json").read_bytes())

    def test_changed_notebook_or_multiple_snapshots_are_not_silently_selected(self):
        doc = self.notebook(self.snapshot())
        doc["cells"][1]["source"] = ["print('changed')"]
        self.reject(doc, "source differs")
        doc = self.notebook(self.snapshot())
        doc["cells"][6]["outputs"] = deepcopy(doc["cells"][5]["outputs"])
        self.reject(doc, "exactly one")

    def test_payload_hash_size_encoding_and_unsafe_paths_fail_before_writes(self):
        original = self.snapshot()
        for mutation in ("hash", "decoded", "size", "encoding", "path", "extra", "missing"):
            with self.subTest(mutation=mutation):
                snap = deepcopy(original)
                item = snap["files"][export.RUN + "steering.jsonl"]
                if mutation == "hash":item["compressed_sha256"] = "0" * 64
                elif mutation == "decoded":item["sha256"] = "0" * 64
                elif mutation == "size":item["bytes"] = 1
                elif mutation == "encoding":item["encoding"] = "unknown"
                elif mutation == "path":snap["files"]["artifacts/../escape"] = pack(b"bad")
                elif mutation == "extra":snap["files"]["artifacts/unexpected.txt"] = pack(b"extra")
                else:del snap["files"][self.old_runtime]
                self.reject(snap)

    def test_immutable_and_local_original_changes_are_rejected(self):
        snap = self.snapshot()
        snap["files"][self.old_setup] = pack(b"Rewritten prior setup")
        self.reject(snap, "prior payload changed")
        original = self.project / "artifacts/pilot-20-phase3-checkpoint-0430/steering.jsonl"
        original.write_bytes(self.prefix(1))
        self.reject(self.snapshot(), "Local original checkpoint differs")

    def test_grid_metadata_reordering_retained_replacement_and_prior_rollback_rejected(self):
        snap = self.snapshot()
        raw = export.decode_files(snap["files"])[export.RUN + "steering.jsonl"]
        rows = export.jsonl(raw)
        for mutation in ("order", "condition", "retained", "newline"):
            changed = deepcopy(rows)
            if mutation == "order":changed[28], changed[29] = changed[29], changed[28]
            elif mutation == "condition":changed[28]["direction"] = "vector"
            elif mutation == "retained":changed[2]["reasoning"] = "Replaced retained output"
            revised = b"".join(encoded(row) for row in changed)
            if mutation == "newline":revised = revised[:-1]
            bad = deepcopy(snap);bad["files"][export.RUN + "steering.jsonl"] = pack(revised)
            self.reject(bad)
        prior = self.root / "later.jsonl";prior.write_bytes(self.prefix(48))
        with self.assertRaisesRegex(ValueError, "prior acquisition"):
            self.run_export(snap, prior_paths=[prior])
        self.assertFalse((self.root / "result").exists())

    def test_symlinks_and_artifact_destination_are_rejected(self):
        source = self.root / "input.json";source.write_bytes(encoded(self.snapshot()))
        linked = self.root / "linked.json";linked.symlink_to(source)
        parent = self.root / "linked-parent";parent.symlink_to(self.project, target_is_directory=True)
        for candidate, out in [(linked, self.root / "result"), (source, parent / "result"),
                               (source, self.project / "artifacts/result")]:
            with self.subTest(out=out):
                with self.assertRaises(ValueError):export.verify_export(candidate, out, self.project)
        self.assertFalse((self.project / "result").exists())

    def test_completion_claim_requires_full_grid_and_complete_nonself_inventory(self):
        snap = self.snapshot();snap["complete_verified"] = "false"
        self.reject(snap, "boolean")
        snap = self.snapshot();snap["complete_verified"] = True
        self.reject(snap, "Incomplete grid")
        snap = self.snapshot(198, complete=True)
        result = self.run_export(snap, name="complete")
        self.assertTrue(result["checks"]["producer_complete_verified_claim"])
        for inventory in (b"", b"0  checksums.sha256\n"):
            bad = deepcopy(snap);bad["files"][export.RUN + "checksums.sha256"] = pack(inventory)
            self.reject(bad)

    def test_explicit_download_identity_and_utc_chronology_are_checked(self):
        for kwargs in ({"expected_bytes": 1}, {"expected_sha256": "0" * 64}, {"source_modified_at": "2020-01-01"}):
            with self.assertRaises(ValueError):self.run_export(self.snapshot(), **kwargs)
            self.assertFalse((self.root / "result").exists())
        snap = self.snapshot();snap["captured_at_utc"] = "2020-01-02T00:00:00+00:00"
        self.reject(snap, "chronology")
        snap = self.snapshot()
        rows = export.jsonl(export.decode_files(snap["files"])[export.RUN + "steering.jsonl"])
        rows[30]["finished_at"] = "2020-01-01T00:00:00+00:00"
        snap["files"][export.RUN + "steering.jsonl"] = pack(b"".join(encoded(row) for row in rows))
        self.reject(snap, "row chronology")

    def test_new_setup_and_runner_metadata_cannot_change_with_rehashed_payloads(self):
        for field, value in [("scientific_commit", "changed"), ("hardware_addendum", {}),
                             ("restored_publication_sha256", {}), ("restored_payload_sha256", {})]:
            snap = self.snapshot()
            setup = export.json_object(export.decode_files(snap["files"])[self.new_setup])
            setup[field] = value;snap["files"][self.new_setup] = pack(encoded(setup))
            self.reject(snap, "frozen identities")
        for name in (self.new_setup, self.new_runtime):
            snap = self.snapshot()
            item = export.json_object(export.decode_files(snap["files"])[name])
            target = item["runtime"] if name == self.new_setup else item
            target["git_tracked_changes"] = "M src/phase3.py"
            snap["files"][name] = pack(encoded(item))
            self.reject(snap)

    def test_started_runner_without_new_outcomes_still_requires_valid_metadata(self):
        snap = self.snapshot(28)
        self.run_export(snap, name="before-runner")
        setup = export.json_object(export.decode_files(snap["files"])[self.new_setup])
        runtime = deepcopy(setup["runtime"])
        snap["files"][self.new_runtime] = pack(encoded(runtime))
        result = self.run_export(snap, name="started-no-new-rows")
        self.assertEqual(result["checks"]["retained_records"], 28)
        runtime["git_tracked_changes"] = "M src/phase3.py"
        snap["files"][self.new_runtime] = pack(encoded(runtime))
        self.reject(snap, "Runner runtime differs")

    def test_strict_json_rejects_duplicate_keys_nonfinite_and_wrong_encoding(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', '{"a":1}'.encode('utf-16')):
            with self.assertRaises((ValueError, UnicodeError)):export.json_object(raw)

    def test_interrupted_write_never_claims_completion_or_reuses_partial_directory(self):
        source = self.root / "source.json";source.write_bytes(encoded(self.snapshot()))
        original = source.read_bytes()
        with patch.object(Path, "rename", side_effect=OSError("Synthetic interrupted write")):
            with self.assertRaisesRegex(OSError, "interrupted"):
                export.verify_export(source, self.root / "partial", self.project)
        self.assertFalse((self.root / "partial/verification-complete.json").exists())
        self.assertEqual(source.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "fresh directory"):
            export.verify_export(source, self.root / "partial", self.project)


if __name__ == "__main__":
    unittest.main()
