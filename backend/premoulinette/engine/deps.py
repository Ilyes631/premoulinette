"""Collaborators of the analysis pipeline, resolved lazily from their documented module paths.

The pipeline only talks to other modules through :class:`EngineDeps`. Production code uses
:func:`default_deps`; unit tests build an ``EngineDeps`` with fakes (``dataclasses.replace``).
Lazy resolution keeps ``premoulinette.engine`` importable even when an optional module is broken,
and the error surfaces where the function is actually needed.
"""
from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

AnyFn = Callable[..., Any]


def lazy(module: str, attr: str) -> AnyFn:
    """Return a proxy calling ``module.attr`` (imported on first call)."""

    def proxy(*args: Any, **kwargs: Any) -> Any:
        return getattr(importlib.import_module(module), attr)(*args, **kwargs)

    proxy.__name__ = attr
    proxy.__qualname__ = f"lazy({module}.{attr})"
    return proxy


_PY = "premoulinette.languages.python"


@dataclass(frozen=True)
class EngineDeps:
    # project/
    snapshot_from_path: AnyFn = lazy("premoulinette.project.ingest", "snapshot_from_path")
    detect_root: AnyFn = lazy("premoulinette.project.root_detect", "detect_root")
    resolve: AnyFn = lazy("premoulinette.project.root_detect", "resolve")
    list_tree: AnyFn = lazy("premoulinette.project.tree", "list_tree")
    read_git_info: AnyFn = lazy("premoulinette.project.git_info", "read_git_info")
    # languages/python (static)
    analyze_project: AnyFn = lazy(f"{_PY}.static", "analyze_project")
    check_structure: AnyFn = lazy(f"{_PY}.checks_structure", "check_structure")
    check_git: AnyFn = lazy(f"{_PY}.checks_structure", "check_git")
    check_syntax: AnyFn = lazy(f"{_PY}.checks_static", "check_syntax")
    check_functions: AnyFn = lazy(f"{_PY}.checks_static", "check_functions")
    check_constraints: AnyFn = lazy(f"{_PY}.checks_static", "check_constraints")
    check_import_side_effects: AnyFn = lazy(f"{_PY}.checks_static", "check_import_side_effects")
    # tests, sandbox, evaluation
    generate_tests: AnyFn = lazy("premoulinette.testgen.generate", "generate_tests")
    detect_docker: AnyFn = lazy("premoulinette.sandbox.detect", "detect_docker")
    get_sandbox: AnyFn = lazy("premoulinette.sandbox.base", "get_sandbox")
    eval_context: AnyFn = lazy("premoulinette.compare.evaluate", "EvalContext")
    evaluate_function: AnyFn = lazy("premoulinette.compare.evaluate", "evaluate_function")
    evaluate_script: AnyFn = lazy("premoulinette.compare.evaluate", "evaluate_script")
    evaluate_import: AnyFn = lazy("premoulinette.compare.evaluate", "evaluate_import")
    # fixes + scoring
    attach_fixes: AnyFn = lazy("premoulinette.explain.fixes", "attach_fixes")
    compute_score: AnyFn = lazy("premoulinette.scoring.score", "compute_score")


def default_deps() -> EngineDeps:
    return EngineDeps()
