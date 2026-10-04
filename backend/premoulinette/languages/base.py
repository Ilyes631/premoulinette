"""Language plugin protocol.

The engine only needs a handful of operations per language. Python is the only implementation today;
a new language provides the same functions (structure + git checks are language-agnostic enough to be
reused as-is). Implementations are resolved lazily so importing this module stays cheap.
"""
from __future__ import annotations

import importlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from premoulinette.project.root_detect import RootDetection
from premoulinette.results.models import CheckResult, GitInfo, TreeEntry
from premoulinette.spec.models import PracticalSpec

FileMap = Mapping[str, str | None]


@runtime_checkable
class LanguagePlugin(Protocol):
    name: str                         # spec.language value, e.g. "python"
    source_extensions: tuple[str, ...]

    def check_structure(
        self, spec: PracticalSpec, snapshot_root: Path, det: RootDetection, tree: list[TreeEntry]
    ) -> tuple[list[CheckResult], list[TreeEntry], dict[str, str | None]]: ...

    def check_git(self, spec: PracticalSpec, git: GitInfo, file_map: FileMap) -> list[CheckResult]: ...

    def analyze_project(self, root: Path, files: list[str]) -> dict[str, Any]: ...

    def check_syntax(self, modules: dict[str, Any], file_map: FileMap, spec: PracticalSpec) -> list[CheckResult]: ...

    def check_functions(self, spec: PracticalSpec, modules: dict[str, Any], file_map: FileMap) -> list[CheckResult]: ...

    def check_constraints(self, spec: PracticalSpec, modules: dict[str, Any], file_map: FileMap) -> list[CheckResult]: ...

    def check_import_side_effects(
        self, spec: PracticalSpec, modules: dict[str, Any], file_map: FileMap
    ) -> list[CheckResult]: ...


class _ModulePlugin:
    """Plugin whose operations are plain functions of a few modules, imported on first use."""

    _OPERATIONS = {
        "check_structure": "checks_structure",
        "check_git": "checks_structure",
        "analyze_project": "static",
        "check_syntax": "checks_static",
        "check_functions": "checks_static",
        "check_constraints": "checks_static",
        "check_import_side_effects": "checks_static",
    }

    def __init__(self, name: str, package: str, source_extensions: tuple[str, ...]) -> None:
        self.name = name
        self.package = package
        self.source_extensions = source_extensions

    def __getattr__(self, attr: str) -> Any:
        module = self._OPERATIONS.get(attr)
        if module is None:
            raise AttributeError(attr)
        return getattr(importlib.import_module(f"{self.package}.{module}"), attr)

    def __repr__(self) -> str:
        return f"<LanguagePlugin {self.name}>"


_PLUGINS: dict[str, LanguagePlugin] = {
    "python": _ModulePlugin("python", "premoulinette.languages.python", (".py",)),  # type: ignore[dict-item]
}


def supported_languages() -> list[str]:
    return sorted(_PLUGINS)


def get_plugin(language: str) -> LanguagePlugin:
    """Plugin for ``language`` (case-insensitive, e.g. ``"Python"``, ``"python3"``)."""
    key = (language or "python").strip().lower()
    if key.startswith("python"):
        key = "python"
    try:
        return _PLUGINS[key]
    except KeyError:
        raise ValueError(f"Unsupported language {language!r} (supported: {', '.join(supported_languages())})") from None
