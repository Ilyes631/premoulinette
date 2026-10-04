from __future__ import annotations

import os
import stat
from pathlib import Path

from premoulinette.engine.snapshots import (
    find_git_root,
    new_snapshot_dir,
    prefix_git_paths,
    prune_snapshots,
    relative_posix,
)
from premoulinette.results.models import GitInfo


def test_new_snapshot_dirs_are_fresh_and_ordered(tmp_path: Path) -> None:
    a = new_snapshot_dir(tmp_path, "proj1")
    b = new_snapshot_dir(tmp_path, "proj1")
    assert not a.exists() and not b.exists()
    assert a.parent == b.parent == tmp_path / "proj1"
    assert a != b and a.name < b.name


def test_prune_keeps_recent_and_protected(tmp_path: Path) -> None:
    dirs = []
    for _ in range(5):
        d = new_snapshot_dir(tmp_path, "p")
        d.mkdir()
        (d / "f.txt").write_text("x")
        dirs.append(d)
    # read-only file (git objects on Windows) must not prevent deletion
    ro = dirs[1] / "ro.txt"
    ro.write_text("r")
    os.chmod(ro, stat.S_IREAD)
    outside = tmp_path / "keep-me"
    outside.mkdir()
    prune_snapshots(tmp_path, "p", keep=2, protect=[dirs[0]])
    remaining = sorted(p.name for p in (tmp_path / "p").iterdir())
    assert remaining == sorted([dirs[0].name, dirs[3].name, dirs[4].name])
    assert outside.is_dir()


def test_find_git_root_never_looks_upward(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()                       # e.g. the PréMoulinette checkout itself
    snapshot = tmp_path / "data" / "snap"
    (snapshot / "a" / "b").mkdir(parents=True)
    assert find_git_root(snapshot) is None
    (snapshot / "a" / "repo" / ".git").mkdir(parents=True)
    assert find_git_root(snapshot) == snapshot / "a" / "repo"
    (snapshot / ".git").mkdir()
    assert find_git_root(snapshot) == snapshot
    assert find_git_root(snapshot, preferred="a/repo") == snapshot / "a" / "repo"


def test_git_file_is_ignored(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text("gitdir: C:/somewhere/else")   # worktree pointer: never followed
    assert find_git_root(tmp_path) is None


def test_prefix_git_paths_and_relative_posix(tmp_path: Path) -> None:
    info = GitInfo(is_repo=True, modified=["a.py"], untracked=["b.py"], staged=["c.py"], ignored_required=["d.py"])
    out = prefix_git_paths(info, "repo")
    assert (out.modified, out.untracked, out.staged, out.ignored_required) == (
        ["repo/a.py"], ["repo/b.py"], ["repo/c.py"], ["repo/d.py"])
    assert prefix_git_paths(info, "") is info
    (tmp_path / "x" / "y").mkdir(parents=True)
    assert relative_posix(tmp_path / "x" / "y", tmp_path) == "x/y"
    assert relative_posix(tmp_path, tmp_path) == ""
