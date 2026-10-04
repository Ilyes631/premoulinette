"""Grounding of AI-extracted items and the parse_subject pipeline (heuristic + optional AI merge)."""
from __future__ import annotations

from pathlib import Path

import pytest

from premoulinette.spec.models import (
    BehaviorRule,
    Constraints,
    ExerciseSpec,
    FunctionSignature,
    FunctionSpec,
    FunctionTest,
    Origin,
    Param,
    PracticalSpec,
    ScriptSpec,
)
from premoulinette.subject.ai_parser import spec_from_tool_input
from premoulinette.subject.extract import extract_document
from premoulinette.subject.grounding import ground_spec
from premoulinette.subject.heuristic import parse_heuristic
from premoulinette.subject.pipeline import merge_specs, parse_subject
from subject_ai_fakes import FakeClient, demo_tool_input, text_response, tool_response

DEMO = Path(__file__).resolve().parents[2] / "demo" / "subject_demo.html"


@pytest.fixture(scope="module")
def doc():
    return extract_document(DEMO.read_bytes(), DEMO.name)


def _ai() -> Origin:
    return Origin(provenance="ai_extracted", confidence=0.7)


# ---------------------------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------------------------


def test_grounding_promotes_verbatim_items_and_flags_others(doc):
    spec = spec_from_tool_input(demo_tool_input(), doc).spec
    g = ground_spec(spec, doc)
    kelvin = g.exercise("kelvin")
    assert kelvin.origin.provenance == "explicit" and kelvin.origin.source.line
    t1, t2 = kelvin.functions[0].tests
    assert t1.origin.provenance == "explicit" and t1.origin.confidence == 0.9
    assert t1.origin.source.line and "to_kelvin(0)" in t1.origin.source.excerpt
    assert t2.origin.provenance == "ai_extracted" and t2.origin.confidence <= 0.6   # to_kelvin(10): invented
    safe = g.exercise("safe_speed").functions[0]
    assert safe.rules[0].origin.provenance == "explicit"            # "speed <= limit" ... True
    assert safe.rules[1].origin.provenance == "explicit"            # otherwise ... False
    assert safe.tests[0].origin.provenance == "explicit"
    assert safe.tests[1].origin.provenance == "ai_extracted"        # 'False' (str) is not in the subject
    assert kelvin.functions[0].reference == "celsius + 273.15"      # grounded reference kept
    script = g.exercise("access_code").script
    assert script.prompts == ["Enter access code: "]                # invented prompt removed
    assert script.tests[0].origin.provenance == "explicit"
    assert script.tests[1].origin.provenance == "ai_extracted"       # "Hacked!" session invented
    c = g.global_constraints
    assert c.forbidden_builtins == ["abs", "max"]                   # "exec" not in the subject: removed
    assert c.origin.provenance == "ai_extracted"
    notes = "\n".join(g.notes)
    assert "Password please" in notes and "exec" in notes
    assert spec.exercise("access_code").script.prompts[-1] == "Password please: "   # input not mutated


def test_grounding_removes_invented_reference_and_keeps_heuristic_items(doc):
    heur = parse_heuristic(doc).spec
    assert ground_spec(heur, doc) == heur                            # heuristic items are already anchored
    fn = FunctionSpec(
        signature=FunctionSignature(name="to_kelvin", params=[Param(name="celsius")]),
        reference="celsius + 273", rules=[BehaviorRule(when="celsius < 0", returns="0.0", origin=_ai())],
        tests=[FunctionTest(id="to_kelvin#ex1", function="to_kelvin", args=["100"], expected_return="373.15",
                            origin=_ai())],
        origin=_ai(),
    )
    ex = ExerciseSpec(id="k", title="k", file_path="MysteryInc/FirstLaunch/flight_functions/kelvin.py",
                      functions=[fn], origin=_ai(), constraints=Constraints(forbidden_methods=["sort"], origin=_ai()))
    g = ground_spec(PracticalSpec(exercises=[ex]), doc)
    gfn = g.exercises[0].functions[0]
    assert gfn.reference is None and any("celsius + 273" in n for n in g.notes)
    assert gfn.rules[0].origin.provenance == "ai_extracted"
    assert gfn.tests[0].origin.provenance == "explicit"
    assert g.exercises[0].constraints.forbidden_methods == []


# ---------------------------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------------------------


def test_merge_heuristic_wins_and_ai_fills_gaps(doc):
    heur = parse_heuristic(doc).spec
    ai = ground_spec(spec_from_tool_input(demo_tool_input(), doc).spec, doc)
    merged = merge_specs(heur, ai, "claude-sonnet-5-5")
    assert merged.metadata.parser == "heuristic+ai:claude-sonnet-5-5"
    assert [e.id for e in merged.exercises] == [e.id for e in heur.exercises]      # no duplicate exercise
    kelvin = merged.exercise("kelvin").functions[0]
    # heuristic tests kept as-is; only the new call (to_kelvin(10)) is added, with a fresh id
    assert [(t.id, t.args) for t in kelvin.tests] == [
        ("to_kelvin#ex1", ["0"]), ("to_kelvin#ex2", ["100"]), ("to_kelvin#ex3", ["-273.15"]), ("to_kelvin#ex4", ["10"]),
    ]
    assert kelvin.tests[3].origin.provenance == "ai_extracted"
    safe = merged.exercise("safe_speed").functions[0]
    assert [t.expected_return for t in safe.tests] == ["True", "False"]           # AI's 'False' (str) ignored
    assert len(safe.rules) == 2
    ac = merged.exercise("access_code").script
    assert [t.id for t in ac.tests] == ["access_code#session1", "access_code#session2"]   # heuristic sessions kept
    assert ac.prompts == ["Enter access code: "]
    assert merged.exercise("emoji_grade").bonus is True and len(merged.exercise("emoji_grade").functions) == 1
    assert merged.global_constraints.forbidden_builtins == heur.global_constraints.forbidden_builtins
    assert len(merged.structure.files) == len(heur.structure.files)
    assert any("contributed" in n for n in merged.notes)


def test_merge_adds_missing_exercise_and_function(doc):
    heur = parse_heuristic(doc).spec
    extra = PracticalSpec(exercises=[
        ExerciseSpec(id="kelvin", title="Extra", file_path="extra/kelvin.py", origin=_ai(), kind="functions",
                     functions=[FunctionSpec(signature=FunctionSignature(name="to_celsius"), origin=_ai(),
                                             tests=[FunctionTest(id="to_celsius#ex1", function="to_celsius",
                                                                 args=["0"], expected_return="-273.15",
                                                                 origin=_ai())])]),
        ExerciseSpec(id="mission_clock", title="clock", file_path="MysteryInc/FirstLaunch/route_math/mission_clock.py",
                     origin=_ai(), script=ScriptSpec(prompts=["Seconds: "], origin=_ai()), kind="script"),
    ])
    merged = merge_specs(heur, extra)
    assert merged.exercises[-1].id == "kelvin_2" and merged.exercises[-1].file_path == "extra/kelvin.py"
    assert merged.exercises[-1].functions[0].tests[0].id == "to_celsius#ex1"
    clock = merged.exercise("mission_clock")
    assert clock.kind == "functions" and clock.script.prompts == ["Seconds: "]


# ---------------------------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------------------------


def test_pipeline_without_ai_never_calls_client():
    client = FakeClient()
    _, result = parse_subject(DEMO.read_bytes(), DEMO.name, ai_client=client)
    assert client.calls == [] and result.spec.metadata.parser == "heuristic"


def test_pipeline_ai_requested_without_key():
    _, result = parse_subject(DEMO.read_bytes(), DEMO.name, use_ai=True, api_key=None)
    assert result.spec.metadata.parser == "heuristic"
    assert any("no Anthropic API key" in w for w in result.warnings)


def test_pipeline_with_ai(doc):
    client = FakeClient(tool_response(demo_tool_input()))
    pdoc, result = parse_subject(DEMO.read_bytes(), DEMO.name, use_ai=True, api_key="sk-test", ai_client=client)
    assert pdoc.sha256 == doc.sha256
    assert len(client.calls) == 1
    assert result.spec.metadata.parser == "heuristic+ai:claude-sonnet-5-5"
    assert len(result.spec.exercises) == 11
    assert any("not found verbatim" in w for w in result.warnings)
    assert result.stats["function_tests"] == parse_heuristic(doc).stats["function_tests"] + 1


@pytest.mark.parametrize("client", [
    FakeClient(text_response(stop_reason="refusal")),
    FakeClient(error=RuntimeError("boom")),
])
def test_pipeline_ai_failure_falls_back_to_heuristic(client):
    _, result = parse_subject(DEMO.read_bytes(), DEMO.name, use_ai=True, api_key="sk-test", ai_client=client)
    assert result.spec.metadata.parser == "heuristic"
    assert len(result.spec.exercises) == 11
    assert any(w.startswith("AI parsing failed") for w in result.warnings)


def test_pipeline_appends_validation_warnings():
    md = b"# T\n\n## Exercise 1\n\nFile: `a.py`\n\n```python\ndef f(x: int) -> int:\n```\n"
    _, result = parse_subject(md, "t.md")
    assert any(w.startswith("Spec warning at exercises[0]") for w in result.warnings)


def test_pipeline_unreadable_document_raises_value_error():
    with pytest.raises(ValueError):
        parse_subject(b"%PDF-1.7 broken", "s.pdf")
