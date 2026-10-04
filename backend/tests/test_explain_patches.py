"""The minimal patches of explain/fixes.py are real unified diffs: `git apply` accepts them and produces
exactly the intended file (only the targeted lines change, indentation and line endings are kept)."""
from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path

import pytest

from premoulinette.explain.fixes import build_fix
from premoulinette.languages.python.static_models import CallSite, FunctionInfo, ModuleInfo, ReturnInfo, StringLiteral
from premoulinette.results.models import CheckResult, Evidence, Location, ValueSnapshot

GIT = shutil.which("git")
pytestmark = pytest.mark.skipif(GIT is None, reason="git is not installed")


def module_info(source: str, path: str) -> ModuleInfo:
    """Tiny stand-in for the static analyser: only the fields the fix builders read."""
    tree = ast.parse(source)
    functions: list[FunctionInfo] = []
    strings: list[StringLiteral] = []
    calls: list[CallSite] = []
    for top in tree.body:
        fn = top.name if isinstance(top, ast.FunctionDef) else None
        for node in ast.walk(top):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                calls.append(CallSite(name=node.func.id, kind="local", line=node.lineno, col=node.col_offset, in_function=fn))
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        strings.append(StringLiteral(value=arg.value, line=arg.lineno, end_line=arg.end_lineno or arg.lineno,
                                                     col=arg.col_offset, end_col=arg.end_col_offset or 0,
                                                     in_call=node.func.id, in_function=fn))
        if isinstance(top, ast.FunctionDef):
            returns = [ReturnInfo(line=n.lineno, value_src=ast.unparse(n.value) if n.value else None,
                                  value_kind="constant" if isinstance(n.value, ast.Constant) else "expression")
                       for n in ast.walk(top) if isinstance(n, ast.Return)]
            prints = [n.lineno for n in ast.walk(top)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"]
            functions.append(FunctionInfo(name=top.name, line=top.lineno, end_line=top.end_lineno or top.lineno,
                                          returns=returns, prints=sorted(prints),
                                          has_value_return=any(r.value_src not in (None, "None") for r in returns)))
    return ModuleInfo(path=path, ok=True, functions=functions, strings=strings, calls=calls)


def check(**kw: object) -> CheckResult:
    base: dict[str, object] = {"id": "x", "category": "functions", "status": "fail", "severity": "major",
                               "title": "t", "message": "m"}
    base.update(kw)
    return CheckResult(**base)  # type: ignore[arg-type]


def git_apply(tmp_path: Path, files: dict[str, str], patch: str) -> None:
    for rel, text in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    (tmp_path / "fix.patch").write_bytes(patch.encode("utf-8"))
    result = subprocess.run(
        [GIT, "-c", "core.autocrlf=false", "apply", "--whitespace=nowarn", "fix.patch"],  # type: ignore[list-item]
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def read(tmp_path: Path, rel: str) -> str:
    return (tmp_path / rel).read_bytes().decode("utf-8")


def fixed_source(tmp_path: Path, path: str, source: str, c: CheckResult) -> str:
    fix = build_fix(c, {path: source}, {path: module_info(source, path)})
    assert fix is not None and fix.patch is not None
    git_apply(tmp_path, {path: source}, fix.patch)
    return read(tmp_path, path)


def test_str_instead_of_bool_far_apart_returns_give_two_hunks_that_apply(tmp_path: Path):
    path = "pkg/safe_speed.py"
    source = ('def is_safe(speed: int, limit: int) -> bool:\n'
              '    if speed <= limit:\n'
              '        return "True"\n'
              '    # a\n    # b\n    # c\n    # d\n'
              '    return "False"\n')
    c = check(diagnosis="str_instead_of_bool", function="is_safe", file=path)
    fix = build_fix(c, {path: source}, {path: module_info(source, path)})
    assert fix is not None and fix.patch is not None
    assert fix.patch.count("\n@@ ") == 2                      # one hunk per changed line
    assert "@@ -2,3 +2,3 @@\n     if speed <= limit:\n-        return \"True\"\n+        return True\n" in fix.patch
    assert "@@ -7,2 +7,2 @@\n     # d\n-    return \"False\"\n+    return False\n" in fix.patch
    git_apply(tmp_path, {path: source}, fix.patch)
    assert read(tmp_path, path) == source.replace('return "True"', "return True").replace('return "False"', "return False")


def test_last_line_without_newline(tmp_path: Path):
    path = "s.py"
    source = 'def is_ok(x):\n    if x:\n        return "True"\n    return "False"'
    result = fixed_source(tmp_path, path, source, check(diagnosis="str_instead_of_bool", function="is_ok", file=path))
    assert result == 'def is_ok(x):\n    if x:\n        return True\n    return False'


def test_prompt_and_rename_patches_apply(tmp_path: Path):
    path = "launch_sequence.py"
    source = ('name = input("Pilot name:")\n'
              "fuel = int(input('Starting fuel: '))\n"
              'print(f"Welcome {name}")\n')
    expected, actual = "Pilot name: ", "Pilot name:"
    c = check(id="prompt:launch_sequence:1", category="output", diagnosis="prompt_mismatch", file=path,
              location=Location(file=path, line=1),
              evidence=Evidence(expected_value=ValueSnapshot(repr=repr(expected), type="str"),
                                actual_value=ValueSnapshot(repr=repr(actual), type="str")))
    assert fixed_source(tmp_path, path, source, c) == source.replace('"Pilot name:"', '"Pilot name: "')

    path = "kelvin.py"
    source = "def to_kelvn(celsius: float) -> float:\n    return celsius + 273.15\n"
    c = check(diagnosis="wrong_function_name", function="to_kelvin", file=path, location=Location(file=path, line=1),
              message="Function 'to_kelvin' not found; a similar function 'to_kelvn' is defined (line 1).")
    assert fixed_source(tmp_path / "k", path, source, c) == source.replace("to_kelvn", "to_kelvin")


def test_print_to_return_and_new_gitignore_apply(tmp_path: Path):
    path = "kelvin.py"
    source = "def to_kelvin(celsius):\n    print(celsius + 273.15)\n"
    c = check(diagnosis="prints_instead_of_returns", function="to_kelvin", file=path)
    assert fixed_source(tmp_path, path, source, c) == "def to_kelvin(celsius):\n    return celsius + 273.15\n"

    fix = build_fix(check(id="structure:gitignore", category="structure", diagnosis="missing_gitignore"), {}, {})
    assert fix is not None and fix.patch is not None
    repo = tmp_path / "repo"
    repo.mkdir()
    git_apply(repo, {}, fix.patch)
    assert read(repo, ".gitignore") == "__pycache__/\n*.pyc\n.DS_Store\n"
