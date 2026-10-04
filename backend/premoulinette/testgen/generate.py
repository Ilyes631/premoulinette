"""Test generation: explicit tests of the spec, derived boundary tests, heuristic edge cases.

* explicit  — the spec's own tests (expected value filled by the oracle only when missing);
* derived   — boundaries of the comparisons in trusted rules (``speed <= limit`` -> speed == limit,
              limit + 1, limit - 1), expected value computed by the oracle; never a call already tested;
* heuristic — zero / -1 / 10**6 / "" (max 3 per function), never official, warnings only.

The spec is never mutated: every generated test is a fresh copy.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel

from premoulinette.spec.models import (
    ExerciseSpec,
    FunctionSpec,
    FunctionTest,
    Origin,
    PracticalSpec,
    Provenance,
    ScriptTest,
)
from premoulinette.testgen.oracle import (
    OracleError,
    OracleOutcome,
    assignment_key,
    base_values,
    bind_literal_args,
    boundary_cases,
    expected_outcome,
    literal,
    param_kind,
)

TRUSTED_PROVENANCES: frozenset[str] = frozenset({"explicit", "user", "ai_extracted"})
DERIVED_CONFIDENCE = 0.9
AI_DERIVED_CONFIDENCE = 0.6
HEURISTIC_CONFIDENCE = 0.5
MAX_HEURISTIC_PER_FUNCTION = 3
DEFAULT_TIMEOUT_S = 5.0

# (label, value per simple parameter kind), in priority order
_HEURISTIC_VALUES: list[tuple[str, dict[str, object]]] = [
    ("zero", {"int": 0, "float": 0.0}),
    ("negative value", {"int": -1, "float": -1.0}),
    ("large value", {"int": 10**6, "float": 1e6}),
    ("empty string", {"str": ""}),
]

FunctionCategory = Literal["explicit_tests", "derived_tests", "heuristic_tests"]
_AssignmentKey = tuple[tuple[str, object], ...]


class GeneratedFunctionTest(BaseModel):
    test: FunctionTest
    exercise_id: str
    category: FunctionCategory
    rule: str | None = None          # rule / reference the expected value comes from


class GeneratedScriptTest(BaseModel):
    test: ScriptTest
    exercise_id: str
    category: Literal["explicit_tests", "output"]


def generate_tests(spec: PracticalSpec) -> tuple[list[GeneratedFunctionTest], list[GeneratedScriptTest]]:
    used_ids = {t.id for _, _, t in spec.all_function_tests()} | {t.id for _, t in spec.all_script_tests()}
    functions: list[GeneratedFunctionTest] = []
    for ex in spec.exercises:
        for fn in ex.functions:
            functions.extend(_FunctionGenerator(ex, fn, used_ids).generate())
    scripts = [
        GeneratedScriptTest(
            test=t.model_copy(deep=True),
            exercise_id=ex.id,
            category="output" if t.expected_stdout is not None else "explicit_tests",
        )
        for ex, t in spec.all_script_tests()
    ]
    return functions, scripts


def category_for(provenance: Provenance) -> FunctionCategory:
    if provenance == "derived":
        return "derived_tests"
    if provenance == "heuristic":
        return "heuristic_tests"
    return "explicit_tests"


def trusted_view(fn: FunctionSpec) -> FunctionSpec:
    """The function restricted to rules/reference a derivation may rely on."""
    rules = [r for r in fn.rules if r.origin.provenance in TRUSTED_PROVENANCES]
    reference = fn.reference if fn.origin.provenance in TRUSTED_PROVENANCES else None
    return fn.model_copy(update={"rules": rules, "reference": reference})


def _round_trips(value: object) -> bool:
    """True if ``repr(value)`` is a literal that rebuilds exactly ``value`` (same type)."""
    try:
        rebuilt = literal(repr(value))
    except OracleError:
        return False
    return type(rebuilt) is type(value) and rebuilt == value


class _FunctionGenerator:
    def __init__(self, ex: ExerciseSpec, fn: FunctionSpec, used_ids: set[str]) -> None:
        self.ex = ex
        self.fn = fn
        self.trusted = trusted_view(fn)
        self.used_ids = used_ids
        self.taken: set[_AssignmentKey] = set()
        self.timeout = fn.tests[0].timeout_s if fn.tests else DEFAULT_TIMEOUT_S
        self.params = fn.signature.params

    def generate(self) -> list[GeneratedFunctionTest]:
        explicit = [self._explicit(t) for t in self.fn.tests]
        derived = list(self._derived())
        heuristic = list(self._heuristic())
        return explicit + derived + heuristic

    # ---- explicit -----------------------------------------------------------------------------
    def _explicit(self, original: FunctionTest) -> GeneratedFunctionTest:
        test = original.model_copy(deep=True)
        outcome: OracleOutcome | None = None
        try:
            assignment = bind_literal_args(self.fn, test.args, test.kwargs)
        except OracleError:
            assignment = None
        if assignment is not None:
            self.taken.add(assignment_key(self.fn, assignment))
            outcome = expected_outcome(self.trusted, list(assignment.values()))
        needs_expected = (
            test.expected_return is None and test.expected_exception is None
            and test.expected_stdout is None and self.fn.must_return
        )
        if needs_expected and outcome is not None:
            if outcome.kind == "value" and _round_trips(outcome.value):
                test.expected_return = repr(outcome.value)
            elif outcome.kind == "raises":
                test.expected_exception = outcome.exception
        return GeneratedFunctionTest(
            test=test, exercise_id=self.ex.id, category=category_for(test.origin.provenance),
            rule=outcome.rule_text if outcome is not None else None,
        )

    # ---- derived ------------------------------------------------------------------------------
    def _derived(self) -> Iterator[GeneratedFunctionTest]:
        if not self.fn.must_return:
            return          # the rules describe what is printed, not a return value: nothing to derive
        for case in boundary_cases(self.trusted, self.trusted.rules):
            key = assignment_key(self.fn, case.assignment)
            if key in self.taken:
                continue
            args = list(case.assignment.values())
            outcome = expected_outcome(self.trusted, args)
            test = self._new_test("derived", args, outcome)
            if test is None:
                continue
            self.taken.add(key)
            from_ai = case.rule.origin.provenance == "ai_extracted" or (
                outcome.rule is not None and outcome.rule.origin.provenance == "ai_extracted"
            )
            note = f"Boundary of rule '{case.rule.when}' ({case.description})"
            if from_ai:
                note += "; the rule was extracted by AI and not found verbatim in the subject: review it"
            test.origin = Origin(
                provenance="derived",
                confidence=AI_DERIVED_CONFIDENCE if from_ai else DERIVED_CONFIDENCE,
                source=case.rule.origin.source,
                note=note,
            )
            yield GeneratedFunctionTest(test=test, exercise_id=self.ex.id, category="derived_tests", rule=outcome.rule_text)

    # ---- heuristic ----------------------------------------------------------------------------
    def _heuristic(self) -> Iterator[GeneratedFunctionTest]:
        base = base_values(self.fn)
        if any(p.name not in base for p in self.params):
            return
        produced = 0
        for label, values in _HEURISTIC_VALUES:
            if produced >= MAX_HEURISTIC_PER_FUNCTION:
                return
            for param in self.params:
                value = values.get(param_kind(param, base[param.name]) or "")
                if value is None:
                    continue
                assignment = {**base, param.name: value}
                key = assignment_key(self.fn, assignment)
                if key in self.taken:
                    continue
                args = [assignment[p.name] for p in self.params]
                outcome = expected_outcome(self.trusted, args)
                if not self.fn.must_return and outcome.kind != "error":
                    outcome = OracleOutcome("unknown", reason="the function prints its result")
                if outcome.kind == "error":
                    continue        # outside the rules' domain (e.g. division by zero): not a useful case
                test = self._new_test("heur", args, outcome, type_only_ok=True)
                if test is None:
                    continue
                self.taken.add(key)
                test.origin = Origin(
                    provenance="heuristic",
                    confidence=HEURISTIC_CONFIDENCE,
                    note=f"Heuristic edge case ({label}: {param.name} = {value!r}); not from the subject",
                )
                produced += 1
                yield GeneratedFunctionTest(
                    test=test, exercise_id=self.ex.id, category="heuristic_tests", rule=outcome.rule_text
                )
                break

    # ---- helpers ------------------------------------------------------------------------------
    def _new_test(
        self, tag: str, args: list[object], outcome: OracleOutcome, *, type_only_ok: bool = False
    ) -> FunctionTest | None:
        if not all(_round_trips(a) for a in args):
            return None
        expected_return: str | None = None
        expected_exception: str | None = None
        expected_type: str | None = None
        if outcome.kind == "value":
            if not _round_trips(outcome.value):
                return None
            expected_return = repr(outcome.value)
        elif outcome.kind == "raises":
            expected_exception = outcome.exception
        elif type_only_ok and outcome.kind == "unknown":
            expected_type = self.fn.signature.return_annotation
        else:
            return None
        return FunctionTest(
            id=self._next_id(tag),
            function=self.fn.name,
            args=[repr(a) for a in args],
            expected_return=expected_return,
            expected_type=expected_type,
            expected_exception=expected_exception,
            timeout_s=self.timeout,
        )

    def _next_id(self, tag: str) -> str:
        n = 1
        while f"{self.fn.name}#{tag}{n}" in self.used_ids:
            n += 1
        test_id = f"{self.fn.name}#{tag}{n}"
        self.used_ids.add(test_id)
        return test_id
