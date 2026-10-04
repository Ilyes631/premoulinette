"""Helpers shared by the Markdown and HTML renderers (labels, ordering, diff rows, visible chars)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from premoulinette.results.models import AnalysisReport, CheckResult, DiffLine, TextDiff

DISCLAIMER = (
    "Readiness Score is not an official grade. It only covers the requirements PréMoulinette could verify "
    "from the subject; the real grader may run hidden tests."
)

PROVENANCE_LABELS: dict[str, str] = {
    "explicit": "Explicit requirement",
    "derived": "Derived test",
    "heuristic": "Heuristic (not official)",
    "ai_extracted": "AI-extracted (needs review)",
    "user": "User-defined requirement",
}

STATUS_LABELS: dict[str, str] = {
    "pass": "PASS", "fail": "FAIL", "warning": "WARNING", "info": "INFO", "bonus": "BONUS", "skipped": "SKIPPED",
}

EXERCISE_STATUS_LABELS: dict[str, str] = {
    "pass": "PASS", "fail": "FAIL", "warning": "PASS (warnings)", "missing": "MISSING",
    "not_implemented": "NOT IMPLEMENTED", "partial": "PARTIAL",
}

CATEGORY_LABELS: dict[str, str] = {
    "structure": "Structure", "syntax": "Compilation", "functions": "Required functions",
    "explicit_tests": "Known tests", "derived_tests": "Derived tests", "heuristic_tests": "Heuristic tests",
    "output": "Output matching", "constraints": "Constraints", "runtime": "Import safety", "git": "Git",
}

ISSUE_STATUSES = frozenset({"fail", "skipped", "warning", "bonus"})
_STATUS_RANK = {"fail": 0, "skipped": 1, "warning": 2, "bonus": 3, "info": 4, "pass": 5}
_SEVERITY_RANK = {"critical": 0, "major": 1, "minor": 2, "style": 3}

GENERAL_GROUP = "General"
MAX_DIFF_ROWS = 400

_VISIBLE = {" ": "·", "\t": "→", "\r": "␍", "\n": "↵"}
_EOL_MARKERS = {"\n": "↵", "\r\n": "␍↵", "\r": "␍", "": ""}


def visible(text: str) -> str:
    """Single-line visible form: ' '→'·', tab→'→', CR→'␍', LF→'↵'."""
    return "".join(_VISIBLE.get(ch, ch) for ch in text)


def eol_marker(eol: str) -> str:
    return _EOL_MARKERS.get(eol, visible(eol))


def provenance_label(check: CheckResult) -> str:
    return PROVENANCE_LABELS.get(check.origin.provenance, check.origin.provenance)


def location_text(check: CheckResult) -> str | None:
    loc = check.location
    if loc is not None:
        return f"{loc.file}:{loc.line}" if loc.line else loc.file
    return check.file


def fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}%"


def is_issue(check: CheckResult) -> bool:
    return check.status in ISSUE_STATUSES


def issue_order(check: CheckResult) -> tuple[int, int, str]:
    return (_STATUS_RANK.get(check.status, 9), _SEVERITY_RANK.get(check.severity or "", 9), check.id)


def sorted_issues(checks: list[CheckResult]) -> list[CheckResult]:
    return sorted((c for c in checks if is_issue(c)), key=issue_order)


def group_issues_by_file(report: AnalysisReport) -> list[tuple[str, list[CheckResult]]]:
    """Issues grouped by file: spec files first (spec order), then other files, then checks without file.

    ``check.file`` (the spec path the check is about) wins over the location, so e.g. a wrong-case file is
    listed with its exercise file rather than under the misnamed path.
    """
    groups: dict[str, list[CheckResult]] = {}
    for c in sorted_issues(report.checks):
        key = c.file or (c.location.file if c.location else None) or GENERAL_GROUP
        groups.setdefault(key, []).append(c)
    spec_order = [f.path for f in report.spec.expected_files()]
    ordered = [p for p in spec_order if p in groups]
    ordered += sorted(k for k in groups if k not in spec_order and k != GENERAL_GROUP)
    if GENERAL_GROUP in groups:
        ordered.append(GENERAL_GROUP)
    return [(k, groups[k]) for k in ordered]


# ---- diff rows --------------------------------------------------------------------------------

Part = tuple[str, bool]  # (raw text, highlighted)


@dataclass(frozen=True)
class DiffRow:
    sign: Literal[" ", "-", "+"]
    lineno: int | None
    parts: tuple[Part, ...]
    eol: str
    eol_changed: bool = False
    source: str | None = None
    hints: tuple[str, ...] = ()


def _segment_parts(line_text: str, segments: list[tuple[str, str]]) -> tuple[Part, ...]:
    parts = tuple((text, op != "equal") for op, text in segments if text)
    if "".join(t for t, _ in parts) != line_text:  # inconsistent segments: highlight the whole line
        return ((line_text, True),)
    return parts


def _source_text(line: DiffLine) -> str | None:
    if line.source is None:
        return None
    return f"{line.source.file}:{line.source.line}" if line.source.line else line.source.file


def diff_rows(diff: TextDiff, limit: int = MAX_DIFF_ROWS) -> tuple[list[DiffRow], int]:
    """Flatten a TextDiff into displayable rows. Returns (rows, number of omitted rows)."""
    rows = _rows_from_lines(diff) if diff.lines else _rows_from_texts(diff)
    if len(rows) > limit:
        return rows[:limit], len(rows) - limit
    return rows, 0


def _rows_from_lines(diff: TextDiff) -> list[DiffRow]:
    rows: list[DiffRow] = []
    for line in diff.lines:
        source, hints = _source_text(line), tuple(line.hints)
        exp, act = line.expected or "", line.actual or ""
        if line.op == "equal":
            rows.append(DiffRow(" ", line.expected_lineno, ((exp, False),), line.expected_eol, source=source))
        elif line.op == "missing":
            rows.append(DiffRow("-", line.expected_lineno, ((exp, True),), line.expected_eol, True, hints=hints))
        elif line.op == "extra":
            rows.append(DiffRow("+", line.actual_lineno, ((act, True),), line.actual_eol, True, source, hints))
        else:  # changed: expected side then actual side, char segments highlighted
            eol_changed = line.expected_eol != line.actual_eol
            if line.segments:
                exp_parts = _segment_parts(exp, [(s.op, s.expected) for s in line.segments if s.op != "insert"])
                act_parts = _segment_parts(act, [(s.op, s.actual) for s in line.segments if s.op != "delete"])
            else:
                exp_parts, act_parts = ((exp, True),), ((act, True),)
            rows.append(DiffRow("-", line.expected_lineno, exp_parts, line.expected_eol, eol_changed))
            rows.append(DiffRow("+", line.actual_lineno, act_parts, line.actual_eol, eol_changed, source, hints))
    return rows


def _split_eol(raw: str) -> tuple[str, str]:
    for eol in ("\r\n", "\n", "\r"):
        if raw.endswith(eol):
            return raw[: -len(eol)], eol
    return raw, ""


def _text_rows(text: str, sign: Literal[" ", "-", "+"]) -> list[DiffRow]:
    highlighted = sign != " "
    return [
        DiffRow(sign, i, ((body, highlighted),), eol, highlighted)
        for i, (body, eol) in enumerate(map(_split_eol, text.splitlines(keepends=True)), start=1)
    ]


def _rows_from_texts(diff: TextDiff) -> list[DiffRow]:
    """Fallback when the producer gave no line alignment: whole expected, then whole actual."""
    if diff.equal:
        return _text_rows(diff.expected, " ")
    return _text_rows(diff.expected, "-") + _text_rows(diff.actual, "+")
