"""Markdown rendering of checks: summary tables and per-issue details (evidence, diffs, fixes)."""
from __future__ import annotations

from premoulinette.report.common import (
    STATUS_LABELS,
    diff_rows,
    eol_marker,
    location_text,
    provenance_label,
    sorted_issues,
    visible,
)
from premoulinette.report.md_utils import MarkdownWriter, md_code, md_fence, md_table, md_text
from premoulinette.results.models import CheckResult, CodeExcerpt, Evidence, Fix, TextDiff

NO_CHECKS = "*No checks in this section.*"


def status_text(c: CheckResult) -> str:
    label = f"**{STATUS_LABELS.get(c.status, c.status.upper())}**"
    return f"{label} ({c.severity})" if c.severity and c.status != "pass" else label


def checks_table(checks: list[CheckResult]) -> str:
    rows = [
        [
            status_text(c),
            f"{md_text(c.title)} · {md_code(c.id, table=True)}",
            md_code(loc, table=True) if (loc := location_text(c)) else "",
            md_text(provenance_label(c)),
            md_text(c.message),
        ]
        for c in checks
    ]
    return md_table(["Status", "Check", "Location", "Origin", "Result"], rows)


def write_check_section(w: MarkdownWriter, checks: list[CheckResult], *, details: bool = True) -> None:
    """Summary table of every check, then a details block for each issue."""
    if not checks:
        w.block(NO_CHECKS)
        return
    w.block(checks_table(checks))
    if details:
        for c in sorted_issues(checks):
            write_check_details(w, c)


def write_check_details(w: MarkdownWriter, c: CheckResult) -> None:
    w.heading(4, f"{STATUS_LABELS.get(c.status, c.status.upper())} — {md_text(c.title)}")
    meta = [md_code(c.id)]
    if c.severity:
        meta.append(f"severity: {c.severity}")
    meta.append(md_text(provenance_label(c)))
    if loc := location_text(c):
        meta.append(md_code(loc))
    if c.diagnosis:
        meta.append(f"diagnosis: {md_code(c.diagnosis)}")
    w.block(" · ".join(meta))
    w.block(md_text(c.message))
    if c.blocked_by:
        w.block(f"Not run: blocked by {md_code(c.blocked_by)}.")
    if c.evidence is not None:
        _write_evidence(w, c.evidence)
    if c.fix is not None:
        _write_fix(w, c.fix)


def _write_evidence(w: MarkdownWriter, ev: Evidence) -> None:
    items: list[str] = []
    if ev.call:
        items.append(f"Call: {md_code(ev.call)}")
    if ev.argv:
        items.append("Arguments: " + " ".join(md_code(a) for a in ev.argv))
    if ev.stdin:
        items.append(f"Standard input: {md_code(visible(ev.stdin))}")
    if ev.expected_value is not None:
        items.append(f"Expected: {md_code(ev.expected_value.repr)} ({md_text(ev.expected_value.type)})")
    if ev.actual_value is not None:
        items.append(f"Actual: {md_code(ev.actual_value.repr)} ({md_text(ev.actual_value.type)})")
    if ev.rule:
        items.append(f"Rule from the subject: {md_code(ev.rule)}")
    if ev.exit_code is not None:
        items.append(f"Exit code: {ev.exit_code}")
    if ev.timed_out:
        items.append("Timed out.")
    w.bullets(items)

    if ev.value_diff is not None and not ev.value_diff.equal:
        write_diff(w, "Value difference", ev.value_diff)
    if ev.stdout_diff is not None and not ev.stdout_diff.equal:
        write_diff(w, "Output difference", ev.stdout_diff)
    elif ev.stdout_diff is None and ev.expected_stdout is not None and ev.actual_stdout is not None \
            and ev.expected_stdout != ev.actual_stdout:
        w.block("**Expected output**")
        w.block(md_fence(_visible_lines(ev.expected_stdout), "text"))
        w.block("**Actual output**")
        w.block(md_fence(_visible_lines(ev.actual_stdout), "text"))
    if ev.exception is not None:
        w.block(f"Exception: {md_code(ev.exception.type)}: {md_text(ev.exception.message)}")
        if ev.exception.traceback:
            w.block(md_fence(ev.exception.traceback, "text"))
    elif ev.stderr:
        w.block("**Standard error**")
        w.block(md_fence(ev.stderr, "text"))
    if ev.code is not None:
        w.block(md_fence(_excerpt(ev.code), "text"))


def _visible_lines(text: str) -> str:
    return "\n".join(visible(line) for line in text.splitlines(keepends=True))


def write_diff(w: MarkdownWriter, label: str, diff: TextDiff) -> None:
    rows, omitted = diff_rows(diff)
    w.block(f"**{label}**" + (f" — {md_text(diff.summary)}" if diff.summary else ""))
    lines = [f"{r.sign} {''.join(visible(text) for text, _ in r.parts)}{eol_marker(r.eol)}" for r in rows]
    if omitted:
        lines.append(f"  … {omitted} more line(s) not shown")
    w.block(md_fence("\n".join(lines), "diff"))
    notes: list[str] = []
    for r in rows:
        if r.sign == " " or not (r.hints or r.source):
            continue
        side = "Actual" if r.sign == "+" else "Expected"
        note = f"{side} line {r.lineno}" if r.lineno is not None else side
        if r.hints:
            note += ": " + "; ".join(md_text(h) for h in r.hints)
        if r.source and r.sign == "+":
            note += f" (printed by {md_code(r.source)})"
        notes.append(note)
    w.bullets(notes)


def _excerpt(code: CodeExcerpt) -> str:
    width = len(str(code.start_line + max(len(code.lines) - 1, 0)))
    out = [f"# {code.file}"]
    for offset, line in enumerate(code.lines):
        n = code.start_line + offset
        marker = ">" if n in code.highlight else " "
        out.append(f"{marker} {n:>{width}} | {line}")
    return "\n".join(out)


def _write_fix(w: MarkdownWriter, fix: Fix) -> None:
    w.block(f"**Suggested fix** (confidence: {fix.confidence}): {md_text(fix.summary)}")
    if fix.patch:
        w.block(md_fence(fix.patch, "diff"))
    elif fix.before is not None or fix.after is not None:
        w.bullets([f"Before: {md_code(fix.before or '')}", f"After: {md_code(fix.after or '')}"])
