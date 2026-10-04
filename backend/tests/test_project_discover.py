from __future__ import annotations

import os
from pathlib import Path

import pytest

from premoulinette.project import discover as d
from premoulinette.project.discover import DiscoveredProject, ScanRoot

from test_api_fakes import harness_factory  # noqa: F401  (fixture)

TS = 1727700000  # 2024-09-30T12:40:00Z


def make_repo(path: Path, *, branch: str = "main", ts: int | None = TS, message: str = "commit: TP2",
              remote: str | None = "git@git.forge.epita.fr:p/tp.git", git_file: bool = False) -> Path:
    git = path / ".git"
    git.mkdir(parents=True)
    (git / "HEAD").write_text(f"ref: refs/heads/{branch}\n", encoding="utf-8")
    if ts is not None:
        (git / "logs").mkdir()
        old = "0" * 40
        lines = [f"{old} {'a' * 40} Jane Doe <jane@x.fr> {ts - 100} +0200\tclone: from https://jane:tok@h/x.git",
                 f"{'a' * 40} {'b' * 40} Jane Doe <jane@x.fr> {ts} +0200\t{message}"]
        (git / "logs" / "HEAD").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if remote is not None:
        (git / "config").write_text(
            f'[core]\n\tbare = false\n[remote "upstream"]\n\turl = https://other/x.git\n'
            f'[remote "origin"]\n\turl = {remote}\n\tfetch = +refs/heads/*:refs/remotes/origin/*\n',
            encoding="utf-8",
        )
    return path


def run_scan(*roots: ScanRoot, exclude=()) -> dict:
    return d.scan([lambda r=r: [r] for r in roots], exclude=exclude, budget_s=10)


def win_root(path: Path, **kw) -> ScanRoot:
    return ScanRoot(str(path), str(path), "windows", **kw)


# ---- pure helpers ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(("url", "expected"), [
    ("https://user:token@github.com/x/y.git", "https://github.com/x/y.git"),
    ("https://token@github.com/x/y.git", "https://github.com/x/y.git"),
    ("ssh://git@host:22/x.git", "ssh://host:22/x.git"),
    ("git@git.forge.epita.fr:p/x.git", "git@git.forge.epita.fr:p/x.git"),   # scp-like: no secret
    ("https://github.com/a/b@c", "https://github.com/a/b@c"),
    ("clone: from https://u:p@h/x.git", "clone: from https://h/x.git"),
    (None, None),
])
def test_strip_credentials(url, expected) -> None:
    assert d.strip_credentials(url) == expected


@pytest.mark.parametrize(("url", "host"), [
    ("https://u:p@git.forge.epita.fr/x.git", "git.forge.epita.fr"),
    ("ssh://git@Git.Forge.EPITA.fr:22/x", "git.forge.epita.fr"),
    ("ilyes.gharib@git.forge.epita.fr:p/x.git", "git.forge.epita.fr"),
    ("git@github.com:a/b.git", "github.com"),
    ("https://[::1]:8080/x", "::1"),
    ("", ""),
    (None, ""),
])
def test_remote_host(url, host) -> None:
    assert d.remote_host(url) == host


def test_is_school() -> None:
    assert d.is_school_project("epita-prepa-tp", None)
    assert d.is_school_project("tp", "git@git.forge.epita.fr:p/x.git")
    assert not d.is_school_project("tp", "https://github.com/someone/epita-notes.git")   # host only
    assert not d.is_school_project("my-epita-tp", None)


def test_parse_head() -> None:
    assert d.parse_head("ref: refs/heads/feature/x\n") == "feature/x"
    assert d.parse_head("a" * 40 + "\n") is None
    assert d.parse_head("") is None
    assert d.parse_head(None) is None


def test_parse_reflog_tail() -> None:
    text = ("0 1 A <a@b> 100 +0000\tcommit (initial): first\n"
            "1 2 Name With Spaces <a@b> 1727700000 -0700\tcommit: TP2\n\n")
    assert d.parse_reflog_tail(text) == (1727700000, "commit: TP2")
    assert d.parse_reflog_tail("garbage line") is None
    assert d.parse_reflog_tail("1 2 A <a@b> notanumber +0000\tx") is None
    assert d.parse_reflog_tail("") is None


def test_parse_remote_url() -> None:
    cfg = '[remote "upstream"]\n url = https://up/x\n# comment\n[Remote "origin"]\n\tURL = "git@h:o.git"\n[branch "main"]\n url = nope\n'
    assert d.parse_remote_url(cfg) == "git@h:o.git"
    assert d.parse_remote_url('[remote "fork"]\nurl = https://fork/x\n') == "https://fork/x"
    assert d.parse_remote_url("[core]\nurl = x\n") is None
    assert d.parse_remote_url(None) is None


def test_sort_projects() -> None:
    def p(name, school, ts):
        return DiscoveredProject(name, name, "windows", None, name, None, None, None, None, school, ts)

    ordered = d.sort_projects([p("old", False, 10.0), p("none", False, None), p("new", False, 20.0),
                               p("school-old", True, 1.0), p("school-none", True, None), p("school-new", True, 5.0)])
    assert [x.name for x in ordered] == ["school-new", "school-old", "school-none", "new", "old", "none"]


def _utf16(text: str) -> bytes:
    return b"\xff\xfe" + text.encode("utf-16-le")


def test_parse_wsl_list_quiet_utf16() -> None:
    raw = _utf16("Ubuntu\r\ndocker-desktop\r\ndocker-desktop-data\r\nDebian\r\n\r\n")
    assert d.parse_wsl_list_quiet(raw) == ["Ubuntu", "Debian"]
    assert d.parse_wsl_list_quiet("Ubuntu-22.04\nkali-linux\n".encode()) == ["Ubuntu-22.04", "kali-linux"]
    # an error message (spaces) is never taken for a distribution name
    assert d.parse_wsl_list_quiet(_utf16("Windows Subsystem for Linux has no installed distributions.\r\n")) == []


def test_parse_wsl_list_verbose_finds_default() -> None:
    raw = _utf16("  NOM                   ÉTAT            VERSION\r\n  Debian   Stopped  2\r\n"
                 "* Ubuntu                 Running         2\r\n  docker-desktop    Stopped   2\r\n")
    names, default = d.parse_wsl_list_verbose(raw)
    assert names == ["Debian", "Ubuntu"]
    assert default == "Ubuntu"
    assert d.order_distros(names, default) == ["Ubuntu", "Debian"]
    assert d.order_distros(["docker-desktop", "A b", "Arch"], None) == ["Arch"]


def test_linux_path_to_wsl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(d, "UNC_PREFIXES", (str(tmp_path) + os.sep,))
    (tmp_path / "Debian" / "root" / "tp").mkdir(parents=True)
    (tmp_path / "Ubuntu" / "root").mkdir(parents=True)
    expected = os.path.join(str(tmp_path) + os.sep + "Debian", "root", "tp")
    assert d.linux_path_to_wsl("/root/tp", ["Ubuntu", "Debian"]) == expected
    assert d.linux_path_to_wsl("/root/./x/../tp/", ["Ubuntu", "Debian"]) == expected
    assert d.linux_path_to_wsl("/root/missing", ["Ubuntu", "Debian"]) is None
    assert d.linux_path_to_wsl("/root/tp", []) is None
    assert d.linux_path_to_wsl("relative/tp", ["Debian"]) is None
    assert d.linux_path_to_wsl("//server/share", ["Debian"]) is None
    calls: list[str] = []
    d.linux_path_to_wsl("/root/tp", ["../evil", "Ubuntu"], is_dir=lambda p: calls.append(p) or False)
    assert all("evil" not in c for c in calls) and calls


# ---- scanning temp trees ---------------------------------------------------------------------------------


def test_scan_reads_metadata_without_git(tmp_path: Path) -> None:
    make_repo(tmp_path / "epita-prepa-tp", remote="https://jane:secret@git.forge.epita.fr/p/x.git")
    result = run_scan(win_root(tmp_path))
    [proj] = result["projects"]
    assert proj["path"] == str(tmp_path / "epita-prepa-tp")
    assert proj["name"] == "epita-prepa-tp"
    assert proj["location"] == "windows" and proj["distro"] is None
    assert proj["display_path"] == proj["path"]
    assert proj["branch"] == "main"
    assert proj["last_activity"] == "2024-09-30T12:40:00+00:00"
    assert proj["last_message"] == "commit: TP2"
    assert proj["remote_url"] == "https://git.forge.epita.fr/p/x.git"
    assert "secret" not in str(result)
    assert proj["is_school"] is True
    assert result["scanned"] == [str(tmp_path)]
    assert result["duration_ms"] >= 0


def test_scan_falls_back_to_index_mtime(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "tp", ts=None, remote=None)
    (repo / ".git" / "index").write_bytes(b"DIRC")
    os.utime(repo / ".git" / "index", (TS, TS))
    [proj] = run_scan(win_root(tmp_path))["projects"]
    assert proj["last_activity"] == "2024-09-30T12:40:00+00:00"
    assert proj["last_message"] is None and proj["remote_url"] is None and proj["is_school"] is False


def test_scan_depth_skip_dirs_and_nested(tmp_path: Path) -> None:
    make_repo(tmp_path / "a" / "b" / "c" / "depth4")
    make_repo(tmp_path / "a" / "b" / "c" / "d" / "depth5")
    make_repo(tmp_path / "node_modules" / "pkg")
    make_repo(tmp_path / ".hidden" / "x")
    make_repo(tmp_path / "venv" / "x")
    outer = make_repo(tmp_path / "outer")
    make_repo(outer / "inner")              # never descend into a found repository
    (tmp_path / "broken").mkdir()
    names = {p["name"] for p in run_scan(win_root(tmp_path))["projects"]}
    assert names == {"depth4", "outer"}


def test_scan_excludes_premoulinette_and_dedupes(tmp_path: Path) -> None:
    make_repo(tmp_path / "PreMoulinette")
    make_repo(tmp_path / "PreMoulinette" / "demo" / "student")
    make_repo(tmp_path / "tp")
    result = run_scan(win_root(tmp_path), win_root(tmp_path / "tp"), exclude=[tmp_path / "PreMoulinette"])
    assert [p["name"] for p in result["projects"]] == ["tp"]
    assert run_scan(win_root(tmp_path / "PreMoulinette"), exclude=[tmp_path / "PreMoulinette"])["projects"] == []


def test_scan_worktree_git_file(tmp_path: Path) -> None:
    main = make_repo(tmp_path / "main-repo", remote="git@github.com:a/b.git")
    wt_git = main / ".git" / "worktrees" / "wt"
    wt_git.mkdir(parents=True)
    (wt_git / "HEAD").write_text("ref: refs/heads/feature\n", encoding="utf-8")
    (wt_git / "commondir").write_text("../..\n", encoding="utf-8")
    wt = tmp_path / "other" / "wt"
    wt.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {wt_git}\n", encoding="utf-8")
    projects = {p["name"]: p for p in run_scan(win_root(tmp_path))["projects"]}
    assert projects["wt"]["branch"] == "feature"
    assert projects["wt"]["remote_url"] == "git@github.com:a/b.git"


def test_wsl_display_path_and_sorting(tmp_path: Path) -> None:
    make_repo(tmp_path / "home" / "jane" / "perso", ts=TS + 1000, remote="git@github.com:j/p.git")
    make_repo(tmp_path / "root" / "epita-tp", ts=TS)
    roots = [
        ScanRoot(str(tmp_path / "root"), "Ubuntu: /root", "wsl", "Ubuntu", "/root", str(tmp_path)),
        ScanRoot(str(tmp_path / "home" / "jane"), "Ubuntu: /home/jane", "wsl", "Ubuntu", "/home/jane", str(tmp_path)),
    ]
    result = run_scan(*roots)
    assert [p["name"] for p in result["projects"]] == ["epita-tp", "perso"]   # school first despite older
    assert result["projects"][0]["display_path"] == "Ubuntu: /root/epita-tp"
    assert result["projects"][0]["location"] == "wsl" and result["projects"][0]["distro"] == "Ubuntu"
    assert set(result["scanned"]) == {"Ubuntu: /root", "Ubuntu: /home/jane"}


def test_scan_respects_time_budget(tmp_path: Path) -> None:
    make_repo(tmp_path / "tp")
    result = d.scan([lambda: [win_root(tmp_path)]], budget_s=0)
    assert result["projects"] == []


def test_windows_roots(tmp_path: Path) -> None:
    for sub in ("Desktop", "source/repos", "OneDrive - EPITA/Documents"):
        (tmp_path / sub).mkdir(parents=True)
    roots = d.windows_roots(tmp_path)
    assert roots[0].path == str(tmp_path) and roots[0].max_depth == 1
    paths = {r.path for r in roots[1:]}
    assert paths == {str(tmp_path / "Desktop"), str(tmp_path / "source" / "repos"),
                     str(tmp_path / "OneDrive - EPITA" / "Documents")}


def test_discover_projects_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    d.clear_cache()
    calls: list[int] = []

    def tasks():
        calls.append(1)
        return [lambda: [win_root(tmp_path)]]

    monkeypatch.setattr(d, "default_tasks", tasks)
    make_repo(tmp_path / "tp")
    first = d.discover_projects()
    make_repo(tmp_path / "tp2")
    assert d.discover_projects() == first and len(calls) == 1
    assert {p["name"] for p in d.discover_projects(refresh=True)["projects"]} == {"tp", "tp2"}
    assert len(calls) == 2
    d.clear_cache()


# ---- API --------------------------------------------------------------------------------------------------


def test_discover_route(harness_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    d.clear_cache()
    scan_dir = tmp_path / "scan"
    make_repo(scan_dir / "epita-tp")
    monkeypatch.setattr(d, "default_tasks", lambda: [lambda: [win_root(scan_dir)]])
    h = harness_factory()
    r = h.client.get("/api/projects/discover", params={"refresh": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"projects", "scanned", "duration_ms"}
    [proj] = body["projects"]
    assert set(proj) == {"path", "name", "location", "distro", "display_path", "branch", "last_activity",
                         "last_message", "remote_url", "is_school"}
    assert proj["is_school"] is True
    # the discovered path can be imported as-is
    imported = h.client.post("/api/projects", data={"path": proj["path"]})
    assert imported.status_code == 200, imported.text
    assert imported.json()["name"] == "epita-tp"
    d.clear_cache()


def test_discover_route_excludes_data_dir(harness_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    d.clear_cache()
    h = harness_factory()
    make_repo(h.ctx.paths.root / "snapshots" / "x" / "repo")
    monkeypatch.setattr(d, "default_tasks", lambda: [lambda: [win_root(tmp_path)]])
    names = [p["name"] for p in h.client.get("/api/projects/discover?refresh=1").json()["projects"]]
    assert "repo" not in names
    d.clear_cache()
