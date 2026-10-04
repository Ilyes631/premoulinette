"""Map runtime evidence back to student source: printed text -> string literal, stdout offset -> the
print()/input() call that wrote it (from harness I/O events), function -> code excerpt."""
from __future__ import annotations

import bisect
import difflib
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from premoulinette.compare.text_diff import split_lines
from premoulinette.languages.python.static_models import FunctionInfo, ModuleInfo, StringLiteral
from premoulinette.results.models import CodeExcerpt, DiffLine, Location, TextDiff
from premoulinette.runner.models import RawEvent
from premoulinette.testgen.oracle import OracleError, literal

MIN_COMMON = 4
MAX_EXCERPT_LINES = 30
_IO_CALLS = ("print", "input")
_LINE_SPLIT = re.compile(r"\r\n|\r|\n")   # same line numbering as the ast module


# ------------------------------------------------------------------------------------------------
# Text -> string literal
# ------------------------------------------------------------------------------------------------


def locate_text(text: str, module: ModuleInfo | None) -> Location | None:
    """Location of the string literal that most likely produced (or contains) ``text``.

    Preference: identical literal > f-string template matching the text > literal containing the
    text > literal contained in the text > longest common substring (>= 4 chars, case-insensitive).
    print()/input() arguments win ties.
    """
    if module is None or not module.strings:
        return None
    needle = text.strip("\r\n")
    if not needle.strip():
        return None
    best: StringLiteral | None = None
    best_score: tuple[int, int, int, int] | None = None
    for lit in module.strings:
        score = _score(needle, lit)
        if score is not None and (best_score is None or score > best_score):
            best, best_score = lit, score
    if best is None:
        return None
    return Location(file=module.path, line=best.line, end_line=best.end_line, col=best.col)


def _score(needle: str, lit: StringLiteral) -> tuple[int, int, int, int] | None:
    value = lit.value
    if not value.strip():
        return None
    io = 1 if lit.in_call in _IO_CALLS else 0
    if value == needle:
        return (5, io, len(value), -lit.line)
    if lit.is_fstring and _template_matches(value, needle):
        return (4, io, len(value), -lit.line)
    if needle in value:
        return (3, io, -len(value), -lit.line)
    static = value.replace("{}", "")
    if len(static.strip()) >= MIN_COMMON and all(p in needle for p in value.split("{}") if p):
        return (2, io, len(static), -lit.line)
    common = _longest_common(needle.lower(), static.lower())
    if common >= MIN_COMMON:
        return (1, io, common, -lit.line)
    return None


def _template_matches(template: str, text: str) -> bool:
    pattern = ".*".join(re.escape(part) for part in template.split("{}"))
    return re.fullmatch(pattern, text, flags=re.S) is not None


def _longest_common(a: str, b: str) -> int:
    if not a or not b:
        return 0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b)).size


# ------------------------------------------------------------------------------------------------
# stdout offsets -> I/O events
# ------------------------------------------------------------------------------------------------


def event_location(event: RawEvent | None) -> Location | None:
    if event is None or not event.file:
        return None
    return Location(file=event.file, line=event.line)


@dataclass(frozen=True)
class OutputSpans:
    """Character ranges of stdout written by each output event (consistent prefix only)."""

    starts: list[int]
    ends: list[int]
    events: list[RawEvent]

    def at(self, offset: int) -> RawEvent | None:
        k = bisect.bisect_right(self.starts, offset) - 1
        if 0 <= k < len(self.events) and offset < self.ends[k]:
            return self.events[k]
        return None


def output_spans(events: Iterable[RawEvent], stdout: str) -> OutputSpans:
    starts: list[int] = []
    ends: list[int] = []
    kept: list[RawEvent] = []
    pos = 0
    for ev in events:
        if ev.kind != "output" or not ev.text:
            continue
        end = pos + len(ev.text)
        if stdout[pos:end] != ev.text:
            break       # events and stdout diverge (truncation...): stop mapping here
        starts.append(pos)
        ends.append(end)
        kept.append(ev)
        pos = end
    return OutputSpans(starts, ends, kept)


def _first_edit_offset(line: DiffLine) -> int:
    """Offset (in the actual line) of the character the first difference should be blamed on.

    Text *missing* from the actual output (a pure delete, e.g. the trailing space of
    ``input("Pilot name:")``) belongs to the call that wrote the character just before the gap,
    not to the next call: blame ``offset - 1`` in that case.
    """
    offset = 0
    for seg in line.segments:
        if seg.op != "equal":
            if seg.op == "delete" and offset > 0:
                return offset - 1
            return offset
        offset += len(seg.actual)
    return len(line.actual or "")


def attach_line_sources(diff: TextDiff, events: Sequence[RawEvent], module: ModuleInfo | None = None) -> None:
    """Fill ``DiffLine.source`` for every actual line from the event that wrote it.

    For a changed line, the event covering its first differing character is used (a line can be
    written by several calls: an input() prompt then a print()).
    """
    spans = output_spans(events, diff.actual)
    starts: list[int] = []
    pos = 0
    for text, eol in split_lines(diff.actual):
        starts.append(pos)
        pos += len(text) + len(eol)
    for line in diff.lines:
        if line.actual_lineno is None or line.actual_lineno > len(starts):
            continue
        start = starts[line.actual_lineno - 1]
        offset = start + (_first_edit_offset(line) if line.op == "changed" else 0)
        event = spans.at(offset) or spans.at(start)
        source = event_location(event)
        if source is None and module is not None and line.op != "equal" and line.actual:
            source = locate_text(line.actual, module)
        line.source = source


# ------------------------------------------------------------------------------------------------
# input() prompts
# ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ActualPrompt:
    """What was on screen when the program asked for input number n.

    ``segments`` = output written since the previous input() (each with the call that wrote it).
    A real prompt is the output event of the input() call itself; text printed just before with
    ``print(..., end="")`` or an ``input("menu\\nYour choice: ")`` also counts, as only the tail
    after the last newline(s) is compared.
    """

    segments: tuple[tuple[str, Location | None], ...]
    input_location: Location | None      # the input() call (or where EOFError was raised)

    def tail(self, newlines: int = 0) -> tuple[str, Location | None]:
        """Last ``newlines + 1`` line fragments of the pending output, and who wrote their start."""
        text = "".join(t for t, _ in self.segments)
        tail = "\n".join(text.split("\n")[-(newlines + 1):])
        start = len(text) - len(tail)
        pos = 0
        for segment, location in self.segments:
            if pos + len(segment) > start:
                return tail, location or self.input_location
            pos += len(segment)
        return tail, self.input_location


def actual_prompts(
    events: Sequence[RawEvent], *, eof: bool = False, eof_location: Location | None = None
) -> list[ActualPrompt]:
    """One entry per input() call, plus the call that hit end of input when ``eof`` is True."""
    prompts: list[ActualPrompt] = []
    pending: list[tuple[str, Location | None]] = []
    for ev in events:
        if ev.kind == "output":
            pending.append((ev.text, event_location(ev)))
        elif ev.kind == "input":
            prompts.append(ActualPrompt(tuple(pending), event_location(ev)))
            pending = []
    if eof:
        prompts.append(ActualPrompt(tuple(pending), eof_location))
    return prompts


# ------------------------------------------------------------------------------------------------
# Code excerpts
# ------------------------------------------------------------------------------------------------


def source_lines(source: str) -> list[str]:
    lines = _LINE_SPLIT.split(source)
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def code_excerpt(
    source: str | None, file: str, start: int, end: int, highlight: Sequence[int] = (), max_lines: int = MAX_EXCERPT_LINES
) -> CodeExcerpt | None:
    """Lines ``start..end`` (1-based, inclusive) of ``source``, windowed around the first highlight."""
    if not source:
        return None
    lines = source_lines(source)
    if not lines:
        return None
    start = max(1, start)
    end = min(len(lines), max(end, start))
    if start > len(lines):
        return None
    if end - start + 1 > max_lines:
        center = highlight[0] if highlight else start
        start = max(start, min(center - max_lines // 2, end - max_lines + 1))
        end = start + max_lines - 1
    return CodeExcerpt(file=file, start_line=start, lines=lines[start - 1:end],
                       highlight=sorted({h for h in highlight if start <= h <= end}))


def function_excerpt(source: str | None, file: str, fn: FunctionInfo, highlight: Sequence[int] = ()) -> CodeExcerpt | None:
    return code_excerpt(source, file, fn.line, fn.end_line, highlight)


def return_lines_for(fn: FunctionInfo, actual_repr: str) -> list[int]:
    """Lines of ``return`` statements whose constant value is the returned value (same type)."""
    try:
        actual = literal(actual_repr)
    except OracleError:
        return []
    lines: list[int] = []
    for ret in fn.returns:
        if ret.value_src is None:
            if actual is None:
                lines.append(ret.line)
            continue
        if ret.value_kind != "constant":
            continue
        try:
            value = literal(ret.value_src)
        except OracleError:
            continue
        if type(value) is type(actual) and value == actual:
            lines.append(ret.line)
    return lines
