"""Re-parse saved v2 generations with the current parser v2 (no model calls).

python -m src.reparse_v2

Updates answer / answer_rule / answer_letters / status in place for Phase 1 responses,
Phase 3 calibration and Phase 3 sweep. The first time a row is re-parsed, its original
values are kept in answer_v2_0 / answer_rule_v2_0 / status_v2_0. Raw text is never touched.
Idempotent: running it twice changes nothing.
"""
from __future__ import annotations

from pathlib import Path

from .common import read_jsonl, write_jsonl
from .parser_v2 import parse_answer_v2, response_status_v2

FILES = (Path("artifacts/v2/phase1/responses.jsonl"), Path("artifacts/v2/phase3/calibration.jsonl"),
         Path("artifacts/v2/phase3/sweep.jsonl"))


def reparse_row(row):
    parsed = parse_answer_v2(row["content"])
    finish = row["finish_reason"]
    status = response_status_v2(row["reasoning"], row["content"], finish,
                                complete_thinking=row["complete_thinking"] or finish != "stop")
    new = {"answer": parsed["answer"], "answer_rule": parsed["rule"], "answer_letters": parsed["letters"], "status": status}
    changed = any(row.get(k) != v for k, v in new.items())
    if changed and "answer_v2_0" not in row:
        row = {**row, "answer_v2_0": row.get("answer"), "answer_rule_v2_0": row.get("answer_rule"),
               "status_v2_0": row.get("status")}
    return {**row, **new}, changed


def main():
    for path in FILES:
        if not path.exists():
            continue
        rows, changes = [], []
        for row in read_jsonl(path):
            new, changed = reparse_row(row)
            rows.append(new)
            if changed:
                changes.append((new.get("hint_type") or new.get("direction"), new.get("fraction"),
                                new["status_v2_0"], new["status"], new["answer"]))
        if changes:
            write_jsonl(path, rows)
        print(f"{path}: {len(changes)} rows changed", *changes, sep="\n  ")


if __name__ == "__main__":
    main()
