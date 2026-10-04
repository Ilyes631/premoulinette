"""Tiny stdlib-only child used by ``test_fixtures_sanity.py`` to execute demo student code.

Run as ``python -I -B -X utf8 child_runner.py <mode> <file>`` with cwd = the file's directory.
stdout is reconfigured to write ``\\n`` verbatim (Windows would otherwise translate it to ``\\r\\n``),
so the bytes captured by the parent are exactly what the student code wrote.

Modes
-----
``import``  import the module; its stdout/stderr pass through untouched.
``calls``   read ``[[function, "args source"], ...]`` (JSON) from stdin, import the module with
            stdout captured, call each function and print one JSON report on stdout.
``script``  run the file like ``python file.py`` (``__name__ == "__main__"``), stdin passed through.
"""
from __future__ import annotations

import ast
import importlib.util
import io
import json
import os
import runpy
import sys
from types import ModuleType


def _load(path: str) -> ModuleType:
    name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call(module: ModuleType, function: str, args_src: str) -> dict[str, object]:
    func = getattr(module, function, None)
    if func is None:
        return {"missing": True}
    args = ast.literal_eval(f"({args_src},)") if args_src.strip() else ()
    real_stdout, captured = sys.stdout, io.StringIO()
    sys.stdout = captured
    try:
        value = func(*args)
    except Exception as exc:  # report, do not crash: the parent asserts on it
        return {"exception": f"{type(exc).__name__}: {exc}", "stdout": captured.getvalue()}
    finally:
        sys.stdout = real_stdout
    return {"repr": repr(value), "type": type(value).__name__, "stdout": captured.getvalue()}


def _run_calls(path: str) -> None:
    calls = json.loads(sys.stdin.read())
    sys.stdin = io.StringIO("")  # any input() from student code hits EOF
    real_stdout, captured = sys.stdout, io.StringIO()
    sys.stdout = captured
    try:
        module = _load(path)
    finally:
        sys.stdout = real_stdout
    results = [_call(module, function, args_src) for function, args_src in calls]
    sys.stdout.write(json.dumps({"import_stdout": captured.getvalue(), "results": results}))


def main() -> None:
    sys.stdout.reconfigure(newline="\n")
    sys.stderr.reconfigure(newline="\n")
    mode, path = sys.argv[1], os.path.abspath(sys.argv[2])
    sys.path.insert(0, os.path.dirname(path))  # sibling imports, like `python file.py`
    if mode == "import":
        _load(path)
    elif mode == "calls":
        _run_calls(path)
    elif mode == "script":
        sys.argv = [os.path.basename(path)]
        runpy.run_path(path, run_name="__main__")
    else:
        raise SystemExit(f"unknown mode {mode!r}")


if __name__ == "__main__":
    main()
