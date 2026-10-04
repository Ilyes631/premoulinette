"""Sandbox protocol, factory and the filesystem helpers shared by the Docker and local sandboxes.

A sandbox runs a :class:`RunPlan` with the stdlib-only harness
(``languages/python/harness/run_plan.py`` + ``child.py``) and returns :class:`RunResults`
(one result per planned job, ``harness_error`` when the harness itself failed).
Result parsing, budgets and cleanup live in :mod:`premoulinette.sandbox.common`.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from premoulinette.results.models import SandboxInfo
from premoulinette.runner.models import RunPlan, RunResults
from premoulinette.sandbox.common import HARNESS_DIR, HARNESS_FILES

SandboxMode = Literal["docker", "local"]

# never copied into the sandbox: VCS internals and stale bytecode (a fresh clone has neither in a usable state)
COPY_IGNORED_DIRS = frozenset({".git", "__pycache__"})


@runtime_checkable
class Sandbox(Protocol):
    mode: SandboxMode

    def run(self, plan: RunPlan, project_root: Path) -> RunResults: ...

    def info(self) -> SandboxInfo: ...


def get_sandbox(mode: SandboxMode, *, image: str = "python:3.12-slim") -> Sandbox:
    """Factory: ``"docker"`` (safe mode) or ``"local"`` (developer mode)."""
    if mode == "docker":
        from premoulinette.sandbox.docker import DockerSandbox

        return DockerSandbox(image=image)
    if mode == "local":
        from premoulinette.sandbox.local import LocalSandbox

        return LocalSandbox()
    raise ValueError(f"unknown sandbox mode: {mode!r}")


# ---------------------------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------------------------


def copy_project(src: Path, dest: Path) -> None:
    """Copy a project snapshot into ``dest`` (created), skipping ``.git``, ``__pycache__`` and symlinks."""

    def ignore(directory: str, names: list[str]) -> set[str]:
        skipped: set[str] = set()
        for name in names:
            if name in COPY_IGNORED_DIRS:
                skipped.add(name)
                continue
            try:
                if os.path.islink(os.path.join(directory, name)):
                    skipped.add(name)  # never follow links out of the snapshot
            except OSError:
                skipped.add(name)
        return skipped

    shutil.copytree(src, dest, ignore=ignore, symlinks=False)


def copy_harness(dest: Path) -> Path:
    """Copy the harness scripts into ``dest`` (created) and return it."""
    dest.mkdir(parents=True, exist_ok=True)
    for name in HARNESS_FILES:
        shutil.copyfile(HARNESS_DIR / name, dest / name)
    return dest


def write_plan(plan: RunPlan, dest_dir: Path) -> Path:
    """Write ``plan.json`` into ``dest_dir`` (created) and return its path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "plan.json"
    path.write_text(plan.model_dump_json(), encoding="utf-8")
    return path


def make_world_readable(root: Path) -> None:
    """POSIX: let an unprivileged container user (65534) read a directory tree (no-op on Windows)."""
    if os.name == "nt":
        return
    for dirpath, dirnames, filenames in os.walk(root):
        try:
            os.chmod(dirpath, 0o755)
        except OSError:
            pass
        for name in filenames:
            try:
                os.chmod(os.path.join(dirpath, name), 0o644)
            except OSError:
                pass
