"""Snapshot directory management and small repository helpers used by the engine and the API.

Layout: ``<data>/snapshots/<project_id>/<timestamp>-<rand>/`` (one directory per ingestion).
Only directories under ``<data>/snapshots/<project_id>`` are ever deleted.
"""
from __future__ import annotations

import logging
import os
import shutil
import stat
import sys
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from premoulinette.results.models import GitInfo

log = logging.getLogger(__name__)

_GIT_SEARCH_SKIP = frozenset({"node_modules", ".venv", "venv", "env", "__pycache__", ".tox", ".mypy_cache"})


def new_snapshot_dir(snapshots_root: Path, project_id: str) -> Path:
    """Return a fresh, not-yet-existing directory path for a new snapshot of ``project_id``."""
    base = snapshots_root / _safe_component(project_id)
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    return base / f"{stamp}-{uuid.uuid4().hex[:6]}"


def prune_snapshots(snapshots_root: Path, project_id: str, keep: int, protect: Iterable[Path] = ()) -> None:
    """Delete the oldest snapshot directories of a project, keeping the ``keep`` most recent."""
    base = (snapshots_root / _safe_component(project_id)).resolve()
    if not base.is_dir():
        return
    protected = {Path(p).resolve() for p in protect}
    entries = sorted((p for p in base.iterdir() if p.is_dir() and not p.is_symlink()), key=lambda p: p.name)
    for old in entries[: max(0, len(entries) - keep)]:
        resolved = old.resolve()
        if resolved in protected or any(p.is_relative_to(resolved) for p in protected):
            continue
        if not resolved.is_relative_to(base):
            continue
        remove_tree(resolved)


def remove_tree(path: Path) -> None:
    """``rmtree`` that also removes read-only files (git objects on Windows); never raises."""

    def _retry(func: Any, target: str, _exc: Any) -> None:
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            log.warning("Could not remove %s", target)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_retry)
    else:  # pragma: no cover - Python 3.11
        shutil.rmtree(path, onerror=_retry)


def find_git_root(root: Path, preferred: str = "", max_depth: int = 3) -> Path | None:
    """Directory containing a ``.git`` *directory*, searched downward from ``root`` only.

    Never looks above ``root``: snapshots live inside the PréMoulinette data dir, which may itself
    be inside a git checkout that must not be mistaken for the student's repository.
    """
    candidates = ([root / preferred] if preferred else []) + [root]
    for c in candidates:
        if (c / ".git").is_dir():
            return c
    frontier = [root]
    for _ in range(max_depth):
        next_frontier: list[Path] = []
        for d in frontier:
            try:
                children = sorted(d.iterdir(), key=lambda p: p.name)
            except OSError:
                continue
            for child in children:
                if child.name in _GIT_SEARCH_SKIP or child.name == ".git" or child.is_symlink() or not child.is_dir():
                    continue
                if (child / ".git").is_dir():
                    return child
                next_frontier.append(child)
        frontier = next_frontier
    return None


def prefix_git_paths(info: GitInfo, prefix: str) -> GitInfo:
    """Express git paths (relative to the git root) relative to the snapshot root instead."""
    if not prefix:
        return info

    def p(paths: list[str]) -> list[str]:
        return [f"{prefix}/{x}" for x in paths]

    return info.model_copy(update={
        "modified": p(info.modified), "untracked": p(info.untracked), "staged": p(info.staged),
        "ignored_required": p(info.ignored_required),
    })


def relative_posix(path: Path, root: Path) -> str:
    rel = path.resolve().relative_to(root.resolve()).as_posix()
    return "" if rel == "." else rel


def count_python_files(tree: Iterable[Any]) -> int:
    return sum(1 for e in tree if getattr(e, "kind", None) == "file" and str(e.path).endswith(".py"))


def _safe_component(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
    if not cleaned or cleaned.strip("_") == "":
        raise ValueError(f"Invalid project id for a snapshot directory: {name!r}")
    return cleaned
