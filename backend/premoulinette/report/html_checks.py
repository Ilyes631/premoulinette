"""HTML fragments for checks: badges, issue cards, evidence, diffs and fixes.

Every piece of text goes through :func:`esc` (or :func:`vis`), because check messages and evidence
contain student output and source code, which may contain HTML.
"""
from __future__ import annotations

import html
import re

from premoulinette.report.common import (
    STATUS_LABELS,
    DiffRow,
    diff_rows,
    eol_marker,
    location_text,
    provenance_label,
    visible,
)
from premoulinette.results.models import CheckResult, CodeExcerpt, Evidence, Fix, TextDiff


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


_INVISIBLE_RUN = re.compile(r"[ \t\r\n]+")


def vis(text: str) -> str:
    """Escaped text with invisible characters made visible (and dimmed).

    Safe to post-process after escaping: html.escape never emits whitespace.
    """
    return _INVISIBLE_RUN.sub(lambda m: f'<span class="ws">{visible(m.group())}</span>', html.escape(text, quote=True))


def badge(status: str, label: str | None = None) -> str:
    return f'<span class="badge b-{esc(status)}">{esc(label or STATUS_LABELS.get(status, status.upper()))}</span>'


def check_card(c: CheckResult) -> str:
    head = [badge(c.status)]
    if c.severity:
        head.append(f'<span class="sev sev-{esc(c.severity)}">{esc(c.severity)}</span>')
    head.append(f"<h4>{esc(c.title)}</h4>")
    meta = [f"<code>{esc(c.id)}</code>",
            f'<span class="prov prov-{esc(c.origin.provenance)}">{esc(provenance_label(c))}</span>']
    if loc := location_text(c):
        meta.append(f"<code>{esc(loc)}</code>")
    if c.diagnosis:
        meta.append(f"<span>diagnosis: <code>{esc(c.diagnosis)}</code></span>")
    body = [
        f'<div class="card-head">{"".join(head)}</div>',
        f'<div class="card-meta">{"".join(meta)}</div>',
        f'<p class="msg">{esc(c.message)}</p>',
    ]
    if c.blocked_by:
        body.append(f'<p class="muted">Not run: blocked by <code>{esc(c.blocked_by)}</code>.</p>')
    if c.evidence is not None:
        body.append(evidence_html(c.evidence))
    if c.fix is not None:
        body.append(fix_html(c.fix))
    return f'<article class="card s-{esc(c.status)}">{"".join(body)}</article>'


def evidence_html(ev: Evidence) -> str:
    rows: list[tuple[str, str]] = []
    if ev.call:
        rows.append(("Call", f"<code>{esc(ev.call)}</code>"))
    if ev.argv:
        rows.append(("Arguments", " ".join(f"<code>{esc(a)}</code>" for a in ev.argv)))
    if ev.stdin:
        rows.append(("Standard input", f"<code>{vis(ev.stdin)}</code>"))
    if ev.expected_value is not None:
        rows.append(("Expected", f"<code>{esc(ev.expected_value.repr)}</code> <span class=\"muted\">"
                                 f"({esc(ev.expected_value.type)})</span>"))
    if ev.actual_value is not None:
        rows.append(("Actual", f"<code>{esc(ev.actual_value.repr)}</code> <span class=\"muted\">"
                               f"({esc(ev.actual_value.type)})</span>"))
    if ev.rule:
        rows.append(("Rule from the subject", f"<code>{esc(ev.rule)}</code>"))
    if ev.exit_code is not None:
        rows.append(("Exit code", esc(ev.exit_code)))
    if ev.timed_out:
        rows.append(("Timeout", "the program did not finish in time"))
    parts = []
    if rows:
        parts.append('<dl class="kv">' + "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in rows) + "</dl>")
    if ev.value_diff is not None and not ev.value_diff.equal:
        parts.append(diff_html("Value difference", ev.value_diff))
    if ev.stdout_diff is not None and not ev.stdout_diff.equal:
        parts.append(diff_html("Output difference", ev.stdout_diff))
    elif ev.stdout_diff is None and ev.expected_stdout is not None and ev.actual_stdout is not None \
            and ev.expected_stdout != ev.actual_stdout:
        parts.append(f'<div class="diff-title">Expected output</div><pre>{_vis_lines(ev.expected_stdout)}</pre>')
        parts.append(f'<div class="diff-title">Actual output</div><pre>{_vis_lines(ev.actual_stdout)}</pre>')
    if ev.exception is not None:
        parts.append(f'<p><b>Exception</b> <code>{esc(ev.exception.type)}</code>: {esc(ev.exception.message)}</p>')
        if ev.exception.traceback:
            parts.append(f"<pre>{esc(ev.exception.traceback)}</pre>")
    elif ev.stderr:
        parts.append(f'<div class="diff-title">Standard error</div><pre>{esc(ev.stderr)}</pre>')
    if ev.code is not None:
        parts.append(code_excerpt_html(ev.code))
    return "".join(parts)


def _vis_lines(text: str) -> str:
    return "\n".join(vis(line) for line in text.splitlines(keepends=True))


def _row_html(row: DiffRow) -> str:
    cls = {" ": "row-eq", "-": "row-del", "+": "row-ins"}[row.sign]
    mark = "hl-del" if row.sign == "-" else "hl-ins"
    text = "".join(f'<mark class="{mark}">{vis(t)}</mark>' if hl and t else vis(t) for t, hl in row.parts)
    if row.eol:
        eol_cls = "eol eol-changed" if row.eol_changed else "eol"
        text += f'<span class="{eol_cls}">{esc(eol_marker(row.eol))}</span>'
    notes = list(row.hints)
    if row.source and row.sign == "+":
        notes.append(f"printed by {row.source}")
    sign = {" ": "", "-": "−", "+": "+"}[row.sign]
    lineno = "" if row.lineno is None else str(row.lineno)
    return (f'<tr class="{cls}"><td class="sign">{sign}</td><td class="ln">{esc(lineno)}</td>'
            f'<td class="txt">{text}</td><td class="note">{esc(" · ".join(notes))}</td></tr>')


def diff_html(label: str, diff: TextDiff) -> str:
    rows, omitted = diff_rows(diff)
    title = esc(label) + (f" — {esc(diff.summary)}" if diff.summary else "")
    body = "".join(_row_html(r) for r in rows)
    if omitted:
        body += f'<tr><td></td><td></td><td class="note" colspan="2">… {omitted} more line(s) not shown</td></tr>'
    return (f'<div class="diff-block"><div class="diff-title">{title}</div>'
            f'<div class="diff-scroll"><table class="diff"><tbody>{body}</tbody></table></div>'
            '<div class="legend">− expected · + actual · <span class="ws">·</span> space · '
            '<span class="ws">→</span> tab · <span class="ws">↵</span> newline</div></div>')


def code_excerpt_html(code: CodeExcerpt) -> str:
    width = len(str(code.start_line + max(len(code.lines) - 1, 0)))
    lines = []
    for offset, line in enumerate(code.lines):
        n = code.start_line + offset
        content = f"{n:>{width}} | {esc(line)}"
        lines.append(f'<span class="hl-line">{content}</span>' if n in code.highlight else content)
    return f'<div class="diff-title">{esc(code.file)}</div><pre class="code">' + "\n".join(lines) + "</pre>"


def fix_html(fix: Fix) -> str:
    parts = [f'<div class="fix-title">Suggested fix <span class="muted">(confidence: {esc(fix.confidence)})</span></div>',
             f"<p>{esc(fix.summary)}</p>"]
    if fix.patch:
        parts.append('<pre class="patch">' + "\n".join(_patch_line(line) for line in fix.patch.splitlines()) + "</pre>")
    elif fix.before is not None or fix.after is not None:
        parts.append(f'<pre class="patch"><span class="p-del">- {esc(fix.before or "")}</span>\n'
                     f'<span class="p-add">+ {esc(fix.after or "")}</span></pre>')
    return f'<div class="fix">{"".join(parts)}</div>'


def _patch_line(line: str) -> str:
    if line.startswith("@@"):
        return f'<span class="p-hunk">{esc(line)}</span>'
    if line.startswith("+") and not line.startswith("+++"):
        return f'<span class="p-add">{esc(line)}</span>'
    if line.startswith("-") and not line.startswith("---"):
        return f'<span class="p-del">{esc(line)}</span>'
    return esc(line)
