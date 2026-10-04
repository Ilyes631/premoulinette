"""Exact text comparison: line alignment, character segments, short human hints and a summary.

Lines are compared on their text; line terminators are compared separately so that a missing final
newline or a ``\\r\\n`` shows up as a precise hint instead of shifting the whole alignment.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass

from premoulinette.results.models import DiffKind, DiffLine, DiffSegment, TextDiff

MAX_DIFF_LINES = 2000          # alignment work is capped to the first N lines of each side
PAIR_RATIO = 0.4               # two lines of a replace block are "the same line, changed" above this
MAX_CHAR_DIFF = 5000           # longer lines: prefix/suffix diff only (SequenceMatcher is quadratic)
MAX_PAIR_CELLS = 10_000        # bigger replace blocks are paired positionally
MAX_HINTS_PER_LINE = 3

MINOR_KINDS: frozenset[str] = frozenset(
    {"typo", "case", "whitespace", "trailing_whitespace", "missing_newline", "extra_newline", "crlf"}
)
_KIND_LABELS: dict[str, str] = {
    "typo": "typo", "case": "case differs", "whitespace": "whitespace differs",
    "trailing_whitespace": "trailing whitespace", "missing_newline": "missing newline",
    "extra_newline": "extra newline", "crlf": "Windows line ending", "different": "different text",
}

Line = tuple[str, str]   # (text without terminator, terminator: "\n", "\r\n" or "")


def visible(s: str) -> str:
    """Make invisible characters visible: ' '→'·', '\\t'→'→', '\\n'→'↵\\n', '\\r'→'␍'."""
    return s.replace("\r", "␍").replace(" ", "·").replace("\t", "→").replace("\n", "↵\n")


def split_lines(text: str) -> list[Line]:
    """Split keeping terminators apart; a final line without terminator is kept, no empty tail line."""
    lines: list[Line] = []
    start = 0
    while start < len(text):
        idx = text.find("\n", start)
        if idx == -1:
            lines.append((text[start:], ""))
            break
        if idx > start and text[idx - 1] == "\r":
            lines.append((text[start:idx - 1], "\r\n"))
        else:
            lines.append((text[start:idx], "\n"))
        start = idx + 1
    return lines


def only_minor(kinds: list[str]) -> bool:
    """True when every difference is a typo/case/whitespace/newline-style difference."""
    return bool(kinds) and all(k in MINOR_KINDS for k in kinds)


def first_hint(diff: TextDiff) -> str:
    """Hints of the first differing line (comma separated), else the summary."""
    line = next((ln for ln in diff.lines if ln.op != "equal"), None)
    return ", ".join(line.hints) if line is not None and line.hints else diff.summary


def first_difference(expected: str, actual: str) -> int | None:
    if expected == actual:
        return None
    n = min(len(expected), len(actual))
    lo, hi = 0, n   # binary search on the common prefix (slices compare in C)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if expected[:mid] == actual[:mid]:
            lo = mid
        else:
            hi = mid - 1
    return lo


def diff_text(expected: str, actual: str) -> TextDiff:
    exp_lines, act_lines = split_lines(expected), split_lines(actual)
    truncated = len(exp_lines) > MAX_DIFF_LINES or len(act_lines) > MAX_DIFF_LINES
    exp_lines, act_lines = exp_lines[:MAX_DIFF_LINES], act_lines[:MAX_DIFF_LINES]
    if expected == actual:
        lines = [_equal(e, i, i) for i, e in enumerate(exp_lines)]
        return TextDiff(expected=expected, actual=actual, equal=True, lines=lines,
                        kinds=["identical"], summary="Output is identical")
    rows = _align(exp_lines, act_lines)
    lines = [r.line for r in rows]
    kinds = _unique([r.kind for r in rows if r.kind])
    summary = _summary(rows)
    if truncated:
        note = f"only the first {MAX_DIFF_LINES} lines were compared"
        if not summary:
            summary = f"No difference in the first {MAX_DIFF_LINES} lines; the outputs differ further on"
            kinds = ["different"]
        else:
            summary += f" ({note})"
        if lines:
            lines[-1].hints.append(note)
    return TextDiff(
        expected=expected, actual=actual, equal=False, lines=lines, kinds=kinds,  # type: ignore[arg-type]
        summary=summary, first_difference=first_difference(expected, actual),
    )


# ------------------------------------------------------------------------------------------------
# Line alignment
# ------------------------------------------------------------------------------------------------


@dataclass
class _Row:
    line: DiffLine
    kind: DiffKind | None    # None for equal lines


def _equal(line: Line, i: int, j: int) -> DiffLine:
    return DiffLine(op="equal", expected_lineno=i + 1, actual_lineno=j + 1, expected=line[0], actual=line[0],
                    expected_eol=line[1], actual_eol=line[1])


def _missing(line: Line, i: int) -> _Row:
    text, eol = line
    hints = ["missing empty line (newline)"] if text == "" else []
    return _Row(DiffLine(op="missing", expected_lineno=i + 1, expected=text, expected_eol=eol, hints=hints),
                "missing_newline" if text == "" else "missing_lines")


def _extra(line: Line, j: int) -> _Row:
    text, eol = line
    hints = ["extra newline (empty line)"] if text == "" else []
    return _Row(DiffLine(op="extra", actual_lineno=j + 1, actual=text, actual_eol=eol, hints=hints),
                "extra_newline" if text == "" else "extra_lines")


def _pair(exp: Line, act: Line, i: int, j: int) -> _Row:
    if exp == act:
        return _Row(_equal(exp, i, j), None)
    segments = char_segments(exp[0], act[0])
    kind, hints = _classify(exp, act, segments)
    line = DiffLine(op="changed", expected_lineno=i + 1, actual_lineno=j + 1, expected=exp[0], actual=act[0],
                    expected_eol=exp[1], actual_eol=act[1], segments=segments, hints=hints)
    return _Row(line, kind)


def _align(exp: list[Line], act: list[Line]) -> list[_Row]:
    matcher = difflib.SequenceMatcher(None, [t for t, _ in exp], [t for t, _ in act], autojunk=False)
    rows: list[_Row] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            rows.extend(_pair(exp[i1 + k], act[j1 + k], i1 + k, j1 + k) for k in range(i2 - i1))
        elif tag == "delete":
            rows.extend(_missing(exp[i], i) for i in range(i1, i2))
        elif tag == "insert":
            rows.extend(_extra(act[j], j) for j in range(j1, j2))
        else:
            rows.extend(_replace_block(exp, act, i1, i2, j1, j2))
    return rows


def _replace_block(exp: list[Line], act: list[Line], i1: int, i2: int, j1: int, j2: int) -> list[_Row]:
    """Pair similar lines (greedy by similarity, order preserving); the rest is missing/extra."""
    pairs: list[tuple[int, int]] = []
    if (i2 - i1) * (j2 - j1) <= MAX_PAIR_CELLS:
        candidates = [
            (ratio, i, j)
            for i in range(i1, i2) for j in range(j1, j2)
            if (ratio := line_ratio(exp[i][0], act[j][0])) >= PAIR_RATIO
        ]
        candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
        for _, i, j in candidates:
            if all((pi - i) * (pj - j) > 0 for pi, pj in pairs):
                pairs.append((i, j))
        pairs.sort()
    else:
        pairs = [(i, j) for i, j in zip(range(i1, i2), range(j1, j2))
                 if line_ratio(exp[i][0], act[j][0]) >= PAIR_RATIO]
    rows: list[_Row] = []
    ci, cj = i1, j1
    for i, j in pairs:
        rows.extend(_missing(exp[k], k) for k in range(ci, i))
        rows.extend(_extra(act[k], k) for k in range(cj, j))
        rows.append(_pair(exp[i], act[j], i, j))
        ci, cj = i + 1, j + 1
    rows.extend(_missing(exp[k], k) for k in range(ci, i2))
    rows.extend(_extra(act[k], k) for k in range(cj, j2))
    return rows


def line_ratio(a: str, b: str) -> float:
    if a == b:
        return 1.0
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if matcher.real_quick_ratio() < PAIR_RATIO or matcher.quick_ratio() < PAIR_RATIO:
        return 0.0
    if len(a) > MAX_CHAR_DIFF or len(b) > MAX_CHAR_DIFF:
        return matcher.quick_ratio()
    return matcher.ratio()


# ------------------------------------------------------------------------------------------------
# Character segments
# ------------------------------------------------------------------------------------------------


def char_segments(expected: str, actual: str) -> list[DiffSegment]:
    if expected == actual:
        return [DiffSegment(op="equal", expected=expected, actual=actual)] if expected else []
    if len(expected) > MAX_CHAR_DIFF or len(actual) > MAX_CHAR_DIFF:
        return _prefix_suffix_segments(expected, actual)
    matcher = difflib.SequenceMatcher(None, expected, actual, autojunk=False)
    raw = [DiffSegment(op=tag, expected=expected[i1:i2], actual=actual[j1:j2])  # type: ignore[arg-type]
           for tag, i1, i2, j1, j2 in matcher.get_opcodes()]
    return _slide_to_words(_merge(raw))


def _prefix_suffix_segments(expected: str, actual: str) -> list[DiffSegment]:
    p = first_difference(expected, actual) or 0
    s = 0
    limit = min(len(expected), len(actual)) - p
    while s < limit and expected[-1 - s] == actual[-1 - s]:
        s += 1
    mid_e, mid_a = expected[p:len(expected) - s], actual[p:len(actual) - s]
    segments = [DiffSegment(op="equal", expected=expected[:p], actual=actual[:p])] if p else []
    segments.append(DiffSegment(op=_op_for(mid_e, mid_a), expected=mid_e, actual=mid_a))
    if s:
        segments.append(DiffSegment(op="equal", expected=expected[len(expected) - s:], actual=actual[len(actual) - s:]))
    return segments


def _op_for(expected: str, actual: str) -> str:
    if expected and actual:
        return "replace"
    return "delete" if expected else "insert"


def _is_boundary(before: str, after: str) -> bool:
    """Word boundary between two characters ("" = edge of the line)."""
    return not before or not after or before.isalnum() != after.isalnum()


def _slide_to_words(segments: list[DiffSegment]) -> list[DiffSegment]:
    """Shift pure insertions/deletions to word boundaries when the text allows it.

    ``"Fuel after the trip"`` -> ``"Fuel after trip"``: difflib may report ``'he t'`` deleted; the
    same edit is better shown as ``'the '``. Only shifts that keep both texts identical are tried.
    """
    out = list(segments)
    for k, seg in enumerate(out):
        if seg.op not in ("insert", "delete"):
            continue
        has_left = k > 0 and out[k - 1].op == "equal"
        has_right = k + 1 < len(out) and out[k + 1].op == "equal"
        left = out[k - 1].expected if has_left else ""
        right = out[k + 1].expected if has_right else ""
        moved = seg.actual if seg.op == "insert" else seg.expected
        # a neighbour may only be emptied when it is at the edge of the line
        min_left = 0 if k - 1 == 0 or not has_left else 1
        min_right = 0 if k + 1 == len(out) - 1 or not has_right else 1
        candidates = [(left, moved, right, 0)]
        lt, mv, rt, shift = left, moved, right, 0
        while len(lt) > min_left and lt[-1] == mv[-1]:
            lt, mv, rt, shift = lt[:-1], lt[-1] + mv[:-1], mv[-1] + rt, shift - 1
            candidates.append((lt, mv, rt, shift))
        lt, mv, rt, shift = left, moved, right, 0
        while len(rt) > min_right and rt[0] == mv[0]:
            lt, mv, rt, shift = lt + mv[0], mv[1:] + rt[0], rt[1:], shift + 1
            candidates.append((lt, mv, rt, shift))
        if len(candidates) == 1:
            continue

        def score(c: tuple[str, str, str, int]) -> tuple[int, bool, int]:
            lt_, mv_, rt_, sh = c
            bounds = _is_boundary(lt_[-1:], mv_[:1]) + _is_boundary(mv_[-1:], rt_[:1])
            return bounds, not mv_[0].isspace(), -abs(sh)

        lt, mv, rt, _ = max(candidates, key=score)
        if has_left:
            out[k - 1] = DiffSegment(op="equal", expected=lt, actual=lt)
        if has_right:
            out[k + 1] = DiffSegment(op="equal", expected=rt, actual=rt)
        out[k] = DiffSegment(op=seg.op, expected="" if seg.op == "insert" else mv, actual=mv if seg.op == "insert" else "")
    return [s for s in out if s.op != "equal" or s.expected]


def _merge(segments: list[DiffSegment]) -> list[DiffSegment]:
    """Merge adjacent segments of the same nature (consecutive edits become one replace)."""
    merged: list[DiffSegment] = []
    for seg in segments:
        if merged and (merged[-1].op == "equal") == (seg.op == "equal"):
            prev = merged[-1]
            exp, act = prev.expected + seg.expected, prev.actual + seg.actual
            op = "equal" if seg.op == "equal" else _op_for(exp, act)
            merged[-1] = DiffSegment(op=op, expected=exp, actual=act)  # type: ignore[arg-type]
        else:
            merged.append(seg)
    return merged


# ------------------------------------------------------------------------------------------------
# Hints
# ------------------------------------------------------------------------------------------------


def _q(s: str, limit: int = 40) -> str:
    return repr(s if len(s) <= limit else s[: limit - 1] + "…")


def _eol_hint(exp_eol: str, act_eol: str) -> tuple[DiffKind, str]:
    if exp_eol == "\n" and act_eol == "\r\n":
        return "crlf", "Windows line ending (\\r\\n)"
    if exp_eol == "\r\n" and act_eol == "\n":
        return "crlf", "Unix line ending (\\n) instead of \\r\\n"
    if exp_eol and not act_eol:
        return "missing_newline", "missing newline at end of output"
    return "extra_newline", "extra newline at end of output"


def _classify(exp: Line, act: Line, segments: list[DiffSegment]) -> tuple[DiffKind, list[str]]:
    et, ee = exp
    at, ae = act
    if et == at:
        kind, hint = _eol_hint(ee, ae)
        return kind, [hint]
    kind: DiffKind
    if et.rstrip() == at.rstrip():
        kind, hints = "trailing_whitespace", [_trailing_hint(et, at)]
    elif et.lower() == at.lower():
        kind, hints = "case", _case_hints(et, at)
    elif "".join(et.split()) == "".join(at.split()):
        kind, hints = "whitespace", _segment_hints(segments) or [f"different whitespace (col {_first_col(segments)})"]
    else:
        kind = "typo" if _is_typo(segments) else "different"
        hints = _segment_hints(segments)
    if ee != ae:
        hints.append(_eol_hint(ee, ae)[1])
    return kind, hints


def _first_col(segments: list[DiffSegment]) -> int:
    col = 1
    for seg in segments:
        if seg.op != "equal":
            return col
        col += len(seg.expected)
    return col


def _ws_phrase(verb: str, ws: str, where: str) -> str:
    if set(ws) == {" "}:
        return f"{verb} {where}space" if len(ws) == 1 else f"{verb} {len(ws)} {where}spaces"
    if set(ws) == {"\t"}:
        return f"{verb} {where}tab" if len(ws) == 1 else f"{verb} {len(ws)} {where}tabs"
    return f"{verb} {where}whitespace"


def _trailing_hint(et: str, at: str) -> str:
    base = et.rstrip()
    we, wa = et[len(base):], at[len(base):]
    if we.startswith(wa):
        return _ws_phrase("missing", we[len(wa):], "trailing ")
    if wa.startswith(we):
        return _ws_phrase("extra", wa[len(we):], "trailing ")
    return "different trailing whitespace"


def _case_hints(et: str, at: str) -> list[str]:
    if len(et) != len(at):
        return ["case differs"]
    runs: list[tuple[int, int]] = []
    for k, (x, y) in enumerate(zip(et, at)):
        if x != y:
            if runs and runs[-1][1] == k:
                runs[-1] = (runs[-1][0], k + 1)
            else:
                runs.append((k, k + 1))
    hints = [f"case differs: {_q(et[a:b])} → {_q(at[a:b])} (col {a + 1})" for a, b in runs[:MAX_HINTS_PER_LINE]]
    if len(runs) > MAX_HINTS_PER_LINE:
        hints.append(f"{len(runs) - MAX_HINTS_PER_LINE} more case difference(s)")
    return hints


def _is_typo(segments: list[DiffSegment]) -> bool:
    edits = [s for s in segments if s.op != "equal"]
    size = sum(max(len(s.expected), len(s.actual)) for s in edits)
    return 0 < len(edits) <= 2 and size <= 3


def _segment_hints(segments: list[DiffSegment]) -> list[str]:
    edits: list[tuple[DiffSegment, int]] = []
    col = 1
    for seg in segments:
        if seg.op != "equal":
            edits.append((seg, col))
        col += len(seg.expected)
    hints = [_segment_hint(seg, c) for seg, c in edits[:MAX_HINTS_PER_LINE]]
    if len(edits) > MAX_HINTS_PER_LINE:
        hints.append(f"{len(edits) - MAX_HINTS_PER_LINE} more difference(s)")
    return hints


def _segment_hint(seg: DiffSegment, col: int) -> str:
    e, a = seg.expected, seg.actual
    if seg.op == "replace":
        if e.lower() == a.lower():
            return f"case differs: {_q(e)} → {_q(a)} (col {col})"
        if e.isspace() and a.isspace():
            return f"different whitespace (col {col})"
        if len(e) == 1 and len(a) == 1:
            return f"typo: {_q(e)} → {_q(a)} (col {col})"
        return f"different text: {_q(e)} → {_q(a)} (col {col})"
    if seg.op == "delete":
        return f"{_ws_phrase('missing', e, '')} (col {col})" if e.isspace() else f"missing text: {_q(e)} (col {col})"
    return f"{_ws_phrase('extra', a, '')} (col {col})" if a.isspace() else f"extra text: {_q(a)} (col {col})"


# ------------------------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------------------------


def _unique(items: list[DiffKind]) -> list[DiffKind]:
    return list(dict.fromkeys(items))


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _numbers(nums: list[int]) -> str:
    shown = ", ".join(str(n) for n in nums[:5])
    return shown + (", …" if len(nums) > 5 else "")


def _summary(rows: list[_Row]) -> str:
    changed = [r for r in rows if r.line.op == "changed"]
    missing_idx = [k for k, r in enumerate(rows) if r.line.op == "missing"]
    extra_idx = [k for k, r in enumerate(rows) if r.line.op == "extra"]
    parts: list[str] = []
    if changed:
        nums = [r.line.expected_lineno or 0 for r in changed]
        labels = ", ".join(dict.fromkeys(_KIND_LABELS.get(r.kind or "different", "different text") for r in changed))
        if len(changed) == 1:
            parts.append(f"1 line differs (line {nums[0]}): {labels}")
        else:
            parts.append(f"{len(changed)} lines differ (lines {_numbers(nums)}): {labels}")
    if missing_idx:
        last_actual = max((k for k, r in enumerate(rows) if r.line.actual_lineno is not None), default=-1)
        n = len(missing_idx)
        word = "empty line" if all(rows[k].line.expected == "" for k in missing_idx) else "line"
        if all(k > last_actual for k in missing_idx):
            parts.append(f"{_plural(n, word)} missing at the end")
        else:
            parts.append(f"{_plural(n, word)} missing (from line {rows[missing_idx[0]].line.expected_lineno})")
    if extra_idx:
        last_expected = max((k for k, r in enumerate(rows) if r.line.expected_lineno is not None), default=-1)
        n = len(extra_idx)
        word = "extra empty line" if all(rows[k].line.actual == "" for k in extra_idx) else "extra line"
        if all(k > last_expected for k in extra_idx):
            parts.append(f"{_plural(n, word)} at the end")
        else:
            parts.append(f"{_plural(n, word)} (from line {rows[extra_idx[0]].line.actual_lineno})")
    return "; ".join(parts)
