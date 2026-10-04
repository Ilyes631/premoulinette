"""Report export tests: JSON round-trip, Markdown sections/labels/diffs, standalone and escaped HTML."""
from __future__ import annotations

import json
import re

import pytest

from premoulinette.report.common import GENERAL_GROUP, group_issues_by_file
from premoulinette.report.export import to_html, to_json, to_markdown
from premoulinette.report.md_utils import md_code, md_text
from premoulinette.report.render_md import SECTIONS
from premoulinette.results.models import AnalysisReport, CheckResult, DiffLine, DiffSegment, Evidence, TextDiff
from report_factory import P_FIXME, hostile_check, make_report, passing_checks

DISCLAIMER_FRAGMENT = "Readiness Score is not an official grade"


@pytest.fixture(scope="module")
def buggy() -> AnalysisReport:
    return make_report()


@pytest.fixture(scope="module")
def hostile() -> AnalysisReport:
    return make_report(checks=passing_checks() + [hostile_check()])


# ---- JSON -----------------------------------------------------------------------------------------

def test_json_round_trips(buggy: AnalysisReport) -> None:
    text = to_json(buggy)
    assert text.startswith("{\n  ")  # indent=2
    assert AnalysisReport.model_validate_json(text) == buggy
    assert json.loads(text)["score"]["verdict"] == "not_ready"


# ---- Markdown -------------------------------------------------------------------------------------

def test_markdown_has_all_sections_in_order(buggy: AnalysisReport) -> None:
    md = to_markdown(buggy)
    assert SECTIONS == (
        "Repository", "Subject", "Mandatory requirements", "Optional requirements", "Structure", "Functions",
        "Scripts", "Constraints", "Static analysis", "Runtime analysis", "Known tests", "Derived tests",
        "Warnings", "Bonus",
    )
    positions = [md.index(f"\n## {title}\n") for title in SECTIONS]
    assert positions == sorted(positions)


def test_markdown_header_verdict_and_disclaimer(buggy: AnalysisReport) -> None:
    md = to_markdown(buggy)
    assert md.startswith("# PréMoulinette report — TP 1 — MysteryInc: First Launch\n")
    assert "**DO NOT SUBMIT YET**" in md
    assert f"Readiness Score: **{buggy.score.readiness:.1f}%**" in md
    assert DISCLAIMER_FRAGMENT in md


def test_markdown_provenance_labels(buggy: AnalysisReport) -> None:
    md = to_markdown(buggy)
    for label in ("Explicit requirement", "Derived test", "Heuristic (not official)"):
        assert label in md
    ai = make_report(spec=None, checks=[CheckResult(
        id="test:is_safe#ai1", category="explicit_tests", status="pass", title="AI case", message="ok",
        origin={"provenance": "ai_extracted", "confidence": 0.5})])
    assert "AI-extracted (needs review)" in to_markdown(ai)


def test_markdown_diff_shows_invisible_characters(buggy: AnalysisReport) -> None:
    md = to_markdown(buggy)
    assert "```diff\n" in md
    assert "- Fuel·after·the·trip:·280↵" in md
    assert "+ Fuel·after·trip:·280↵" in md
    # Missing trailing space of the prompt is visible on the expected side only.
    assert "- Set·a·trap·or·collect·evidence?·(trap/evidence)·\n+ Set·a·trap·or·collect·evidence?·(trap/evidence)\n" in md
    assert "missing trailing space" in md


def test_markdown_shows_values_exception_and_fix(buggy: AnalysisReport) -> None:
    md = to_markdown(buggy)
    assert "Expected: `True` (bool)" in md
    assert "Actual: `'True'` (str)" in md
    assert "ZeroDivisionError" in md
    assert "+        return True" in md            # fix patch
    assert "Not run: blocked by" in md             # skipped/blocked bonus checks


def test_markdown_escapes_html_outside_code(hostile: AnalysisReport) -> None:
    md = to_markdown(hostile)
    outside_code = re.sub(r"(`{3,}).*?\n\1", "", md, flags=re.S)   # drop fenced blocks
    outside_code = re.sub(r"(`+).+?\1", "", outside_code)           # drop code spans
    assert not re.search(r"(?<!\\)<", outside_code), "unescaped '<' outside code would be raw HTML"
    assert r"\<script\>" in md and r"\<img src=x onerror=alert(1)\>" in md


def test_md_helpers() -> None:
    assert md_text("a|b <x> *y* snake_case _lead") == r"a\|b \<x\> \*y\* snake_case \_lead"
    assert md_code("x`y") == "``x`y``"
    assert md_code("`x") == "`` `x ``"
    assert md_code("a|b", table=True) == r"`a\|b`"
    assert md_code("") == "*(empty)*"
    assert md_text("line1\nline2") == "line1 ↵ line2"


def test_markdown_ready_report() -> None:
    md = to_markdown(make_report(variant="fixed"))
    assert "**READY TO SUBMIT**" in md
    assert "No mandatory failure." in md
    assert "Hidden grader tests may still exist" in md


# ---- HTML -----------------------------------------------------------------------------------------

def test_html_is_standalone_and_themable(buggy: AnalysisReport) -> None:
    page = to_html(buggy)
    assert page.startswith("<!DOCTYPE html>")
    assert '<meta charset="utf-8">' in page
    assert "<style>" in page and "prefers-color-scheme: dark" in page and "@media print" in page
    assert "Content-Security-Policy" in page
    assert not re.search(r"<(script|link|img|iframe)\b", page, flags=re.I)
    assert not re.search(r"(src|href)\s*=", page, flags=re.I)
    assert "DO NOT SUBMIT YET" in page and "verdict-not_ready" in page
    assert DISCLAIMER_FRAGMENT in page
    assert 'class="bar-fill' in page


def test_html_groups_issues_by_file_with_diff_segments(buggy: AnalysisReport) -> None:
    page = to_html(buggy)
    section = page[page.index("<h2>Issues by file</h2>"):]
    assert "<code>MysteryInc/FirstLaunch/launch_sequence.py</code>" in section
    # Changed characters are wrapped in coloured marks, spaces rendered as dimmed middle dots.
    assert '<mark class="hl-del">he<span class="ws">·</span>t</mark>' in section
    assert '<span class="ws">·</span>' in section
    assert "printed by MysteryInc/FirstLaunch/launch_sequence.py:21" in section
    assert "Heuristic (not official)" in page


def test_issue_groups_follow_spec_file_order(buggy: AnalysisReport) -> None:
    groups = group_issues_by_file(buggy)
    keys = [k for k, _ in groups]
    spec_paths = [f.path for f in buggy.spec.expected_files()]
    spec_keys = [k for k in keys if k in spec_paths]
    assert spec_keys == sorted(spec_keys, key=spec_paths.index)
    assert keys[: len(spec_keys)] == spec_keys            # spec files first
    assert keys[-1] == GENERAL_GROUP                       # git:dirty has no file
    fixme = dict(groups)[P_FIXME]
    assert f"structure:file:{P_FIXME}" in [c.id for c in fixme]   # wrong-case issue listed with its spec file
    assert [c.status for c in fixme][0] == "fail" and fixme[0].severity == "critical"  # most severe first


def test_html_escapes_every_student_string(hostile: AnalysisReport) -> None:
    page = to_html(hostile)
    assert "<script" not in page.lower()
    assert "<img" not in page.lower()
    assert "<b>evil" not in page and "<b>Boom" not in page
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in page
    assert "&lt;b&gt;evil&lt;/b&gt;.py" in page


def test_html_escapes_subject_and_project_names() -> None:
    report = make_report(variant="fixed")
    report = report.model_copy(update={
        "subject": report.subject.model_copy(update={"title": "<script>alert(1)</script>"}),
        "project": report.project.model_copy(update={"name": '"><img src=x>'}),
    })
    page = to_html(report)
    assert "<script" not in page.lower() and "<img" not in page.lower()
    assert "<title>PréMoulinette report — &lt;script&gt;alert(1)&lt;/script&gt;</title>" in page


def test_html_ready_banner() -> None:
    page = to_html(make_report(variant="fixed"))
    assert "READY TO SUBMIT" in page and "verdict-ready" in page
    assert "No issue found." in page


def test_diff_without_line_alignment_falls_back_to_full_texts() -> None:
    check = CheckResult(
        id="test:x#session1", category="output", status="fail", severity="major", title="Output differs",
        message="differs", evidence=Evidence(stdout_diff=TextDiff(expected="a b\n", actual="a  b", equal=False)),
    )
    report = make_report(checks=passing_checks() + [check])
    md = to_markdown(report)
    assert "- a·b↵\n+ a··b\n" in md
    assert "a<span class=\"ws\">··</span>b" in to_html(report)


def test_inconsistent_segments_highlight_whole_line() -> None:
    line = DiffLine(op="changed", expected_lineno=1, actual_lineno=1, expected="abc", actual="abd",
                    segments=[DiffSegment(op="equal", expected="zz", actual="zz")])
    check = CheckResult(
        id="test:x#session2", category="output", status="fail", severity="minor", title="Output differs",
        message="differs", evidence=Evidence(stdout_diff=TextDiff(expected="abc", actual="abd", equal=False,
                                                                  lines=[line])),
    )
    page = to_html(make_report(checks=passing_checks() + [check]))
    assert '<mark class="hl-del">abc</mark>' in page and '<mark class="hl-ins">abd</mark>' in page
