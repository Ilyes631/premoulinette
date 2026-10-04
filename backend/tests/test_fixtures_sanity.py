"""Sanity checks of the demo data itself, deliberately independent of the ``premoulinette`` package.

* The fixed demo project is checked against the subject by direct execution in isolated
  subprocesses (``python -I -B -X utf8``): silent imports, every doctest example (exact ``repr``),
  rule boundaries, and every terminal session (byte-exact raw stdout, nothing normalized).
* The buggy demo project is checked to be "fixed project + the declared bugs, nothing else", and to
  fail exactly where intended.
* The fixture variants are checked to be in sync with the fixed project (one mutation each), and
  ``fixtures/expected.json`` is checked against the ARCHITECTURE id grammar and diagnosis registry.

Generic helpers live in ``fixtures/sanity_support.py``; the subject oracle is hard-coded here.
"""
from __future__ import annotations

import ast
import html
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from conftest import DEMO_DIR, FIXTURES_DIR, REPO


def _load(name: str) -> ModuleType:
    """Load a stdlib-only helper from fixtures/ (not a package) without writing bytecode."""
    spec = importlib.util.spec_from_file_location(name, FIXTURES_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses need the module registered
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


make_fixtures = _load("make_fixtures")
support = _load("sanity_support")
Call, Session, CallReport = support.Call, support.Session, support.CallReport
run_child, run_calls, assert_call = support.run_child, support.run_calls, support.assert_call
list_files, snapshot, read_source, parse = support.list_files, support.snapshot, support.read_source, support.parse
builtin_uses, called_names, input_prompts = support.builtin_uses, support.called_names, support.input_prompts

FIXED = DEMO_DIR / "projects" / "mysteryinc_fixed"
BUGGY = DEMO_DIR / "projects" / "mysteryinc_buggy"
VARIANTS_DIR = FIXTURES_DIR / "projects"
EXPECTED_JSON = FIXTURES_DIR / "expected.json"
DEMO_DOC = REPO / "docs" / "DEMO_EXPECTATIONS.md"

SUBJECT_HTML = (DEMO_DIR / "subject_demo.html").read_bytes().decode("utf-8")
SUBJECT_TEXT = html.unescape(SUBJECT_HTML)

# ---------------------------------------------------------------------------------------------
# What the subject says (hard-coded on purpose, cross-checked against the HTML below)
# ---------------------------------------------------------------------------------------------

BASE = "MysteryInc/FirstLaunch"
KELVIN = f"{BASE}/flight_functions/kelvin.py"
SAFE_SPEED = f"{BASE}/flight_functions/safe_speed.py"
GRADE_LANDING = f"{BASE}/flight_functions/grade_landing.py"
FUEL_SHARE = f"{BASE}/route_math/fuel_share.py"
MISSION_CLOCK = f"{BASE}/route_math/mission_clock.py"
FIXME2 = f"{BASE}/FIXME2.py"
ACCESS_CODE = f"{BASE}/access_code.py"
LAUNCH_SEQUENCE = f"{BASE}/launch_sequence.py"
MAX_ALTITUDE = f"{BASE}/bonus/max_altitude.py"
COUNTDOWN = f"{BASE}/bonus/countdown.py"

SUBJECT_TREE = frozenset({
    ".gitignore", KELVIN, SAFE_SPEED, GRADE_LANDING, FUEL_SHARE, MISSION_CLOCK,
    FIXME2, ACCESS_CODE, LAUNCH_SEQUENCE, MAX_ALTITUDE, COUNTDOWN,
})

ALLOWED_BUILTINS = frozenset({"input", "print", "len", "int", "str", "float", "bool"})
FORBIDDEN_BUILTINS = frozenset({"abs", "max", "min", "round", "sorted", "sum", "eval"})

SIGNATURES: dict[str, list[str]] = {
    KELVIN: ["def to_kelvin(celsius: float) -> float:"],
    SAFE_SPEED: ["def is_safe(speed: int, limit: int) -> bool:"],
    GRADE_LANDING: [
        "def landing_grade(vertical_speed: int) -> str:",
        "def emoji_grade(vertical_speed: int) -> str:",
    ],
    FUEL_SHARE: [
        "def fuel_share(total_fuel: int, crew: int) -> int:",
        "def remaining_fuel(total_fuel: int, crew: int) -> int:",
    ],
    MISSION_CLOCK: ["def mission_clock(seconds: int) -> str:"],
    FIXME2: ["def average_speed(distance: float, hours: float) -> float:"],
    MAX_ALTITUDE: ["def max_altitude(a: int, b: int, c: int) -> int:"],
}

PROMPTS: dict[str, list[str]] = {
    ACCESS_CODE: ["Enter access code: "],
    LAUNCH_SEQUENCE: [
        "Pilot name: ", "Starting fuel: ", "Your choice: ", "Set a trap or collect evidence? (trap/evidence) ",
    ],
    COUNTDOWN: ["Countdown start: "],
}

EXAMPLES: list[Call] = [  # every `>>>` example of the subject, in order
    Call(KELVIN, "to_kelvin", "0", "273.15"),
    Call(KELVIN, "to_kelvin", "100", "373.15"),
    Call(KELVIN, "to_kelvin", "-273.15", "0.0"),
    Call(SAFE_SPEED, "is_safe", "200, 250", "True"),
    Call(SAFE_SPEED, "is_safe", "300, 250", "False"),
    Call(GRADE_LANDING, "landing_grade", "1", "'Perfect touchdown'"),
    Call(GRADE_LANDING, "landing_grade", "4", "'Hard landing'"),
    Call(GRADE_LANDING, "landing_grade", "9", "'Crash!'"),
    Call(FUEL_SHARE, "fuel_share", "400, 3", "133"),
    Call(FUEL_SHARE, "remaining_fuel", "400, 3", "1"),
    Call(FUEL_SHARE, "fuel_share", "500, 3", "166"),
    Call(MISSION_CLOCK, "mission_clock", "3725", "'01:02:05'"),
    Call(MISSION_CLOCK, "mission_clock", "0", "'00:00:00'"),
    Call(FIXME2, "average_speed", "150.0, 2.0", "75.0"),
    Call(FIXME2, "average_speed", "10.0, 0.0", "0.0"),
    Call(GRADE_LANDING, "emoji_grade", "0", "'🟢'"),
    Call(GRADE_LANDING, "emoji_grade", "7", "'🔴'"),
    Call(MAX_ALTITUDE, "max_altitude", "120, 450, 300", "450"),
    Call(MAX_ALTITUDE, "max_altitude", "-5, -2, -9", "-2"),
]

RULE_CASES: list[Call] = [  # boundaries of the subject's rules (what derived tests will probe)
    Call(SAFE_SPEED, "is_safe", "250, 250", "True"),
    Call(SAFE_SPEED, "is_safe", "251, 250", "False"),
    Call(GRADE_LANDING, "landing_grade", "2", "'Perfect touchdown'"),
    Call(GRADE_LANDING, "landing_grade", "3", "'Hard landing'"),
    Call(GRADE_LANDING, "landing_grade", "5", "'Hard landing'"),
    Call(GRADE_LANDING, "landing_grade", "6", "'Crash!'"),
    Call(GRADE_LANDING, "emoji_grade", "2", "'🟢'"),
    Call(GRADE_LANDING, "emoji_grade", "3", "'🟡'"),
    Call(GRADE_LANDING, "emoji_grade", "5", "'🟡'"),
    Call(GRADE_LANDING, "emoji_grade", "6", "'🔴'"),
    Call(FUEL_SHARE, "remaining_fuel", "500, 3", "2"),
    Call(MISSION_CLOCK, "mission_clock", "86399", "'23:59:59'"),
    Call(FIXME2, "average_speed", "10.0, 4.0", "2.5"),
    Call(MAX_ALTITUDE, "max_altitude", "1, 2, 3", "3"),
    Call(MAX_ALTITUDE, "max_altitude", "3, 2, 1", "3"),
    Call(MAX_ALTITUDE, "max_altitude", "7, 7, 1", "7"),
]

SESSIONS: list[Session] = [
    Session("access_code#session1", ACCESS_CODE,
            "Enter access code: <kbd>SCOOBY</kbd>\n"
            "Access granted. Welcome aboard!\n"),
    Session("access_code#session2", ACCESS_CODE,
            "Enter access code: <kbd>scooby</kbd>\n"
            "Access denied.\n"),
    Session("launch_sequence#session1", LAUNCH_SEQUENCE,
            "Pilot name: <kbd>Camille</kbd>\n"
            "Starting fuel: <kbd>400</kbd>\n"
            "Where's the Mystery Machine headed today?\n"
            "1 - Crystal Cove\n"
            "2 - The Old Mill\n"
            "3 - Spooky Swamp\n"
            "Your choice: <kbd>2</kbd>\n"
            "Destination: The Old Mill\n"
            "Fuel after the trip: 280\n"
            "Set a trap or collect evidence? (trap/evidence) <kbd>trap</kbd>\n"
            "Camille sets a trap at The Old Mill. Zoinks!\n"),
    Session("launch_sequence#session2", LAUNCH_SEQUENCE,
            "Pilot name: <kbd>Fred</kbd>\n"
            "Starting fuel: <kbd>100</kbd>\n"
            "Where's the Mystery Machine headed today?\n"
            "1 - Crystal Cove\n"
            "2 - The Old Mill\n"
            "3 - Spooky Swamp\n"
            "Your choice: <kbd>3</kbd>\n"
            "Not enough fuel! The gang stays home.\n"),
    Session("launch_sequence#session3", LAUNCH_SEQUENCE,
            "Pilot name: <kbd>Velma</kbd>\n"
            "Starting fuel: <kbd>250</kbd>\n"
            "Where's the Mystery Machine headed today?\n"
            "1 - Crystal Cove\n"
            "2 - The Old Mill\n"
            "3 - Spooky Swamp\n"
            "Your choice: <kbd>1</kbd>\n"
            "Destination: Crystal Cove\n"
            "Fuel after the trip: 200\n"
            "Set a trap or collect evidence? (trap/evidence) <kbd>evidence</kbd>\n"
            "Velma collects evidence at Crystal Cove. Jinkies!\n"),
    Session("countdown#session1", COUNTDOWN,
            "Countdown start: <kbd>3</kbd>\n"
            "3\n"
            "2\n"
            "1\n"
            "Liftoff!\n"),
]
SESSION_BY_ID = {s.id: s for s in SESSIONS}

# ---------------------------------------------------------------------------------------------
# What the buggy demo project contains (fixed project + these edits, nothing else)
# ---------------------------------------------------------------------------------------------

MISPLACED_CLOCK = f"{BASE}/mission_clock.py"
PYC_PARASITE = f"{BASE}/flight_functions/__pycache__/kelvin.cpython-312.pyc"
DS_STORE_PARASITE = "MysteryInc/.DS_Store"
BUGGY_TREE = (SUBJECT_TREE - {".gitignore", MISSION_CLOCK, COUNTDOWN}) | {MISPLACED_CLOCK, PYC_PARASITE, DS_STORE_PARASITE}

MAX_ALTITUDE_BODY = (
    "    # max() is forbidden, so compare by hand\n"
    "    highest = a\n"
    "    if b > highest:\n"
    "        highest = b\n"
    "    if c > highest:\n"
    "        highest = c\n"
    "    return highest\n"
)

# buggy file -> (fixed file it comes from, [(old, new), ...]); each `old` occurs exactly once.
BUGGY_EDITS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    KELVIN: (KELVIN, [("    return celsius + 273.15\n", "    return celsius + 273.15\n\n\nprint(to_kelvin(25))\n")]),
    SAFE_SPEED: (SAFE_SPEED, [("return True", 'return "True"'), ("return False", 'return "False"')]),
    GRADE_LANDING: (GRADE_LANDING, [
        ('if vertical_speed <= 2:\n        return "Perfect touchdown"',
         'if vertical_speed < 2:\n        return "Perfect touchdown"'),
        (make_fixtures.EMOJI_GRADE_BLOCK, ""),
    ]),
    FUEL_SHARE: (FUEL_SHARE, [
        ("return total_fuel // crew", "return round(total_fuel / crew)"),
        ("def remaining_fuel(", "def remaining_fuels("),
    ]),
    MISPLACED_CLOCK: (MISSION_CLOCK, [
        ('    return f"{hours:02}:{minutes:02}:{secs:02}"\n', '    print(f"{hours:02}:{minutes:02}:{secs:02}")\n'),
    ]),
    FIXME2: (FIXME2, [("    if hours == 0:\n", "    if hours == 0\n")]),
    ACCESS_CODE: (ACCESS_CODE, [('if code == "SCOOBY":', 'if code.upper() == "SCOOBY":')]),
    LAUNCH_SEQUENCE: (LAUNCH_SEQUENCE, [
        ('input("Pilot name: ")', 'input("Pilot name:")'),
        ('print("2 - The Old Mill")', 'print("2 - The Older Mill")'),
        ("or collect evidence?", "or callect evidence?"),
    ]),
    MAX_ALTITUDE: (MAX_ALTITUDE, [(MAX_ALTITUDE_BODY, "    return max(a, b, c)\n")]),
}

BUGGY_CALLS: list[Call] = [
    # leftover debug print at import, but the function itself is right
    Call(KELVIN, "to_kelvin", "0", "273.15"),
    Call(KELVIN, "to_kelvin", "100", "373.15"),
    Call(KELVIN, "to_kelvin", "-273.15", "0.0"),
    # strings instead of booleans
    Call(SAFE_SPEED, "is_safe", "200, 250", "'True'"),
    Call(SAFE_SPEED, "is_safe", "300, 250", "'False'"),
    # boundary bug: the explicit examples pass, the rule boundary does not; bonus absent
    Call(GRADE_LANDING, "landing_grade", "1", "'Perfect touchdown'"),
    Call(GRADE_LANDING, "landing_grade", "4", "'Hard landing'"),
    Call(GRADE_LANDING, "landing_grade", "9", "'Crash!'"),
    Call(GRADE_LANDING, "landing_grade", "2", "'Hard landing'"),
    Call(GRADE_LANDING, "emoji_grade", "0", None),
    # round(): 400/3 passes by luck, 500/3 rounds up; remaining_fuel misnamed
    Call(FUEL_SHARE, "fuel_share", "400, 3", "133"),
    Call(FUEL_SHARE, "fuel_share", "500, 3", "167"),
    Call(FUEL_SHARE, "remaining_fuel", "400, 3", None),
    Call(FUEL_SHARE, "remaining_fuels", "400, 3", "1"),
    # misplaced file, prints instead of returning
    Call(MISPLACED_CLOCK, "mission_clock", "3725", "None", stdout="01:02:05\n"),
    Call(MISPLACED_CLOCK, "mission_clock", "0", "None", stdout="00:00:00\n"),
    # bonus: right results with the forbidden max()
    Call(MAX_ALTITUDE, "max_altitude", "120, 450, 300", "450"),
    Call(MAX_ALTITUDE, "max_altitude", "-5, -2, -9", "-2"),
]

LAUNCH_TYPOS = [
    ("Pilot name: ", "Pilot name:"),
    ("2 - The Old Mill\n", "2 - The Older Mill\n"),
    ("or collect evidence?", "or callect evidence?"),
]


def buggy_session_stdout(session: Session) -> bytes:
    """Exact raw stdout the buggy project produces for a subject session."""
    if session.id == "access_code#session2":  # "scooby".upper() == "SCOOBY"
        return b"Enter access code: Access granted. Welcome aboard!\n"
    text = session.expected_stdout.decode("utf-8")
    if session.file == LAUNCH_SEQUENCE:
        for old, new in LAUNCH_TYPOS:
            text = text.replace(old, new)
    return text.encode("utf-8")


# ---------------------------------------------------------------------------------------------
# The hard-coded oracle really is the subject
# ---------------------------------------------------------------------------------------------


def test_examples_are_the_subject_doctests() -> None:
    assert len(EXAMPLES) == SUBJECT_TEXT.count(">>> ")
    for call in EXAMPLES:
        assert f">>> {call.function}({call.args})\n{call.expected}\n" in SUBJECT_TEXT, call


def test_sessions_are_the_subject_transcripts() -> None:
    assert len(SESSIONS) == SUBJECT_HTML.count("42sh$ python3 ")
    for session in SESSIONS:
        assert f"42sh$ python3 {Path(session.file).name}\n{session.transcript}" in SUBJECT_HTML, session
    # golden values of ARCHITECTURE.md
    first = SESSION_BY_ID["launch_sequence#session1"]
    assert first.stdin == b"Camille\n400\n2\ntrap\n"
    assert first.expected_stdout.startswith(b"Pilot name: Starting fuel: Where's the Mystery Machine headed today?\n")


def test_signatures_prompts_and_tree_are_from_the_subject() -> None:
    for lines in SIGNATURES.values():
        for line in lines:
            assert line in SUBJECT_TEXT, line
    for prompts in PROMPTS.values():
        for prompt in prompts:
            assert f'"{prompt}"' in SUBJECT_TEXT, prompt
    for rel in SUBJECT_TREE - {".gitignore"}:
        assert Path(rel).name in SUBJECT_TEXT, rel


# ---------------------------------------------------------------------------------------------
# Fixed demo project: fully correct
# ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fixed_calls() -> CallReport:
    return run_calls(FIXED, EXAMPLES + RULE_CASES)


def test_fixed_tree_is_exactly_the_subject_tree() -> None:
    assert list_files(FIXED) == SUBJECT_TREE
    assert make_fixtures.find_parasites(FIXED) == []
    gitignore = read_source(FIXED, ".gitignore").splitlines()
    assert {"__pycache__/", "*.pyc", ".DS_Store"} <= set(gitignore)


@pytest.mark.parametrize("project", [FIXED, BUGGY], ids=["fixed", "buggy"])
def test_sources_are_utf8_with_lf_newlines(project: Path) -> None:
    for rel in sorted(list_files(project)):
        if rel.endswith((".py", ".gitignore")):
            data = (project / rel).read_bytes()
            data.decode("utf-8")
            assert b"\r" not in data, rel
            assert data.endswith(b"\n"), rel


@pytest.mark.parametrize("rel", sorted(SIGNATURES))
def test_fixed_function_files_only_define_the_subject_functions(rel: str) -> None:
    tree = parse(FIXED, rel)
    assert all(isinstance(node, ast.FunctionDef) for node in tree.body), "top-level code in a function file"
    assert [support.def_line(fn) for fn in tree.body] == SIGNATURES[rel]
    assert not called_names(tree) & {"print", "input"}, "functions must return, never print/ask"


def test_fixed_project_respects_builtins_and_imports() -> None:
    for rel in sorted(SUBJECT_TREE - {".gitignore"}):
        tree = parse(FIXED, rel)
        assert not [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))], rel
        used = set(builtin_uses(tree))
        assert used <= ALLOWED_BUILTINS, f"{rel}: {sorted(used - ALLOWED_BUILTINS)}"
        assert not used & FORBIDDEN_BUILTINS, rel


@pytest.mark.parametrize("rel", sorted(PROMPTS))
def test_fixed_input_prompts_are_exact(rel: str) -> None:
    assert input_prompts(parse(FIXED, rel)) == PROMPTS[rel]


@pytest.mark.parametrize("rel", sorted(SIGNATURES))
def test_fixed_function_files_are_silent_at_import(rel: str) -> None:
    proc = run_child("import", FIXED / rel)
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, b"", b"")


@pytest.mark.parametrize("call", EXAMPLES, ids=str)
def test_fixed_subject_examples(fixed_calls: CallReport, call: Call) -> None:
    assert_call(fixed_calls, call)


@pytest.mark.parametrize("call", RULE_CASES, ids=str)
def test_fixed_rule_boundaries(fixed_calls: CallReport, call: Call) -> None:
    assert_call(fixed_calls, call)


def test_fixed_imports_print_nothing_in_call_mode(fixed_calls: CallReport) -> None:
    assert fixed_calls.import_stdout == dict.fromkeys(SIGNATURES, "")


@pytest.mark.parametrize("session", SESSIONS, ids=str)
def test_fixed_sessions_are_byte_exact(session: Session) -> None:
    proc = run_child("script", FIXED / session.file, session.stdin)
    assert proc.stderr == b""
    assert proc.returncode == 0
    assert proc.stdout == session.expected_stdout


# ---------------------------------------------------------------------------------------------
# Buggy demo project: exactly the declared bugs
# ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def buggy_calls() -> CallReport:
    return run_calls(BUGGY, BUGGY_CALLS)


def test_buggy_tree() -> None:
    assert list_files(BUGGY) == BUGGY_TREE
    assert not (BUGGY / ".gitignore").exists()
    assert not (BUGGY / COUNTDOWN).exists()
    assert make_fixtures.find_parasites(BUGGY) == [
        DS_STORE_PARASITE, f"{BASE}/flight_functions/__pycache__", PYC_PARASITE,
    ]


def test_buggy_python_files_are_fixed_files_plus_declared_bugs() -> None:
    assert set(BUGGY_EDITS) == {rel for rel in BUGGY_TREE if rel.endswith(".py")}
    for buggy_rel, (fixed_rel, edits) in BUGGY_EDITS.items():
        text = read_source(FIXED, fixed_rel)
        for old, new in edits:
            assert text.count(old) == 1, f"{fixed_rel}: {old!r}"
            text = text.replace(old, new)
        assert read_source(BUGGY, buggy_rel) == text, buggy_rel


def test_buggy_static_bugs() -> None:
    assert builtin_uses(parse(BUGGY, FUEL_SHARE)).get("round") == [3]
    assert builtin_uses(parse(BUGGY, MAX_ALTITUDE)).get("max") == [2]
    kelvin = parse(BUGGY, KELVIN)
    top_level = [n for n in kelvin.body if not isinstance(n, ast.FunctionDef)]
    assert [(n.lineno, ast.unparse(n)) for n in top_level] == [(6, "print(to_kelvin(25))")]
    returns = [n.value for n in ast.walk(parse(BUGGY, SAFE_SPEED)) if isinstance(n, ast.Return)]
    assert [v.value for v in returns if isinstance(v, ast.Constant)] == ["True", "False"]
    clock = parse(BUGGY, MISPLACED_CLOCK)
    assert not [n for n in ast.walk(clock) if isinstance(n, ast.Return)]
    assert "print" in called_names(clock)
    assert support.method_calls(parse(BUGGY, ACCESS_CODE)) == ["upper"]
    assert support.top_level_functions(parse(BUGGY, FUEL_SHARE)) == ["fuel_share", "remaining_fuels"]
    assert support.top_level_functions(parse(BUGGY, GRADE_LANDING)) == ["landing_grade"]
    assert input_prompts(parse(BUGGY, LAUNCH_SEQUENCE)) == [
        "Pilot name:", "Starting fuel: ", "Your choice: ", "Set a trap or callect evidence? (trap/evidence) ",
    ]


def test_buggy_fixme2_does_not_compile() -> None:
    with pytest.raises(SyntaxError) as info:
        compile(read_source(BUGGY, FIXME2), FIXME2, "exec")
    assert info.value.lineno == 3
    proc = run_child("import", BUGGY / FIXME2)
    assert proc.returncode != 0
    assert b"SyntaxError" in proc.stderr


def test_buggy_kelvin_prints_at_import() -> None:
    proc = run_child("import", BUGGY / KELVIN)
    assert (proc.returncode, proc.stdout, proc.stderr) == (0, b"298.15\n", b"")


@pytest.mark.parametrize("call", BUGGY_CALLS, ids=str)
def test_buggy_function_results(buggy_calls: CallReport, call: Call) -> None:
    assert_call(buggy_calls, call)


def test_buggy_import_stdout(buggy_calls: CallReport) -> None:
    expected = dict.fromkeys(buggy_calls.import_stdout, "")
    expected[KELVIN] = "298.15\n"
    assert buggy_calls.import_stdout == expected


@pytest.mark.parametrize("session", [s for s in SESSIONS if s.file != COUNTDOWN], ids=str)
def test_buggy_sessions(session: Session) -> None:
    proc = run_child("script", BUGGY / session.file, session.stdin)
    assert (proc.returncode, proc.stderr) == (0, b"")
    assert proc.stdout == buggy_session_stdout(session)
    should_pass = session.id == "access_code#session1"
    assert (proc.stdout == session.expected_stdout) is should_pass


# ---------------------------------------------------------------------------------------------
# Generated fixture variants
# ---------------------------------------------------------------------------------------------

VARIANT_CHANGED_FILES: dict[str, set[str]] = {
    "correct_project": set(),
    "wrong_bool_type": {SAFE_SPEED},
    "wrong_prompt": {LAUNCH_SEQUENCE},
    "missing_file": {FUEL_SHARE},
    "syntax_error": {FIXME2},
    "forbidden_builtin": {KELVIN},
    "wrong_function_name": {SAFE_SPEED},
    "missing_bonus": {GRADE_LANDING, MAX_ALTITUDE, COUNTDOWN},
}


def variant(name: str) -> Path:
    return VARIANTS_DIR / name


def test_variants_are_in_sync_with_the_fixed_project(tmp_path: Path) -> None:
    names = [v.name for v in make_fixtures.VARIANTS]
    assert sorted(names) == sorted(VARIANT_CHANGED_FILES)
    assert sorted(p.name for p in VARIANTS_DIR.iterdir() if p.is_dir()) == sorted(names)
    make_fixtures.build_all(tmp_path, FIXED)
    for name in names:
        assert snapshot(variant(name)) == snapshot(tmp_path / name), f"{name} is stale: run make_fixtures.py"


@pytest.mark.parametrize("name", sorted(VARIANT_CHANGED_FILES))
def test_variant_changes_only_its_files(name: str) -> None:
    base, other = snapshot(FIXED), snapshot(variant(name))
    changed = {rel for rel in base.keys() | other.keys() if base.get(rel) != other.get(rel)}
    assert changed == VARIANT_CHANGED_FILES[name]


def test_mutation_must_match_exactly_once(tmp_path: Path) -> None:
    # applying a mutation twice fails loudly: the replacement no longer matches exactly once
    spec = next(v for v in make_fixtures.VARIANTS if v.name == "wrong_function_name")
    built = make_fixtures.build_variant(spec, tmp_path, FIXED)
    with pytest.raises(make_fixtures.MutationError):
        make_fixtures.apply_mutation(built, make_fixtures.Replace(SAFE_SPEED, "def is_safe(", "def is_save("))
    with pytest.raises(make_fixtures.MutationError):
        make_fixtures.apply_mutation(built, make_fixtures.Delete(f"{BASE}/no_such_file.py"))


def test_variant_wrong_bool_type_returns_strings() -> None:
    call = Call(SAFE_SPEED, "is_safe", "200, 250", "'True'")
    assert_call(run_calls(variant("wrong_bool_type"), [call]), call)


def test_variant_forbidden_builtin_keeps_results() -> None:
    root = variant("forbidden_builtin")
    assert builtin_uses(parse(root, KELVIN)).get("abs") == [3]
    kelvin_examples = [c for c in EXAMPLES if c.file == KELVIN]
    report = run_calls(root, kelvin_examples)
    for call in kelvin_examples:
        assert_call(report, call)


def test_variant_wrong_function_name() -> None:
    assert support.top_level_functions(parse(variant("wrong_function_name"), SAFE_SPEED)) == ["is_save"]


def test_variant_syntax_error() -> None:
    with pytest.raises(SyntaxError) as info:
        compile(read_source(variant("syntax_error"), FIXME2), FIXME2, "exec")
    assert info.value.lineno == 3


def test_variant_wrong_prompt_session() -> None:
    session = SESSION_BY_ID["launch_sequence#session1"]
    proc = run_child("script", variant("wrong_prompt") / LAUNCH_SEQUENCE, session.stdin)
    expected = session.expected_stdout.replace(b"or collect evidence?", b"or callect evidence?")
    assert proc.stdout == expected != session.expected_stdout


def test_variant_missing_file_and_missing_bonus() -> None:
    assert not (variant("missing_file") / FUEL_SHARE).exists()
    root = variant("missing_bonus")
    assert not (root / BASE / "bonus").exists()
    assert support.top_level_functions(parse(root, GRADE_LANDING)) == ["landing_grade"]


# ---------------------------------------------------------------------------------------------
# expected.json: ids and codes follow ARCHITECTURE.md
# ---------------------------------------------------------------------------------------------

DIAGNOSES = frozenset({
    "missing_file", "misplaced_file", "wrong_case_path", "parasite_file", "missing_gitignore", "extra_file",
    "missing_bonus_file", "syntax_error", "indentation_error", "encoding_error", "missing_function",
    "wrong_function_name", "function_in_wrong_file", "wrong_param_count", "wrong_param_names", "wrong_annotation",
    "prints_instead_of_returns", "str_instead_of_bool", "nested_function", "wrong_value", "wrong_type",
    "number_as_str", "int_instead_of_float", "returns_none", "wrong_string", "exception", "timeout",
    "output_limit", "blocked_syscall", "unexpected_stdout", "stdout_mismatch", "prompt_mismatch", "missing_prompt",
    "missing_output", "extra_output", "exit_code", "script_crash", "eof_error", "forbidden_builtin",
    "builtin_not_allowed", "forbidden_import", "forbidden_method", "forbidden_construct",
    "missing_required_construct", "builtin_bypass", "import_side_effects", "import_crash", "import_waits_input",
    "untracked_file", "ignored_file", "dirty_tree", "bonus_not_implemented",
})
STATUSES = frozenset({"pass", "fail", "warning", "info", "bonus", "skipped"})
SEVERITIES = frozenset({"critical", "major", "minor", "style"})
ID_FAMILIES = frozenset({
    "structure", "syntax", "function", "signature", "returns", "constraint", "import_effects", "git", "test", "prompt",
})
EXERCISE_IDS = frozenset({
    "kelvin", "safe_speed", "grade_landing", "fuel_share", "mission_clock", "FIXME2", "access_code",
    "launch_sequence", "emoji_grade", "max_altitude", "countdown",
})
FUNCTIONS = frozenset({
    "to_kelvin", "is_safe", "landing_grade", "fuel_share", "remaining_fuel", "mission_clock", "average_speed",
    "emoji_grade", "max_altitude",
})
SCRIPTS = frozenset({"access_code", "launch_sequence", "countdown"})
CONSTRAINT_RULES = frozenset({"forbidden_builtin", "builtin_not_allowed", "import", "method", "construct", "required_construct"})


def check_id_prefix(prefix: str) -> None:
    """Assert an id (or id prefix) follows the stable id grammar of ARCHITECTURE.md."""
    family, _, rest = prefix.partition(":")
    assert family in ID_FAMILIES, prefix
    if rest == "":  # a whole family, e.g. "function:"
        return
    if family == "structure":
        kind, _, path = rest.partition(":")
        assert kind in {"file", "parasite", "gitignore", "extra"}, prefix
        if kind == "file":
            assert path == "" or path in SUBJECT_TREE, prefix
    elif family == "syntax":
        assert rest in SUBJECT_TREE, prefix
    elif family in {"function", "signature", "returns"}:
        exercise, _, function = rest.partition(":")
        assert exercise in EXERCISE_IDS and (function == "" or function in FUNCTIONS), prefix
    elif family == "constraint":
        exercise, _, tail = rest.partition(":")
        rule = tail.partition(":")[0]
        assert exercise in EXERCISE_IDS and (rule == "" or rule in CONSTRAINT_RULES), prefix
    elif family == "import_effects":
        assert rest in EXERCISE_IDS, prefix
    elif family == "test":
        target, _, suffix = rest.partition("#")
        assert target in FUNCTIONS | SCRIPTS, prefix
        assert re.fullmatch(r"(|ex\d*|derived\d*|heur\d*|session\d*)", suffix), prefix
    elif family == "prompt":
        assert rest.partition(":")[0] in SCRIPTS, prefix


def _as_set(value: str | list[str] | None) -> set[str]:
    if value is None:
        return set()
    return {value} if isinstance(value, str) else set(value)


def _check_entry(name: str, entry: dict[str, Any]) -> None:
    assert entry["verdict"] in {"ready", "not_ready"}, name
    assert isinstance(entry["exhaustive"], bool), name
    for det in entry["detections"]:
        check_id_prefix(det["id_prefix"])
        assert _as_set(det["status"]) and _as_set(det["status"]) <= STATUSES, det
        assert _as_set(det.get("diagnosis")) <= DIAGNOSES, det
        assert _as_set(det.get("severity")) <= SEVERITIES, det
        assert int(det.get("min_count", 1)) >= 1, det
    for prefix in entry["tolerated"] + entry["must_pass"]:
        check_id_prefix(prefix)
    blocking = [d for d in entry["detections"] if _as_set(d["status"]) & {"fail", "skipped"}]
    assert bool(blocking) is (entry["verdict"] == "not_ready"), name


def test_expected_json_follows_the_architecture() -> None:
    data = json.loads(EXPECTED_JSON.read_bytes().decode("utf-8"))
    variants = data["variants"]
    assert sorted(variants) == sorted(v.name for v in make_fixtures.VARIANTS)
    for name, entry in variants.items():
        assert (REPO / entry["path"]) == variant(name), name
        _check_entry(name, entry)
    demo = data["demo_projects"]
    assert (REPO / demo["mysteryinc_fixed"]["path"]) == FIXED
    assert demo["mysteryinc_fixed"]["same_as_variant"] in variants
    assert (REPO / demo["mysteryinc_buggy"]["path"]) == BUGGY
    _check_entry("mysteryinc_buggy", demo["mysteryinc_buggy"])


def test_demo_doc_lists_every_buggy_detection() -> None:
    doc = DEMO_DOC.read_bytes().decode("utf-8")
    buggy = json.loads(EXPECTED_JSON.read_bytes().decode("utf-8"))["demo_projects"]["mysteryinc_buggy"]
    missing = [d["id_prefix"] for d in buggy["detections"] if f"`{d['id_prefix']}" not in doc]
    assert missing == []
