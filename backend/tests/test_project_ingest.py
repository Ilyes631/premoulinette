"""Project ingestion: path / zip / upload snapshots, limits, zip-slip, bombs, .git sanitization."""
from __future__ import annotations

import io
import os
import stat
import struct
import zipfile
from pathlib import Path

import pytest

from premoulinette.project import ingest
from premoulinette.project.ingest import (
    clean_member_path,
    sanitize_git_dir,
    snapshot_from_path,
    snapshot_from_upload,
    snapshot_from_zip,
)

from conftest import DEMO_DIR


def make_zip(entries: list[tuple[str, bytes]], *, compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=compression) as zf:
        for name, data in entries:
            zf.writestr(zipfile.ZipInfo(name), data, compress_type=compression)
    return buf.getvalue()


def files_under(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


# ---------------------------------------------------------------------------------------------
# path validation
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["../evil.py", "a/../../evil.py", "/etc/passwd", "\\\\server\\share\\x.py",
                                 "C:/Windows/x.py", "c:evil.py", "a\\..\\..\\x", "x\x00.py"])
def test_clean_member_path_rejects_escaping_paths(bad: str) -> None:
    with pytest.raises(ValueError):
        clean_member_path(bad)


def test_clean_member_path_normalizes() -> None:
    assert clean_member_path("./a\\b//c.py") == "a/b/c.py"
    assert clean_member_path("./") == ""


# ---------------------------------------------------------------------------------------------
# zip
# ---------------------------------------------------------------------------------------------


def test_zip_extracts_tree_as_is(tmp_path: Path) -> None:
    data = make_zip([("repo/", b""), ("repo/a.py", b"print(1)\n"), ("repo/pkg/b.py", b"x = 1\n"),
                     ("repo/pkg/__pycache__/b.cpython-312.pyc", b"\x00\x01")])
    snap = snapshot_from_zip(data, tmp_path / "snap", "myrepo")
    assert snap.source_kind == "zip" and snap.name == "myrepo" and snap.source_path is None
    assert snap.root == (tmp_path / "snap").resolve()
    assert files_under(snap.root) == {"repo/a.py", "repo/pkg/b.py", "repo/pkg/__pycache__/b.cpython-312.pyc"}
    assert snap.file_count == 3
    assert snap.total_bytes == len(b"print(1)\n") + len(b"x = 1\n") + 2
    assert (snap.root / "repo" / "a.py").read_bytes() == b"print(1)\n"


@pytest.mark.parametrize("evil", ["../evil.py", "repo/../../evil.py", "/abs.py", "C:/evil.py", "C:\\evil.py"])
def test_zip_slip_and_absolute_paths_rejected_before_writing(tmp_path: Path, evil: str) -> None:
    data = make_zip([("repo/ok.py", b"ok"), (evil, b"pwned")])
    dest = tmp_path / "out" / "snap"
    with pytest.raises(ValueError):
        snapshot_from_zip(data, dest, "x")
    assert not dest.exists()                       # nothing extracted at all
    assert not (tmp_path / "evil.py").exists() and not (tmp_path / "out" / "evil.py").exists()


def test_zip_symlink_member_is_not_extracted(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("repo/a.py", b"x = 1\n")
        link = zipfile.ZipInfo("repo/link.py")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(link, "../../../../etc/passwd")
    snap = snapshot_from_zip(buf.getvalue(), tmp_path / "snap", "x")
    assert files_under(snap.root) == {"repo/a.py"}
    assert not (snap.root / "repo" / "link.py").exists() and not (snap.root / "repo" / "link.py").is_symlink()
    assert any("link.py" in s and "symbolic link" in s for s in snap.skipped)


def test_zip_bomb_ratio_rejected(tmp_path: Path) -> None:
    data = make_zip([("bomb.txt", b"\x00" * (4 * ingest.MB))])   # ~1000:1 ratio
    with pytest.raises(ValueError, match="zip bomb"):
        snapshot_from_zip(data, tmp_path / "snap", "x")
    assert not (tmp_path / "snap").exists()


def test_zip_total_size_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "MAX_TOTAL_BYTES", 1000)
    monkeypatch.setattr(ingest, "MAX_FILE_BYTES", 900)
    data = make_zip([(f"f{i}.txt", os.urandom(400)) for i in range(3)], compression=zipfile.ZIP_STORED)
    with pytest.raises(ValueError, match="too large"):
        snapshot_from_zip(data, tmp_path / "snap", "x")
    assert not (tmp_path / "snap").exists()


def test_zip_file_count_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "MAX_FILES", 5)
    data = make_zip([(f"src/f{i}.py", b"x") for i in range(6)])
    with pytest.raises(ValueError, match="too many files"):
        snapshot_from_zip(data, tmp_path / "snap", "x")


def test_zip_member_larger_than_declared_is_rejected(tmp_path: Path) -> None:
    payload = b"A" * 5000
    data = bytearray(make_zip([("a.txt", payload)], compression=zipfile.ZIP_DEFLATED))
    # Lie about the uncompressed size (local header @22, central directory @24).
    local = data.find(b"PK\x03\x04")
    central = data.find(b"PK\x01\x02")
    struct.pack_into("<I", data, local + 22, 10)
    struct.pack_into("<I", data, central + 24, 10)
    with pytest.raises(ValueError):
        snapshot_from_zip(bytes(data), tmp_path / "snap", "x")
    assert not (tmp_path / "snap").exists() or files_under(tmp_path / "snap") == set()   # partial copy discarded


def test_zip_skips_dependency_dirs_keeps_pycache_and_placeholders(tmp_path: Path) -> None:
    data = make_zip([
        ("p/a.py", b"x"), ("p/node_modules/lib/index.js", b"y"), ("p/.venv/bin/python", b"z"),
        ("p/__pycache__/a.cpython-312.pyc", b"c"), ("__MACOSX/p/._a.py", b"m"),
    ])
    snap = snapshot_from_zip(data, tmp_path / "snap", "x")
    assert files_under(snap.root) == {"p/a.py", "p/__pycache__/a.cpython-312.pyc"}
    assert (snap.root / "p" / "node_modules").is_dir() and not any((snap.root / "p" / "node_modules").iterdir())
    assert not (snap.root / "__MACOSX").exists()
    assert any(s.startswith("p/node_modules/") for s in snap.skipped)
    assert any(s.startswith("p/.venv/") for s in snap.skipped)


def test_zip_case_collision_keeps_first_and_warns(tmp_path: Path) -> None:
    data = make_zip([("Kelvin.py", b"first"), ("kelvin.py", b"second"), ("dir/a.py", b"1"), ("DIR/b.py", b"2")])
    snap = snapshot_from_zip(data, tmp_path / "snap", "x")
    assert (snap.root / "Kelvin.py").read_bytes() == b"first"
    names = {p.name for p in snap.root.iterdir()}
    assert "Kelvin.py" in names and "kelvin.py" not in names and "DIR" not in names
    assert any("kelvin.py" in w for w in snap.warnings)
    assert any("DIR/b.py" in w for w in snap.warnings)


def test_zip_windows_unsafe_names_skipped(tmp_path: Path) -> None:
    data = make_zip([("ok.py", b"1"), ("dir/file.py:stream", b"2"), ("CON.py", b"3"), ("what?.py", b"4")])
    snap = snapshot_from_zip(data, tmp_path / "snap", "x")
    assert files_under(snap.root) == {"ok.py"}
    assert len([s for s in snap.skipped if "not extracted" in s]) == 3


def test_invalid_zip_is_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a valid zip"):
        snapshot_from_zip(b"not a zip", tmp_path / "snap", "x")


# ---------------------------------------------------------------------------------------------
# upload
# ---------------------------------------------------------------------------------------------


def test_upload_writes_relative_paths(tmp_path: Path) -> None:
    snap = snapshot_from_upload([("Repo/a.py", b"x = 1\n"), ("Repo\\pkg\\b.py", b"y\n")], tmp_path / "snap", "Repo")
    assert snap.source_kind == "upload" and snap.file_count == 2
    assert files_under(snap.root) == {"Repo/a.py", "Repo/pkg/b.py"}


@pytest.mark.parametrize("bad", ["../x.py", "Repo/../../x.py", "/etc/x", "C:/x.py", ""])
def test_upload_rejects_invalid_paths(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError):
        snapshot_from_upload([("Repo/a.py", b"1"), (bad, b"2")], tmp_path / "snap", "x")
    assert not (tmp_path / "x.py").exists()


def test_upload_too_big_file_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "MAX_FILE_BYTES", 10)
    snap = snapshot_from_upload([("a.py", b"x"), ("big.bin", b"0" * 11)], tmp_path / "snap", "x")
    assert files_under(snap.root) == {"a.py"}
    assert any(s.startswith("big.bin (file too large") for s in snap.skipped)


# ---------------------------------------------------------------------------------------------
# path
# ---------------------------------------------------------------------------------------------


def test_path_snapshot_of_demo_keeps_diagnostic_files(tmp_path: Path) -> None:
    src = DEMO_DIR / "projects" / "mysteryinc_buggy"
    snap = snapshot_from_path(src, tmp_path / "snap", kind="demo")
    got = files_under(snap.root)
    assert "MysteryInc/.DS_Store" in got
    assert "MysteryInc/FirstLaunch/flight_functions/__pycache__/kelvin.cpython-312.pyc" in got
    assert "MysteryInc/FirstLaunch/mission_clock.py" in got
    assert snap.file_count == len(got) and snap.source_kind == "demo"
    assert snap.source_path == str(src.resolve()) and snap.name == "mysteryinc_buggy"
    assert snap.warnings == []      # demo: no "inside another repository" warning


def test_path_snapshot_skips_heavy_dirs_and_big_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "MAX_FILE_BYTES", 100)
    src = tmp_path / "proj"
    for rel, data in {"a.py": b"x", "node_modules/m/i.js": b"j", "venv/lib/x.py": b"v", ".pytest_cache/v": b"c",
                      "sub/env/x.txt": b"e", "big.dat": b"0" * 101, "__pycache__/a.pyc": b"p"}.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_bytes(data)
    snap = snapshot_from_path(src, tmp_path / "snap")
    assert files_under(snap.root) == {"a.py", "__pycache__/a.pyc"}
    for placeholder in ("node_modules", "venv", ".pytest_cache", "sub/env"):
        assert (snap.root / placeholder).is_dir(), placeholder
    assert any(s.startswith("big.dat (file too large") for s in snap.skipped)
    assert (src / "big.dat").exists()               # the source is never modified


def test_path_snapshot_too_many_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "MAX_FILES", 3)
    src = tmp_path / "proj"
    src.mkdir()
    for i in range(5):
        (src / f"f{i}.py").write_text("x")
    with pytest.raises(ValueError, match="too many files"):
        snapshot_from_path(src, tmp_path / "snap")
    assert not (tmp_path / "snap").exists()


def test_path_snapshot_dest_inside_source_rejected(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x")
    with pytest.raises(ValueError, match="inside the project"):
        snapshot_from_path(tmp_path, tmp_path / ".data" / "snap")


def test_path_snapshot_missing_or_file_source(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        snapshot_from_path(tmp_path / "nope", tmp_path / "snap")
    (tmp_path / "f.txt").write_text("x")
    with pytest.raises(NotADirectoryError):
        snapshot_from_path(tmp_path / "f.txt", tmp_path / "snap2")


def test_path_snapshot_never_follows_symlinks(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    src = tmp_path / "proj"
    src.mkdir()
    (src / "a.py").write_text("x")
    try:
        os.symlink(outside, src / "linkdir", target_is_directory=True)
        os.symlink(outside / "secret.txt", src / "link.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks cannot be created here (Windows without developer mode)")
    snap = snapshot_from_path(src, tmp_path / "snap")
    assert files_under(snap.root) == {"a.py"}
    assert not (snap.root / "linkdir").exists() and not (snap.root / "link.txt").exists()
    assert any("linkdir" in s for s in snap.skipped) and any("link.txt" in s for s in snap.skipped)


@pytest.mark.skipif(os.name != "nt", reason="junctions are a Windows feature")
def test_path_snapshot_never_follows_windows_junctions(tmp_path: Path) -> None:
    import subprocess

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    src = tmp_path / "proj"
    src.mkdir()
    (src / "a.py").write_text("x")
    proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(src / "junction"), str(outside)], capture_output=True)
    if proc.returncode != 0:
        pytest.skip("mklink /J is not available")
    snap = snapshot_from_path(src, tmp_path / "snap")
    assert files_under(snap.root) == {"a.py"}
    assert any(s.startswith("junction (symbolic link or junction") for s in snap.skipped)


def test_path_snapshot_warns_when_inside_another_repository(tmp_path: Path) -> None:
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    sub = tmp_path / "repo" / "MysteryInc"
    sub.mkdir()
    (sub / "a.py").write_text("x")
    snap = snapshot_from_path(sub, tmp_path / "snap")
    assert any("not its root" in w for w in snap.warnings)


# ---------------------------------------------------------------------------------------------
# .git sanitization
# ---------------------------------------------------------------------------------------------

EVIL_CONFIG = """[core]
\trepositoryformatversion = 0
\tfilemode = true
\tbare = false
\tfsmonitor = /tmp/evil.sh
\thooksPath = /tmp/evil-hooks
\tsshCommand = evil
\tpager = evil
\tautocrlf = true
[include]
\tpath = /tmp/evil.config
[filter "lfs"]
\tclean = evil %f
[remote "origin"]
\turl = https://user:token@example.com/student/repo.git
\tfetch = +refs/heads/*:refs/remotes/origin/*
[alias]
\tst = !evil
"""


def make_fake_git(root: Path) -> Path:
    git = root / ".git"
    (git / "hooks").mkdir(parents=True)
    (git / "objects" / "info").mkdir(parents=True)
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n")
    (git / "config").write_text(EVIL_CONFIG)
    (git / "config.worktree").write_text("[core]\n\tfsmonitor = evil\n")
    (git / "hooks" / "pre-commit").write_text("#!/bin/sh\necho evil\n")
    (git / "hooks" / "post-checkout.sample").write_text("#!/bin/sh\n")
    (git / "objects" / "info" / "alternates").write_text("/somewhere/else/objects\n")
    sub = git / "modules" / "lib"
    (sub / "hooks").mkdir(parents=True)
    (sub / "objects").mkdir()
    (sub / "HEAD").write_text("ref: refs/heads/main\n")
    (sub / "config").write_text("[core]\n\tfsmonitor = evil\n\tworktree = ../../../lib\n")
    (sub / "hooks" / "post-index-change").write_text("#!/bin/sh\necho evil\n")
    return git


def test_sanitize_git_dir_neutralizes_config_and_hooks(tmp_path: Path) -> None:
    git = make_fake_git(tmp_path)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / ".git").write_text("gitdir: ../../../elsewhere\n")   # git link file
    sanitize_git_dir(tmp_path)
    config = (git / "config").read_text()
    for bad in ("fsmonitor", "hooksPath", "sshCommand", "pager", "include", "filter", "alias", "evil"):
        assert bad not in config, bad
    assert "repositoryformatversion = 0" in config and "bare = false" in config
    assert "autocrlf = true" in config                                    # safe line-ending setting kept
    assert '[remote "origin"]' in config and "example.com/student/repo.git" in config
    assert list((git / "hooks").iterdir()) == []
    assert not (git / "config.worktree").exists()
    assert not (git / "objects" / "info" / "alternates").exists()
    sub_config = (git / "modules" / "lib" / "config").read_text()
    assert "fsmonitor" not in sub_config and "worktree" not in sub_config
    assert list((git / "modules" / "lib" / "hooks").iterdir()) == []
    assert not (tmp_path / "lib" / ".git").exists()


def test_sanitize_keeps_branch_refs_named_hooks(tmp_path: Path) -> None:
    git = make_fake_git(tmp_path)
    (git / "refs" / "heads" / "hooks").mkdir(parents=True)
    (git / "refs" / "heads" / "hooks" / "fix").write_text("0" * 40 + "\n")
    sanitize_git_dir(tmp_path)
    assert (git / "refs" / "heads" / "hooks" / "fix").is_file()
    assert list((git / "hooks").iterdir()) == []


def test_snapshot_sanitizes_copied_git_dir(tmp_path: Path) -> None:
    src = tmp_path / "proj"
    src.mkdir()
    (src / "a.py").write_text("x")
    make_fake_git(src)
    snap = snapshot_from_path(src, tmp_path / "snap")
    assert snap.file_count == 1                       # .git internals are not project files
    assert (snap.root / ".git" / "HEAD").is_file()
    assert list((snap.root / ".git" / "hooks").iterdir()) == []
    assert "fsmonitor" not in (snap.root / ".git" / "config").read_text()
    assert (src / ".git" / "hooks" / "pre-commit").exists()     # the student's repo is untouched
    assert "fsmonitor" in (src / ".git" / "config").read_text()


def test_zip_with_git_dir_is_sanitized(tmp_path: Path) -> None:
    data = make_zip([("repo/a.py", b"x"), ("repo/.git/HEAD", b"ref: refs/heads/main\n"),
                     ("repo/.git/config", EVIL_CONFIG.encode()), ("repo/.git/hooks/pre-commit", b"#!/bin/sh\nevil\n"),
                     ("repo/.git/objects/", b"")])
    snap = snapshot_from_zip(data, tmp_path / "snap", "x")
    assert snap.file_count == 1
    assert not (snap.root / "repo" / ".git" / "hooks" / "pre-commit").exists()
    assert "fsmonitor" not in (snap.root / "repo" / ".git" / "config").read_text()


def test_git_dir_over_budget_is_dropped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "GIT_MAX_FILES", 2)
    src = tmp_path / "proj"
    src.mkdir()
    (src / "a.py").write_text("x")
    make_fake_git(src)
    snap = snapshot_from_path(src, tmp_path / "snap")
    assert not (snap.root / ".git").exists()
    assert files_under(snap.root) == {"a.py"}
    assert any("git checks" in w for w in snap.warnings)
