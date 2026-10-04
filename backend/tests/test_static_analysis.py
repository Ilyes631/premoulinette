"""languages/python/static.py — AST analysis (never executes student code)."""
from __future__ import annotations

import textwrap
from pathlib import Path

from premoulinette.languages.python.builtins_catalog import PYTHON_BUILTINS
from premoulinette.languages.python.static import analyze_file, analyze_project, analyze_source, source_lines_of


def src(code: str) -> str:
    return textwrap.dedent(code).lstrip("\n")


def calls(mod, name, **attrs):
    return [c for c in mod.calls if c.name == name and all(getattr(c, k) == v for k, v in attrs.items())]


# ---- builtins catalogue --------------------------------------------------------------------------


def test_builtins_catalog_is_stable_and_complete():
    for name in ("abs", "max", "min", "round", "sorted", "sum", "eval", "exec", "print", "input", "len", "range",
                 "int", "str", "float", "bool", "map", "__import__", "ValueError"):
        assert name in PYTHON_BUILTINS
    assert "WindowsError" not in PYTHON_BUILTINS   # host-dependent names are excluded


# ---- builtin vs local resolution -----------------------------------------------------------------


def test_builtin_call_detected_with_function_and_location():
    mod = analyze_source(src("""
        def fuel_share(total, crew):
            return round(total / crew)
    """), "a.py")
    assert mod.ok
    (c,) = calls(mod, "round")
    assert (c.kind, c.line, c.col, c.in_function, c.referenced_only) == ("builtin", 2, 11, "fuel_share", False)


def test_shadowed_builtins_are_not_builtin_calls():
    mod = analyze_source(src("""
        import math
        from os import path as max
        def abs(x):
            return x if x > 0 else -x
        sum = 0
        for min in range(3):
            pass
        def f(sorted, *round):
            print(abs(-1), max(1), sum, min, sorted([1]))
            try:
                pass
            except ValueError as len:
                len()
            with open("x") as eval:
                eval()
            return [ascii(i) for ascii in "ab"]
        g = lambda chr: chr(1)
    """), "a.py")
    assert mod.ok
    for name in ("abs", "sorted", "len", "eval", "ascii", "chr"):
        assert all(c.kind == "local" for c in calls(mod, name, referenced_only=False)), name
    assert calls(mod, "max")[0].kind == "local"
    assert calls(mod, "print")[0].kind == "builtin"
    assert calls(mod, "range")[0].kind == "builtin"
    assert calls(mod, "open")[0].kind == "builtin"
    assert not [c for c in mod.calls if c.kind == "builtin" and c.name in ("sum", "min", "abs")]
    assert {"abs", "sum", "min", "max", "math", "f", "g"} <= set(mod.defined_names)


def test_function_local_binding_does_not_shadow_other_functions():
    mod = analyze_source(src("""
        def a(xs):
            max = 3
            return max
        def b(xs):
            return max(xs)
    """), "a.py")
    (c,) = calls(mod, "max", referenced_only=False)
    assert (c.kind, c.in_function) == ("builtin", "b")


def test_global_declaration_binds_at_module_level():
    mod = analyze_source(src("""
        def setup():
            global abs
            abs = lambda x: x
        def use(x):
            return abs(x)
    """), "a.py")
    assert calls(mod, "abs", referenced_only=False)[0].kind == "local"


def test_referenced_only_builtins():
    mod = analyze_source(src("""
        def f(xs):
            g = abs
            return list(map(abs, xs)), g
    """), "a.py")
    refs = calls(mod, "abs")
    assert len(refs) == 2 and all(r.referenced_only and r.kind == "builtin" for r in refs)
    assert [r.line for r in refs] == [2, 3]
    assert calls(mod, "map")[0].referenced_only is False


def test_method_vs_module_attr_calls():
    mod = analyze_source(src("""
        import math
        import os.path
        import numpy as np
        from os import path
        def f(xs, s):
            xs.sort()
            s.upper().strip()
            os.path.join("a", "b")
            path.exists("x")
            np.array(xs)
            return math.sqrt(4)
    """), "a.py")
    kinds = {(c.name, c.kind) for c in mod.calls if not c.referenced_only}
    assert ("sort", "method") in kinds
    assert ("upper", "method") in kinds and ("strip", "method") in kinds
    assert ("math.sqrt", "module_attr") in kinds
    assert ("os.path.join", "module_attr") in kinds
    assert ("os.path.exists", "module_attr") in kinds
    assert ("numpy.array", "module_attr") in kinds
    assert [(i.module, i.names, i.line) for i in mod.imports] == [
        ("math", [], 1), ("os.path", [], 2), ("numpy", [], 3), ("os", ["path"], 4)]


def test_builtins_access_is_recorded():
    mod = analyze_source("x = __builtins__\n", "a.py")
    assert calls(mod, "__builtins__")[0].referenced_only


# ---- constructs ----------------------------------------------------------------------------------


def test_constructs_with_lines():
    mod = analyze_source(src("""
        import math
        class A:
            pass
        def fact(n):
            global G
            if n <= 1:
                return 1
            return n * fact(n - 1)
        def g(xs):
            for x in xs:
                pass
            while False:
                pass
            ys = [x for x in xs]
            h = lambda y: y
            try:
                pass
            except Exception:
                pass
            with open("f") as fh:
                pass
            if (n := len(xs)) > 1:
                pass
            match xs:
                case _:
                    pass
            return f"{n}"
        def gen():
            yield 1
    """), "a.py")
    got = {(c.name, c.line) for c in mod.constructs}
    expected = {("import", 1), ("class", 2), ("global", 5), ("recursion", 8), ("for", 10), ("while", 12),
                ("comprehension", 14), ("lambda", 15), ("try", 16), ("with", 20), ("walrus", 22), ("match", 24),
                ("fstring", 27), ("yield", 29)}
    assert expected <= got
    assert mod.function("fact").is_recursive
    assert not mod.function("g").is_recursive
    assert next(c for c in mod.constructs if c.name == "recursion").in_function == "fact"


def test_method_calling_same_name_is_not_recursion():
    mod = analyze_source(src("""
        def area(r):
            return r * r
        class Circle:
            def area(self):
                return area(self.r)
    """), "a.py")
    assert not [c for c in mod.constructs if c.name == "recursion"]


# ---- strings --------------------------------------------------------------------------------------


def test_string_literals_and_fstrings():
    mod = analyze_source(src('''
        """Module docstring."""
        def f(name, h, m):
            """Doc."""
            x = input("Pilot name: ")
            print(f"Hello {name}!", "raw")
            print("Total: " + name)
            return f"{h:02}:{m:02}"
    '''), "a.py")
    by_value = {s.value: s for s in mod.strings}
    assert "Module docstring." not in by_value and "Doc." not in by_value
    assert by_value["Pilot name: "].in_call == "input"
    assert by_value["Pilot name: "].in_function == "f"
    hello = by_value["Hello {}!"]
    assert hello.is_fstring and hello.in_call == "print" and hello.line == 5
    assert by_value["raw"].in_call == "print"
    assert by_value["Total: "].in_call is None          # not a direct argument
    clock = by_value["{}:{}"]
    assert clock.is_fstring and clock.in_call is None
    assert "02" not in by_value                          # format specs are not string literals
    assert len([c for c in mod.constructs if c.name == "fstring"]) == 2


# ---- functions -----------------------------------------------------------------------------------


def test_function_info_params_returns_prints():
    mod = analyze_source(src('''
        def is_safe(speed: int, limit: int = 100, /, *args, flag: bool = False, **kw) -> bool:
            """Check."""
            print("debug")
            if speed <= limit:
                return "True"
            return -1
        def clock(s: int) -> str:
            print(f"{s}")
            x = input()
        def nothing():
            return None
        def outer():
            def inner():
                return 1
            return inner()
    '''), "a.py")
    f = mod.function("is_safe")
    assert (f.line, f.end_line, f.return_annotation, f.docstring) == (1, 6, "bool", "Check.")
    assert [(p.name, p.kind, p.annotation, p.default) for p in f.params] == [
        ("speed", "posonly", "int", None), ("limit", "posonly", "int", "100"), ("args", "vararg", None, None),
        ("flag", "kwonly", "bool", "False"), ("kw", "varkw", None, None)]
    assert f.prints == [3] and f.has_value_return
    assert [(r.line, r.value_src, r.value_kind, r.constant_type) for r in f.returns] == [
        (5, "'True'", "constant", "str"), (6, "-1", "constant", "int")]
    c = mod.function("clock")
    assert c.prints == [8] and c.inputs == [9] and not c.has_value_return and c.returns == []
    n = mod.function("nothing")
    assert not n.has_value_return and n.returns[0].constant_type == "NoneType"
    outer = mod.function("outer")
    assert outer.returns[0].value_kind == "call"
    assert [x.name for x in mod.nested_functions] == ["inner"] and mod.nested_functions[0].nested
    assert mod.function("inner") is None


def test_redefinition_keeps_last_def():
    mod = analyze_source("def f():\n    return 1\n\ndef f(x):\n    return x\n", "a.py")
    assert len(mod.functions) == 1 and mod.function("f").line == 4


# ---- import-time effects ------------------------------------------------------------------------


def test_top_level_effects_outside_main_guard():
    mod = analyze_source(src("""
        import math
        X = int("3")
        def to_kelvin(c):
            print("inside")
            return c + 273.15
        print(to_kelvin(25))
        value = input("Value: ")
        to_kelvin(1)
        data = [1, 2]
        data.append(3)
        if __name__ == "__main__":
            print(to_kelvin(30))
            main()
    """), "a.py")
    assert mod.has_main_guard
    assert [(e.kind, e.line, e.src) for e in mod.top_level_effects] == [
        ("print", 6, "print(to_kelvin(25))"), ("input", 7, 'value = input("Value: ")'), ("call", 8, "to_kelvin(1)")]


def test_main_guard_only_module_is_clean():
    mod = analyze_source(src("""
        def main():
            print(input("x"))
        if '__main__' == __name__:
            main()
    """), "a.py")
    assert mod.has_main_guard and mod.top_level_effects == []


# ---- errors ---------------------------------------------------------------------------------------


def test_syntax_error_line_col_text():
    mod = analyze_source("def f(hours):\n    if hours == 0\n        return 0.0\n", "FIXME2.py")
    assert not mod.ok
    err = mod.syntax_error
    assert (err.kind, err.line, err.col, err.text) == ("SyntaxError", 2, 18, "    if hours == 0")
    assert "expected ':'" in err.message
    assert mod.line_count == 3


def test_indentation_and_compiler_errors():
    ind = analyze_source("def f():\n  x = 1\n    y = 2\n", "a.py")
    assert ind.syntax_error.kind == "IndentationError" and ind.syntax_error.line == 3
    tab = analyze_source("def f():\n\tif 1:\n        pass\n", "a.py")
    assert tab.syntax_error.kind == "TabError"
    ret = analyze_source("x = 1\nreturn x\n", "a.py")   # only the compiler detects this one
    assert not ret.ok and ret.syntax_error.line == 2 and ret.syntax_error.text == "return x"


def test_encoding_error_and_bom(tmp_path: Path):
    bad = tmp_path / "bad.py"
    bad.write_bytes(b"x = 1\ns = '\xe9t\xe9'\n")
    info = analyze_file(bad, "bad.py")
    assert not info.ok and info.syntax_error is None
    assert "line 2" in info.encoding_error and "UTF-8" in info.encoding_error
    bom = tmp_path / "bom.py"
    bom.write_bytes("﻿def f():\n    return 'é'\n".encode("utf-8"))
    ok = analyze_file(bom, "bom.py")
    assert ok.ok and ok.function("f") and ok.strings[0].value == "é"
    latin = tmp_path / "latin.py"
    latin.write_bytes(b"# -*- coding: latin-1 -*-\ns = '\xe9'\n")
    assert analyze_file(latin, "latin.py").ok


def test_analyze_project_only_py_and_safe_paths(tmp_path: Path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    (tmp_path.parent / "outside.py").write_text("x = 1\n", encoding="utf-8")
    out = analyze_project(tmp_path, ["pkg/a.py", "notes.txt", "../outside.py", "missing.py"])
    assert list(out) == ["pkg/a.py"]
    assert out["pkg/a.py"].path == "pkg/a.py" and out["pkg/a.py"].function("f")
    assert source_lines_of(out["pkg/a.py"]) == ["def f():", "    return 1"]


def test_student_code_is_never_executed(tmp_path: Path):
    marker = tmp_path / "executed.txt"
    code = f"open({str(marker)!r}, 'w').write('x')\nimport os\nos.system('echo pwned')\n"
    mod = analyze_source(code, "evil.py")
    assert mod.ok and not marker.exists()
