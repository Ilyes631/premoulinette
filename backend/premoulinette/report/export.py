"""Report export (ARCHITECTURE.md, ``report/export.py``): JSON, Markdown and standalone HTML.

All formats state that the Readiness Score is not an official grade, label every requirement with its
provenance, and make invisible characters visible in output differences.
"""
from __future__ import annotations

from premoulinette.report.render_html import render_html
from premoulinette.report.render_md import render_markdown
from premoulinette.results.models import AnalysisReport

__all__ = ["to_json", "to_markdown", "to_html"]


def to_json(report: AnalysisReport) -> str:
    return report.model_dump_json(indent=2)


def to_markdown(report: AnalysisReport) -> str:
    """Sections: Repository, Subject, Mandatory requirements, Optional requirements, Structure, Functions,
    Scripts, Constraints, Static analysis, Runtime analysis, Known tests, Derived tests, Warnings, Bonus."""
    return render_markdown(report)


def to_html(report: AnalysisReport) -> str:
    """Single self-contained file: inline CSS, light/dark, printable, every string HTML-escaped."""
    return render_html(report)
