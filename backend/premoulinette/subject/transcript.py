"""Split terminal transcripts shown in a subject into runs of input/output steps.

A transcript may contain several runs; each run starts at a shell prompt line
(``42sh$ python3 x.py``, ``$ cmd``, ``% cmd``, ``> python3 x.py``, ``C:\\dir> python x.py``).

Input detection, by decreasing reliability:

1. explicit spans (``<kbd>``/``<b>`` inside ``<pre>``): confidence 1.0. The newline that follows a
   typed value is the terminal echo of Enter, NOT program output, so it is dropped.
2. ``known_prompts``: a line starting with a known prompt is split into (prompt output, typed input).
3. ``known_inputs``: values matched in order at the end of lines.
4. nothing: the whole run is output (confidence <= 0.4).
"""
from __future__ import annotations

import re
import shlex

from premoulinette.spec.models import InteractionStep

_CMD = r"(?P<cmd>[A-Za-z_./~\"'][^\n]*?)"
_PROMPT_RES: tuple[re.Pattern[str], ...] = (
    # "$ cmd", "42sh$ cmd", "user@host:~/dir$ cmd", "[user@host dir]$ cmd", "~/tp$ cmd"
    re.compile(
        r"^\s*(?:\[[^\]\n]*\]|[\w.\-]+@[\w.\-]+(?::\S*?)?|42sh|bash(?:-[\d.]+)?|zsh|sh|~\S*?|\S*/\S*?)?"
        rf"\s?\$\s+{_CMD}\s*$"
    ),
    re.compile(rf"^\s*(?:[\w.\-]+@[\w.\-]+\s*)?%\s+{_CMD}\s*$"),
    re.compile(r"^\s*>\s*(?P<cmd>(?:python[\d.]*|py)(?:\s[^\n]*?)?)\s*$"),
    re.compile(r"^\s*(?:PS\s+)?[A-Za-z]:\\[^>\n]*>\s*(?P<cmd>\S[^\n]*?)\s*$"),
)

LOW_CONFIDENCE = 0.3
PROMPT_CONFIDENCE = 0.7
KNOWN_INPUT_CONFIDENCE = 0.8

Session = tuple[str, list[InteractionStep], float]


def match_prompt(line: str) -> str | None:
    """Return the command of a shell prompt line, or None."""
    line = line.rstrip("\n")
    for rx in _PROMPT_RES:
        m = rx.match(line)
        if m:
            return m.group("cmd").strip()
    return None


def has_prompt_lines(code: str) -> bool:
    return any(match_prompt(line) is not None for line in code.split("\n"))


def command_script_and_argv(command: str) -> tuple[str | None, list[str], str | None]:
    """``"python3 x.py a b"`` -> ``("x.py", ["a", "b"], None)``.

    Returns (script, argv, problem) where problem describes unsupported shell syntax (pipes, redirections).
    """
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        tokens = command.split()
    problem = None
    if any(t in {"|", "<", ">", ">>", "<<", "&&", ";"} or t.startswith(("<", ">", "|")) for t in tokens):
        problem = f"shell redirection/pipe in '{command}' is not supported; argv/stdin may be incomplete"
    for idx, tok in enumerate(tokens):
        if tok.endswith(".py"):
            argv = tokens[idx + 1:]
            if problem:
                argv = []
            return tok, argv, problem
    return None, [], problem


# ----------------------------------------------------------------------------------------------
# Run splitting
# ----------------------------------------------------------------------------------------------


def _lines(code: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    pos = 0
    while pos < len(code):
        nl = code.find("\n", pos)
        end = len(code) if nl < 0 else nl + 1
        out.append((pos, code[pos:end]))
        pos = end
    return out


def _find_runs(code: str) -> list[tuple[str, int, int]]:
    runs: list[tuple[str, int, int]] = []
    cmd: str | None = None
    seg_start = 0
    for off, line in _lines(code):
        c = match_prompt(line)
        if c is None:
            continue
        if cmd is not None or code[seg_start:off].strip():
            runs.append((cmd or "", seg_start, off))
        cmd = c
        seg_start = off + len(line)
    if cmd is not None or code[seg_start:].strip():
        runs.append((cmd or "", seg_start, len(code)))
    return runs


def _normalize_spans(inputs: list[tuple[int, int]] | None, size: int) -> list[tuple[int, int]]:
    spans = sorted((max(0, int(s)), min(size, int(e))) for s, e in (inputs or []) if int(e) > int(s))
    merged: list[tuple[int, int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def _out(text: str) -> InteractionStep:
    return InteractionStep(kind="output", text=text)


def _inp(text: str) -> InteractionStep:
    return InteractionStep(kind="input", text=text)


def _steps_from_spans(code: str, start: int, end: int, spans: list[tuple[int, int]]) -> list[InteractionStep]:
    steps: list[InteractionStep] = []
    pos = start
    for s, e in spans:
        if e <= start or s >= end:
            continue
        s, e = max(s, pos), min(e, end)
        if s >= e:
            continue
        if s > pos:
            steps.append(_out(code[pos:s]))
        typed = code[s:e]
        ends_with_newline = typed.endswith("\n")
        parts = typed.split("\n")
        if ends_with_newline:
            parts = parts[:-1]
        steps.extend(_inp(p) for p in parts)
        pos = e
        if not ends_with_newline and pos < end and code[pos] == "\n":
            pos += 1  # echo of the Enter key, not program output
    if pos < end:
        steps.append(_out(code[pos:end]))
    return steps


def _segment_lines(segment: str) -> list[str]:
    lines = segment.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _steps_from_prompts(segment: str, prompts: list[str]) -> tuple[list[InteractionStep], int]:
    ordered = sorted({p for p in prompts if p}, key=len, reverse=True)
    steps: list[InteractionStep] = []
    matched = 0
    for line in _segment_lines(segment):
        for p in ordered:
            if line.startswith(p):
                steps += [_out(p), _inp(line[len(p):])]
                matched += 1
                break
            if p.rstrip() and line.rstrip() == p.rstrip():
                steps += [_out(p), _inp("")]
                matched += 1
                break
        else:
            steps.append(_out(line + "\n"))
    return steps, matched


def _steps_from_known_inputs(segment: str, known: list[str], cursor: list[int]) -> tuple[list[InteractionStep], int]:
    steps: list[InteractionStep] = []
    matched = 0
    for line in _segment_lines(segment):
        idx = cursor[0]
        if idx < len(known) and known[idx] and line.endswith(known[idx]):
            prompt = line[: len(line) - len(known[idx])]
            if prompt:
                steps.append(_out(prompt))
            steps.append(_inp(known[idx]))
            cursor[0] += 1
            matched += 1
        else:
            steps.append(_out(line + "\n"))
    return steps, matched


def _finalize(steps: list[InteractionStep]) -> list[InteractionStep]:
    merged: list[InteractionStep] = []
    for st in steps:
        if st.kind == "output" and not st.text:
            continue
        if st.kind == "output" and merged and merged[-1].kind == "output":
            merged[-1] = _out(merged[-1].text + st.text)
        else:
            merged.append(st)
    if merged and merged[-1].kind == "output":
        text = re.sub(r"(?:\n[ \t]*)+\Z", "\n", merged[-1].text)
        if not text.strip():
            merged.pop()
        else:
            merged[-1] = _out(text if text.endswith("\n") else text + "\n")
    return merged


def split_sessions(
    code: str,
    inputs: list[tuple[int, int]] | None = None,
    *,
    known_inputs: list[str] | None = None,
    known_prompts: list[str] | None = None,
) -> list[Session]:
    """Split a terminal block into runs: ``[(command, steps, confidence), ...]``."""
    spans = _normalize_spans(inputs, len(code))
    cursor = [0]
    sessions: list[Session] = []
    for command, start, end in _find_runs(code):
        segment = code[start:end]
        if spans:
            steps, confidence = _steps_from_spans(code, start, end, spans), 1.0
        else:
            steps, confidence = [_out(segment)], LOW_CONFIDENCE
            if known_prompts:
                p_steps, matched = _steps_from_prompts(segment, known_prompts)
                if matched:
                    steps, confidence = p_steps, PROMPT_CONFIDENCE
            if confidence == LOW_CONFIDENCE and known_inputs:
                k_steps, matched = _steps_from_known_inputs(segment, known_inputs, cursor)
                if matched:
                    steps, confidence = k_steps, KNOWN_INPUT_CONFIDENCE
        sessions.append((command, _finalize(steps), confidence))
    return sessions


def split_transcript(
    code: str,
    inputs: list[tuple[int, int]] | None = None,
    known_inputs: list[str] | None = None,
    *,
    known_prompts: list[str] | None = None,
) -> tuple[list[str], list[InteractionStep], float]:
    """Flattened view of :func:`split_sessions`: (commands, all steps in order, min confidence)."""
    sessions = split_sessions(code, inputs, known_inputs=known_inputs, known_prompts=known_prompts)
    commands = [c for c, _, _ in sessions if c]
    steps = [s for _, st, _ in sessions for s in st]
    confidence = min((c for _, _, c in sessions), default=0.0)
    return commands, steps, confidence
