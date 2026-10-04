"""Golden test: the demo subject parsed by the deterministic parser (ARCHITECTURE.md expectations)."""
from __future__ import annotations

from pathlib import Path

import pytest

from premoulinette.spec.models import PracticalSpec
from premoulinette.subject.extract import extract_document
from premoulinette.subject.heuristic import parse_heuristic
from premoulinette.subject.pipeline import parse_subject

DEMO = Path(__file__).resolve().parents[2] / "demo" / "subject_demo.html"
BASE = "MysteryInc/FirstLaunch/"


@pytest.fixture(scope="module")
def parsed():
    doc = extract_document(DEMO.read_bytes(), DEMO.name)
    return doc, parse_heuristic(doc)


@pytest.fixture(scope="module")
def spec(parsed) -> PracticalSpec:
    return parsed[1].spec


def _fn(spec: PracticalSpec, name: str):
    return next(f for e in spec.exercises for f in e.functions if f.name == name)


def test_document(parsed):
    doc, _ = parsed
    assert doc.media_type == "html"
    assert doc.title == "TP 1 — MysteryInc: First Launch"
    assert "&gt;" not in doc.text and "<kbd>" not in doc.text
    assert doc.sha256 and len(doc.sha256) == 64


def test_title_and_metadata(spec):
    assert spec.metadata.title == "TP 1 — MysteryInc: First Launch"
    assert spec.metadata.parser == "heuristic"
    assert spec.metadata.source_name == "subject_demo.html"


def test_exercises(spec):
    ids = [e.id for e in spec.exercises]
    assert ids == [
        "kelvin", "safe_speed", "grade_landing", "fuel_share", "mission_clock", "FIXME2",
        "access_code", "launch_sequence", "emoji_grade", "max_altitude", "countdown",
    ]
    mandatory = [e.id for e in spec.exercises if not e.bonus]
    bonus = [e.id for e in spec.exercises if e.bonus]
    assert len(mandatory) == 8 and len(bonus) == 3
    assert bonus == ["emoji_grade", "max_altitude", "countdown"]
    assert all(not e.required for e in spec.exercises if e.bonus)
    kinds = {e.id: e.kind for e in spec.exercises}
    assert kinds["access_code"] == kinds["launch_sequence"] == kinds["countdown"] == "script"
    assert all(kinds[i] == "functions" for i in ("kelvin", "safe_speed", "grade_landing", "fuel_share",
                                                 "mission_clock", "FIXME2", "emoji_grade", "max_altitude"))
    ex = {e.id: e for e in spec.exercises}
    assert ex["emoji_grade"].file_path == BASE + "flight_functions/grade_landing.py"
    assert ex["grade_landing"].file_path == BASE + "flight_functions/grade_landing.py"
    assert ex["FIXME2"].file_path == BASE + "FIXME2.py"
    assert [f.name for f in ex["FIXME2"].functions] == ["average_speed"]
    assert [f.name for f in ex["fuel_share"].functions] == ["fuel_share", "remaining_fuel"]
    assert ex["countdown"].file_path == BASE + "bonus/countdown.py"


def test_every_item_has_explicit_origin(spec):
    for e in spec.exercises:
        assert e.origin.provenance == "explicit" and e.origin.source and e.origin.source.line
        for f in e.functions:
            assert f.origin.provenance == "explicit" and f.origin.source.line
            for r in f.rules:
                assert r.origin.provenance == "explicit" and r.origin.source.excerpt
            for t in f.tests:
                assert t.origin.provenance == "explicit" and t.origin.source.line
        if e.script:
            for t in e.script.tests:
                assert t.origin.provenance == "explicit" and t.origin.confidence == 1.0


def test_constraints(spec):
    c = spec.global_constraints
    assert c.allowed_builtins == ["input", "print", "len", "int", "str", "float", "bool"]
    assert c.forbidden_builtins == ["abs", "max", "min", "round", "sorted", "sum", "eval"]
    assert c.allowed_imports == []
    assert c.origin.provenance == "explicit"
    for e in spec.exercises:
        assert e.constraints is None or e.constraints.is_empty()


def test_return_and_import_rules(spec):
    for e in spec.exercises:
        if e.kind == "functions":
            assert e.import_side_effects_allowed is False
            for f in e.functions:
                assert f.must_return is True and f.may_print is False
        else:
            assert e.import_side_effects_allowed is True


def test_structure(spec):
    st = spec.structure
    assert st.require_gitignore is True
    assert st.forbidden_patterns_are_errors is True
    files = {f.path: f for f in st.files}
    assert ".gitignore" in files and files[".gitignore"].required
    for rel in ("flight_functions/grade_landing.py", "flight_functions/kelvin.py", "flight_functions/safe_speed.py",
                "route_math/fuel_share.py", "route_math/mission_clock.py", "FIXME2.py", "access_code.py",
                "launch_sequence.py"):
        assert files[BASE + rel].required and not files[BASE + rel].bonus, rel
    for rel in ("bonus/countdown.py", "bonus/max_altitude.py"):
        assert not files[BASE + rel].required and files[BASE + rel].bonus, rel
    # grade_landing.py also hosts the bonus emoji_grade but is used by a mandatory exercise
    assert files[BASE + "flight_functions/grade_landing.py"].required
    assert len(st.files) == 11


def test_rules(spec):
    landing = _fn(spec, "landing_grade")
    assert [(r.when, r.returns) for r in landing.rules] == [
        ("vertical_speed <= 2", '"Perfect touchdown"'),
        ("2 < vertical_speed <= 5", '"Hard landing"'),
        ("vertical_speed > 5", '"Crash!"'),
    ]
    safe = _fn(spec, "is_safe")
    assert [(r.when, r.returns) for r in safe.rules] == [("speed <= limit", "True"), (None, "False")]
    avg = _fn(spec, "average_speed")
    assert [(r.when, r.returns) for r in avg.rules] == [("hours == 0", "0.0"), (None, "distance / hours")]
    assert len(_fn(spec, "emoji_grade").rules) == 3


def test_references(spec):
    assert _fn(spec, "to_kelvin").reference == "celsius + 273.15"
    assert _fn(spec, "fuel_share").reference == "total_fuel // crew"
    assert _fn(spec, "remaining_fuel").reference == "total_fuel % crew"
    assert _fn(spec, "mission_clock").reference == 'f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"'
    assert _fn(spec, "is_safe").reference is None
    assert _fn(spec, "max_altitude").reference is None


def test_signatures(spec):
    sig = _fn(spec, "is_safe").signature
    assert sig.render() == "def is_safe(speed: int, limit: int) -> bool"
    assert _fn(spec, "max_altitude").signature.render() == "def max_altitude(a: int, b: int, c: int) -> int"


def test_explicit_examples(spec):
    def calls(name):
        return [(t.id, t.args, t.expected_return) for t in _fn(spec, name).tests]

    assert calls("to_kelvin") == [
        ("to_kelvin#ex1", ["0"], "273.15"), ("to_kelvin#ex2", ["100"], "373.15"),
        ("to_kelvin#ex3", ["-273.15"], "0.0"),
    ]
    assert calls("is_safe") == [("is_safe#ex1", ["200", "250"], "True"), ("is_safe#ex2", ["300", "250"], "False")]
    assert calls("landing_grade") == [
        ("landing_grade#ex1", ["1"], "'Perfect touchdown'"), ("landing_grade#ex2", ["4"], "'Hard landing'"),
        ("landing_grade#ex3", ["9"], "'Crash!'"),
    ]
    assert calls("fuel_share") == [("fuel_share#ex1", ["400", "3"], "133"), ("fuel_share#ex2", ["500", "3"], "166")]
    assert calls("remaining_fuel") == [("remaining_fuel#ex1", ["400", "3"], "1")]
    assert calls("mission_clock") == [("mission_clock#ex1", ["3725"], "'01:02:05'"),
                                      ("mission_clock#ex2", ["0"], "'00:00:00'")]
    assert calls("average_speed") == [("average_speed#ex1", ["150.0", "2.0"], "75.0"),
                                      ("average_speed#ex2", ["10.0", "0.0"], "0.0")]
    assert calls("emoji_grade") == [("emoji_grade#ex1", ["0"], "'🟢'"), ("emoji_grade#ex2", ["7"], "'🔴'")]
    assert calls("max_altitude") == [("max_altitude#ex1", ["120", "450", "300"], "450"),
                                     ("max_altitude#ex2", ["-5", "-2", "-9"], "-2")]
    # the bool stays a bool, the str stays a str
    t = _fn(spec, "is_safe").tests[0]
    assert t.expected_return == "True" and t.expected_return != "'True'"


def test_launch_sequence(spec):
    ex = spec.exercise("launch_sequence")
    assert ex.script.prompts == ["Pilot name: ", "Starting fuel: ", "Your choice: ",
                                 "Set a trap or collect evidence? (trap/evidence) "]
    tests = ex.script.tests
    assert [t.id for t in tests] == ["launch_sequence#session1", "launch_sequence#session2", "launch_sequence#session3"]
    s1 = tests[0]
    assert s1.stdin == "Camille\n400\n2\ntrap\n"
    assert s1.expected_stdout.startswith("Pilot name: Starting fuel: Where's the Mystery Machine headed today?\n")
    assert s1.expected_stdout == (
        "Pilot name: Starting fuel: Where's the Mystery Machine headed today?\n"
        "1 - Crystal Cove\n2 - The Old Mill\n3 - Spooky Swamp\n"
        "Your choice: Destination: The Old Mill\nFuel after the trip: 280\n"
        "Set a trap or collect evidence? (trap/evidence) Camille sets a trap at The Old Mill. Zoinks!\n"
    )
    assert s1.expected_exit_code == 0
    assert tests[1].stdin == "Fred\n100\n3\n"
    assert tests[1].expected_stdout.endswith("Your choice: Not enough fuel! The gang stays home.\n")
    assert tests[2].stdin == "Velma\n250\n1\nevidence\n"
    assert [s.kind for s in s1.steps][:4] == ["output", "input", "output", "input"]
    assert s1.steps[0].text == "Pilot name: " and s1.steps[1].text == "Camille"


def test_access_code_and_countdown(spec):
    ac = spec.exercise("access_code")
    assert ac.script.prompts == ["Enter access code: "]
    assert [(t.id, t.stdin, t.expected_stdout) for t in ac.script.tests] == [
        ("access_code#session1", "SCOOBY\n", "Enter access code: Access granted. Welcome aboard!\n"),
        ("access_code#session2", "scooby\n", "Enter access code: Access denied.\n"),
    ]
    cd = spec.exercise("countdown")
    assert cd.bonus and cd.script.prompts == ["Countdown start: "]
    assert [(t.id, t.stdin, t.expected_stdout) for t in cd.script.tests] == [
        ("countdown#session1", "3\n", "Countdown start: 3\n2\n1\nLiftoff!\n"),
    ]


def test_ids_unique_and_spec_roundtrip(spec):
    again = PracticalSpec.model_validate_json(spec.model_dump_json())
    assert again == spec


def test_generic_parser_has_no_demo_literals():
    src_dir = Path(__file__).resolve().parents[1] / "premoulinette" / "subject"
    for path in src_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for literal in ("MysteryInc", "Mystery", "launch_sequence", "SCOOBY"):
            assert literal not in text, f"{path.name} contains demo literal {literal!r}"


def test_pipeline_on_demo_without_ai():
    doc, result = parse_subject(DEMO.read_bytes(), DEMO.name)
    assert result.spec.metadata.parser == "heuristic"
    assert len(result.spec.exercises) == 11
    assert result.stats["exercises"] == 11 and result.stats["bonus_exercises"] == 3
    assert not [w for w in result.warnings if w.startswith("Spec error")]
