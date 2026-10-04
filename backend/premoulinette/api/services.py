"""Functions of other modules used by the API, resolved lazily (tests swap them with fakes)."""
from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Any

from premoulinette.engine.deps import AnyFn, lazy

log = logging.getLogger(__name__)


def validate_spec_default(spec: Any) -> list[Any]:
    """``premoulinette.spec.validate.validate_spec`` when available, else no issues.

    ``spec/validate.py`` has no documented signature in ARCHITECTURE.md; it is optional here.
    """
    try:
        module = importlib.import_module("premoulinette.spec.validate")
    except ModuleNotFoundError as exc:
        if exc.name != "premoulinette.spec.validate":
            raise
        return []
    fn = getattr(module, "validate_spec", None)
    if fn is None:
        log.debug("premoulinette.spec.validate has no validate_spec(); skipping validation")
        return []
    return list(fn(spec))


@dataclass(frozen=True)
class ApiServices:
    parse_subject: AnyFn = lazy("premoulinette.subject.pipeline", "parse_subject")
    validate_spec: AnyFn = validate_spec_default
    generate_tests: AnyFn = lazy("premoulinette.testgen.generate", "generate_tests")
    snapshot_from_path: AnyFn = lazy("premoulinette.project.ingest", "snapshot_from_path")
    snapshot_from_zip: AnyFn = lazy("premoulinette.project.ingest", "snapshot_from_zip")
    snapshot_from_upload: AnyFn = lazy("premoulinette.project.ingest", "snapshot_from_upload")
    list_tree: AnyFn = lazy("premoulinette.project.tree", "list_tree")
    read_git_info: AnyFn = lazy("premoulinette.project.git_info", "read_git_info")
    detect_docker: AnyFn = lazy("premoulinette.sandbox.detect", "detect_docker")
    pull_image: AnyFn = lazy("premoulinette.sandbox.detect", "pull_image")
    explain: AnyFn = lazy("premoulinette.explain.templates", "explain")
    how_to_fix: AnyFn = lazy("premoulinette.explain.templates", "how_to_fix")
    expected_behavior: AnyFn = lazy("premoulinette.explain.templates", "expected_behavior")
    explain_with_ai: AnyFn = lazy("premoulinette.explain.ai", "explain_with_ai")
    build_ai_payload: AnyFn = lazy("premoulinette.explain.ai", "build_payload")
    to_json: AnyFn = lazy("premoulinette.report.export", "to_json")
    to_markdown: AnyFn = lazy("premoulinette.report.export", "to_markdown")
    to_html: AnyFn = lazy("premoulinette.report.export", "to_html")
    run_analysis: AnyFn = lazy("premoulinette.engine.pipeline", "run_analysis")
