"""Markdown report. Section order is part of the contract (ARCHITECTURE.md, ``report/export.py``)."""
from __future__ import annotations

from datetime import timezone

from premoulinette.report.common import (
    DISCLAIMER,
    EXERCISE_STATUS_LABELS,
    PROVENANCE_LABELS,
    STATUS_LABELS,
    fmt_pct,
    location_text,
    sorted_issues,
)
from premoulinette.report.md_checks import write_check_section
from premoulinette.report.md_utils import MarkdownWriter, md_code, md_table, md_text
from premoulinette.results.models import AnalysisReport, CheckResult, ExerciseScore
from premoulinette.spec.models import Constraints

SECTIONS: tuple[str, ...] = (
    "Repository", "Subject", "Mandatory requirements", "Optional requirements", "Structure", "Functions",
    "Scripts", "Constraints", "Static analysis", "Runtime analysis", "Known tests", "Derived tests",
    "Warnings", "Bonus",
)

# Category-driven sections (bonus checks are shown in "Bonus" only).
_CATEGORY_SECTIONS: dict[str, str] = {
    "Structure": "structure", "Functions": "functions", "Scripts": "output", "Constraints": "constraints",
    "Static analysis": "syntax", "Runtime analysis": "runtime", "Known tests": "explicit_tests",
    "Derived tests": "derived_tests",
}

LEGEND = (
    "In differences, `-` lines are expected and `+` lines are what the program produced. Invisible characters "
    "are shown as `·` (space), `→` (tab), `↵` (newline) and `␍` (carriage return)."
)


def render_markdown(report: AnalysisReport) -> str:
    w = MarkdownWriter()
    _header(w, report)
    for title in SECTIONS:
        w.heading(2, title)
        _SECTION_WRITERS[title](w, report)
    w.block("---")
    w.block(f"*{md_text(DISCLAIMER)}*")
    return w.render()


def _category_checks(report: AnalysisReport, category: str) -> list[CheckResult]:
    return [c for c in report.checks if c.category == category and not c.bonus]


def _header(w: MarkdownWriter, r: AnalysisReport) -> None:
    s = r.score
    created = r.created_at.astimezone(timezone.utc) if r.created_at.tzinfo else r.created_at
    w.heading(1, f"PréMoulinette report — {md_text(r.subject.title)}")
    w.block(
        f"Analysis #{r.number} · {created:%Y-%m-%d %H:%M} UTC · {r.duration_ms / 1000:.1f} s · "
        f"sandbox: {md_text(r.sandbox.mode)}"
    )
    w.block(f"> **{md_text(s.verdict_title)}** — {md_text(s.verdict_message)}")
    bonus = (f"{fmt_pct(s.bonus_completion)} ({s.bonus_passed}/{s.bonus_total} bonus exercises)"
             if s.bonus_completion is not None else "no bonus in this subject")
    w.bullets([
        f"Readiness Score: **{fmt_pct(s.readiness)}** ({s.mandatory_passed}/{s.mandatory_total} mandatory checks passed)",
        f"Mandatory failures: **{s.mandatory_failures}**",
        f"Bonus completion: {bonus}",
        f"Confidence: **{s.confidence}**",
    ])
    if s.confidence_reasons:
        w.block("Confidence notes:")
        w.bullets([md_text(reason) for reason in s.confidence_reasons])
    w.block(f"*{md_text(DISCLAIMER)}*")
    w.block(LEGEND)


# ---- sections ---------------------------------------------------------------------------------

def _repository(w: MarkdownWriter, r: AnalysisReport) -> None:
    p = r.project
    rows = [
        ["Project", md_text(p.name)],
        ["Source", md_text(p.source_kind)],
        ["Path", md_code(p.path, table=True) if p.path else "—"],
        ["Detected root", md_code(p.detected_root, table=True) if p.detected_root else "(top level)"],
        ["Files", f"{p.file_count} ({p.python_files} Python)"],
    ]
    if p.root_note:
        rows.append(["Root detection", md_text(p.root_note)])
    w.block(md_table(["Property", "Value"], rows))
    w.heading(3, "Git")
    git = p.git
    if git is None or not git.is_repo:
        w.block(md_text(git.error) if git and git.error else "Not a git repository (or git information unavailable).")
    else:
        git_rows = [
            ["Branch", md_text(git.branch or "—")],
            ["HEAD", md_code(git.head, table=True) if git.head else "—"],
            ["Last commit", md_text(" ".join(x for x in (git.last_commit_date, git.last_commit_message) if x) or "—")],
            ["Working tree", "dirty" if git.dirty else "clean"],
            ["Modified / untracked / staged", f"{len(git.modified)} / {len(git.untracked)} / {len(git.staged)}"],
        ]
        if git.ignored_required:
            git_rows.append(["Ignored required files", ", ".join(md_code(x, table=True) for x in git.ignored_required)])
        if git.tags:
            git_rows.append(["Tags", ", ".join(md_code(x, table=True) for x in git.tags)])
        w.block(md_table(["Property", "Value"], git_rows))
    git_checks = _category_checks(r, "git")
    if git_checks:
        write_check_section(w, git_checks)


def _constraint_lines(c: Constraints) -> list[str]:
    def names(xs: list[str]) -> str:
        return ", ".join(md_code(x) for x in xs) if xs else "none"

    lines = [
        "Allowed builtins: " + ("no restriction" if c.allowed_builtins is None else names(c.allowed_builtins)),
        f"Forbidden builtins: {names(c.forbidden_builtins)}",
        "Allowed imports: " + ("no restriction" if c.allowed_imports is None
                               else ("no import allowed" if not c.allowed_imports else names(c.allowed_imports))),
    ]
    for label, values in (("Forbidden imports", c.forbidden_imports), ("Forbidden methods", c.forbidden_methods),
                          ("Forbidden constructs", list(c.forbidden_constructs)),
                          ("Required constructs", list(c.required_constructs))):
        if values:
            lines.append(f"{label}: {names(values)}")
    return lines


def _subject(w: MarkdownWriter, r: AnalysisReport) -> None:
    spec = r.spec
    mandatory = sum(1 for e in spec.exercises if e.required and not e.bonus)
    bonus = sum(1 for e in spec.exercises if e.bonus)
    w.block(md_table(["Property", "Value"], [
        ["Title", md_text(r.subject.title)],
        ["Source file", md_text(r.subject.source_name or "—")],
        ["Parser", md_text(r.subject.parser)],
        ["Language", md_text(spec.language + (f" {spec.language_version}" if spec.language_version else ""))],
        ["Reviewed by user", "yes" if spec.metadata.reviewed_by_user else "no"],
        ["Exercises", f"{len(spec.exercises)} ({mandatory} mandatory, {bonus} bonus)"],
    ]))
    w.heading(3, "Global constraints")
    w.bullets(_constraint_lines(spec.global_constraints))
    w.heading(3, "Exercises")
    rows = [
        [md_code(e.id, table=True), md_text(e.title), md_code(e.file_path, table=True), e.kind,
         "bonus" if e.bonus else ("mandatory" if e.required else "optional"),
         md_text(PROVENANCE_LABELS.get(e.origin.provenance, e.origin.provenance))]
        for e in spec.exercises
    ]
    w.block(md_table(["Id", "Title", "File", "Kind", "Requirement", "Origin"], rows) if rows else "*No exercise.*")
    if spec.notes:
        w.heading(3, "Parser notes")
        w.bullets([md_text(n) for n in spec.notes])


def _exercise_table(exercises: list[ExerciseScore]) -> str:
    rows = [
        [md_text(e.title), md_code(e.file, table=True), f"**{EXERCISE_STATUS_LABELS.get(e.status, e.status)}**",
         f"{e.passed}/{e.total}", fmt_pct(e.score), str(e.issues)]
        for e in exercises
    ]
    return md_table(["Exercise", "File", "Status", "Checks passed", "Score", "Issues"], rows)


def _mandatory(w: MarkdownWriter, r: AnalysisReport) -> None:
    s = r.score
    w.block(f"Readiness Score: **{fmt_pct(s.readiness)}** — {s.mandatory_passed}/{s.mandatory_total} mandatory "
            f"checks passed, {s.mandatory_failures} failure(s).")
    w.heading(3, "Score by category")
    if s.categories:
        w.block(md_table(
            ["Category", "Passed", "Total", "Score", "Failed", "Warnings"],
            [[md_text(c.label), str(c.passed), str(c.total), fmt_pct(c.score), str(c.failed), str(c.warnings)]
             for c in s.categories],
        ))
    else:
        w.block("*No mandatory check.*")
    mandatory_ex = [e for e in s.exercises if e.required and not e.bonus]
    if mandatory_ex:
        w.heading(3, "Mandatory exercises")
        w.block(_exercise_table(mandatory_ex))
    w.heading(3, "Blocking issues")
    blocking = [c for c in sorted_issues(r.checks) if c.mandatory and not c.bonus and c.status in ("fail", "skipped")]
    if not blocking:
        w.block("No mandatory failure.")
        return
    items = []
    for c in blocking:
        loc = location_text(c)
        item = f"**{STATUS_LABELS[c.status]}**" + (f" ({c.severity})" if c.severity else "")
        item += f" {md_text(c.title)} — {md_text(c.message)}"
        if loc:
            item += f" ({md_code(loc)})"
        items.append(item)
    w.bullets(items)


def _optional(w: MarkdownWriter, r: AnalysisReport) -> None:
    optional_ids = {e.id for e in r.spec.exercises if not e.required and not e.bonus}
    optional_ex = [e for e in r.score.exercises if e.exercise_id in optional_ids]
    optional_files = [f for f in r.spec.structure.files if not f.required and not f.bonus]
    info = [c for c in r.checks if c.status == "info" and not c.bonus]
    if not (optional_ex or optional_files or info):
        w.block("*No optional requirement.*")
        return
    if optional_ex:
        w.heading(3, "Optional exercises")
        w.block(_exercise_table(optional_ex))
    if optional_files:
        w.heading(3, "Optional files")
        w.bullets([md_code(f.path) + (f" — {md_text(f.description)}" if f.description else "") for f in optional_files])
    if info:
        w.heading(3, "Informational checks")
        write_check_section(w, info, details=False)


def _structure(w: MarkdownWriter, r: AnalysisReport) -> None:
    anomalies = [t for t in r.tree if t.status in ("missing", "parasite", "misplaced", "extra")]
    if anomalies:
        w.block(md_table(["Path", "Kind", "Status", "Note"], [
            [md_code(t.path, table=True), t.kind, t.status, md_text(t.note or "")] for t in anomalies
        ]))
    write_check_section(w, _category_checks(r, "structure"))


def _runtime(w: MarkdownWriter, r: AnalysisReport) -> None:
    sb = r.sandbox
    rows = [
        ["Mode", "Docker (safe mode)" if sb.mode == "docker" else "Local (developer mode)"],
        ["Image", md_code(sb.image, table=True) if sb.image else "—"],
        ["Python", md_text(sb.python_version or "—")],
        ["Network", "enabled" if sb.network else "disabled"],
    ]
    if sb.limits:
        rows.append(["Limits", md_text(", ".join(f"{k}={v}" for k, v in sb.limits.items()))])
    w.block(md_table(["Sandbox", "Value"], rows))
    write_check_section(w, _category_checks(r, "runtime"))


def _category_section(title: str):
    def write(w: MarkdownWriter, r: AnalysisReport) -> None:
        write_check_section(w, _category_checks(r, _CATEGORY_SECTIONS[title]))
    return write


def _warnings(w: MarkdownWriter, r: AnalysisReport) -> None:
    general = list(r.pipeline_warnings) + list(r.sandbox.warnings)
    warned = [c for c in r.checks if c.status == "warning" and c.category != "heuristic_tests"]
    heuristic = [c for c in r.checks if c.category == "heuristic_tests"]
    if not (general or warned or heuristic):
        w.block("*No warning.*")
        return
    if general:
        w.bullets([md_text(x) for x in general])
    if warned:
        w.block("Warnings do not block the submission but deserve a look (details in their sections):")
        write_check_section(w, warned, details=False)
    if heuristic:
        w.heading(3, "Heuristic tests (not official)")
        w.block("Extra cases proposed by PréMoulinette. They are not requirements of the subject and never change "
                "the Readiness Score.")
        write_check_section(w, heuristic)


def _bonus(w: MarkdownWriter, r: AnalysisReport) -> None:
    s = r.score
    if s.bonus_completion is None:
        w.block("*This subject has no bonus exercise.*")
        return
    w.block(f"Bonus completion: **{fmt_pct(s.bonus_completion)}** ({s.bonus_passed}/{s.bonus_total} bonus exercises "
            "fully passing). Bonus items never block the submission.")
    w.block(_exercise_table([e for e in s.exercises if e.bonus]))
    write_check_section(w, [c for c in r.checks if c.bonus])


_SECTION_WRITERS = {
    "Repository": _repository,
    "Subject": _subject,
    "Mandatory requirements": _mandatory,
    "Optional requirements": _optional,
    "Structure": _structure,
    "Runtime analysis": _runtime,
    "Warnings": _warnings,
    "Bonus": _bonus,
    **{title: _category_section(title) for title in _CATEGORY_SECTIONS if title not in ("Structure", "Runtime analysis")},
}
