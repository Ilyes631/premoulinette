"""project.root_detect, project.tree, project.paths, project.source, project.diagnostics."""
from __future__ import annotations

from pathlib import Path

from premoulinette.project.diagnostics import lines_text, plural, requirement_outcome, short_list
from premoulinette.project.paths import DirIndex, normalize_rel, strip_base
from premoulinette.project.root_detect import detect_root, resolve
from premoulinette.project.source import make_excerpt, split_lines
from premoulinette.project.tree import list_tree
from premoulinette.spec.models import ExerciseSpec, PracticalSpec

FL = "MysteryInc/FirstLaunch"


def spec(*paths: str) -> PracticalSpec:
    return PracticalSpec(exercises=[ExerciseSpec(id=f"e{i}", title="t", file_path=p) for i, p in enumerate(paths)])


def touch(root: Path, rel: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x = 1\n")


SPEC = spec(f"{FL}/a.py", f"{FL}/route/b.py", f"{FL}/c.py")


def test_root_at_snapshot_top(tmp_path: Path) -> None:
    for p in (f"{FL}/a.py", f"{FL}/route/b.py", f"{FL}/c.py"):
        touch(tmp_path, p)
    det = detect_root(tmp_path, SPEC)
    assert (det.root, det.strip_prefix, det.matched, det.expected, det.confident) == ("", "", 3, 3, True)
    assert resolve(f"{FL}/a.py", det) == f"{FL}/a.py"


def test_root_inside_zip_top_folder(tmp_path: Path) -> None:
    for p in (f"repo/{FL}/a.py", f"repo/{FL}/route/b.py"):
        touch(tmp_path, p)
    det = detect_root(tmp_path, SPEC)
    assert det.root == "repo" and det.strip_prefix == "" and det.matched == 2
    assert resolve(f"{FL}/c.py", det) == f"repo/{FL}/c.py"


def test_selected_subfolder_strips_prefix(tmp_path: Path) -> None:
    for p in ("a.py", "route/b.py", "c.py"):
        touch(tmp_path, p)
    det = detect_root(tmp_path, SPEC)
    assert det.root == "" and det.strip_prefix == f"{FL}/" and det.matched == 3
    assert det.note and "not its root" in det.note and not det.confident
    assert resolve(f"{FL}/route/b.py", det) == "route/b.py"


def test_git_root_is_never_stripped(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    for p in ("FirstLaunch/a.py", "FirstLaunch/route/b.py"):     # a folder level is missing
        touch(tmp_path, p)
    det = detect_root(tmp_path, SPEC)
    assert det.root == "" and det.strip_prefix == ""             # files will be reported misplaced
    assert det.matched == 0


def test_exact_case_index(tmp_path: Path) -> None:
    touch(tmp_path, "Ex/Kelvin.py")
    index = DirIndex(tmp_path)
    assert index.kind("Ex/Kelvin.py") == "file" and index.kind("Ex") == "directory"
    assert index.kind("ex/kelvin.py") is None                     # even on a case-insensitive file system
    assert index.find_case_insensitive("ex/kelvin.py") == "Ex/Kelvin.py"
    assert index.find_case_insensitive("ex/missing.py") is None


def test_list_tree_skips_git_and_sorts(tmp_path: Path) -> None:
    touch(tmp_path, "b/z.py")
    touch(tmp_path, "B2.py")
    touch(tmp_path, "a.py")
    touch(tmp_path, ".git/HEAD")
    tree = list_tree(tmp_path)
    assert [e.path for e in tree] == ["a.py", "b", "b/z.py", "B2.py"]
    assert {e.path: e.kind for e in tree}["b"] == "directory"
    assert all(e.size == 6 for e in tree if e.kind == "file")


def test_path_helpers() -> None:
    assert normalize_rel("./a\\b//c/") == "a/b/c"
    assert strip_base("a/b/c", "a") == "b/c" and strip_base("a", "a") == "" and strip_base("x", "") == "x"


def test_source_helpers() -> None:
    assert split_lines("a\r\nb\rc\x0cd\n") == ["a", "b", "c\x0cd"]     # form feed is not a line break for Python
    excerpt = make_excerpt("1\n2\n3\n4\n5\n6\n", "f.py", 4, context=1)
    assert excerpt and excerpt.start_line == 3 and excerpt.lines == ["3", "4", "5"] and excerpt.highlight == [4]
    assert make_excerpt("1\n", "f.py", 9) is None


def test_diagnostics_helpers() -> None:
    assert requirement_outcome(True, False) == ("fail", True)
    assert requirement_outcome(False, True) == ("bonus", False)
    assert requirement_outcome(False, False) == ("warning", False)
    assert plural(1, "file") == "1 file" and plural(2, "file") == "2 files"
    assert short_list(range(7), limit=3) == "0, 1, 2 (+4 more)"
    assert lines_text([3]) == "line 3" and lines_text([7, 3, 3]) == "lines 3, 7"
