"""Interactive scripts: quoted input() prompts and example terminal sessions -> :class:`ScriptSpec`."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from premoulinette.spec.models import Origin, ScriptSpec, ScriptTest, SourceRef, explicit
from premoulinette.subject.document import Block
from premoulinette.subject.textutil import excerpt
from premoulinette.subject.transcript import command_script_and_argv, split_sessions

PROMPT_ENDINGS = (": ", "? ", ") ", "> ")
_QUOTED_RE = re.compile(r'"([^"\n]+)"')
_INPUT_WORDS_RE = re.compile(
    r"(?i)\b(?:asks?|prompts?|input|enters?|types?|reads?|demande\w*|saisi\w*|entr\w+|tape\w*|lit|lire)\b"
)


@dataclass
class ScriptFindings:
    script: ScriptSpec | None = None
    notes: list[str] = field(default_factory=list)


def _unquote(code: str) -> str | None:
    c = code
    for q in ('"', "'"):
        if len(c) >= 2 and c.startswith(q) and c.endswith(q):
            return c[1:-1]
    return None


def extract_prompts(blocks: list[Block]) -> list[tuple[str, Block]]:
    """Quoted strings ending like a prompt (": ", "? ", ") ") in order, trailing spaces preserved."""
    found: list[tuple[str, Block]] = []
    seen: set[str] = set()
    for block in blocks:
        if block.kind == "code":
            continue
        candidates = [_unquote(c) for c in block.inline_code]
        if not block.inline_code:
            candidates = _QUOTED_RE.findall(block.text)
        for inner in candidates:
            if inner and inner.endswith(PROMPT_ENDINGS) and inner.strip() and inner not in seen:
                seen.add(inner)
                found.append((inner, block))
    return found


def _session_prompts(tests: list[ScriptTest]) -> list[str] | None:
    """Prompts derived from the richest session (text right before each input), if all are non-empty."""
    best = max(tests, key=lambda t: sum(1 for s in (t.steps or []) if s.kind == "input"), default=None)
    if best is None or not best.steps:
        return None
    prompts: list[str] = []
    prev = None
    for step in best.steps:
        if step.kind == "input":
            if prev is None or prev.kind != "output":
                return None
            prompt = prev.text.rsplit("\n", 1)[-1]
            if not prompt:
                return None
            prompts.append(prompt)
        prev = step
    return prompts or None


def build_script(
    exercise_id: str, file_path: str, blocks: list[Block], terminal_blocks: list[Block], section_text: str
) -> ScriptFindings:
    out = ScriptFindings()
    prompts_found = extract_prompts(blocks)
    prompts = [p for p, _ in prompts_found]
    tests: list[ScriptTest] = []
    expected_script = PurePosixPath(file_path).name
    mentions_input = bool(prompts) or bool(_INPUT_WORDS_RE.search(section_text))
    for block in terminal_blocks:
        for command, steps, confidence in split_sessions(block.text, block.inputs, known_prompts=prompts or None):
            n = len(tests) + 1
            script, argv, problem = command_script_and_argv(command) if command else (None, [], None)
            if problem:
                out.notes.append(f"{exercise_id} session {n}: {problem}.")
            if script and PurePosixPath(script.replace("\\", "/")).name != expected_script:
                out.notes.append(
                    f"{exercise_id} session {n} runs '{script}' but the exercise file is '{expected_script}'."
                )
            provenance = "explicit"
            note = None
            if confidence < 0.5:
                if mentions_input:
                    provenance = "heuristic"
                    note = "Typed input could not be told apart from program output; review this session."
                    out.notes.append(f"{exercise_id} session {n}: {note}")
                else:
                    confidence = 0.8
                    note = "No input marker: the whole session is treated as program output."
            elif confidence < 1.0:
                note = "Typed input detected from the known prompts (no explicit input markers)."
            origin = Origin(
                provenance=provenance, confidence=confidence, note=note,
                source=SourceRef(excerpt=excerpt(block.text), section=block.section or None, line=block.line),
            )
            tests.append(ScriptTest(
                id=f"{exercise_id}#session{n}", title=command or f"Session {n}", argv=argv, steps=steps, origin=origin,
            ))
    if not prompts and tests:
        derived = _session_prompts(tests)
        if derived:
            prompts = derived
            out.notes.append(f"{exercise_id}: input prompts taken from the example session (not quoted in the text).")
    if not tests and not prompts:
        return out
    first = prompts_found[0][1] if prompts_found else (terminal_blocks[0] if terminal_blocks else None)
    origin = explicit(excerpt(first.text), first.section or None, first.line) if first else Origin()
    out.script = ScriptSpec(prompts=prompts, tests=tests, origin=origin)
    return out
