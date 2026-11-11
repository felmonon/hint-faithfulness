"""Answer parser v2 (primary for the v2 run) plus the frozen pilot parser (strict).

v2 accepts, anywhere in the final response (never in the reasoning):
  * ``line_declaration``: a line that, after Markdown/LaTeX decoration is removed,
    starts with ``Answer`` or ``Final Answer`` followed by a letter, optionally in
    parentheses and optionally followed by option text, e.g. ``**Answer:** (B) 125``.
  * ``boxed``: ``\\boxed{X}``, ``\\boxed{(X)}``, ``\\boxed{\\text{X}}`` or ``\\boxed{\\text{(X)}}``
    (the ``\\text`` forms were added on 2026-11-11 as a bug fix; see PLAN_V2 changelog).
Every declaration found is collected. Two or more different letters -> rejected
(``conflict``). The matched rule is always recorded.
"""
from __future__ import annotations

import re

LETTERS = "ABCD"

_STRICT = re.compile(r"(?:^|\n)\s*Answer:\s*\(([ABCD])\)\s*\Z")
_BOXED = re.compile(r"\\boxed\s*\{\s*(?:\(?\s*([ABCD])\s*\)?"
                    r"|\\text\s*\{\s*\(?\s*([ABCD])\s*\)?\s*\})\s*\}")
# Letter in parentheses (anything may follow) or a bare letter that ends the
# line or is followed only by punctuation/space + option text after a delimiter.
_DECL = re.compile(
    r"^(?:final\s+answer|answer)\s*(?:is)?\s*[:：]?\s*"
    r"(?:\(\s*([ABCD])\s*\)|([ABCD])(?=\s*$|\s*[.):\]]|\s+[-–—]))",
    re.IGNORECASE,
)


def parse_answer_strict(content):
    """The pilot parser: only ``Answer: (X)`` as the very last text."""
    if not isinstance(content, str):
        return None
    match = _STRICT.search(content)
    return match.group(1) if match else None


def _clean_line(line):
    line = re.sub(r"\\text\s*\{([^}]*)\}", r"\1", line)   # \text{Answer: } -> Answer:
    line = re.sub(r"\\(?:mathbf|textbf)\s*\{([^}]*)\}", r"\1", line)
    line = line.replace("$", " ")
    line = re.sub(r"[*_`#>]", "", line)                  # Markdown emphasis/headings/quotes
    return line.strip().lstrip("-•").strip()


def parse_answer_v2(content):
    """Return {'answer': letter|None, 'rule': str, 'letters': [...]}."""
    if not isinstance(content, str) or not content.strip():
        return {"answer": None, "rule": "none", "letters": []}
    if parse_answer_strict(content):
        strict = parse_answer_strict(content)
    else:
        strict = None
    found = []  # (rule, letter)
    for raw in content.splitlines():
        line = _clean_line(raw)
        match = _DECL.match(line)
        if match:
            found.append(("line_declaration", match.group(1) or match.group(2)))
    for match in _BOXED.finditer(content):
        found.append(("boxed", match.group(1) or match.group(2)))
    letters = sorted({letter.upper() for _, letter in found})
    if len(letters) > 1:
        return {"answer": None, "rule": "conflict", "letters": letters}
    if not letters:
        return {"answer": None, "rule": "none", "letters": []}
    if strict:
        rule = "strict_terminal"
    else:
        rules = sorted({rule for rule, _ in found})
        rule = rules[0] if len(rules) == 1 else "+".join(rules)
    return {"answer": letters[0], "rule": rule, "letters": letters}


def response_status_v2(reasoning, content, finish_reason, complete_thinking=True):
    """Same categories as the pilot, with parser v2 for the answer."""
    if finish_reason in ("length", "max_tokens"):
        return "truncated"
    if not complete_thinking:
        return "incomplete_thinking"
    if parse_answer_v2(content)["answer"] is None:
        return "invalid_answer"
    if not isinstance(reasoning, str) or not reasoning.strip():
        return "missing_reasoning"
    return "ok"
