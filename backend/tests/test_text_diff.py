import time

import pytest

from premoulinette.compare.text_diff import (
    MAX_DIFF_LINES,
    diff_text,
    first_hint,
    only_minor,
    split_lines,
    visible,
)


def changed(diff):
    return [line for line in diff.lines if line.op != "equal"]


# ---- helpers ---------------------------------------------------------------------------------------


def test_split_lines_keeps_terminators_and_final_partial_line():
    assert split_lines("") == []
    assert split_lines("a") == [("a", "")]
    assert split_lines("a\n") == [("a", "\n")]
    assert split_lines("a\r\nb\nc") == [("a", "\r\n"), ("b", "\n"), ("c", "")]
    assert split_lines("\n\n") == [("", "\n"), ("", "\n")]


def test_visible_marks_invisible_characters():
    assert visible("a b\tc\r\n") == "a·b→c␍↵\n"
    assert visible("") == ""


def test_identical_outputs():
    diff = diff_text("Hello\nWorld\n", "Hello\nWorld\n")
    assert diff.equal and diff.kinds == ["identical"] and diff.summary == "Output is identical"
    assert diff.first_difference is None
    assert [line.op for line in diff.lines] == ["equal", "equal"]
    assert diff_text("", "").equal


# ---- product brief examples ------------------------------------------------------------------------


def test_prompt_typo_is_located_at_the_right_column():
    expected = "Set a trap or collect evidence? (trap/evidence) "
    actual = "Set a trap or callect evidence? (trap/evidence) "
    diff = diff_text(expected, actual)
    assert not diff.equal and diff.kinds == ["typo"]
    (line,) = changed(diff)
    assert line.op == "changed" and line.expected_lineno == 1 and line.actual_lineno == 1
    assert line.hints == ["typo: 'o' → 'a' (col 16)"]
    assert expected[15] == "o" and actual[15] == "a"          # col 16 is 1-based
    assert [(s.op, s.expected, s.actual) for s in line.segments] == [
        ("equal", "Set a trap or c", "Set a trap or c"),
        ("replace", "o", "a"),
        ("equal", "llect evidence? (trap/evidence) ", "llect evidence? (trap/evidence) "),
    ]
    assert diff.first_difference == 15
    assert diff.summary == "1 line differs (line 1): typo"


def test_extra_text_in_a_menu_line():
    expected = "Where's the Mystery Machine headed today?\n1 - Crystal Cove\n2 - The Old Mill\n3 - Spooky Swamp\n"
    actual = expected.replace("The Old Mill", "The Older Mill")
    diff = diff_text(expected, actual)
    (line,) = changed(diff)
    assert line.expected_lineno == 3 and line.actual_lineno == 3
    assert line.expected == "2 - The Old Mill" and line.actual == "2 - The Older Mill"
    assert line.hints == ["extra text: 'er' (col 12)"]
    assert ("insert", "", "er") in [(s.op, s.expected, s.actual) for s in line.segments]
    assert diff.summary.startswith("1 line differs (line 3)")
    assert diff.first_difference == expected.index("Old Mill") + 3


def test_missing_trailing_space():
    diff = diff_text("Pilot name: ", "Pilot name:")
    (line,) = changed(diff)
    assert line.hints == ["missing trailing space"]
    assert diff.kinds == ["trailing_whitespace"]
    assert only_minor(diff.kinds)
    assert diff.first_difference == 11


def test_missing_text_hint():
    diff = diff_text("2 - The Older Mill", "2 - The Old Mill")
    assert changed(diff)[0].hints == ["missing text: 'er' (col 12)"]


# ---- hints and kinds -------------------------------------------------------------------------------


@pytest.mark.parametrize(("expected", "actual", "kind", "hint"), [
    ("Pilot name:", "Pilot name: ", "trailing_whitespace", "extra trailing space"),
    ("ok", "ok   ", "trailing_whitespace", "extra 3 trailing spaces"),
    ("Mill", "mill", "case", "case differs: 'M' → 'm' (col 1)"),
    ("Access granted", "Access Granted", "case", "case differs: 'g' → 'G' (col 8)"),
    ("a b", "a  b", "whitespace", "extra space (col 3)"),
    ("a\tb", "a b", "whitespace", "different whitespace (col 2)"),
    ("Hello", "Hallo", "typo", "typo: 'e' → 'a' (col 2)"),
    ("Fuel after the trip: 280", "Fuel left after trip: 2800", "different", "extra text: 'left ' (col 6)"),
])
def test_line_classification(expected, actual, kind, hint):
    diff = diff_text(expected + "\n", actual + "\n")
    assert diff.kinds == [kind]
    (line,) = changed(diff)
    if hint is not None:
        assert line.hints[0] == hint


def test_newline_differences():
    missing = diff_text("Liftoff!\n", "Liftoff!")
    assert missing.kinds == ["missing_newline"]
    assert changed(missing)[0].hints == ["missing newline at end of output"]
    assert changed(missing)[0].expected_eol == "\n" and changed(missing)[0].actual_eol == ""

    extra_at_end = diff_text("Liftoff!", "Liftoff!\n")
    assert extra_at_end.kinds == ["extra_newline"]
    assert changed(extra_at_end)[0].hints == ["extra newline at end of output"]

    blank = diff_text("a\nb\n", "a\n\nb\n")
    (line,) = changed(blank)
    assert line.op == "extra" and line.actual == "" and line.hints == ["extra newline (empty line)"]
    assert blank.kinds == ["extra_newline"]
    assert blank.summary == "1 extra empty line (from line 2)"


def test_windows_line_endings():
    diff = diff_text("a\nb\n", "a\r\nb\r\n")
    assert diff.kinds == ["crlf"]
    assert all(line.hints == ["Windows line ending (\\r\\n)"] for line in changed(diff))
    assert diff.summary == "2 lines differ (lines 1, 2): Windows line ending"


def test_missing_and_extra_lines_summaries():
    missing = diff_text("a\nb\nc\n", "a\n")
    assert missing.summary == "2 lines missing at the end"
    assert [line.op for line in missing.lines] == ["equal", "missing", "missing"]
    assert missing.kinds == ["missing_lines"]

    extra = diff_text("a\n", "a\nDEBUG x=3\n")
    assert extra.summary == "1 extra line at the end"
    assert extra.kinds == ["extra_lines"]

    middle = diff_text("a\nb\nc\n", "a\nc\n")
    assert middle.summary == "1 line missing (from line 2)"


def test_multi_line_output_with_a_missing_line_and_an_extra_line_is_aligned():
    expected = ("Where's the Mystery Machine headed today?\n1 - Crystal Cove\n2 - The Old Mill\n3 - Spooky Swamp\n"
                "Your choice: Destination: The Old Mill\nFuel after the trip: 280\n")
    actual = ("Where's the Mystery Machine headed today?\n1 - Crystal Cove\n2 - The Old Mill\n"
              "Your choice: Destination: The Old Mill\nDEBUG fuel=400\nFuel after the trip: 280\n")
    diff = diff_text(expected, actual)
    rows = [(line.op, line.expected_lineno, line.actual_lineno) for line in diff.lines]
    assert rows == [("equal", 1, 1), ("equal", 2, 2), ("equal", 3, 3), ("missing", 4, None), ("equal", 5, 4),
                    ("extra", None, 5), ("equal", 6, 6)]
    assert diff.lines[3].expected == "3 - Spooky Swamp" and diff.lines[5].actual == "DEBUG fuel=400"
    assert diff.kinds == ["missing_lines", "extra_lines"]
    assert diff.summary == "1 line missing (from line 4); 1 extra line (from line 5)"
    assert not only_minor(diff.kinds)


def test_replace_block_pairs_similar_lines_and_reports_the_rest():
    expected = "Destination: The Old Mill\nFuel after the trip: 280\n"
    actual = "Destination: The Old mill\nDEBUG fuel=400\nFuel after trip: 280\n"
    diff = diff_text(expected, actual)
    ops = [(line.op, line.expected_lineno, line.actual_lineno) for line in diff.lines]
    assert ops == [("changed", 1, 1), ("extra", None, 2), ("changed", 2, 3)]
    assert diff.lines[0].hints == ["case differs: 'M' → 'm' (col 22)"]
    assert diff.lines[2].hints == ["missing text: 'the ' (col 12)"]     # slid to a word boundary


def test_insertions_and_deletions_slide_to_word_boundaries():
    line = changed(diff_text("Fuel after the trip", "Fuel after trip"))[0]
    assert [(s.op, s.expected, s.actual) for s in line.segments] == [
        ("equal", "Fuel after ", "Fuel after "), ("delete", "the ", ""), ("equal", "trip", "trip"),
    ]
    line = changed(diff_text("Velma collects evidence", "Velma collects the evidence"))[0]
    assert line.hints == ["extra text: 'the ' (col 16)"]
    # nothing to slide: the edit stays where difflib put it
    line = changed(diff_text("2 - The Old Mill", "2 - The Older Mill"))[0]
    assert line.hints == ["extra text: 'er' (col 12)"]
    # every reconstruction stays faithful to both texts
    for exp, act in [("aaa b", "aa b"), ("x the the y", "x the y"), ("abcabc", "abc"), (" a", "a"), ("a ", "a")]:
        segs = changed(diff_text(exp, act))[0].segments
        assert "".join(s.expected for s in segs) == exp and "".join(s.actual for s in segs) == act


def test_unrelated_lines_are_missing_and_extra_not_changed():
    diff = diff_text("Access granted. Welcome aboard!\n", "zzz\n")
    assert [line.op for line in diff.lines] == ["missing", "extra"]
    assert diff.kinds == ["missing_lines", "extra_lines"]


def test_empty_sides():
    only_actual = diff_text("", "hello\n")
    assert [line.op for line in only_actual.lines] == ["extra"]
    assert only_actual.first_difference == 0
    only_expected = diff_text("hello\n", "")
    assert [line.op for line in only_expected.lines] == ["missing"]
    assert only_expected.summary == "1 line missing at the end"


def test_first_hint_and_only_minor():
    diff = diff_text("Pilot name: \n", "pilot name:\n")
    assert changed(diff)[0].hints == ["case differs: 'P' → 'p' (col 1)", "missing space (col 12)"]
    assert first_hint(diff) == "case differs: 'P' → 'p' (col 1), missing space (col 12)"
    missing_only = diff_text("a\nb\n", "a\n")
    assert first_hint(missing_only) == missing_only.summary == "1 line missing at the end"
    assert not only_minor([])
    assert only_minor(["typo", "case"])
    assert not only_minor(["typo", "missing_lines"])


def test_many_edits_on_one_line_are_capped():
    diff = diff_text("abcdefghij", "aXcXeXgXiX")
    (line,) = changed(diff)
    assert len(line.hints) == 4 and line.hints[-1] == "2 more difference(s)"
    assert diff.kinds == ["different"]


def test_huge_outputs_are_capped_and_fast():
    expected = "".join(f"line {i}\n" for i in range(5000))
    actual = expected.replace("line 10\n", "line 1O\n")
    started = time.perf_counter()
    diff = diff_text(expected, actual)
    assert time.perf_counter() - started < 5
    assert len(diff.lines) == MAX_DIFF_LINES
    assert "only the first 2000 lines were compared" in diff.summary
    assert diff.lines[-1].hints[-1] == "only the first 2000 lines were compared"

    tail_only = expected + "extra\n"
    capped = diff_text(expected, tail_only)
    assert not capped.equal and capped.kinds == ["different"]
    assert capped.summary.startswith("No difference in the first 2000 lines")


def test_very_long_single_line_uses_prefix_suffix_segments():
    expected = "x" * 20000
    actual = "x" * 10000 + "y" + "x" * 9999
    started = time.perf_counter()
    diff = diff_text(expected, actual)
    assert time.perf_counter() - started < 5
    (line,) = changed(diff)
    assert [s.op for s in line.segments] == ["equal", "replace", "equal"]
    assert diff.first_difference == 10000
