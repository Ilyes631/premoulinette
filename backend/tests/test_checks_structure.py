"""check_structure: exact-case paths, misplaced files, parasites, .gitignore, extra files, annotated tree."""
from __future__ import annotations

from pathlib import Path

import pytest

from premoulinette.languages.python.checks_structure import check_structure, match_forbidden, repo_path
from premoulinette.project.ingest import snapshot_from_path
from premoulinette.project.root_detect import RootDetection, detect_root
from premoulinette.project.tree import list_tree
from premoulinette.results.models import CheckResult, TreeEntry
from premoulinette.spec.models import ExerciseSpec, FileRequirement, PracticalSpec, StructureSpec

from conftest import DEMO_DIR

FL = "MysteryInc/FirstLaunch"


def demo_spec(*, errors: bool = True) -> PracticalSpec:
    """Hand-built equivalent of the demo subject's structure (independent of the subject parser)."""
    ex = [
        ("kelvin", f"{FL}/flight_functions/kelvin.py", False),
        ("safe_speed", f"{FL}/flight_functions/safe_speed.py", False),
        ("grade_landing", f"{FL}/flight_functions/grade_landing.py", False),
        ("fuel_share", f"{FL}/route_math/fuel_share.py", False),
        ("mission_clock", f"{FL}/route_math/mission_clock.py", False),
        ("FIXME2", f"{FL}/FIXME2.py", False),
        ("access_code", f"{FL}/access_code.py", False),
        ("launch_sequence", f"{FL}/launch_sequence.py", False),
        ("emoji_grade", f"{FL}/flight_functions/grade_landing.py", True),
        ("max_altitude", f"{FL}/bonus/max_altitude.py", True),
        ("countdown", f"{FL}/bonus/countdown.py", True),
    ]
    files = [FileRequirement(path=".gitignore")] + [
        FileRequirement(path=p, required=not b, bonus=b) for _, p, b in ex if not p.endswith("grade_landing.py") or not b
    ]
    return PracticalSpec(
        structure=StructureSpec(files=files, require_gitignore=True, forbidden_patterns_are_errors=errors),
        exercises=[ExerciseSpec(id=i, title=i, file_path=p, bonus=b) for i, p, b in ex],
    )


def analyze(root: Path, spec: PracticalSpec, det: RootDetection | None = None):
    det = det or detect_root(root, spec)
    checks, tree, file_map = check_structure(spec, root, det, list_tree(root))
    return {c.id: c for c in checks}, tree, file_map, det


def write(root: Path, rel: str, text: str = "x = 1\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture()
def buggy(tmp_path: Path) -> Path:
    return snapshot_from_path(DEMO_DIR / "projects" / "mysteryinc_buggy", tmp_path / "snap", kind="demo").root


# ---------------------------------------------------------------------------------------------
# demo projects
# ---------------------------------------------------------------------------------------------


def test_demo_buggy_misplaced_parasites_gitignore_bonus(buggy: Path) -> None:
    checks, tree, file_map, _ = analyze(buggy, demo_spec())

    misplaced = checks[f"structure:file:{FL}/route_math/mission_clock.py"]
    assert (misplaced.status, misplaced.severity, misplaced.mandatory) == ("fail", "critical", True)
    assert misplaced.diagnosis == "misplaced_file" and misplaced.exercise_id == "mission_clock"
    assert misplaced.message.startswith(
        f"Found at {FL}/mission_clock.py, expected at {FL}/route_math/mission_clock.py."
    )
    assert misplaced.evidence.details["found_path"] == f"{FL}/mission_clock.py"
    assert misplaced.evidence.details["expected_path"] == f"{FL}/route_math/mission_clock.py"
    assert misplaced.location.file == f"{FL}/mission_clock.py"
    assert file_map[f"{FL}/route_math/mission_clock.py"] == f"{FL}/mission_clock.py"   # tests can still run

    bonus = checks[f"structure:file:{FL}/bonus/countdown.py"]
    assert (bonus.status, bonus.mandatory, bonus.bonus, bonus.diagnosis) == ("bonus", False, True, "missing_bonus_file")
    assert bonus.severity is None and file_map[f"{FL}/bonus/countdown.py"] is None
    assert checks[f"structure:file:{FL}/bonus/max_altitude.py"].status == "pass"
    assert checks[f"structure:file:{FL}/bonus/max_altitude.py"].mandatory is False

    gitignore = checks["structure:gitignore"]
    assert (gitignore.status, gitignore.severity, gitignore.diagnosis) == ("fail", "major", "missing_gitignore")
    assert "structure:file:.gitignore" not in checks          # reported once, not twice
    assert file_map[".gitignore"] is None

    pycache = checks[f"structure:parasite:{FL}/flight_functions/__pycache__/"]
    assert (pycache.status, pycache.severity, pycache.mandatory) == ("fail", "major", True)
    assert pycache.diagnosis == "parasite_file" and "1 file inside" in pycache.message
    ds_store = checks["structure:parasite:MysteryInc/.DS_Store"]
    assert ds_store.status == "fail"
    parasite_ids = [i for i in checks if i.startswith("structure:parasite:")]
    assert sorted(parasite_ids) == sorted([pycache.id, ds_store.id])     # the .pyc inside is not reported again

    passes = [c for c in checks.values() if c.id.startswith("structure:file:") and c.status == "pass"]
    assert len(passes) == 8
    assert not [i for i in checks if i.startswith("structure:extra:")]

    rows = {e.path: e for e in tree}
    assert rows[f"{FL}/mission_clock.py"].status == "misplaced"
    assert rows[f"{FL}/route_math/mission_clock.py"].status == "missing"
    assert rows[f"{FL}/bonus/countdown.py"].status == "missing" and rows[f"{FL}/bonus/countdown.py"].bonus
    assert rows[".gitignore"].status == "missing"
    assert rows[f"{FL}/flight_functions/__pycache__"].status == "parasite"
    assert rows[f"{FL}/flight_functions/__pycache__/kelvin.cpython-312.pyc"].status == "parasite"
    assert rows[f"{FL}/flight_functions/kelvin.py"].status == "expected"
    assert [e.path for e in tree] == sorted([e.path for e in tree], key=lambda p: [(x.lower(), x) for x in p.split("/")])


def test_parasites_are_warnings_when_not_forbidden_explicitly(buggy: Path) -> None:
    checks, _, _, _ = analyze(buggy, demo_spec(errors=False))
    c = checks[f"structure:parasite:{FL}/flight_functions/__pycache__/"]
    assert (c.status, c.severity, c.mandatory) == ("warning", "minor", False)


def test_demo_fixed_is_clean(tmp_path: Path) -> None:
    root = snapshot_from_path(DEMO_DIR / "projects" / "mysteryinc_fixed", tmp_path / "snap", kind="demo").root
    checks, _, file_map, _ = analyze(root, demo_spec())
    assert all(c.status == "pass" for c in checks.values()), [c.id for c in checks.values() if c.status != "pass"]
    assert checks["structure:gitignore"].status == "pass"
    assert all(v is not None for v in file_map.values())


# ---------------------------------------------------------------------------------------------
# exact case (Windows is case-insensitive!)
# ---------------------------------------------------------------------------------------------


def test_case_mismatch_is_critical_even_on_case_insensitive_fs(tmp_path: Path) -> None:
    write(tmp_path, "ex/Kelvin.py")
    write(tmp_path, "Ex2/speed.py")
    spec = PracticalSpec(exercises=[
        ExerciseSpec(id="kelvin", title="k", file_path="ex/kelvin.py"),
        ExerciseSpec(id="speed", title="s", file_path="ex2/speed.py"),
    ])
    checks, tree, file_map, _ = analyze(tmp_path, spec, RootDetection())   # os.path.exists may lie here
    k = checks["structure:file:ex/kelvin.py"]
    assert (k.status, k.severity, k.diagnosis) == ("fail", "critical", "wrong_case_path")
    assert "Found at ex/Kelvin.py, expected at ex/kelvin.py" in k.message and "'Kelvin.py' instead of 'kelvin.py'" in k.message
    assert file_map["ex/kelvin.py"] == "ex/Kelvin.py"
    s = checks["structure:file:ex2/speed.py"]
    assert s.diagnosis == "wrong_case_path" and "'Ex2' instead of 'ex2'" in s.message
    assert file_map["ex2/speed.py"] == "Ex2/speed.py"
    rows = {e.path: e for e in tree}
    assert rows["ex/Kelvin.py"].status == "misplaced" and rows["ex/kelvin.py"].status == "missing"
    assert rows["ex2"].status == "missing" and rows["ex2"].kind == "directory"


def test_misplaced_with_different_case_and_closest_candidate(tmp_path: Path) -> None:
    write(tmp_path, "a/other/Utils.py")
    write(tmp_path, "b/x/utils.py")
    write(tmp_path, "b/utils_old.py")
    spec = PracticalSpec(exercises=[ExerciseSpec(id="u", title="u", file_path="b/sub/utils.py")])
    checks, _, file_map, _ = analyze(tmp_path, spec, RootDetection())
    c = checks["structure:file:b/sub/utils.py"]
    assert c.diagnosis == "misplaced_file"
    assert file_map["b/sub/utils.py"] == "b/x/utils.py"      # exact name + closest folder preferred


def test_two_expected_files_with_same_name_do_not_steal_each_other(tmp_path: Path) -> None:
    write(tmp_path, "a/utils.py")
    spec = PracticalSpec(exercises=[
        ExerciseSpec(id="a", title="a", file_path="a/utils.py"),
        ExerciseSpec(id="b", title="b", file_path="b/utils.py"),
    ])
    checks, _, file_map, _ = analyze(tmp_path, spec, RootDetection())
    assert checks["structure:file:a/utils.py"].status == "pass"
    missing = checks["structure:file:b/utils.py"]
    assert (missing.status, missing.diagnosis) == ("fail", "missing_file")
    assert "The folder b/ does not exist." in missing.message
    assert file_map == {"a/utils.py": "a/utils.py", "b/utils.py": None}


def test_missing_file_suggests_similar_name_and_extra_file_did_you_mean(tmp_path: Path) -> None:
    write(tmp_path, "ex/kelvn.py")
    write(tmp_path, "ex/helper.py")
    spec = PracticalSpec(exercises=[ExerciseSpec(id="kelvin", title="k", file_path="ex/kelvin.py")])
    checks, tree, _, _ = analyze(tmp_path, spec, RootDetection())
    missing = checks["structure:file:ex/kelvin.py"]
    assert missing.diagnosis == "missing_file" and "similar name exists: ex/kelvn.py" in missing.message
    extra = checks["structure:extra:ex/kelvn.py"]
    assert (extra.status, extra.mandatory, extra.diagnosis) == ("info", False, "extra_file")
    assert "Did you mean ex/kelvin.py?" in extra.message
    helper = checks["structure:extra:ex/helper.py"]
    assert helper.status == "info" and "Did you mean" not in helper.message
    assert {e.path: e.status for e in tree}["ex/helper.py"] == "extra"


def test_extra_files_warn_when_not_allowed(tmp_path: Path) -> None:
    write(tmp_path, "main.py")
    write(tmp_path, "other.py")
    spec = PracticalSpec(structure=StructureSpec(allow_extra_files=False),
                         exercises=[ExerciseSpec(id="m", title="m", file_path="main.py")])
    checks, _, _, _ = analyze(tmp_path, spec, RootDetection())
    assert (checks["structure:extra:other.py"].status, checks["structure:extra:other.py"].severity) == ("warning", "minor")


def test_optional_and_directory_requirements(tmp_path: Path) -> None:
    write(tmp_path, "docs/readme.md")
    spec = PracticalSpec(structure=StructureSpec(files=[
        FileRequirement(path="docs", kind="directory"),
        FileRequirement(path="assets", kind="directory"),
        FileRequirement(path="NOTES.md", required=False),
    ]))
    checks, _, file_map, _ = analyze(tmp_path, spec, RootDetection())
    assert checks["structure:file:docs"].status == "pass" and checks["structure:file:docs"].title == "Folder present"
    assert checks["structure:file:assets"].status == "fail" and file_map["assets"] is None
    optional = checks["structure:file:NOTES.md"]
    assert (optional.status, optional.severity, optional.mandatory) == ("warning", "minor", False)


# ---------------------------------------------------------------------------------------------
# parasites
# ---------------------------------------------------------------------------------------------


def test_forbidden_patterns_matching() -> None:
    patterns = ["__pycache__/", "*.pyc", ".DS_Store", "*~", "build/*.o", "*.egg-info/"]
    assert match_forbidden(patterns, "a/__pycache__", "directory") == "__pycache__/"
    assert match_forbidden(patterns, "a/__pycache__", "file") is None
    assert match_forbidden(patterns, "a/b.pyc", "file") == "*.pyc"
    assert match_forbidden(patterns, "deep/x/.DS_Store", "file") == ".DS_Store"
    assert match_forbidden(patterns, "notes.txt~", "file") == "*~"
    assert match_forbidden(patterns, "build/x.o", "file") == "build/*.o"
    assert match_forbidden(patterns, "src/build/x.o", "file") is None
    assert match_forbidden(patterns, "pkg.egg-info", "directory") == "*.egg-info/"
    assert match_forbidden(patterns, "a/B.PYC", "file") is None       # case-sensitive like the grader


def test_parasite_dirs_reported_once_and_placeholders(tmp_path: Path) -> None:
    src = tmp_path / "src"
    write(src, "main.py")
    write(src, ".idea/workspace.xml")
    write(src, ".idea/sub/x.pyc")
    write(src, "pkg/__pycache__/a.pyc")
    write(src, "pkg/__pycache__/b.pyc")
    write(src, "venv/lib/site.py")
    write(src, "notes.txt~")
    root = snapshot_from_path(src, tmp_path / "snap").root
    spec = PracticalSpec(exercises=[ExerciseSpec(id="m", title="m", file_path="main.py")])
    checks, tree, _, _ = analyze(root, spec, RootDetection())
    parasites = sorted(i for i in checks if i.startswith("structure:parasite:"))
    assert parasites == ["structure:parasite:.idea/", "structure:parasite:notes.txt~",
                         "structure:parasite:pkg/__pycache__/", "structure:parasite:venv/"]
    assert "2 files inside" in checks["structure:parasite:pkg/__pycache__/"].message
    assert "not copied" in checks["structure:parasite:venv/"].message
    assert all(checks[p].status == "warning" for p in parasites)      # default: not explicitly forbidden
    assert not [i for i in checks if i.startswith("structure:extra:")]  # venv/lib/site.py was never copied


# ---------------------------------------------------------------------------------------------
# root detection interplay
# ---------------------------------------------------------------------------------------------


def test_paths_are_shown_from_the_repository_root(tmp_path: Path) -> None:
    det = RootDetection(root="Repo", strip_prefix="MysteryInc/FirstLaunch/")
    assert repo_path("Repo/mission_clock.py", det) == "MysteryInc/FirstLaunch/mission_clock.py"
    assert repo_path("Repo", det) == "MysteryInc/FirstLaunch"
    assert repo_path("Other/x.py", det) == "Other/x.py"
    write(tmp_path, "Repo/mission_clock.py")
    write(tmp_path, "Repo/route_math/fuel_share.py")
    spec = PracticalSpec(exercises=[
        ExerciseSpec(id="mc", title="mc", file_path=f"{FL}/route_math/mission_clock.py"),
        ExerciseSpec(id="fs", title="fs", file_path=f"{FL}/route_math/fuel_share.py"),
    ])
    checks, _, file_map, _ = analyze(tmp_path, spec, det)
    c = checks[f"structure:file:{FL}/route_math/mission_clock.py"]
    assert c.message.startswith(f"Found at {FL}/mission_clock.py, expected at {FL}/route_math/mission_clock.py.")
    assert file_map[f"{FL}/route_math/mission_clock.py"] == "Repo/mission_clock.py"
    assert file_map[f"{FL}/route_math/fuel_share.py"] == "Repo/route_math/fuel_share.py"


def test_zip_like_top_folder_and_gitignore_lookalike(tmp_path: Path) -> None:
    write(tmp_path, "student-tp/main.py")
    write(tmp_path, "student-tp/gitignore.txt", "__pycache__/\n")
    write(tmp_path, ".DS_Store")                       # outside the repository root: not the student's repo
    spec = PracticalSpec(structure=StructureSpec(require_gitignore=True),
                         exercises=[ExerciseSpec(id="m", title="m", file_path="main.py")])
    checks, _, file_map, det = analyze(tmp_path, spec)
    assert det.root == "student-tp"
    assert checks["structure:file:main.py"].status == "pass" and file_map["main.py"] == "student-tp/main.py"
    gi = checks["structure:gitignore"]
    assert gi.status == "fail" and "gitignore.txt" in gi.message
    assert not [i for i in checks if i.startswith("structure:parasite:")]


def test_check_ids_are_stable_and_unique(buggy: Path) -> None:
    spec = demo_spec()
    det = detect_root(buggy, spec)
    first, _, _ = check_structure(spec, buggy, det, list_tree(buggy))
    second, _, _ = check_structure(spec, buggy, det, list_tree(buggy))
    ids = [c.id for c in first]
    assert len(ids) == len(set(ids))
    assert ids == [c.id for c in second]
    assert all(isinstance(c, CheckResult) and c.category == "structure" for c in first)
    assert all(c.severity is None for c in first if c.status in ("pass", "info", "bonus"))
    assert all(c.severity is not None for c in first if c.status in ("fail", "warning"))


def test_tree_entries_are_tree_entries(buggy: Path) -> None:
    _, tree, _, _ = analyze(buggy, demo_spec())
    assert all(isinstance(e, TreeEntry) for e in tree)
