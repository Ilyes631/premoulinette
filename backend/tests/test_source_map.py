from premoulinette.compare.source_map import (
    actual_prompts,
    attach_line_sources,
    code_excerpt,
    locate_text,
    output_spans,
    return_lines_for,
)
from premoulinette.compare.text_diff import diff_text
from premoulinette.languages.python.static_models import FunctionInfo, ModuleInfo, ReturnInfo, StringLiteral
from premoulinette.results.models import Location
from premoulinette.runner.models import RawEvent

F = "pkg/launch.py"


def lit(value, line, in_call=None, is_fstring=False):
    return StringLiteral(value=value, line=line, end_line=line, col=4, end_col=4 + len(value) + 2,
                         in_call=in_call, is_fstring=is_fstring)


MODULE = ModuleInfo(path=F, ok=True, strings=[
    lit("Pilot name: ", 1, "input"),
    lit("Destination: ", 13, "print"),
    lit("{} sets a trap at {}. Zoinks!", 17, "print", is_fstring=True),
    lit("Set a trap or callect evidence? (trap/evidence) ", 15, "input"),
    lit("Pilot name: ", 30),
])


def test_locate_text_prefers_identical_literal_in_an_io_call():
    assert locate_text("Pilot name: ", MODULE) == Location(file=F, line=1, end_line=1, col=4)


def test_locate_text_fstring_template_and_fuzzy_match():
    assert locate_text("Camille sets a trap at The Old Mill. Zoinks!\n", MODULE).line == 17
    assert locate_text("Set a trap or collect evidence? (trap/evidence) ", MODULE).line == 15
    assert locate_text("Destination: The Old Mill", MODULE).line == 13


def test_locate_text_without_candidates():
    assert locate_text("anything", None) is None
    assert locate_text("   \n", MODULE) is None
    assert locate_text("zzzz", ModuleInfo(path=F, ok=True)) is None


def test_output_spans_and_line_sources():
    events = [RawEvent(kind="output", text="Pilot name: ", file=F, line=1), RawEvent(kind="input", text="Fred", file=F, line=1),
              RawEvent(kind="stderr", text="warn", file=F, line=2), RawEvent(kind="output", text="Hi Fred\n", file=F, line=3)]
    stdout = "Pilot name: Hi Fred\n"
    spans = output_spans(events, stdout)
    assert spans.at(0).line == 1 and spans.at(12).line == 3 and spans.at(len(stdout)) is None
    diff = diff_text("Pilot name: Hello Fred\n", stdout)
    attach_line_sources(diff, events)
    assert diff.lines[0].source == Location(file=F, line=3)       # first difference is in the print() part


def test_output_spans_stop_when_events_and_stdout_diverge():
    events = [RawEvent(kind="output", text="abc\n", file=F, line=1), RawEvent(kind="output", text="def\n", file=F, line=2)]
    spans = output_spans(events, "abc\nxyz\n")
    assert len(spans.events) == 1 and spans.at(5) is None


def test_attach_line_sources_falls_back_to_string_literals():
    diff = diff_text("Destination: The Old Mill\n", "Destination: The Old mill\n")
    attach_line_sources(diff, [], MODULE)
    assert diff.lines[0].source.line == 13


def test_actual_prompts_group_output_until_each_input_and_eof():
    events = [RawEvent(kind="output", text="Menu\n", file=F, line=3), RawEvent(kind="output", text="Your choice: ", file=F, line=7),
              RawEvent(kind="input", text="2", file=F, line=7), RawEvent(kind="output", text="Again? ", file=F, line=9)]
    prompts = actual_prompts(events, eof=True, eof_location=Location(file=F, line=9))
    assert len(prompts) == 2
    assert prompts[0].tail() == ("Your choice: ", Location(file=F, line=7))
    assert prompts[0].tail(1) == ("Menu\nYour choice: ", Location(file=F, line=3))
    assert prompts[0].input_location == Location(file=F, line=7)
    assert prompts[1].tail() == ("Again? ", Location(file=F, line=9))


def test_code_excerpt_windows_and_highlights():
    source = "".join(f"line{i}\n" for i in range(1, 101))
    excerpt = code_excerpt(source, F, 1, 100, [60])
    assert len(excerpt.lines) == 30 and excerpt.start_line <= 60 < excerpt.start_line + 30
    assert excerpt.highlight == [60] and excerpt.lines[60 - excerpt.start_line] == "line60"
    assert code_excerpt(source, F, 98, 104, [99]).lines == ["line98", "line99", "line100"]
    assert code_excerpt(None, F, 1, 2) is None
    assert code_excerpt(source, F, 200, 210) is None


def test_return_lines_for_constant_returns():
    fn = FunctionInfo(name="is_safe", line=1, end_line=5, returns=[
        ReturnInfo(line=3, value_src="'True'", value_kind="constant", constant_type="str"),
        ReturnInfo(line=4, value_src="True", value_kind="constant", constant_type="bool"),
        ReturnInfo(line=5, value_src=None, value_kind="none"),
    ])
    assert return_lines_for(fn, "'True'") == [3]
    assert return_lines_for(fn, "True") == [4]
    assert return_lines_for(fn, "None") == [5]
    assert return_lines_for(fn, "<object>") == []
