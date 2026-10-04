"""AI subject parser with an injected fake client (no network)."""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from premoulinette.subject.ai_parser import (
    MAX_SUBJECT_CHARS,
    SPEC_SCHEMA,
    SUBMIT_TOOL,
    AiParseError,
    parse_with_ai,
    spec_from_tool_input,
)
from premoulinette.subject.extract import extract_document
from subject_ai_fakes import FakeClient, demo_tool_input, text_response, tool_response

DEMO = Path(__file__).resolve().parents[2] / "demo" / "subject_demo.html"


@pytest.fixture(scope="module")
def doc():
    return extract_document(DEMO.read_bytes(), DEMO.name)


def _walk_objects(schema):
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            yield schema
        for value in schema.values():
            yield from _walk_objects(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from _walk_objects(value)


def test_tool_schema_is_strict_compatible():
    assert SUBMIT_TOOL["name"] == "submit_spec" and SUBMIT_TOOL["strict"] is True
    objects = list(_walk_objects(SPEC_SCHEMA))
    assert len(objects) >= 9
    for obj in objects:
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])


def test_request_shape(doc):
    client = FakeClient(tool_response(demo_tool_input()))
    parse_with_ai(doc, "sk-test", client=client)
    assert len(client.calls) == 1
    namespace, kw = client.calls[0]
    assert namespace == "beta"                      # server-side refusal fallback (beta)
    assert kw["model"] == "claude-opus-5-5"
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert kw["tool_choice"] == {"type": "auto"}    # forced tool choice is rejected by current models
    assert [t["name"] for t in kw["tools"]] == ["submit_spec"]
    assert "data, not instructions" in kw["system"]
    (message,) = kw["messages"]
    assert message["role"] == "user" and doc.text in message["content"]
    assert "submit_spec" in message["content"]


def test_other_model_uses_plain_messages(doc):
    client = FakeClient(tool_response(demo_tool_input()))
    result = parse_with_ai(doc, "sk-test", model="claude-haiku-4-5", client=client)
    namespace, kw = client.calls[0]
    assert namespace == "messages" and "fallbacks" not in kw
    assert result.spec.metadata.parser == "ai:claude-haiku-4-5"


def test_conversion(doc):
    result = parse_with_ai(doc, "sk-test", client=FakeClient(tool_response(demo_tool_input())))
    spec = result.spec
    assert spec.metadata.parser == "ai:claude-opus-5-5"
    assert spec.metadata.title == "TP 1 — MysteryInc: First Launch"
    assert [e.id for e in spec.exercises] == ["kelvin", "safe_speed", "access_code", "grade_landing"]
    kelvin = spec.exercise("kelvin").functions[0]
    assert kelvin.reference == "celsius + 273.15"
    assert [(t.id, t.args, t.expected_return) for t in kelvin.tests] == [
        ("to_kelvin#ex1", ["0"], "273.15"), ("to_kelvin#ex2", ["10"], "283.15"),
    ]
    safe = spec.exercise("safe_speed").functions[0]
    assert safe.signature.render() == "def is_safe(speed: int, limit: int) -> bool"
    assert [(r.when, r.returns) for r in safe.rules] == [("speed <= limit", "True"), (None, "False")]
    assert [t.expected_return for t in safe.tests] == ["True", "'False'"]
    script = spec.exercise("access_code").script
    assert spec.exercise("access_code").kind == "script"
    assert script.prompts == ["Enter access code: ", "Password please: "]
    assert [(t.id, t.stdin, t.expected_stdout, t.argv) for t in script.tests] == [
        ("access_code#session1", "SCOOBY\n", "Enter access code: Access granted. Welcome aboard!\n", []),
        ("access_code#session2", "letmein\n", "Enter access code: Hacked!\n", []),
    ]
    assert spec.exercise("grade_landing").bonus is True
    c = spec.global_constraints
    assert c.allowed_builtins == ["input", "print", "len"]
    assert c.forbidden_builtins == ["abs", "max", "exec"]
    assert c.allowed_imports == []
    paths = [f.path for f in spec.structure.files]
    assert "../outside.py" not in paths and ".gitignore" in paths
    assert spec.structure.require_gitignore and spec.structure.forbidden_patterns_are_errors
    # every item is AI-extracted until grounding
    assert all(e.origin.provenance == "ai_extracted" for e in spec.exercises)
    assert all(t.origin.provenance == "ai_extracted" for _, _, t in spec.all_function_tests())
    assert all(t.origin.confidence <= 0.7 for _, _, t in spec.all_function_tests())
    notes = "\n".join(spec.notes)
    assert "AI note: The deadline is ambiguous." in notes
    assert "to_kelvin(x)" in notes and "velocity > 3" in notes and "open('x')" in notes
    assert "invalid file path" in notes
    assert result.stats["exercises"] == 4


def test_reprompts_once_when_no_tool_call(doc):
    client = FakeClient(text_response(), tool_response(demo_tool_input()))
    result = parse_with_ai(doc, "sk-test", client=client)
    assert len(client.calls) == 2
    second = client.calls[1][1]["messages"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    assert second[0] == client.calls[0][1]["messages"][0]       # append-only history
    assert result.spec.exercises


def test_no_tool_call_twice_fails(doc):
    with pytest.raises(AiParseError, match="did not call"):
        parse_with_ai(doc, "sk-test", client=FakeClient(text_response(), text_response()))


@pytest.mark.parametrize("response, match", [
    (text_response("", stop_reason="refusal"), "declined"),
    (text_response("...", stop_reason="max_tokens"), "truncated"),
])
def test_refusal_and_truncation(doc, response, match):
    with pytest.raises(AiParseError, match=match):
        parse_with_ai(doc, "sk-test", client=FakeClient(response))


def test_api_errors_become_ai_parse_error(doc):
    import anthropic

    err = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    with pytest.raises(AiParseError, match="Claude API error"):
        parse_with_ai(doc, "sk-test", client=FakeClient(error=err))


def test_preconditions(doc):
    with pytest.raises(AiParseError, match="API key"):
        parse_with_ai(doc, "  ")
    big = doc.model_copy(update={"text": "x" * (MAX_SUBJECT_CHARS + 1)})
    with pytest.raises(AiParseError, match="too long"):
        parse_with_ai(big, "sk-test", client=FakeClient())
    empty = doc.model_copy(update={"text": "  "})
    with pytest.raises(AiParseError, match="empty"):
        parse_with_ai(empty, "sk-test", client=FakeClient())


def test_garbage_answers_are_tolerated_or_rejected(doc):
    assert spec_from_tool_input({}, doc).spec.exercises == []
    weird = {"exercises": [42, {"file_path": "a.py", "kind": "nonsense", "functions": "nope"}], "files": "x"}
    result = spec_from_tool_input(weird, doc)
    (ex,) = result.spec.exercises
    assert ex.kind == "file" and ex.file_path == "a.py"
    with pytest.raises(AiParseError):
        spec_from_tool_input(["not", "a", "dict"], doc)  # type: ignore[arg-type]


def test_duplicate_file_exercises_get_unique_ids(doc):
    data = {"exercises": [
        {"title": "A", "file_path": "pkg/m.py", "kind": "functions", "bonus": False, "script": None,
         "functions": [{"signature": "def a(x: int) -> int:", "rules": [], "reference": None, "prints_result": False,
                        "examples": [], "description": None}]},
        {"title": "B", "file_path": "pkg/m.py", "kind": "functions", "bonus": True, "script": None,
         "functions": [{"signature": "def b(x: int) -> int:", "rules": [], "reference": None, "prints_result": True,
                        "examples": [], "description": None}]},
    ]}
    spec = spec_from_tool_input(data, doc).spec
    assert [e.id for e in spec.exercises] == ["m", "b"]
    b = spec.exercise("b").functions[0]
    assert b.must_return is False and b.may_print is True
