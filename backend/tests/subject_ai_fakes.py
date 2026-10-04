"""Fake Anthropic client + canned ``submit_spec`` answers for the AI subject parser tests."""
from __future__ import annotations

import copy
from typing import Any


class _Messages:
    def __init__(self, owner: "FakeClient", namespace: str) -> None:
        self.owner = owner
        self.namespace = namespace

    def create(self, **kwargs: Any) -> Any:
        self.owner.calls.append((self.namespace, copy.deepcopy(kwargs)))
        if self.owner.error is not None:
            raise self.owner.error
        if not self.owner.responses:
            raise AssertionError("unexpected extra API call")
        return self.owner.responses.pop(0)


class _Beta:
    def __init__(self, owner: "FakeClient") -> None:
        self.messages = _Messages(owner, "beta")


class FakeClient:
    """Stands in for ``anthropic.Anthropic``: records calls, returns canned responses (dicts)."""

    def __init__(self, *responses: dict[str, Any], error: BaseException | None = None) -> None:
        self.responses = list(responses)
        self.error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.messages = _Messages(self, "messages")
        self.beta = _Beta(self)


def tool_response(data: dict[str, Any], stop_reason: str = "tool_use") -> dict[str, Any]:
    return {
        "stop_reason": stop_reason,
        "content": [
            {"type": "text", "text": "Here is the spec."},
            {"type": "tool_use", "id": "toolu_1", "name": "submit_spec", "input": data},
        ],
    }


def text_response(text: str = "I think the subject asks for...", stop_reason: str = "end_turn") -> dict[str, Any]:
    return {"stop_reason": stop_reason, "content": [{"type": "text", "text": text}]}


def _fn(signature, rules=(), reference=None, examples=(), prints=False, description=None):
    return {"signature": signature, "description": description, "rules": list(rules), "reference": reference,
            "prints_result": prints, "examples": list(examples)}


def _rule(when, returns, raises=None):
    return {"when": when, "returns": returns, "raises": raises}


def _example(call, expected, raises=None):
    return {"call": call, "expected": expected, "raises": raises}


def demo_tool_input() -> dict[str, Any]:
    """A plausible answer for demo/subject_demo.html, with a few invented / broken items."""
    base = "MysteryInc/FirstLaunch/"
    return {
        "title": "TP 1 — MysteryInc: First Launch",
        "files": [
            {"path": ".gitignore", "kind": "file", "required": True, "bonus": False},
            {"path": base + "flight_functions/kelvin.py", "kind": "file", "required": True, "bonus": False},
            {"path": base + "bonus/countdown.py", "kind": "file", "required": False, "bonus": True},
            {"path": "../outside.py", "kind": "file", "required": True, "bonus": False},
        ],
        "require_gitignore": True,
        "forbid_generated_files": True,
        "constraints": {
            "allowed_builtins": ["input", "print()", "len"],
            "forbidden_builtins": ["abs()", "max", "exec"],
            "allowed_imports": [],
            "forbidden_imports": [],
            "forbidden_methods": [],
        },
        "exercises": [
            {
                "title": "Exercise 1 — Kelvin", "file_path": base + "flight_functions/kelvin.py", "kind": "functions",
                "bonus": False, "script": None,
                "functions": [_fn(
                    "def to_kelvin(celsius: float) -> float:", reference="celsius + 273.15",
                    examples=[_example("to_kelvin(0)", "273.15"), _example("to_kelvin(10)", "283.15"),
                              _example("to_kelvin(x)", "1")],
                )],
            },
            {
                "title": "Exercise 2 — Safe speed", "file_path": base + "flight_functions/safe_speed.py",
                "kind": "functions", "bonus": False, "script": None,
                "functions": [_fn(
                    "is_safe(speed: int, limit: int) -> bool",
                    rules=[_rule("speed <= limit", "True"), _rule(None, "False"), _rule("velocity > 3", "False"),
                           _rule("open('x')", "1")],
                    examples=[_example("is_safe(200, 250)", "True"), _example("is_safe(300, 250)", "'False'")],
                )],
            },
            {
                "title": "Exercise 7 — Access code", "file_path": base + "access_code.py", "kind": "script",
                "bonus": False, "functions": [],
                "script": {
                    "prompts": ["Enter access code: ", "Password please: "],
                    "required_outputs": [],
                    "sessions": [
                        {"command": "python3 access_code.py", "steps": [
                            {"kind": "output", "text": "Enter access code: "}, {"kind": "input", "text": "SCOOBY"},
                            {"kind": "output", "text": "Access granted. Welcome aboard!\n"}]},
                        {"command": None, "steps": [
                            {"kind": "output", "text": "Enter access code: "}, {"kind": "input", "text": "letmein"},
                            {"kind": "output", "text": "Hacked!\n"}]},
                        {"command": None, "steps": [{"kind": "input", "text": "two\nlines"}]},
                    ],
                },
            },
            {
                "title": "Bonus 1 — Emoji grade", "file_path": base + "flight_functions/grade_landing.py",
                "kind": "functions", "bonus": True, "script": None,
                "functions": [_fn("def emoji_grade(vertical_speed: int) -> str:",
                                  examples=[_example("emoji_grade(0)", "'🟢'")])],
            },
            {
                "title": "Broken", "file_path": "C:\\abs\\x.py", "kind": "functions", "bonus": False,
                "functions": [], "script": None,
            },
        ],
        "notes": ["The deadline is ambiguous."],
    }
