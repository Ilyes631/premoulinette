"""Grounding: check that (AI-)extracted spec items are literally present in the subject.

Only items that are not already grounded are examined: provenance ``ai_extracted``, or ``explicit``
without a source line (an LLM claiming "explicit"). Items written by the heuristic parser (explicit,
with a line), by the user, or derived/heuristic tests are left untouched.

* found verbatim (modulo whitespace, quote style, arrows, HTML entities) ⇒ ``explicit``,
  confidence 0.9, source line/excerpt/section taken from the subject;
* not found ⇒ ``ai_extracted``, confidence <= 0.6 (must be reviewed);
* values without their own origin (reference expressions, prompts, required outputs, constraint
  names) that cannot be found are removed and the removal is recorded in ``spec.notes``: an invented
  reference or prompt would otherwise produce official-looking checks.
"""
from __future__ import annotations

from collections.abc import Callable

from premoulinette.spec.models import (
    BehaviorRule,
    Constraints,
    ExerciseSpec,
    FunctionSpec,
    FunctionTest,
    Origin,
    PracticalSpec,
    ScriptSpec,
    ScriptTest,
    SourceRef,
)
from premoulinette.subject.document import SubjectDocument
from premoulinette.subject.textindex import TextIndex

GROUNDED_CONFIDENCE = 0.9
PARTIAL_CONFIDENCE = 0.8
UNGROUNDED_CONFIDENCE = 0.6
WINDOW = 400                 # compact chars after an anchor where the paired value must appear
GROUNDED_NOTE = "Extracted by AI; found verbatim in the subject."
UNGROUNDED_NOTE = "Extracted by AI; NOT found verbatim in the subject: review it."
_OTHERWISE_WORDS = ("otherwise", "else", "sinon", "default", "défaut", "autrement", "other")

Hit = tuple[int, str]        # (compact index, needle)


def needs_grounding(origin: Origin) -> bool:
    if origin.provenance == "ai_extracted":
        return True
    return origin.provenance == "explicit" and (origin.source is None or origin.source.line is None)


class _Grounder:
    def __init__(self, spec: PracticalSpec, doc: SubjectDocument) -> None:
        self.spec = spec
        self.doc = doc
        self.index = TextIndex(doc.text)
        self.notes: list[str] = []

    # ---- origins ----------------------------------------------------------------------------
    def _section(self, line: int) -> str | None:
        section = None
        for block in self.doc.blocks:
            if block.line > line:
                break
            section = block.section or section
        return section

    def grounded(self, hit: Hit, confidence: float = GROUNDED_CONFIDENCE) -> Origin:
        pos, needle = hit
        line = self.index.line_of(pos)
        return Origin(
            provenance="explicit", confidence=min(confidence, GROUNDED_CONFIDENCE), note=GROUNDED_NOTE,
            source=SourceRef(excerpt=self.index.excerpt(pos, needle), section=self._section(line), line=line),
        )

    @staticmethod
    def ungrounded(origin: Origin) -> Origin:
        return Origin(
            provenance="ai_extracted", confidence=min(origin.confidence, UNGROUNDED_CONFIDENCE),
            source=origin.source, note=UNGROUNDED_NOTE,
        )

    def apply(self, origin: Origin, hit: Hit | None, confidence: float = GROUNDED_CONFIDENCE) -> Origin:
        if not needs_grounding(origin):
            return origin
        return self.grounded(hit, confidence) if hit else self.ungrounded(origin)

    # ---- search helpers ---------------------------------------------------------------------
    def first(self, *needles: str) -> Hit | None:
        for needle in needles:
            if needle and (pos := self.index.find_bounded(needle)) >= 0:
                return pos, needle
        return None

    def pair(self, anchor: str, value: str, ok: Callable[[int, int], bool] | None = None) -> Hit | None:
        """An occurrence of ``anchor`` followed (within WINDOW) by ``value`` (whole words/numbers)."""
        for pos in self.index.find_all_bounded(anchor):
            vpos = self.index.find_bounded(value, pos, pos + WINDOW + len(value) * 2)
            if vpos >= 0 and (ok is None or ok(pos, vpos)):
                return pos, anchor
        return None

    def sequence(self, needles: list[str]) -> Hit | None:
        """All needles found in order; returns the first one's position."""
        needles = [n for n in needles if n.strip()]
        if not needles:
            return None
        first_hit: Hit | None = None
        for start in self.index.find_all(needles[0]):
            pos = start
            for n in needles[1:]:
                pos = self.index.find(n, pos + 1)
                if pos < 0:
                    break
            else:
                first_hit = (start, needles[0])
                break
        return first_hit

    # ---- items ------------------------------------------------------------------------------
    def rule(self, rule: BehaviorRule) -> BehaviorRule:
        if not needs_grounding(rule.origin):
            return rule
        value = rule.returns if rule.returns is not None else rule.raises
        hit: Hit | None = None
        if rule.when is not None and value is not None:
            hit = self.pair(rule.when, value)
        elif rule.when is not None:
            hit = self.first(rule.when)
        elif value is not None:   # "otherwise" rule: the value must follow an otherwise-like word
            for pos in self.index.find_all_bounded(value):
                before = self.index.lower[max(0, pos - 60):pos]
                if any(w in before for w in _OTHERWISE_WORDS):
                    hit = (pos, value)
                    break
        rule.origin = self.apply(rule.origin, hit)
        return rule

    def test(self, test: FunctionTest) -> FunctionTest:
        if not needs_grounding(test.origin):
            return test
        call = test.call_repr()
        value = test.expected_return or test.expected_exception or test.expected_stdout
        hit = self.pair(call, value) if value is not None else self.first(call)
        test.origin = self.apply(test.origin, hit)
        return test

    def function(self, fn: FunctionSpec, ai_owned: bool) -> FunctionSpec:
        if needs_grounding(fn.origin):
            hit = self.first(f"def {fn.name}(")
            confidence = GROUNDED_CONFIDENCE
            if hit is None and (hit := self.first(fn.name)) is not None:
                confidence = PARTIAL_CONFIDENCE
            fn.origin = self.apply(fn.origin, hit, confidence)
        fn.rules = [self.rule(r) for r in fn.rules]
        fn.tests = [self.test(t) for t in fn.tests]
        if fn.reference is not None and ai_owned and self.index.find_bounded(fn.reference) < 0:
            self.notes.append(
                f"AI-proposed reference '{fn.reference}' for '{fn.name}' is not in the subject: removed."
            )
            fn.reference = None
        return fn

    def script_test(self, test: ScriptTest) -> ScriptTest:
        if not needs_grounding(test.origin):
            return test
        needles: list[str] = []
        for step in test.steps or []:
            if step.kind == "input":
                needles.append(step.text)
            else:
                needles += [line for line in step.text.split("\n") if line.strip()]
        if not needles and test.expected_stdout:
            needles = [line for line in test.expected_stdout.split("\n") if line.strip()]
        test.origin = self.apply(test.origin, self.sequence(needles))
        return test

    def script(self, script: ScriptSpec, ex_id: str, ai_owned: bool) -> ScriptSpec:
        if ai_owned:
            kept = []
            for p in script.prompts:
                if self.index.find(p) >= 0:
                    kept.append(p)
                else:
                    self.notes.append(f"{ex_id}: AI-proposed prompt {p!r} is not in the subject: removed.")
            script.prompts = kept
            outputs = []
            for out in script.required_outputs:
                if self.index.find(out) >= 0:
                    outputs.append(out)
                else:
                    self.notes.append(f"{ex_id}: AI-proposed required output {out!r} is not in the subject: removed.")
            script.required_outputs = outputs
        script.tests = [self.script_test(t) for t in script.tests]
        if needs_grounding(script.origin):
            anchor = script.prompts[0] if script.prompts else None
            script.origin = self.apply(script.origin, self.first(anchor) if anchor else None)
        return script

    def constraints(self, c: Constraints | None, where: str) -> Constraints | None:
        if c is None or not needs_grounding(c.origin):
            return c
        removed: list[str] = []

        def keep(names: list[str]) -> list[str]:
            out = []
            for n in names:
                (out if self.index.contains_word(n) else removed).append(n)
            return out

        c.forbidden_builtins = keep(c.forbidden_builtins)
        c.forbidden_imports = keep(c.forbidden_imports)
        c.forbidden_methods = keep(c.forbidden_methods)
        if c.allowed_builtins is not None:
            c.allowed_builtins = keep(c.allowed_builtins)
        if c.allowed_imports:
            c.allowed_imports = keep(c.allowed_imports)
        if removed:
            self.notes.append(f"{where}: AI-proposed constraint names not found in the subject were removed: {removed}.")
        names = (c.forbidden_builtins + c.forbidden_imports + c.forbidden_methods + (c.allowed_builtins or [])
                 + (c.allowed_imports or []))
        hit = self.first(*names) if names else None
        if hit is None and c.allowed_imports == []:
            hit = self.first("import")
        c.origin = self.apply(c.origin, hit) if not removed else self.ungrounded(c.origin)
        return c

    def exercise(self, ex: ExerciseSpec) -> ExerciseSpec:
        ai_owned = needs_grounding(ex.origin)
        if ai_owned:
            hit = self.first(ex.file_path)
            confidence = GROUNDED_CONFIDENCE
            if hit is None and (hit := self.first(ex.file_path.rsplit("/", 1)[-1])) is not None:
                confidence = PARTIAL_CONFIDENCE
            ex.origin = self.apply(ex.origin, hit, confidence)
        ex.functions = [self.function(f, ai_owned or needs_grounding(f.origin)) for f in ex.functions]
        if ex.script is not None:
            ex.script = self.script(ex.script, ex.id, ai_owned or needs_grounding(ex.script.origin))
        ex.constraints = self.constraints(ex.constraints, ex.id)
        return ex

    def run(self) -> PracticalSpec:
        st = self.spec.structure
        for req in st.files:
            if needs_grounding(req.origin):
                hit = self.first(req.path.rstrip("/"))
                confidence = GROUNDED_CONFIDENCE
                if hit is None and (hit := self.first(req.path.rstrip("/").rsplit("/", 1)[-1])) is not None:
                    confidence = PARTIAL_CONFIDENCE
                req.origin = self.apply(req.origin, hit, confidence)
        if needs_grounding(st.origin):
            grounded = [f for f in st.files if f.origin.provenance == "explicit"]
            st.origin = self.apply(st.origin, self.first(grounded[0].path) if grounded else None)
        self.spec.global_constraints = self.constraints(self.spec.global_constraints, "global constraints") \
            or Constraints()
        self.spec.exercises = [self.exercise(e) for e in self.spec.exercises]
        self.spec.notes = list(dict.fromkeys(self.spec.notes + self.notes))
        return self.spec


def ground_spec(spec: PracticalSpec, doc: SubjectDocument) -> PracticalSpec:
    """Return a copy of ``spec`` where ungrounded items are marked (or removed) — see module doc."""
    return _Grounder(spec.model_copy(deep=True), doc).run()
