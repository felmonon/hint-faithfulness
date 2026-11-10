"""Export complete saved responses for the required pilot review."""
import argparse
from pathlib import Path
from .common import read_jsonl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = [r for p in args.input for r in read_jsonl(p)]
    if not rows:
        parser.error("No saved responses found")
    if Path(args.output).exists():
        parser.error("Choose a new review path to preserve existing annotations")
    lines = ["# Complete transcript review", "", "Read every response before interpreting aggregates. Record parsing, truncation, and rubric problems in LOG.md.", ""]
    if any(r.get("synthetic") for r in rows):
        lines += ["**SYNTHETIC SOFTWARE TEST — these are not model responses or research results.**", ""]
    for r in sorted(rows, key=lambda x: (x["model"], x["question_id"], x["hint_type"], x.get("baseline_repeat") or 0)):
        lines += [f"## {r['record_id']}", "", f"Model: {r['model']} · Condition: {r['hint_type']} · Repeat: {r.get('baseline_repeat')} · Status: {r['status']}",
                  "", "### Prompt", "", r["prompt"], "", "### Reasoning (complete)", "", r.get("reasoning", ""),
                  "", "### Final response", "", r.get("content", ""), "", "Review notes: __________", ""]
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Exported {len(rows)} complete responses to {path}")


if __name__ == "__main__":
    main()
