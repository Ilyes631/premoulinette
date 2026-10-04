"""Terminal transcript splitting: runs, typed input, prompts with trailing spaces."""
from __future__ import annotations

from premoulinette.spec.models import ScriptTest, steps_to_io
from premoulinette.subject.transcript import (
    command_script_and_argv,
    match_prompt,
    split_sessions,
    split_transcript,
)


def _spans(code: str, *typed: str) -> list[tuple[int, int]]:
    """(start, end) spans of each typed value, searched in order."""
    spans, pos = [], 0
    for t in typed:
        i = code.index(t, pos)
        spans.append((i, i + len(t)))
        pos = i + len(t)
    return spans


def test_prompt_lines():
    assert match_prompt("42sh$ python3 launch.py") == "python3 launch.py"
    assert match_prompt("$ python3 x.py arg") == "python3 x.py arg"
    assert match_prompt("user@host:~/tp$ python x.py") == "python x.py"
    assert match_prompt("> python3 x.py") == "python3 x.py"
    assert match_prompt("C:\\Users\\me> python x.py") == "python x.py"
    assert match_prompt("Your choice: 2") is None
    assert match_prompt("Total: $ 3") is None


def test_command_script_and_argv():
    assert command_script_and_argv("python3 x.py a 'b c'") == ("x.py", ["a", "b c"], None)
    script, argv, problem = command_script_and_argv("python3 x.py < in.txt")
    assert script == "x.py" and argv == [] and problem


def test_trailing_spaces_in_prompts_are_kept_with_input_spans():
    code = "$ python3 ask.py\nName: Bob\nAge? (years) 12\nBob is 12.\n"
    sessions = split_sessions(code, _spans(code, "Bob", "12"))
    assert len(sessions) == 1
    command, steps, conf = sessions[0]
    assert command == "python3 ask.py" and conf == 1.0
    assert [(s.kind, s.text) for s in steps] == [
        ("output", "Name: "), ("input", "Bob"), ("output", "Age? (years) "), ("input", "12"),
        ("output", "Bob is 12.\n"),
    ]
    stdin, stdout = steps_to_io(steps)
    assert stdin == "Bob\n12\n"
    assert stdout == "Name: Age? (years) Bob is 12.\n"


def test_trailing_spaces_with_known_prompts_and_empty_input():
    # editors often strip the trailing space of a prompt line when the user typed nothing
    code = "$ python3 ask.py\nName: Bob\nNickname:\nHello Bob!\n"
    (command, steps, conf), = split_sessions(code, known_prompts=["Name: ", "Nickname: "])
    assert conf == 0.7
    assert [(s.kind, s.text) for s in steps] == [
        ("output", "Name: "), ("input", "Bob"), ("output", "Nickname: "), ("input", ""), ("output", "Hello Bob!\n"),
    ]
    assert steps_to_io(steps) == ("Bob\n\n", "Name: Nickname: Hello Bob!\n")


def test_run_without_input():
    code = "42sh$ python3 hello.py\nHello, world!\n  indented line\n"
    (command, steps, conf), = split_sessions(code)
    assert command == "python3 hello.py"
    assert [(s.kind, s.text) for s in steps] == [("output", "Hello, world!\n  indented line\n")]
    test = ScriptTest(id="hello#session1", steps=steps)
    assert test.stdin == "" and test.expected_stdout == "Hello, world!\n  indented line\n"


def test_multiple_runs_in_one_block():
    code = (
        "$ python3 code.py\nCode: ABC\nGranted\n"
        "$ python3 code.py\nCode: abc\nDenied\n"
        "$ python3 code.py --help\nusage: code.py\n"
    )
    sessions = split_sessions(code, _spans(code, "ABC", "abc"))
    assert [c for c, _, _ in sessions] == ["python3 code.py", "python3 code.py", "python3 code.py --help"]
    assert [steps_to_io(s) for _, s, _ in sessions] == [
        ("ABC\n", "Code: Granted\n"), ("abc\n", "Code: Denied\n"), ("", "usage: code.py\n"),
    ]
    commands, steps, conf = split_transcript(code, _spans(code, "ABC", "abc"))
    assert commands == ["python3 code.py", "python3 code.py", "python3 code.py --help"]
    assert conf == 1.0 and len(steps) == 7


def test_known_inputs_across_runs():
    code = "$ python3 c.py\nValue: 3\n9\n$ python3 c.py\nValue: 4\n16\n"
    sessions = split_sessions(code, known_inputs=["3", "4"])
    assert [steps_to_io(s) for _, s, _ in sessions] == [("3\n", "Value: 9\n"), ("4\n", "Value: 16\n")]
    assert all(c == 0.8 for _, _, c in sessions)


def test_no_marker_is_low_confidence_output():
    code = "$ python3 c.py\nValue: 3\n9\n"
    (_, steps, conf), = split_sessions(code)
    assert conf < 0.5
    assert [(s.kind, s.text) for s in steps] == [("output", "Value: 3\n9\n")]


def test_missing_final_newline_and_trailing_blank_lines():
    code = "$ python3 c.py\nDone\n\n\n"
    (_, steps, _), = split_sessions(code)
    assert steps[-1].text == "Done\n"
    code2 = "$ python3 c.py\nDone"
    (_, steps2, _), = split_sessions(code2)
    assert steps2[-1].text == "Done\n"


def test_input_span_including_enter_newline():
    code = "$ python3 c.py\nN: 5\nok\n"
    i = code.index("5")
    (_, steps, _), = split_sessions(code, [(i, i + 2)])  # span covers "5\n"
    assert steps_to_io(steps) == ("5\n", "N: ok\n")


def test_output_before_first_prompt_line_is_kept():
    code = "Welcome\n$ python3 c.py\nok\n"
    sessions = split_sessions(code)
    assert [c for c, _, _ in sessions] == ["", "python3 c.py"]
