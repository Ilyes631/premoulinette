"""Helpers for ``test_fixtures_sanity.py``: run demo student code in isolated interpreters and
inspect sources with ``ast``. Stdlib only; never imports ``premoulinette``."""
from __future__ import annotations

import ast
import builtins
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RUNNER = Path(__file__).resolve().parent / "child_runner.py"
BUILTIN_NAMES = frozenset(name for name in dir(builtins) if not name.startswith("_"))


@dataclass(frozen=True)
class Call:
    file: str                 # project-relative POSIX path of the module defining the function
    function: str
    args: str                 # source of the positional arguments, e.g. "200, 250"
    expected: str | None      # exact repr of the return value; None = the function must NOT exist
    stdout: str = ""          # exact stdout written during the call

    def __str__(self) -> str:
        return f"{self.function}({self.args})"


@dataclass(frozen=True)
class Session:
    id: str            # "<exercise_id>#session<n>" (ARCHITECTURE test id)
    file: str
    transcript: str    # exactly as printed in the subject: typed input inside <kbd>…</kbd>

    @property
    def stdin(self) -> bytes:
        return "".join(f"{typed}\n" for typed in re.findall(r"<kbd>(.*?)</kbd>", self.transcript)).encode("utf-8")

    @property
    def expected_stdout(self) -> bytes:
        # Piped stdin is not echoed: drop each typed line together with the newline the user typed.
        return re.sub(r"<kbd>.*?</kbd>\n", "", self.transcript).encode("utf-8")

    def __str__(self) -> str:
        return self.id


@dataclass
class CallReport:
    import_stdout: dict[str, str] = field(default_factory=dict)
    results: dict[Call, dict[str, Any]] = field(default_factory=dict)


# ---------------------------------------------------------------------------------------------
# Execution (fresh isolated interpreter per file / session)
# ---------------------------------------------------------------------------------------------


def run_child(mode: str, file: Path, stdin: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    """Execute student code with ``python -I -B -X utf8`` (isolated, no bytecode written), cwd = file dir."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}  # -I ignores it; -X utf8 does the job
    return subprocess.run(
        [sys.executable, "-I", "-B", "-X", "utf8", str(RUNNER), mode, file.name],
        cwd=file.parent, input=stdin, capture_output=True, timeout=30, env=env, check=False,
    )


def run_calls(project: Path, calls: list[Call]) -> CallReport:
    """Import each file once (one interpreter per file) and run its calls."""
    by_file: dict[str, list[Call]] = {}
    for call in calls:
        by_file.setdefault(call.file, []).append(call)
    report = CallReport()
    for rel, file_calls in by_file.items():
        payload = json.dumps([[c.function, c.args] for c in file_calls]).encode("utf-8")
        proc = run_child("calls", project / rel, payload)
        if proc.returncode != 0:
            raise AssertionError(f"{rel}: child failed\n{proc.stderr.decode('utf-8', 'replace')}")
        data = json.loads(proc.stdout)
        report.import_stdout[rel] = data["import_stdout"]
        report.results.update(zip(file_calls, data["results"]))
    return report


def assert_call(report: CallReport, call: Call) -> None:
    result = report.results[call]
    if call.expected is None:
        assert result == {"missing": True}, f"{call} should not be defined, got {result}"
        return
    assert "exception" not in result, f"{call} raised {result['exception']}"
    assert not result.get("missing"), f"{call}: function not defined"
    assert result["repr"] == call.expected, f"{call}: expected {call.expected}, got {result['repr']}"
    assert result["stdout"] == call.stdout, f"{call}: unexpected stdout {result['stdout']!r}"


# ---------------------------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------------------------


def list_files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def snapshot(root: Path) -> dict[str, bytes]:
    return {rel: (root / rel).read_bytes() for rel in sorted(list_files(root))}


def read_source(root: Path, rel: str) -> str:
    return (root / rel).read_bytes().decode("utf-8")


# ---------------------------------------------------------------------------------------------
# Static inspection (ast only, never executes)
# ---------------------------------------------------------------------------------------------


def parse(root: Path, rel: str) -> ast.Module:
    return ast.parse(read_source(root, rel), filename=rel)


def builtin_uses(tree: ast.Module) -> dict[str, list[int]]:
    """Builtins referenced (called or not) -> lines, ignoring names the module defines itself."""
    local = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    local |= {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    local |= {
        a.arg for n in ast.walk(tree) if isinstance(n, ast.arguments) for a in n.posonlyargs + n.args + n.kwonlyargs
    }
    uses: dict[str, list[int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in BUILTIN_NAMES - local:
            uses.setdefault(node.id, []).append(node.lineno)
    return uses


def called_names(tree: ast.AST) -> set[str]:
    return {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def method_calls(tree: ast.AST) -> list[str]:
    return [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]


def input_prompts(tree: ast.Module) -> list[str]:
    """Literal prompts of the ``input(...)`` calls, in source order."""
    calls = sorted(
        (n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "input"),
        key=lambda n: (n.lineno, n.col_offset),
    )
    return [c.args[0].value for c in calls if c.args and isinstance(c.args[0], ast.Constant)]


def def_line(fn: ast.FunctionDef) -> str:
    """Rebuild the ``def`` line as written in a subject, e.g. ``def is_safe(speed: int, limit: int) -> bool:``."""
    returns = f" -> {ast.unparse(fn.returns)}" if fn.returns else ""
    return f"def {fn.name}({ast.unparse(fn.args)}){returns}:"


def top_level_functions(tree: ast.Module) -> list[str]:
    return [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
