"""Deterministic explanations (explain/templates.py): coverage of the diagnosis registry + content checks."""
from __future__ import annotations

import re

import pytest
from conftest import REPO

from premoulinette.explain.templates import (
    DIAGNOSIS_CODES,
    Explanation,
    expected_behavior,
    explain,
    how_to_fix,
)
from premoulinette.results.models import (
    CheckResult,
    CodeExcerpt,
    DiffLine,
    Evidence,
    ExceptionInfo,
    Fix,
    Location,
    TextDiff,
    ValueSnapshot,
)
from premoulinette.spec.models import (
    BehaviorRule,
    Constraints,
    ExerciseSpec,
    FileRequirement,
    FunctionSignature,
    FunctionSpec,
    FunctionTest,
    InteractionStep,
    Origin,
    Param,
    PracticalSpec,
    ScriptSpec,
    ScriptTest,
    SourceRef,
    StructureSpec,
)

SAFE_SPEED = "MysteryInc/FirstLaunch/flight_functions/safe_speed.py"
LAUNCH = "MysteryInc/FirstLaunch/launch_sequence.py"
CATEGORIES = ("structure", "syntax", "functions", "explicit_tests", "derived_tests", "heuristic_tests", "output",
              "constraints", "runtime", "git")


def registry_from_architecture() -> list[str]:
    """Diagnosis codes listed in the docs/ARCHITECTURE.md registry table, in order, without duplicates."""
    text = (REPO / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    section = text.split("## Diagnosis codes", 1)[1].split("\n## ", 1)[0]
    codes: list[str] = []
    for row in section.splitlines():
        if not row.startswith("|") or row.startswith("|---") or "Codes" in row:
            continue
        cells = row.split("|")
        for code in re.findall(r"`([a-z_]+)`", cells[2]):
            if code not in codes:
                codes.append(code)
    return codes


def check(**kw: object) -> CheckResult:
    base: dict[str, object] = {"id": "x", "category": "functions", "status": "fail", "severity": "major",
                               "title": "Some check", "message": "Deterministic message."}
    base.update(kw)
    return CheckResult(**base)  # type: ignore[arg-type]


def rich_check(code: str) -> CheckResult:
    """A failing check carrying every kind of evidence, to exercise every template branch without crashing."""
    diff = TextDiff(
        expected="Pilot name: Camille\nDone\n", actual="Pilot nam: Camille\nDone\nExtra\n", equal=False,
        kinds=["typo", "extra_lines"], summary="1 character differs on line 1 (typo)",
        lines=[
            DiffLine(op="changed", expected_lineno=1, actual_lineno=1, expected="Pilot name: Camille",
                     actual="Pilot nam: Camille", expected_eol="\n", actual_eol="\n", hints=["typo: 'e' missing"],
                     source=Location(file=LAUNCH, line=1)),
            DiffLine(op="equal", expected_lineno=2, actual_lineno=2, expected="Done", actual="Done",
                     expected_eol="\n", actual_eol="\n"),
            DiffLine(op="extra", actual_lineno=3, actual="Extra", actual_eol="\n"),
        ],
    )
    return check(
        id=f"test:{code}#ex1", diagnosis=code, function="is_safe", exercise_id="safe_speed", file=SAFE_SPEED,
        location=Location(file=SAFE_SPEED, line=4),
        evidence=Evidence(
            call="is_safe(200, 250)", stdin="Camille\n400\n", rule="speed <= limit",
            expected_value=ValueSnapshot(repr="True", type="bool"), actual_value=ValueSnapshot(repr="'True'", type="str"),
            stdout_diff=diff, expected_stdout=diff.expected, actual_stdout=diff.actual, stderr="Traceback ...\nValueError: x",
            exit_code=1, exception=ExceptionInfo(type="ZeroDivisionError", message="division by zero",
                                                 traceback="File safe_speed.py, line 4\nZeroDivisionError: division by zero"),
            code=CodeExcerpt(file=SAFE_SPEED, start_line=1, lines=[
                "def is_safe(speed: int, limit: int) -> bool:", "    # comment", "    if speed <= limit:", '        return "True"',
            ], highlight=[4]),
            details={"lines": [4, 9], "expected_signature": "def is_safe(speed: int, limit: int) -> bool",
                     "actual_signature": "def is_safe(speed)", "found": "is_save", "timeout_s": 5.0,
                     "blocked_syscalls": ["socket.connect"], "expected_prompt": "Pilot name: ",
                     "actual_prompt": "Pilot nam: ", "expected_path": SAFE_SPEED,
                     "found_path": "MysteryInc/FirstLaunch/safe_speed.py", "effects": [{"line": 7, "src": "print('debug')"}]},
        ),
    )


# ---------------------------------------------------------------------------------------------
# Registry coverage
# ---------------------------------------------------------------------------------------------


def test_diagnosis_codes_match_the_architecture_registry():
    documented = registry_from_architecture()
    assert len(documented) == 52
    assert list(DIAGNOSIS_CODES) == documented
    assert len(set(DIAGNOSIS_CODES)) == len(DIAGNOSIS_CODES)


@pytest.mark.parametrize("code", DIAGNOSIS_CODES)
def test_every_code_has_french_and_english_templates(code: str):
    for factory in (lambda: check(diagnosis=code), lambda: rich_check(code)):
        fr, en = explain(factory(), "fr"), explain(factory(), "en")
        for e, lang in ((fr, "fr"), (en, "en")):
            assert isinstance(e, Explanation)
            assert e.provider == "template" and e.language == lang and e.sent_payload is None
            assert e.title.strip() and len(e.markdown.strip()) > 40
            if code != "returns_none":   # no leaked Python None from a missing evidence field
                assert "None" not in e.title
        assert fr.markdown != en.markdown
        assert fr.title != en.title


@pytest.mark.parametrize("code", DIAGNOSIS_CODES)
def test_every_code_has_a_fix_hint_in_both_languages(code: str):
    for lang in ("fr", "en"):
        e = how_to_fix(rich_check(code), lang)
        assert e.markdown.strip()
        assert e.title.strip()


@pytest.mark.parametrize("code", DIAGNOSIS_CODES)
def test_passing_check_explains_why_it_passes(code: str):
    c = rich_check(code)
    c.status, c.severity = "pass", None
    assert explain(c, "fr").title == "Pourquoi ce point est validé"
    assert explain(c, "en").title == "Why this passes"
    assert how_to_fix(c, "en").markdown.startswith("Nothing to fix")


@pytest.mark.parametrize("category", CATEGORIES)
def test_generic_fallback_per_category(category: str):
    c = check(category=category, diagnosis="some_future_code", message="Deterministic message.")
    for lang in ("fr", "en"):
        e = explain(c, lang)
        assert e.title.strip() and "Deterministic message." in e.markdown
        assert how_to_fix(c, lang).markdown.strip()
    c.status, c.diagnosis = "pass", None
    assert explain(c, "fr").markdown.strip()


def test_skipped_and_info_checks():
    c = check(status="skipped", severity=None, blocked_by="syntax:kelvin.py", diagnosis="wrong_value")
    e = explain(c, "fr")
    assert "`syntax:kelvin.py`" in e.markdown and "non réussi" in e.markdown
    assert "`syntax:kelvin.py`" in how_to_fix(c, "en").markdown
    info = check(status="info", severity=None, message="Extra file found.")
    assert "Extra file found." in explain(info, "en").markdown


# ---------------------------------------------------------------------------------------------
# Content of key templates
# ---------------------------------------------------------------------------------------------


def test_str_instead_of_bool_follows_the_pedagogical_style():
    c = check(id="test:is_safe#ex1", category="explicit_tests", diagnosis="str_instead_of_bool", function="is_safe",
              file=SAFE_SPEED, location=Location(file=SAFE_SPEED, line=4),
              evidence=Evidence(call="is_safe(200, 250)", expected_value=ValueSnapshot(repr="True", type="bool"),
                                actual_value=ValueSnapshot(repr="'True'", type="str")))
    md = explain(c, "fr").markdown
    assert md.startswith(
        "Ta logique de comparaison est correcte, mais tu retournes une **chaîne de caractères** au lieu d'un **booléen**.\n\n"
        "- `\"True\"` est un `str` (à cause des guillemets)\n- `True` est un `bool`\n\n"
        "Le sujet demande `True` sans guillemets."
    )
    assert "`is_safe(200, 250)`" in md and "ligne 4" in md
    en = explain(c, "en").markdown
    assert "you return a **string** instead of a **boolean**" in en


def test_str_instead_of_bool_static_and_wrong_value_variants():
    static = check(id="returns:safe_speed:is_safe", diagnosis="str_instead_of_bool", function="is_safe",
                   file=SAFE_SPEED, location=Location(file=SAFE_SPEED, line=6),
                   evidence=Evidence(code=CodeExcerpt(file=SAFE_SPEED, start_line=6, lines=['        return "False"'])))
    md = explain(static, "fr").markdown
    assert "La fonction `is_safe` retourne une **chaîne de caractères**" in md
    assert '`"False"` est un `str`' in md
    wrong = check(category="explicit_tests", diagnosis="str_instead_of_bool", function="is_safe",
                  evidence=Evidence(expected_value=ValueSnapshot(repr="False", type="bool"),
                                    actual_value=ValueSnapshot(repr="'True'", type="str")))
    assert "la valeur n'est pas la bonne" in explain(wrong, "fr").markdown


def _diff_block_lines(markdown: str) -> list[str]:
    block = re.search(r"```text\n(.*?)\n```", markdown, re.S)
    assert block is not None
    return block.group(1).split("\n")


def test_typo_shows_expected_received_and_a_caret_under_the_difference():
    expected, actual = "Set a trap or collect evidence? (trap/evidence) ", "Set a trap or callect evidence? (trap/evidence) "
    c = check(id="prompt:launch_sequence:4", category="output", diagnosis="prompt_mismatch", severity="minor",
              file=LAUNCH, location=Location(file=LAUNCH, line=27),
              evidence=Evidence(expected_value=ValueSnapshot(repr=repr(expected), type="str"),
                                actual_value=ValueSnapshot(repr=repr(actual), type="str")))
    md = explain(c, "fr").markdown
    exp_line, act_line, caret_line = _diff_block_lines(md)
    assert exp_line.startswith("attendu :") and act_line.startswith("reçu :")
    assert caret_line.count("^") == 1
    col = caret_line.index("^")
    assert act_line[col] == "a" and exp_line[col] == "o"
    assert "ligne 27" in md


def test_whitespace_difference_mentions_invisible_characters():
    c = check(id="prompt:launch_sequence:1", category="output", diagnosis="prompt_mismatch", severity="minor",
              file=LAUNCH, location=Location(file=LAUNCH, line=1),
              evidence=Evidence(expected_value=ValueSnapshot(repr="'Pilot name: '", type="str"),
                                actual_value=ValueSnapshot(repr="'Pilot name:'", type="str")))
    md = explain(c, "en").markdown
    assert "**invisible**" in md
    exp_line, act_line, caret_line = _diff_block_lines(md)
    assert exp_line.endswith("Pilot␠name:␠") and act_line.endswith("Pilot␠name:")
    assert caret_line.index("^") == len(act_line)
    assert 'input("Pilot name: ")' in md


def test_stdout_mismatch_points_to_the_source_line():
    md = explain(rich_check("stdout_mismatch"), "en").markdown
    assert "produced by line 1 of `MysteryInc/FirstLaunch/launch_sequence.py`" in md
    assert "```text" in md and "^" in md
    assert "`Camille`" in md   # stdin inputs are listed


def test_forbidden_builtin_explains_why_and_gives_an_idea_not_a_solution():
    c = check(id="constraint:kelvin:forbidden_builtin:abs", category="constraints", diagnosis="forbidden_builtin",
              severity="critical", file="k.py", location=Location(file="k.py", line=3),
              evidence=Evidence(details={"lines": [3, 8]}))
    fr = explain(c, "fr").markdown
    assert "`abs()`" in fr and "à la ligne 3" in fr and "8" in fr
    assert "Pourquoi c'est interdit" in fr and "**condition**" in fr
    assert "def " not in fr
    for name, word in (("max", "comparisons"), ("sum", "loop"), ("round", "integer arithmetic")):
        c.id = f"constraint:x:forbidden_builtin:{name}"
        assert word in explain(c, "en").markdown


def test_missing_file_gives_the_exact_path_and_the_case_reminder():
    path = "MysteryInc/FirstLaunch/route_math/fuel_share.py"
    c = check(id=f"structure:file:{path}", category="structure", diagnosis="missing_file", severity="critical")
    md = explain(c, "fr").markdown
    assert f"```\n{path}\n```" in md
    assert "chemin exact" in md and "majuscules" in md
    en = explain(c, "en").markdown
    assert "exact path" in en and "case" in en


def test_misplaced_file_gives_the_git_mv_command():
    c = check(id="structure:file:MysteryInc/FirstLaunch/route_math/fuel_share.py", category="structure",
              diagnosis="misplaced_file", severity="critical",
              evidence=Evidence(details={"found_path": "MysteryInc/FirstLaunch/fuel_share.py"}))
    md = explain(c, "en").markdown
    assert "git mv MysteryInc/FirstLaunch/fuel_share.py MysteryInc/FirstLaunch/route_math/fuel_share.py" in md


def test_untracked_file_says_git_add_and_commit_but_never_push_or_tag():
    path = "MysteryInc/FirstLaunch/access_code.py"
    c = check(id=f"git:untracked:{path}", category="git", diagnosis="untracked_file")
    for lang in ("fr", "en"):
        text = explain(c, lang).markdown + how_to_fix(c, lang).markdown
        assert f"git add {path}" in text and "git commit" in text
        assert "push" not in text.lower() and "tag" not in text.lower()


def test_bonus_failures_reassure_about_the_mandatory_score():
    c = check(category="explicit_tests", status="bonus", severity="major", bonus=True, mandatory=False,
              diagnosis="wrong_value", function="max_altitude",
              evidence=Evidence(call="max_altitude(1, 2, 3)", expected_value=ValueSnapshot(repr="3", type="int"),
                                actual_value=ValueSnapshot(repr="1", type="int")))
    assert "n'affecte pas ton score obligatoire" in explain(c, "fr").markdown
    assert "does not affect your mandatory score" in explain(c, "en").markdown
    missing = check(category="structure", status="bonus", bonus=True, mandatory=False, diagnosis="missing_bonus_file",
                    id="structure:file:MysteryInc/FirstLaunch/bonus/countdown.py")
    md = explain(missing, "fr").markdown
    assert "n'affectent pas ton score obligatoire" in md and "bonus/countdown.py" in md


def test_heuristic_and_ai_extracted_notes():
    c = check(category="heuristic_tests", status="warning", mandatory=False, diagnosis="wrong_value")
    assert "Unofficial test" in explain(c, "en").markdown
    c = check(diagnosis="wrong_value", origin=Origin(provenance="ai_extracted", confidence=0.5))
    assert "extracted by AI" in explain(c, "en").markdown


def test_exception_template_uses_the_exception_hint():
    c = check(category="explicit_tests", diagnosis="exception", function="average_speed",
              location=Location(file="FIXME2.py", line=3),
              evidence=Evidence(call="average_speed(10.0, 0.0)",
                                exception=ExceptionInfo(type="ZeroDivisionError", message="float division by zero")))
    md = explain(c, "fr").markdown
    assert "`ZeroDivisionError: float division by zero`" in md and "division par zéro" in md and "ligne 3" in md


# ---------------------------------------------------------------------------------------------
# how_to_fix
# ---------------------------------------------------------------------------------------------


def test_how_to_fix_shows_the_patch_in_a_diff_block():
    patch = "--- a/s.py\n+++ b/s.py\n@@ -1,2 +1,2 @@\n def is_safe(a, b):\n-    return \"True\"\n+    return True\n"
    c = check(diagnosis="str_instead_of_bool", function="is_safe",
              fix=Fix(summary="Return booleans.", file="s.py", patch=patch, before='return "True"', after="return True"))
    md = how_to_fix(c, "fr").markdown
    assert f"```diff\n{patch.rstrip()}\n```" in md
    assert "jamais appliqué automatiquement" in md
    assert "Étapes" not in md     # a high-confidence patch is enough
    assert how_to_fix(c, "en").title == "How to fix: Some check"


def test_how_to_fix_renders_git_commands_and_low_confidence_hints():
    move = check(category="structure", diagnosis="misplaced_file",
                 fix=Fix(summary="Move it.", file="a.py", after="git mv a.py b/a.py"))
    assert "```sh\ngit mv a.py b/a.py\n```" in how_to_fix(move, "en").markdown
    builtin = check(category="constraints", diagnosis="forbidden_builtin", id="constraint:x:forbidden_builtin:max",
                    fix=Fix(summary="Replace max() with comparisons.", confidence="low"))
    md = how_to_fix(builtin, "fr").markdown
    assert "Il n'y a pas de correctif automatique" in md and "Simple piste" in md
    assert "1. " in md and "comparaisons" in md


def test_how_to_fix_without_fix_gives_numbered_steps():
    c = check(category="explicit_tests", diagnosis="wrong_value", evidence=Evidence(call="f(1)", rule="x <= 2"))
    md = how_to_fix(c, "en").markdown
    assert md.startswith("**Steps:**")
    assert "1. " in md and "2. " in md and "`f(1)`" in md and "`x <= 2`" in md


# ---------------------------------------------------------------------------------------------
# expected_behavior
# ---------------------------------------------------------------------------------------------


def small_spec() -> PracticalSpec:
    is_safe = FunctionSpec(
        signature=FunctionSignature(name="is_safe", params=[Param(name="speed", annotation="int"),
                                                            Param(name="limit", annotation="int")],
                                    return_annotation="bool"),
        rules=[BehaviorRule(when="speed <= limit", returns="True"), BehaviorRule(when=None, returns="False")],
        tests=[FunctionTest(id="is_safe#ex1", function="is_safe", args=["200", "250"], expected_return="True"),
               FunctionTest(id="is_safe#ex2", function="is_safe", args=["300", "250"], expected_return="False")],
        origin=Origin(source=SourceRef(excerpt="Return True if speed <= limit, otherwise return False.",
                                       section="Exercise 2 — Safe speed")),
    )
    steps = [InteractionStep(kind="output", text="Pilot name: "), InteractionStep(kind="input", text="Camille"),
             InteractionStep(kind="output", text="Starting fuel: "), InteractionStep(kind="input", text="400"),
             InteractionStep(kind="output", text="Fuel: 400\n")]
    return PracticalSpec(
        structure=StructureSpec(files=[FileRequirement(path=".gitignore")], require_gitignore=True,
                                forbidden_patterns_are_errors=True),
        global_constraints=Constraints(allowed_builtins=["input", "print", "len"], forbidden_builtins=["abs", "max"],
                                       allowed_imports=[]),
        exercises=[
            ExerciseSpec(id="safe_speed", title="Safe speed", file_path=SAFE_SPEED, functions=[is_safe]),
            ExerciseSpec(id="launch_sequence", title="Launch sequence", kind="script", file_path=LAUNCH,
                         script=ScriptSpec(prompts=["Pilot name: ", "Starting fuel: "],
                                           tests=[ScriptTest(id="launch_sequence#session1", steps=steps)])),
        ],
    )


def test_expected_behavior_for_a_function_test():
    c = check(id="test:is_safe#ex1", category="explicit_tests", diagnosis="str_instead_of_bool", function="is_safe",
              exercise_id="safe_speed", test_id="is_safe#ex1", evidence=Evidence(call="is_safe(200, 250)"))
    e = expected_behavior(c, small_spec(), "fr")
    assert e.title == "Ce que demande le sujet" and e.provider == "template"
    md = e.markdown
    assert "def is_safe(speed: int, limit: int) -> bool:" in md
    assert "si `speed <= limit` → `True`" in md and "sinon → `False`" in md
    assert ">>> is_safe(200, 250)  # <- ce test\nTrue" in md
    assert "Return True if speed <= limit, otherwise return False." in md


def test_expected_behavior_for_a_derived_case():
    c = check(id="test:is_safe#derived1", category="derived_tests", diagnosis="wrong_value", function="is_safe",
              exercise_id="safe_speed", test_id="is_safe#derived1",
              evidence=Evidence(call="is_safe(250, 250)", rule="speed <= limit",
                                expected_value=ValueSnapshot(repr="True", type="bool")))
    md = expected_behavior(c, small_spec(), "en").markdown
    assert "**Tested case:** `is_safe(250, 250)`, expected `True` (`bool`) (derived from the rule `speed <= limit`)." in md


def test_expected_behavior_for_a_script_shows_the_session_with_inputs_and_trailing_spaces():
    c = check(id="test:launch_sequence#session1", category="output", diagnosis="stdout_mismatch",
              exercise_id="launch_sequence", test_id="launch_sequence#session1")
    md = expected_behavior(c, small_spec(), "en").markdown
    assert "$ python3 launch_sequence.py\nPilot name:␠⟨Camille⟩\nStarting fuel:␠⟨400⟩\nFuel: 400" in md
    assert "`␠` marks a space" in md
    assert "**Expected prompts, in order:** `Pilot name:␠`, `Starting fuel:␠`" in md


def test_expected_behavior_for_a_prompt_check():
    c = check(id="prompt:launch_sequence:1", category="output", diagnosis="prompt_mismatch",
              exercise_id="launch_sequence", evidence=Evidence(details={"expected_prompt": "Pilot name: "}))
    md = expected_behavior(c, small_spec(), "fr").markdown
    assert "Ce prompt doit être exactement `Pilot name:␠`" in md


def test_expected_behavior_for_structure_constraints_and_git():
    spec = small_spec()
    gitignore = check(id="structure:gitignore", category="structure", diagnosis="missing_gitignore", file=".gitignore")
    md = expected_behavior(gitignore, spec, "en").markdown
    assert "`.gitignore`" in md and "**explicitly forbids**" in md and "`__pycache__/`" in md
    constraint = check(id="constraint:safe_speed:forbidden_builtin:abs", category="constraints",
                       diagnosis="forbidden_builtin", exercise_id="safe_speed")
    md = expected_behavior(constraint, spec, "fr").markdown
    assert "fonctions intégrées interdites : `abs`, `max`" in md and "imports autorisés : **aucun**" in md
    git = check(id="git:untracked:a.py", category="git", diagnosis="untracked_file")
    assert "committed" in expected_behavior(git, spec, "en").markdown


def test_expected_behavior_without_matching_spec_item():
    c = check(id="syntax:other.py", category="syntax", diagnosis="syntax_error", file="other.py")
    md = expected_behavior(c, PracticalSpec(), "en").markdown
    assert md.strip()
