"""Minimal unified-diff builders (one line of context, ``a/`` ``b/`` paths). Pure functions, no file I/O."""
from __future__ import annotations

import re

NO_NEWLINE = "\\ No newline at end of file"
_NEWLINE = re.compile(r"\r\n|\r|\n")


def split_lines(source: str) -> tuple[list[str], bool]:
    """Source lines without terminators (numbering like ``ast``), and whether the text ends with a newline."""
    if source == "":
        return [], True
    lines = _NEWLINE.split(source)
    ends_with_newline = lines[-1] == ""
    if ends_with_newline:
        lines.pop()
    return lines, ends_with_newline


def _range(start: int, count: int) -> str:
    return str(start) if count == 1 else f"{start},{count}"


def replace_lines_patch(
    path: str, lines: list[str], ends_with_newline: bool, changes: dict[int, str], context: int = 1
) -> str:
    """Unified diff replacing whole lines (1-based ``changes[line] = new text``).

    Hunks whose context windows overlap or touch are merged, so the patch stays valid for ``git apply``.
    """
    if not changes:
        raise ValueError("no change")
    if any(n < 1 or n > len(lines) for n in changes):
        raise ValueError("line out of range")
    hunks: list[list[int]] = []  # [first, last] line numbers (1-based, inclusive)
    for number in sorted(changes):
        first, last = max(1, number - context), min(len(lines), number + context)
        if hunks and first <= hunks[-1][1] + 1:
            hunks[-1][1] = max(hunks[-1][1], last)
        else:
            hunks.append([first, last])
    out = [f"--- a/{path}", f"+++ b/{path}"]
    for first, last in hunks:
        count = last - first + 1
        out.append(f"@@ -{_range(first, count)} +{_range(first, count)} @@")
        for number in range(first, last + 1):
            at_eof = number == len(lines) and not ends_with_newline
            if number in changes:
                out.append("-" + lines[number - 1])
                if at_eof:
                    out.append(NO_NEWLINE)
                out.append("+" + changes[number])
            else:
                out.append(" " + lines[number - 1])
            if at_eof:
                out.append(NO_NEWLINE)
    return "\n".join(out) + "\n"


def new_file_patch(path: str, content_lines: list[str]) -> str:
    """Unified diff creating ``path`` with the given lines (newline-terminated)."""
    out = ["--- /dev/null", f"+++ b/{path}", f"@@ -0,0 +{_range(1, len(content_lines))} @@"]
    out += ["+" + line for line in content_lines]
    return "\n".join(out) + "\n"
