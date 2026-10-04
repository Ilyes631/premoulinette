from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

import pytest

from test_api_fakes import harness_factory, make_project_dir  # noqa: F401  (fixture)


@pytest.fixture(autouse=True)
def no_real_wsl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Linux paths ("/root/…") are looked up in WSL on Windows: never touch the real WSL in tests."""
    from premoulinette.project import discover

    monkeypatch.setattr(discover, "list_wsl_distros", lambda: [])


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    return make_project_dir(tmp_path / "student" / "myrepo")


def create_from_path(h, path: Path | str):
    return h.client.post("/api/projects", data={"path": str(path)})


def test_path_import_creates_snapshot_copy(harness_factory, project_dir: Path) -> None:
    h = harness_factory()
    r = create_from_path(h, project_dir)
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["source_kind"] == "path"
    assert view["name"] == "myrepo"
    assert view["source_path"] == str(project_dir.resolve())
    assert view["language"] == "python"
    assert view["python_files"] == 2
    assert view["file_count"] == 4
    paths = {e["path"] for e in view["tree"]}
    assert {"pkg", "pkg/safe_speed.py", "pkg/hello.py", "README.md"} <= paths
    assert view["git"]["is_repo"] is False   # no .git inside the project

    rec = h.store.get_project(view["id"])
    snapshot = Path(rec.snapshot_path)
    assert snapshot.is_relative_to(h.ctx.paths.snapshots / view["id"])
    # it is a copy: editing the student's folder does not change the snapshot
    (project_dir / "pkg" / "safe_speed.py").write_text("changed\n", encoding="utf-8")
    assert "return speed <= limit" in (snapshot / "pkg" / "safe_speed.py").read_text(encoding="utf-8")

    assert h.client.get(f"/api/projects/{view['id']}").json()["id"] == view["id"]
    assert [p["id"] for p in h.client.get("/api/projects").json()] == [view["id"]]


def test_git_info_is_read_inside_the_snapshot_only(harness_factory, project_dir: Path) -> None:
    calls: list[Path] = []

    from test_api_fakes import fake_read_git_info, make_services

    def spy(root: Path, required: list[str]):
        calls.append(root)
        return fake_read_git_info(root, required)

    (project_dir / ".git").mkdir()
    h = harness_factory(make_services(read_git_info=spy))
    view = create_from_path(h, project_dir).json()
    snapshot = Path(h.store.get_project(view["id"]).snapshot_path)
    assert calls == [snapshot]
    assert view["git"]["branch"] == "main"
    assert view["git"]["untracked"] == ["new.py"]


@pytest.mark.parametrize("bad", ["relative/path", "C:/definitely/not/here/xyz", "/definitely/not/here/xyz"])
def test_invalid_local_paths(harness_factory, bad: str) -> None:
    h = harness_factory()
    r = create_from_path(h, bad)
    assert r.status_code == 400
    assert h.store.list_projects() == []


def _fake_wsl(monkeypatch: pytest.MonkeyPatch, wsl_root: Path, distros: list[str]) -> None:
    import premoulinette.api.routes_projects as routes
    from premoulinette.project import discover

    monkeypatch.setattr(routes, "_ACCEPT_LINUX_PATHS", True)
    monkeypatch.setattr(discover, "UNC_PREFIXES", (str(wsl_root) + os.sep,))
    monkeypatch.setattr(discover, "list_wsl_distros", lambda: list(distros))


def test_linux_path_is_found_in_wsl(harness_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wsl_root = tmp_path / "wsl"
    make_project_dir(wsl_root / "Debian" / "root" / "epita-tp")
    (wsl_root / "Ubuntu" / "root").mkdir(parents=True)
    _fake_wsl(monkeypatch, wsl_root, ["Ubuntu", "Debian"])
    h = harness_factory()
    r = create_from_path(h, "/root/epita-tp")
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "epita-tp"
    assert r.json()["source_path"] == str((wsl_root / "Debian" / "root" / "epita-tp").resolve())


def test_linux_path_not_found_in_wsl(harness_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_wsl(monkeypatch, tmp_path / "wsl", ["Ubuntu", "Debian"])
    h = harness_factory()
    r = create_from_path(h, "/root/missing")
    assert r.status_code == 400
    assert r.json()["detail"] == "Folder not found in Windows nor in WSL (Ubuntu, Debian): /root/missing"


def test_linux_path_cannot_reach_the_data_dir(harness_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h = harness_factory()
    # the fake WSL "distro" is the parent of the data dir: "/data" maps onto it
    _fake_wsl(monkeypatch, tmp_path.parent, [tmp_path.name])
    r = create_from_path(h, "/data")
    assert r.status_code == 400
    assert "data directory" in r.json()["detail"]


def test_file_instead_of_folder(harness_factory, project_dir: Path) -> None:
    h = harness_factory()
    assert create_from_path(h, project_dir / "README.md").status_code == 400


def test_data_dir_cannot_be_imported(harness_factory, tmp_path: Path) -> None:
    h = harness_factory()
    assert create_from_path(h, h.ctx.paths.root).status_code == 400
    assert create_from_path(h, h.ctx.paths.snapshots).status_code == 400
    assert create_from_path(h, tmp_path).status_code == 400   # contains the data dir


def test_exactly_one_mode(harness_factory, project_dir: Path) -> None:
    h = harness_factory()
    assert h.client.post("/api/projects", data={"name": "x"}).status_code == 400
    both = h.client.post(
        "/api/projects", data={"path": str(project_dir)}, files={"file": ("p.zip", b"PK", "application/zip")}
    )
    assert both.status_code == 400


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_zip_import(harness_factory) -> None:
    h = harness_factory()
    data = _zip_bytes({"repo/pkg/a.py": b"x = 1\n", "repo/README.md": b"hi"})
    r = h.client.post("/api/projects", files={"file": ("my-project.zip", data, "application/zip")})
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["source_kind"] == "zip"
    assert view["name"] == "my-project"
    assert view["source_path"] is None
    assert view["python_files"] == 1


def test_bad_zip_is_400_and_cleaned(harness_factory) -> None:
    h = harness_factory()
    r = h.client.post("/api/projects", files={"file": ("broken.zip", b"not a zip", "application/zip")})
    assert r.status_code == 400
    assert list(h.ctx.paths.snapshots.iterdir()) == []


def test_zip_too_large(harness_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    import premoulinette.api.routes_projects as routes

    monkeypatch.setattr(routes, "ZIP_MAX_BYTES", 16)
    h = harness_factory()
    r = h.client.post("/api/projects", files={"file": ("p.zip", b"x" * 17, "application/zip")})
    assert r.status_code == 413


def test_folder_upload(harness_factory) -> None:
    h = harness_factory()
    files = [
        ("files", ("a.py", b"print(1)\n", "text/x-python")),
        ("files", ("README.md", b"# r\n", "text/markdown")),
    ]
    r = h.client.post("/api/projects", files=files, data={"paths": ["myrepo/pkg/a.py", "myrepo/README.md"]})
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["source_kind"] == "upload"
    assert view["name"] == "myrepo"
    assert {"myrepo/pkg/a.py", "myrepo/README.md"} <= {e["path"] for e in view["tree"]}


def test_folder_upload_paths_mismatch(harness_factory) -> None:
    h = harness_factory()
    files = [("files", ("a.py", b"1", "text/plain")), ("files", ("b.py", b"2", "text/plain"))]
    r = h.client.post("/api/projects", files=files, data={"paths": ["x/a.py"]})
    assert r.status_code == 400


def test_folder_upload_total_limit(harness_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    import premoulinette.api.routes_projects as routes

    monkeypatch.setattr(routes, "FOLDER_UPLOAD_MAX_BYTES", 10)
    h = harness_factory()
    files = [("files", ("a.py", b"123456", "text/plain")), ("files", ("b.py", b"789012", "text/plain"))]
    r = h.client.post("/api/projects", files=files, data={"paths": ["r/a.py", "r/b.py"]})
    assert r.status_code == 413


# ---- file viewer --------------------------------------------------------------------------------------


@pytest.fixture
def imported(harness_factory, project_dir: Path):
    h = harness_factory()
    view = create_from_path(h, project_dir).json()
    snapshot = Path(h.store.get_project(view["id"]).snapshot_path)
    # a file right next to the snapshot that must never be reachable
    (snapshot.parent / "secret.txt").write_text("TOP SECRET", encoding="utf-8")
    return h, view["id"], snapshot


def test_file_endpoint_serves_text(imported) -> None:
    h, pid, _ = imported
    r = h.client.get(f"/api/projects/{pid}/file", params={"path": "pkg/safe_speed.py"})
    assert r.status_code == 200
    data = r.json()
    assert data["path"] == "pkg/safe_speed.py"
    assert data["language"] == "python"
    assert data["content"].startswith("def is_safe")
    # backslashes and ./ are normalized
    assert h.client.get(f"/api/projects/{pid}/file", params={"path": ".\\pkg\\hello.py"}).json()["path"] == "pkg/hello.py"


@pytest.mark.parametrize(
    "path",
    ["../secret.txt", "..\\secret.txt", "pkg/../../secret.txt", "../../../../../../Windows/win.ini",
     "/etc/passwd", "C:/Windows/win.ini", "c:secret.txt", "", "./", "pkg/\x00.py"],
)
def test_file_endpoint_rejects_traversal(imported, path: str) -> None:
    h, pid, _ = imported
    r = h.client.get(f"/api/projects/{pid}/file", params={"path": path})
    assert r.status_code in (400, 422), (path, r.status_code)
    assert "TOP SECRET" not in r.text


def test_file_endpoint_other_errors(imported) -> None:
    h, pid, snapshot = imported
    (snapshot / ".git").mkdir()
    (snapshot / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    assert h.client.get(f"/api/projects/{pid}/file", params={"path": ".git/config"}).status_code == 403
    assert h.client.get(f"/api/projects/{pid}/file", params={"path": "data.bin"}).status_code == 415
    assert h.client.get(f"/api/projects/{pid}/file", params={"path": "missing.py"}).status_code == 404
    assert h.client.get(f"/api/projects/{pid}/file", params={"path": "pkg"}).status_code == 404
    assert h.client.get("/api/projects/nope/file", params={"path": "pkg/hello.py"}).status_code == 404


def test_file_endpoint_size_limit(imported, monkeypatch: pytest.MonkeyPatch) -> None:
    import premoulinette.api.routes_projects as routes

    h, pid, _ = imported
    monkeypatch.setattr(routes, "FILE_VIEW_MAX_BYTES", 8)
    assert h.client.get(f"/api/projects/{pid}/file", params={"path": "pkg/safe_speed.py"}).status_code == 413


def test_unknown_project(harness_factory) -> None:
    h = harness_factory()
    assert h.client.get("/api/projects/nope").status_code == 404
