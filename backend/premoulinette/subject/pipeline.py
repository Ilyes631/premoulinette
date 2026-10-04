"""Subject parsing entry point: bytes -> (SubjectDocument, ParseResult).

1. :func:`extract_document` (HTML / Markdown / text / PDF);
2. :func:`parse_heuristic` — deterministic, always run;
3. optionally (``use_ai=True`` + an API key, i.e. explicit user consent) :func:`parse_with_ai`, grounded
   against the subject text (:func:`ground_spec`) and merged *into* the heuristic result: the heuristic
   items (anchored to a subject line) always win; the AI only fills gaps (missing exercises, functions,
   rules, examples, prompts, sessions, constraints, structure files). An AI failure never breaks parsing:
   it becomes a warning and the heuristic result is returned;
4. :func:`validate_spec` issues are appended to the warnings.
"""
from __future__ import annotations

import logging
from typing import Any

from premoulinette.spec.models import (
    ExerciseSpec,
    FunctionSpec,
    FunctionTest,
    PracticalSpec,
    ScriptSpec,
    ScriptTest,
)
from premoulinette.spec.validate import validate_spec
from premoulinette.subject.ai_parser import DEFAULT_MODEL, AiParseError, parse_with_ai
from premoulinette.subject.document import SubjectDocument
from premoulinette.subject.extract import extract_document
from premoulinette.subject.grounding import ground_spec
from premoulinette.subject.heuristic import ParseResult, parse_heuristic, parse_stats

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------------------------------
# Merge (heuristic wins, AI fills gaps)
# ----------------------------------------------------------------------------------------------


class _Merger:
    def __init__(self, base: PracticalSpec, ai: PracticalSpec) -> None:
        self.spec = base.model_copy(deep=True)
        self.ai = ai
        self.test_ids: set[str] = {t.id for _, _, t in self.spec.all_function_tests()} | {
            t.id for _, t in self.spec.all_script_tests()
        }
        self.added = 0

    def _new_id(self, prefix: str, sep: str) -> str:
        n = 1
        while f"{prefix}#{sep}{n}" in self.test_ids:
            n += 1
        tid = f"{prefix}#{sep}{n}"
        self.test_ids.add(tid)
        return tid

    def _fn_test(self, t: FunctionTest) -> FunctionTest:
        t = t.model_copy(deep=True)
        t.id = self._new_id(t.function, "ex")
        return t

    def _script_test(self, t: ScriptTest, ex_id: str) -> ScriptTest:
        t = t.model_copy(deep=True)
        t.id = self._new_id(ex_id, "session")
        return t

    # ---- functions ----------------------------------------------------------------------------
    def _merge_function(self, fn: FunctionSpec, other: FunctionSpec) -> None:
        if not fn.rules and other.rules:
            fn.rules = [r.model_copy(deep=True) for r in other.rules]
            self.added += len(other.rules)
        if fn.reference is None and other.reference is not None:
            fn.reference = other.reference
            self.added += 1
        known = {(tuple(t.args), tuple(sorted(t.kwargs.items()))) for t in fn.tests}
        for t in other.tests:
            key = (tuple(t.args), tuple(sorted(t.kwargs.items())))
            if key not in known:
                known.add(key)
                fn.tests.append(self._fn_test(t))
                self.added += 1

    def _merge_script(self, ex: ExerciseSpec, other: ScriptSpec) -> None:
        if ex.script is None:
            ex.script = ScriptSpec(
                prompts=list(other.prompts), required_outputs=list(other.required_outputs),
                tests=[self._script_test(t, ex.id) for t in other.tests], origin=other.origin,
            )
            self.added += 1
            if ex.kind == "file":
                ex.kind = "script"
                ex.import_side_effects_allowed = True
            return
        if not ex.script.prompts and other.prompts:
            ex.script.prompts = list(other.prompts)
            self.added += len(other.prompts)
        if not ex.script.required_outputs and other.required_outputs:
            ex.script.required_outputs = list(other.required_outputs)
        if not ex.script.tests and other.tests:
            ex.script.tests = [self._script_test(t, ex.id) for t in other.tests]
            self.added += len(other.tests)

    def _merge_exercise(self, ex: ExerciseSpec, other: ExerciseSpec) -> None:
        by_name = {f.name: f for f in ex.functions}
        defined_elsewhere = {f.name for e in self.spec.exercises if e is not ex for f in e.functions}
        for ofn in other.functions:
            if ofn.name in by_name:
                self._merge_function(by_name[ofn.name], ofn)
            elif ofn.name not in defined_elsewhere:
                new = ofn.model_copy(deep=True)
                new.tests = [self._fn_test(t) for t in ofn.tests]
                ex.functions.append(new)
                self.added += 1
                if ex.kind == "file":
                    ex.kind = "functions"
                    ex.import_side_effects_allowed = False
        if other.script is not None:
            self._merge_script(ex, other.script)
        if ex.constraints is None and other.constraints is not None and not other.constraints.is_empty():
            ex.constraints = other.constraints.model_copy(deep=True)

    def _match(self, other: ExerciseSpec, taken: set[int]) -> ExerciseSpec | None:
        names = {f.name for f in other.functions}
        same_file = [e for e in self.spec.exercises if e.file_path == other.file_path and id(e) not in taken]
        for e in same_file:   # several exercises may share a file (bonus in the same module)
            if names and names & {f.name for f in e.functions}:
                return e
        defined = {f.name for e in self.spec.exercises for f in e.functions}
        if len(same_file) == 1 and not names & defined:
            return same_file[0]
        return None

    def _add_exercise(self, other: ExerciseSpec) -> None:
        ex = other.model_copy(deep=True)
        used = {e.id for e in self.spec.exercises}
        if ex.id in used:
            base, n = ex.id, 2
            while f"{base}_{n}" in used:
                n += 1
            ex.id = f"{base}_{n}"
        defined = {f.name for e in self.spec.exercises for f in e.functions}
        ex.functions = [f for f in ex.functions if f.name not in defined]
        for f in ex.functions:
            f.tests = [self._fn_test(t) for t in f.tests]
        if ex.script is not None:
            ex.script.tests = [self._script_test(t, ex.id) for t in ex.script.tests]
        if ex.kind == "functions" and not ex.functions:
            ex.kind = "script" if ex.script else "file"
        self.spec.exercises.append(ex)
        self.added += 1

    # ---- global -------------------------------------------------------------------------------
    def _merge_constraints(self) -> None:
        g, a = self.spec.global_constraints, self.ai.global_constraints
        if a.is_empty():
            return
        was_empty = g.is_empty()
        if g.allowed_builtins is None and a.allowed_builtins is not None:
            g.allowed_builtins = list(a.allowed_builtins)
        if g.allowed_imports is None and a.allowed_imports is not None:
            g.allowed_imports = list(a.allowed_imports)
        for field in ("forbidden_builtins", "forbidden_imports", "forbidden_methods"):
            current: list[str] = getattr(g, field)
            current += [n for n in getattr(a, field) if n not in current]
        if was_empty:
            g.origin = a.origin

    def _merge_structure(self) -> None:
        st, ast_ = self.spec.structure, self.ai.structure
        paths = {f.path for f in st.files}
        for f in ast_.files:
            if f.path not in paths:
                st.files.append(f.model_copy(deep=True))
                paths.add(f.path)
                self.added += 1
        if ast_.require_gitignore and not st.require_gitignore and ".gitignore" in paths:
            gi = next(f for f in st.files if f.path == ".gitignore")
            if gi.origin.provenance == "explicit":   # grounded: ".gitignore" is in the subject
                st.require_gitignore = True

    def run(self, model: str) -> PracticalSpec:
        taken: set[int] = set()
        for other in self.ai.exercises:
            ex = self._match(other, taken)
            if ex is None:
                self._add_exercise(other)
            else:
                taken.add(id(ex))
                self._merge_exercise(ex, other)
        self._merge_constraints()
        self._merge_structure()
        self.spec.metadata.parser = f"heuristic+ai:{model}"
        if self.spec.metadata.title == "Untitled assignment" and self.ai.metadata.title:
            self.spec.metadata.title = self.ai.metadata.title
        self.spec.notes = list(dict.fromkeys(
            self.spec.notes + self.ai.notes + [f"AI parser ({model}) contributed {self.added} item(s); review items marked AI."]
        ))
        # re-validate (unique ids...) through the model validators
        return PracticalSpec.model_validate(self.spec.model_dump())


def merge_specs(heuristic: PracticalSpec, ai_grounded: PracticalSpec, model: str = DEFAULT_MODEL) -> PracticalSpec:
    """Merge a grounded AI spec into the heuristic spec (heuristic items always win)."""
    return _Merger(heuristic, ai_grounded).run(model)


# ----------------------------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------------------------


def _issue_warnings(spec: PracticalSpec) -> list[str]:
    return [f"Spec {i.level} at {i.path}: {i.message}" for i in validate_spec(spec)]


def parse_subject(
    data: bytes,
    filename: str,
    *,
    use_ai: bool = False,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    ai_client: Any = None,
) -> tuple[SubjectDocument, ParseResult]:
    """Extract and parse a subject. ``use_ai`` must only be set with the user's consent.

    Raises ``ValueError`` (``SubjectExtractionError``) when the document cannot be read.
    """
    doc = extract_document(data, filename)
    result = parse_heuristic(doc)
    spec = result.spec
    warnings = list(result.warnings)

    if use_ai:
        if not (api_key and api_key.strip()) and ai_client is None:
            warnings.append("AI parsing was requested but no Anthropic API key is configured: heuristic result only.")
        else:
            try:
                ai = parse_with_ai(doc, api_key or "", model, client=ai_client)
                grounded = ground_spec(ai.spec, doc)
                spec = merge_specs(spec, grounded, model)
                warnings += [f"AI: {w}" for w in ai.warnings]
                n_ungrounded = _count_ungrounded(spec)
                if n_ungrounded:
                    warnings.append(
                        f"{n_ungrounded} AI-extracted item(s) were not found verbatim in the subject: review them."
                    )
            except AiParseError as exc:
                warnings.append(f"AI parsing failed ({exc}); heuristic result only.")
            except Exception as exc:  # never let the optional AI layer break subject import
                log.exception("AI subject parsing crashed")
                warnings.append(f"AI parsing failed unexpectedly ({type(exc).__name__}); heuristic result only.")

    warnings += _issue_warnings(spec)
    return doc, ParseResult(spec=spec, warnings=list(dict.fromkeys(warnings)), stats=parse_stats(spec))


def _count_ungrounded(spec: PracticalSpec) -> int:
    n = sum(1 for f in spec.structure.files if f.origin.provenance == "ai_extracted")
    for ex in spec.exercises:
        n += ex.origin.provenance == "ai_extracted"
        for fn in ex.functions:
            n += fn.origin.provenance == "ai_extracted"
            n += sum(1 for r in fn.rules if r.origin.provenance == "ai_extracted")
            n += sum(1 for t in fn.tests if t.origin.provenance == "ai_extracted")
        if ex.script:
            n += sum(1 for t in ex.script.tests if t.origin.provenance == "ai_extracted")
    return n


__all__ = ["parse_subject", "merge_specs", "AiParseError"]
