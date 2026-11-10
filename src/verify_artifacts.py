"""Read-only integrity audit of the frozen 20-question, 100-attempt Qwen pilot.

Prints JSON to stdout and exits nonzero on integrity failures. No inference,
credentials, network access, artifact writes, or scientific labels are involved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from .common import parse_answer, read_jsonl, response_status, stable_hash, utc_now
from .local_model import MODEL_REVISION
from .prepare import DATASET_REVISION
from .run import make_trials

MODEL = "Qwen/Qwen3-1.7B"
PARAMETERS = {"seed": 20261109, "max_tokens": 4096, "temperature": 0.6, "top_p": 0.95, "top_k": 20}
QUESTIONS_SHA256 = "027ec5964680541b8f0c24310611a7b85670760fa011cd071b255a9622ea313b"
QUESTIONS_BYTES_SHA256 = "e659d7f6a13e6c596fc8b3aee4058090d2338ab5f585c360aa614ac3f5eaff60"
# Verified against the pinned tokenizer and generation_config.json. This checks
# token structure/counts, not decoding; no tokenizer download occurs in an audit.
OPEN_THINK, CLOSE_THINK = 151667, 151668
EOS_IDS = {151645, 151643}
TOKEN_FIELDS = ("prompt_token_ids", "generated_token_ids", "reasoning_token_ids")


def _issue(report, level, code, message, **context):
    report[level].append({"code": code, "message": message, **context})


def _finish(report):
    report["ok"] = not report["failures"]
    return report


def _report():
    return {"schema_version": 1, "audit": "frozen_qwen3_1.7b_pilot_integrity",
            "audited_at": utc_now(), "ok": False, "collection_complete": False,
            "expected_records": 100, "expected_questions": 20,
            "record_count": 0, "unique_record_count": 0, "observed_questions": 0,
            "status_counts": {}, "token_records_checked": 0,
            "failures": [], "warnings": [], "checksums": {"status": "not_checked"},
            "limits": ["Internal consistency and hashes do not independently prove that inference occurred.",
                       "Token checks cover integer IDs, counts, thinking boundaries and EOS, not decoded text equivalence.",
                       "This audit does not validate judge labels or scientific conclusions."]}


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp must be text")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("Timestamp must include UTC timezone")
    return parsed


def _tokens(report, row):
    context = {"record_id": row.get("record_id")}
    provided = [key in row for key in TOKEN_FIELDS]
    if not any(provided):
        _issue(report, "warnings", "tokens_absent", "No exact token arrays supplied for this generation.", **context)
        return
    if not all(provided) or any(not isinstance(row.get(key), list) or
            any(type(token) is not int or token < 0 for token in row[key]) for key in TOKEN_FIELDS if key in row):
        _issue(report, "failures", "token_schema", "All three token arrays must contain nonnegative integer IDs.", **context)
        return
    prompt, generated, reasoning = (row[key] for key in TOKEN_FIELDS)
    report["token_records_checked"] += 1
    usage = row.get("usage", {})
    if not isinstance(usage, dict) or usage.get("prompt_tokens") != len(prompt) or usage.get("completion_tokens") != len(generated):
        _issue(report, "failures", "token_counts", "Usage counts do not match the saved prompt and generated token arrays.", **context)
    if not prompt or not generated or len(generated) > PARAMETERS["max_tokens"]:
        _issue(report, "failures", "token_lengths", "Prompt/output token arrays must be nonempty and respect the frozen cap.", **context)
    complete = CLOSE_THINK in generated
    if row.get("complete_thinking") is not complete:
        _issue(report, "failures", "thinking_boundary", "complete_thinking disagrees with the generated closing token.", **context)
    if complete:
        boundary = generated.index(CLOSE_THINK)
        start = generated.index(OPEN_THINK) + 1 if OPEN_THINK in generated[:boundary] else 0
        expected_reasoning = generated[start:boundary]
    else:
        expected_reasoning = generated
    if reasoning != expected_reasoning:
        _issue(report, "failures", "reasoning_tokens", "Reasoning IDs differ from the exact slice used by the local adapter.", **context)
    expected_finish = "stop" if generated and generated[-1] in EOS_IDS else "length"
    if row.get("finish_reason") != expected_finish:
        _issue(report, "failures", "token_termination", "Saved termination disagrees with the pinned model's EOS tokens.", **context)
    if expected_finish == "length" and len(generated) != PARAMETERS["max_tokens"]:
        _issue(report, "failures", "short_length_stop", "A non-EOS generation ended before the frozen token cap.", **context)


def audit_records(rows, questions, manifest, questions_manifest):
    """Audit already-loaded JSON objects without modifying them."""
    report = _report()
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        _issue(report, "failures", "records_schema", "Responses must be JSON objects in a JSONL file.")
        return _finish(report)
    report["record_count"] = len(rows)
    if (not isinstance(questions, list) or not questions or not all(isinstance(q, dict) for q in questions)
            or not isinstance(manifest, dict) or not isinstance(questions_manifest, dict)):
        _issue(report, "failures", "input_schema", "Questions and both manifests must have their expected JSON shapes.")
        return _finish(report)
    if len(questions) != 150 or stable_hash(questions) != QUESTIONS_SHA256:
        _issue(report, "failures", "frozen_questions", "Question objects differ from the frozen 150-row parent sample.")
    question_manifest_expected = {"count": 150, "revision": DATASET_REVISION, "seed": PARAMETERS["seed"],
                                  "dataset": "cais/mmlu", "split": "test", "sample_sha256": QUESTIONS_SHA256}
    for key, expected in question_manifest_expected.items():
        if questions_manifest.get(key) != expected:
            _issue(report, "failures", "question_manifest", "Question manifest differs from the frozen protocol.", field=key)
    try:
        if len({q["question_id"] for q in questions}) != len(questions):
            raise ValueError("Duplicate question IDs")
        all_trials = make_trials(questions, MODEL, "local", PARAMETERS)
    except (KeyError, TypeError, ValueError) as exc:
        _issue(report, "failures", "trial_reconstruction", "Cannot reconstruct planned trials from the question file.", error_type=type(exc).__name__)
        return _finish(report)
    selected_questions = {q["question_id"] for q in questions[:20]}
    expected_trials = {t["record_id"]: t for t in all_trials if t["question_id"] in selected_questions}
    expected_manifest = {"experiment_id": all_trials[0]["experiment_id"], "model": MODEL, "backend": "local",
                         "revision": MODEL_REVISION, "provider": None, "parameters": PARAMETERS,
                         "questions_sha256": QUESTIONS_SHA256, "device": "cuda",
                         "prompts_sha256": stable_hash([t["messages"] for t in all_trials])}
    for key, expected in expected_manifest.items():
        if key not in manifest or stable_hash(manifest[key]) != stable_hash(expected):
            _issue(report, "failures", "run_manifest", "Run manifest differs from the frozen protocol or reconstructed prompts.", field=key)
    ids = [row.get("record_id") for row in rows]
    if any(not isinstance(record_id, str) for record_id in ids):
        _issue(report, "failures", "record_id_schema", "Every response must have a string record_id.")
    counts = Counter(record_id for record_id in ids if isinstance(record_id, str))
    missing = sorted(set(expected_trials) - set(counts))
    unexpected = sorted(set(counts) - set(expected_trials))
    duplicates = sorted(record_id for record_id, count in counts.items() if count != 1)
    report["unique_record_count"] = len(counts)
    if missing or unexpected or duplicates or len(rows) != 100:
        _issue(report, "failures", "record_set", "Collection must contain each of the expected 100 record IDs exactly once.",
               missing=missing, unexpected=unexpected, duplicate=duplicates)
    question_counts = Counter(row["question_id"] for row in rows if isinstance(row.get("question_id"), str))
    report["observed_questions"] = len(question_counts)
    if set(question_counts) != selected_questions or any(count != 5 for count in question_counts.values()):
        _issue(report, "failures", "question_coverage", "The frozen first 20 questions must each have exactly five conditions.")
    report["collection_complete"] = (len(rows) == 100 and not missing and not unexpected and not duplicates
                                     and set(question_counts) == selected_questions and all(n == 5 for n in question_counts.values()))
    statuses = Counter(row.get("status") if isinstance(row.get("status"), str) else "<missing_or_invalid>" for row in rows)
    report["status_counts"] = dict(sorted(statuses.items()))
    prompt_tokens_by_messages = {}
    for row in rows:
        record_id = row.get("record_id")
        context = {"record_id": record_id if isinstance(record_id, str) else None}
        expected = expected_trials.get(record_id) if isinstance(record_id, str) else None
        if expected:
            changed = [key for key, value in expected.items() if key not in row or stable_hash(row[key]) != stable_hash(value)]
            if changed:
                _issue(report, "failures", "trial_fields", "Saved trial metadata or prompt differs from make_trials output.", fields=changed, **context)
        if row.get("backend") != "local" or row.get("model") != MODEL or row.get("synthetic") is not False:
            _issue(report, "failures", "real_local_model", "This pilot requires a nonsynthetic local Qwen record.", **context)
        try:
            if _timestamp(row.get("finished_at")) < _timestamp(row.get("started_at")):
                raise ValueError("Reversed timestamps")
        except (ValueError, TypeError, OverflowError):
            _issue(report, "failures", "timestamps", "Start/end must be valid UTC timestamps with finish at or after start.", **context)
        if row.get("status") == "error":
            if (not isinstance(row.get("error_type"), str) or not row["error_type"] or row.get("reasoning") != ""
                    or row.get("content") != "" or row.get("answer") is not None or row.get("finish_reason") is not None
                    or row.get("usage") != {} or any(key in row for key in TOKEN_FIELDS)):
                _issue(report, "failures", "error_record", "Recorded exception does not match the runner's error schema.", **context)
            continue
        if row.get("model_revision") != MODEL_REVISION:
            _issue(report, "failures", "model_revision", "Generated record does not identify the pinned checkpoint.", **context)
        if row.get("dtype") != "torch.float16" or not re.fullmatch(r"cuda(?::\d+)?", str(row.get("device", ""))):
            _issue(report, "failures", "runtime_precision", "The frozen pilot requires recorded CUDA/FP16 generation.", **context)
        reasoning, content = row.get("reasoning"), row.get("content")
        if (not isinstance(reasoning, str) or not isinstance(content, str) or
                type(row.get("complete_thinking")) is not bool or row.get("finish_reason") not in ("stop", "length")):
            _issue(report, "failures", "response_schema", "Generation text, completion flag or finish reason is missing/invalid.", **context)
        else:
            expected_status = response_status(reasoning, content, row["finish_reason"])
            if not row["complete_thinking"] and row["finish_reason"] == "stop":
                expected_status = "incomplete_thinking"
            if row.get("status") != expected_status or row.get("answer") != parse_answer(content):
                _issue(report, "failures", "response_status", "Status or parsed answer disagrees with the saved text and termination.", **context)
            if not row["complete_thinking"] and content != "":
                _issue(report, "failures", "unfinished_content", "The local adapter saves empty final text when thinking is unclosed.", **context)
        usage = row.get("usage")
        if not isinstance(usage, dict) or any(type(usage.get(key)) is not int or usage[key] <= 0 for key in ("prompt_tokens", "completion_tokens")):
            _issue(report, "failures", "usage", "Prompt and completion usage must be positive integer token counts.", **context)
        _tokens(report, row)
        if expected and isinstance(row.get("prompt_token_ids"), list):
            key = stable_hash(expected["messages"])
            if key in prompt_tokens_by_messages and prompt_tokens_by_messages[key] != row["prompt_token_ids"]:
                _issue(report, "failures", "prompt_token_consistency", "Identical baseline messages have different prompt token arrays.", **context)
            prompt_tokens_by_messages[key] = row["prompt_token_ids"]
    attrition = {status: count for status, count in sorted(statuses.items()) if status != "ok"}
    if attrition:
        _issue(report, "warnings", "response_attrition", "Collected attempts include non-OK responses; preserve and report their exclusions.", counts=attrition)
    return _finish(report)


def _verify_checksums(report, path, required_files):
    if not path.exists():
        report["checksums"] = {"status": "absent", "verified_files": 0}
        _issue(report, "warnings", "checksums_absent", "No original checksums.json was supplied; file identity was not verified.")
        return
    prior_failures = len(report["failures"])
    report["checksums"] = {"status": "failed", "verified_files": 0, "path": str(path)}
    try:
        hashes = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(hashes, dict) or not hashes:
            raise ValueError("Checksum mapping must be nonempty")
    except (OSError, ValueError, UnicodeError) as exc:
        _issue(report, "failures", "checksums_schema", "Cannot read the original checksum mapping.", error_type=type(exc).__name__)
        return
    root = path.parent.resolve()
    verified_paths = set()
    for name, expected_hash in hashes.items():
        relative = Path(name)
        target = (root / relative).resolve()
        if (relative.is_absolute() or ".." in relative.parts or not target.is_relative_to(root)
                or target == path.resolve() or not re.fullmatch(r"[0-9a-f]{64}", str(expected_hash))):
            _issue(report, "failures", "checksum_entry", "Unsafe path or malformed SHA-256 in the original checksum mapping.", file=name)
            continue
        try:
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
        except OSError:
            _issue(report, "failures", "checksum_missing_file", "A file listed in the original checksums is unavailable.", file=name)
            continue
        if digest != expected_hash:
            _issue(report, "failures", "checksum_mismatch", "File bytes differ from the original checksum.", file=name)
        else:
            verified_paths.add(target)
            report["checksums"]["verified_files"] += 1
    for required in required_files:
        if required.resolve() not in verified_paths:
            _issue(report, "failures", "checksum_core_coverage", "Original checksums do not verify a core raw artifact.", file=required.name)
    if len(report["failures"]) == prior_failures:
        report["checksums"]["status"] = "verified"


def audit_files(records_path, questions_path="data/questions.jsonl", *, manifest_path=None,
                questions_manifest_path=None, checksums_path=None):
    records_path, questions_path = Path(records_path), Path(questions_path)
    manifest_path = Path(manifest_path) if manifest_path else records_path.with_suffix(records_path.suffix + ".manifest.json")
    questions_manifest_path = Path(questions_manifest_path) if questions_manifest_path else questions_path.with_suffix(questions_path.suffix + ".manifest.json")
    checksums_path = Path(checksums_path) if checksums_path else records_path.parent / "checksums.json"
    try:
        if not records_path.is_file() or not questions_path.is_file():
            raise FileNotFoundError("Required JSONL input absent")
        rows, questions = read_jsonl(records_path), read_jsonl(questions_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        questions_manifest = json.loads(questions_manifest_path.read_text(encoding="utf-8"))
        report = audit_records(rows, questions, manifest, questions_manifest)
        if hashlib.sha256(questions_path.read_bytes()).hexdigest() != QUESTIONS_BYTES_SHA256:
            _issue(report, "failures", "question_file_bytes", "Question file bytes differ from the frozen parent-sample checksum.")
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        report = _report()
        _issue(report, "failures", "input_read", "Could not load required JSON/JSONL artifacts; evidence was not changed.", error_type=type(exc).__name__)
    report["inputs"] = {"records": str(records_path), "questions": str(questions_path),
                        "manifest": str(manifest_path), "questions_manifest": str(questions_manifest_path)}
    _verify_checksums(report, checksums_path, [records_path, manifest_path])
    return _finish(report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", required=True, help="Saved responses.jsonl; never modified")
    parser.add_argument("--questions", default="data/questions.jsonl")
    parser.add_argument("--manifest", help="Defaults to <records>.manifest.json")
    parser.add_argument("--questions-manifest", help="Defaults to <questions>.manifest.json")
    parser.add_argument("--checksums", help="Defaults to checksums.json next to records")
    args = parser.parse_args()
    report = audit_files(args.records, args.questions, manifest_path=args.manifest,
                         questions_manifest_path=args.questions_manifest, checksums_path=args.checksums)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
