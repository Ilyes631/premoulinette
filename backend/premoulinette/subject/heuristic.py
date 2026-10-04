"""Deterministic subject parser: :class:`SubjectDocument` -> :class:`PracticalSpec`.

Everything it extracts is literally present in the subject (provenance "explicit", with an excerpt,
section and line). Anything ambiguous is recorded in ``spec.notes`` rather than guessed.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import PurePosixPath

from pydantic import BaseModel, Field

from premoulinette.spec.models import (
    Constraints,
    ExerciseKind,
    ExerciseSpec,
    FunctionSpec,
    FunctionTest,
    Origin,
    PracticalSpec,
    SourceRef,
    SpecMetadata,
    explicit,
)
from premoulinette.subject.constraints import ConstraintFindings, extract_constraints
from premoulinette.subject.document import Block, SubjectDocument
from premoulinette.subject.examples import NO_OUTPUT_NOTE, ExampleDraft, extract_examples
from premoulinette.subject.rules import extract_rules
from premoulinette.subject.scripts import build_script
from premoulinette.subject.sections import ExerciseDraft, build_sections, detect_exercises
from premoulinette.subject.signatures import FoundSignature, find_signatures
from premoulinette.subject.structure import build_structure
from premoulinette.subject.textutil import excerpt

_COURSE_RE = re.compile(r"(?i)\b(?:course|cours|module|mati[èe]re|unit[ée]?)\s*:\s*([^·|\n]+?)\s*(?=[·|\n]|$)")
_DEADLINE_RE = re.compile(
    r"(?i)\b(?:deadline|due\s+date|due|date\s+limite|[ée]ch[ée]ance|[àa]\s+rendre\s+(?:avant\s+)?(?:le\s+)?)\s*:?\s*([^·|\n]+?)\s*(?=[·|\n]|$)"
)
_PRINT_VERB_RE = re.compile(r"(?i)\b(?:prints?|displays?|affiche\w*)\b")
_RETURN_VERB_RE = re.compile(r"(?i)\b(?:returns?|renvoie\w*|retourne\w*|renvoyer|retourner)\b")


class ParseResult(BaseModel):
    spec: PracticalSpec
    warnings: list[str] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)


# ----------------------------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------------------------


def _origin(block: Block, text: str | None = None, line_offset: int = 0, *, confidence: float = 1.0,
            note: str | None = None) -> Origin:
    return Origin(
        provenance="explicit", confidence=confidence, note=note,
        source=SourceRef(excerpt=excerpt(text if text is not None else block.text),
                         section=block.section or None, line=block.line + line_offset),
    )


def _resolve_file(path: str, tree_files: list[str]) -> tuple[str, str | None]:
    if not tree_files or path in tree_files:
        return path, None
    matches = [t for t in tree_files if t.endswith("/" + path)]
    if len(matches) == 1:
        return matches[0], None
    if matches:
        return matches[0], f"'{path}' matches several files of the structure tree {matches}; using '{matches[0]}'."
    return path, f"'{path}' is not listed in the expected structure tree."


def _choose_id(file_path: str, sigs: list[FoundSignature], used: set[str]) -> str:
    stem = re.sub(r"[^\w]", "_", PurePosixPath(file_path).stem) or "exercise"
    if stem not in used:
        return stem
    if len(sigs) == 1 and sigs[0].signature.name not in used:
        return sigs[0].signature.name
    n = 2
    while f"{stem}_{n}" in used:
        n += 1
    return f"{stem}_{n}"


def _description(blocks: list[Block], file_block: Block) -> str | None:
    parts: list[str] = []
    for b in blocks:
        if b.kind == "heading":
            break
        if b.kind in ("paragraph", "list_item") and b is not file_block:
            parts.append(b.text.replace("\n", " "))
        if sum(len(p) for p in parts) > 400:
            break
    text = " ".join(parts).strip()
    return excerpt(text, 500) if text else None


def _minus_global(local: ConstraintFindings, glob: Constraints) -> ConstraintFindings:
    local.forbidden_builtins = [n for n in local.forbidden_builtins if n not in glob.forbidden_builtins]
    local.forbidden_imports = [n for n in local.forbidden_imports if n not in glob.forbidden_imports]
    local.forbidden_methods = [n for n in local.forbidden_methods if n not in glob.forbidden_methods]
    local.forbidden_constructs = [n for n in local.forbidden_constructs if n not in glob.forbidden_constructs]
    local.required_constructs = [n for n in local.required_constructs if n not in glob.required_constructs]
    if local.allowed_builtins is not None and glob.allowed_builtins is not None \
            and set(local.allowed_builtins) == set(glob.allowed_builtins):
        local.allowed_builtins = None
    if local.allowed_imports is not None and glob.allowed_imports is not None \
            and set(local.allowed_imports) == set(glob.allowed_imports):
        local.allowed_imports = None
    return local


def _metadata(doc: SubjectDocument) -> SpecMetadata:
    title = doc.title or next((b.text for b in doc.blocks if b.kind == "heading"), None) or "Untitled assignment"
    course = deadline = None
    for block in doc.blocks[:12]:
        if block.kind not in ("paragraph", "list_item", "table_row"):
            continue
        if course is None and (m := _COURSE_RE.search(block.text)):
            course = m.group(1).strip()
        if deadline is None and (m := _DEADLINE_RE.search(block.text)):
            deadline = m.group(1).strip()
    return SpecMetadata(
        title=title, course=course, deadline=deadline, source_name=doc.source_name,
        source_sha256=doc.sha256, parser="heuristic",
    )


# ----------------------------------------------------------------------------------------------
# Exercise builder
# ----------------------------------------------------------------------------------------------


class _Builder:
    def __init__(self, doc: SubjectDocument, tree_files: list[str], global_c: Constraints) -> None:
        self.doc = doc
        self.tree_files = tree_files
        self.global_c = global_c
        self.used_ids: set[str] = set()
        self.fn_counters: Counter[str] = Counter()
        self.notes: list[str] = []

    def _tests_for(self, sig: FoundSignature, examples: list[ExampleDraft], ex_id: str) -> list[FunctionTest]:
        name = sig.signature.name
        tests: list[FunctionTest] = []
        for ex in examples:
            if ex.function != name:
                continue
            expected_return = ex.expected_return
            if ex.note == NO_OUTPUT_NOTE:
                if (sig.signature.return_annotation or "").strip() != "None":
                    self.notes.append(f"{ex_id}: example '{ex.excerpt.splitlines()[0]}' shows no result; ignored.")
                    continue
            self.fn_counters[name] += 1
            confidence = 1.0 if ex.note is None or ex.note == NO_OUTPUT_NOTE else 0.7
            tests.append(FunctionTest(
                id=f"{name}#ex{self.fn_counters[name]}", function=name, args=ex.args, kwargs=ex.kwargs,
                expected_return=expected_return, expected_exception=ex.expected_exception,
                expected_stdout=ex.expected_stdout,
                origin=_origin(ex.block, ex.excerpt, ex.line_offset, confidence=confidence, note=ex.note),
            ))
        return tests

    def _functions(self, ex_id: str, sigs: list[FoundSignature], blocks: list[Block], prints: bool) -> list[FunctionSpec]:
        examples = extract_examples(blocks, {s.signature.name for s in sigs})
        rule_findings = extract_rules(blocks, [s.signature for s in sigs])
        self.notes += [f"{ex_id}: {n}" for n in rule_findings.notes]
        known = {s.signature.name for s in sigs}
        for ex in examples:
            if ex.function not in known:
                self.notes.append(f"{ex_id}: example for unknown function '{ex.function}' ignored.")
        functions: list[FunctionSpec] = []
        for sig in sigs:
            name = sig.signature.name
            if sig.note:
                self.notes.append(f"{ex_id}: {sig.note}")
            tests = self._tests_for(sig, examples, ex_id)
            ref = next((r for r in rule_findings.references if r.function == name), None)
            stdout_only = bool(tests) and all(t.expected_stdout is not None and t.expected_return is None for t in tests)
            must_return, may_print = True, False
            if prints or stdout_only:
                must_return, may_print = False, True
                self.notes.append(f"{ex_id}: '{name}' is described as printing its result (must_return=False).")
            functions.append(FunctionSpec(
                signature=sig.signature,
                rules=[r.rule for r in rule_findings.rules if r.function == name],
                reference=ref.expr if ref else None,
                must_return=must_return, may_print=may_print, tests=tests,
                origin=_origin(sig.block, sig.raw, sig.line_offset),
            ))
        return functions

    def build(self, draft: ExerciseDraft) -> ExerciseSpec:
        blocks = draft.blocks()
        file_path, path_note = _resolve_file(draft.file_ref.path, self.tree_files)
        sigs = find_signatures(blocks)
        terminal = [b for b in blocks if b.kind == "code" and b.lang == "terminal"]
        kind: ExerciseKind = "functions" if sigs else ("script" if terminal else "file")
        ex_id = _choose_id(file_path, sigs, self.used_ids)
        self.used_ids.add(ex_id)
        if path_note:
            self.notes.append(f"{ex_id}: {path_note}")
        if kind == "file":
            self.notes.append(f"{ex_id}: no function signature and no terminal session found; only the file is checked.")

        section_text = " ".join(b.text for b in blocks if b.kind != "code")
        prints = kind == "functions" and bool(_PRINT_VERB_RE.search(section_text)) \
            and not _RETURN_VERB_RE.search(section_text)
        functions = self._functions(ex_id, sigs, blocks, prints) if sigs else []

        script = None
        if terminal or kind == "script":
            found = build_script(ex_id, file_path, blocks, terminal, section_text)
            self.notes += found.notes
            script = found.script
            if script is not None and kind == "functions":
                self.notes.append(f"{ex_id}: has both function signatures and terminal sessions; both are kept.")

        local = _minus_global(extract_constraints(blocks), self.global_c)
        self.notes += [f"{ex_id}: {n}" for n in local.notes]

        heading = draft.heading
        anchor = heading or draft.file_ref.block
        return ExerciseSpec(
            id=ex_id, title=draft.title, kind=kind, bonus=draft.bonus, file_path=file_path,
            description=_description(blocks, draft.file_ref.block),
            functions=functions, script=script, constraints=local.to_constraints(),
            import_side_effects_allowed=kind != "functions",
            origin=_origin(anchor, f"{anchor.text} — {draft.file_ref.path}" if heading else None),
        )


def _mark_bonus_files(spec: PracticalSpec) -> None:
    for req in spec.structure.files:
        users = [e for e in spec.exercises if e.file_path == req.path]
        if users and all(e.bonus for e in users):
            req.required = False
            req.bonus = True
        elif users and req.bonus and any(not e.bonus for e in users):
            spec.notes.append(f"'{req.path}' is in an optional folder but used by a mandatory exercise.")


def parse_stats(spec: PracticalSpec) -> dict[str, int]:
    """Counters shown with a parse result (exercises, functions, tests, rules, prompts...)."""
    fns = [f for e in spec.exercises for f in e.functions]
    return {
        "exercises": len(spec.exercises),
        "mandatory_exercises": sum(1 for e in spec.exercises if not e.bonus),
        "bonus_exercises": sum(1 for e in spec.exercises if e.bonus),
        "functions": len(fns),
        "function_tests": sum(len(f.tests) for f in fns),
        "script_tests": len(spec.all_script_tests()),
        "rules": sum(len(f.rules) for f in fns),
        "references": sum(1 for f in fns if f.reference),
        "prompts": sum(len(e.script.prompts) for e in spec.exercises if e.script),
        "structure_files": len(spec.structure.files),
        "notes": len(spec.notes),
    }


def parse_heuristic(doc: SubjectDocument) -> ParseResult:
    notes: list[str] = []
    warnings: list[str] = []
    sections = build_sections(doc)
    drafts, others = detect_exercises(sections)
    structure, tree_files = build_structure(doc, notes)

    global_findings = extract_constraints([b for s in others for b in s.all_blocks()])
    notes += global_findings.notes
    global_c = global_findings.to_constraints() or Constraints()
    if global_findings.must_not_print:
        notes.append("Functions must return their result and must not print (may_print=False).")

    builder = _Builder(doc, tree_files, global_c)
    exercises = [builder.build(d) for d in drafts]
    notes += builder.notes
    if not exercises:
        warnings.append("No exercise detected: no section names a source file (e.g. 'File: x.py').")

    spec = PracticalSpec(
        metadata=_metadata(doc), structure=structure, global_constraints=global_c,
        exercises=exercises, notes=list(dict.fromkeys(notes)),
    )
    _mark_bonus_files(spec)
    return ParseResult(spec=spec, warnings=warnings, stats=parse_stats(spec))
