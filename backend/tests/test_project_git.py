"""git_info.read_git_info (hardened, read-only) + checks_structure.check_git on real temporary repositories."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from premoulinette.languages.python.checks_structure import check_git
from premoulinette.project.git_info import parse_status_v2, read_git_info, redact_url
from premoulinette.project.ingest import snapshot_from_path
from premoulinette.results.models import GitInfo
from premoulinette.spec.models import ExerciseSpec, FileRequirement, PracticalSpec, StructureSpec

GIT = shutil.which("git")
needs_git = pytest.mark.skipif(GIT is None, reason="git is not installed")


def git(repo: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "GIT_CEILING_DIRECTORIES": str(repo.parent)})
    proc = subprocess.run([GIT, "-c", "core.autocrlf=false", "-c", "init.defaultBranch=main",
                           "-c", "commit.gpgsign=false", *args],
                          cwd=repo, env=env, capture_output=True, text=True, check=True)
    return proc.stdout


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode())


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "student"
    root.mkdir()
    git(root, "init", "-q")
    write(root, ".gitignore", "__pycache__/\nsecret_*.py\n")
    write(root, "ex/kelvin.py", "def to_kelvin(c):\n    return c + 273.15\n")
    write(root, "ex/speed.py", "def is_safe(s, l):\n    return s <= l\n")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "first commit")
    git(root, "tag", "submit-1")
    git(root, "remote", "add", "origin", "https://alice:hunter2@example.com/alice/tp.git")
    # Working tree changes after the commit:
    write(root, "ex/kelvin.py", "def to_kelvin(c):\n    return c + 273\n")          # modified
    write(root, "ex/grade.py", "def grade(v):\n    return 'ok'\n")                     # untracked (required)
    write(root, "ex/secret_bonus.py", "x = 1\n")                                       # ignored (required bonus)
    write(root, "ex/__pycache__/kelvin.cpython-312.pyc", "pyc")                        # ignored parasite
    return root


def spec() -> PracticalSpec:
    return PracticalSpec(
        structure=StructureSpec(files=[FileRequirement(path=".gitignore")], require_gitignore=True),
        exercises=[
            ExerciseSpec(id="kelvin", title="Kelvin", file_path="ex/kelvin.py"),
            ExerciseSpec(id="speed", title="Speed", file_path="ex/speed.py"),
            ExerciseSpec(id="grade", title="Grade", file_path="ex/grade.py"),
            ExerciseSpec(id="secret", title="Secret", file_path="ex/secret_bonus.py", bonus=True),
            ExerciseSpec(id="later", title="Later", file_path="ex/later.py"),
        ],
    )


def test_parse_status_v2() -> None:
    raw = (b"# branch.oid abcdef0123\x00# branch.head main\x00"
           b"1 .M N... 100644 100644 100644 aaa bbb ex/kelvin.py\x00"
           b"1 A. N... 000000 100644 100644 000 ccc new file.py\x00"
           b"2 R. N... 100644 100644 100644 aaa aaa R100 renamed.py\x00old.py\x00"
           b"u UU N... 100644 100644 100644 100644 a b c conflict.py\x00"
           b"? untracked dir/file.py\x00")
    out = parse_status_v2(raw)
    assert out["oid"] == "abcdef0123" and out["head"] == "main"
    assert out["modified"] == ["ex/kelvin.py", "conflict.py"]
    assert out["staged"] == ["new file.py", "renamed.py", "conflict.py"]
    assert out["untracked"] == ["untracked dir/file.py"]
    assert parse_status_v2(b"# branch.oid (initial)\x00# branch.head (detached)\x00")["oid"] is None


def test_redact_url() -> None:
    assert redact_url("https://alice:hunter2@example.com/x.git") == "https://example.com/x.git"
    assert redact_url("git@github.com:alice/x.git") == "git@github.com:alice/x.git"
    assert redact_url(None) is None


def test_not_a_repository(tmp_path: Path) -> None:
    assert read_git_info(tmp_path, []) == GitInfo(is_repo=False)


@needs_git
def test_read_git_info_on_snapshot(repo: Path, tmp_path: Path) -> None:
    snap = snapshot_from_path(repo, tmp_path / "snap")
    required = ["ex/kelvin.py", "ex/speed.py", "ex/grade.py", "ex/secret_bonus.py", "ex/later.py", ".gitignore"]
    info = read_git_info(snap.root, required)
    assert info.error is None, info.error
    assert info.is_repo and info.branch == "main"
    assert info.head and len(info.head) >= 7
    assert info.last_commit_message == "first commit" and info.last_commit_date
    assert info.modified == ["ex/kelvin.py"]
    assert info.untracked == ["ex/grade.py"]                 # ignored files are not untracked
    assert info.staged == []
    assert info.dirty is True
    assert info.ignored_required == ["ex/secret_bonus.py"]   # tracked / non-ignored ones are not listed
    assert info.tags == ["submit-1"]
    assert info.remote_url == "https://example.com/alice/tp.git"   # credentials never surfaced
    # Read only: the snapshot index was not rewritten and nothing was created in the student's repo.
    assert not (snap.root / ".git" / "index.lock").exists()


@needs_git
def test_check_git_reports_untracked_ignored_dirty(repo: Path, tmp_path: Path) -> None:
    snap = snapshot_from_path(repo, tmp_path / "snap")
    s = spec()
    file_map = {".gitignore": ".gitignore", "ex/kelvin.py": "ex/kelvin.py", "ex/speed.py": "ex/speed.py",
                "ex/grade.py": "ex/grade.py", "ex/secret_bonus.py": "ex/secret_bonus.py", "ex/later.py": None}
    info = read_git_info(snap.root, [p for p in file_map.values() if p])
    checks = {c.id: c for c in check_git(s, info, file_map)}

    untracked = checks["git:untracked:ex/grade.py"]
    assert (untracked.status, untracked.severity, untracked.mandatory) == ("fail", "major", True)
    assert untracked.diagnosis == "untracked_file" and untracked.category == "git"
    assert "not tracked by git" in untracked.message and untracked.exercise_id == "grade"

    ignored = checks["git:ignored:ex/secret_bonus.py"]
    assert ignored.diagnosis == "ignored_file"
    assert (ignored.status, ignored.mandatory, ignored.bonus) == ("bonus", False, True)   # bonus never blocks
    assert "git:untracked:ex/secret_bonus.py" not in checks

    for tracked in ("ex/kelvin.py", "ex/speed.py", ".gitignore"):
        assert checks[f"git:untracked:{tracked}"].status == "pass"
    assert not any(k.endswith("ex/later.py") for k in checks)            # missing files: structure's job

    dirty = checks["git:dirty"]
    assert (dirty.status, dirty.severity, dirty.mandatory, dirty.diagnosis) == ("warning", "minor", False, "dirty_tree")
    assert dirty.evidence and "ex/kelvin.py" in dirty.evidence.details["modified"]


@needs_git
def test_required_file_ignored_is_critical(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    git(root, "init", "-q")
    write(root, ".gitignore", "*.py\n")
    write(root, "main.py", "print(1)\n")
    git(root, "add", ".gitignore")
    git(root, "commit", "-q", "-m", "init")
    info = read_git_info(root, ["main.py"])
    assert info.ignored_required == ["main.py"]
    s = PracticalSpec(exercises=[ExerciseSpec(id="main", title="Main", file_path="main.py")])
    [ignored, dirty] = check_git(s, info, {"main.py": "main.py"})
    assert (ignored.id, ignored.status, ignored.severity, ignored.mandatory) == ("git:ignored:main.py", "fail", "critical", True)
    assert dirty.id == "git:dirty" and dirty.status == "pass"            # ignored files do not dirty the tree


@needs_git
def test_clean_repo_and_no_commit_repo(tmp_path: Path) -> None:
    root = tmp_path / "clean"
    root.mkdir()
    git(root, "init", "-q")
    write(root, "main.py", "print(1)\n")
    s = PracticalSpec(exercises=[ExerciseSpec(id="main", title="Main", file_path="main.py")])

    git(root, "add", "main.py")                                           # staged, never committed
    info = read_git_info(root, ["main.py"])
    assert info.head is None and info.staged == ["main.py"] and info.dirty
    no_commit = {c.id: c for c in check_git(s, info, {"main.py": "main.py"})}["git:untracked:main.py"]
    assert no_commit.status == "fail" and "no commit yet" in no_commit.message

    git(root, "commit", "-q", "-m", "init")
    info = read_git_info(root, ["main.py"])
    assert not info.dirty and info.modified == info.untracked == info.staged == []
    assert [c.status for c in check_git(s, info, {"main.py": "main.py"})] == ["pass", "pass"]


@needs_git
def test_crlf_checkout_with_autocrlf_is_not_reported_modified(tmp_path: Path) -> None:
    """A fresh copy invalidates the index stat cache: git re-hashes, line-ending settings must be kept."""
    root = tmp_path / "crlf"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "core.autocrlf", "true")
    (root / "main.py").write_bytes(b"print(1)\r\nprint(2)\r\n")
    git(root, "-c", "core.autocrlf=true", "add", ".")
    git(root, "-c", "core.autocrlf=true", "commit", "-q", "-m", "init")
    snap = snapshot_from_path(root, tmp_path / "snap")
    assert "autocrlf = true" in (snap.root / ".git" / "config").read_text()
    info = read_git_info(snap.root, ["main.py"])
    assert info.error is None, info.error
    assert info.modified == [] and not info.dirty


@needs_git
def test_case_only_rename_shows_as_untracked(tmp_path: Path) -> None:
    """The grader is case-sensitive: a file committed as Kelvin.py and renamed on disk is not submitted."""
    root = tmp_path / "case"
    root.mkdir()
    git(root, "init", "-q")
    write(root, "Kelvin.py", "x = 1\n")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "init")
    (root / "Kelvin.py").rename(root / "tmp.py")
    (root / "tmp.py").rename(root / "kelvin.py")
    info = read_git_info(root, ["kelvin.py"])
    assert info.error is None
    assert "kelvin.py" in info.untracked


@needs_git
def test_hardened_flags_neutralize_fsmonitor_and_hooks(tmp_path: Path) -> None:
    root = tmp_path / "evil"
    root.mkdir()
    git(root, "init", "-q")
    write(root, "a.py", "x = 1\n")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "init")
    marker = tmp_path / "pwned.txt"
    script = root / ".git" / "evil.sh"
    script.write_text(f"#!/bin/sh\necho pwned > '{marker.as_posix()}'\n", newline="\n")
    os.chmod(script, 0o755)
    hook = root / ".git" / "hooks" / "post-index-change"
    hook.write_text(f"#!/bin/sh\necho hook > '{marker.as_posix()}'\n", newline="\n")
    os.chmod(hook, 0o755)
    git(root, "config", "core.fsmonitor", script.as_posix())
    write(root, "a.py", "x = 2\n")

    # Positive control: plain git really runs the fsmonitor command.
    subprocess.run([GIT, "status", "--porcelain"], cwd=root, capture_output=True)
    if not marker.exists():
        pytest.skip("this git build does not execute fsmonitor commands; nothing to prove")
    marker.unlink()

    info = read_git_info(root, ["a.py"])          # unsanitized repo on purpose: the flags alone must protect
    assert info.error is None, info.error
    assert info.modified == ["a.py"]
    assert not marker.exists()
