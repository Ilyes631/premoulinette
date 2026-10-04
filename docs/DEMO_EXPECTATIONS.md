# Demo expectations

What PréMoulinette must report when the two demo projects and the test fixture variants are analysed against
`demo/subject_demo.html` ("TP 1 — MysteryInc: First Launch"). Check ids and diagnosis codes follow
`docs/ARCHITECTURE.md`. The machine-readable version of this page is `backend/tests/fixtures/expected.json`.
It is the oracle for end-to-end tests.

The demo data is validated without PréMoulinette by `backend/tests/test_fixtures_sanity.py`. That test runs
the student code directly in isolated subprocesses and compares byte-exact output against the subject:

```
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_fixtures_sanity.py -q
```

## Fixed project: `demo/projects/mysteryinc_fixed`

A fully correct submission. Expected verdict: **READY TO SUBMIT**, mandatory readiness 100 %, bonus completion 100 %.

* The tree is exactly the subject tree, including `.gitignore` (`__pycache__/`, `*.pyc`, `.DS_Store`), `bonus/countdown.py`,
  `bonus/max_altitude.py`, and `emoji_grade` in `grade_landing.py`. There are no parasite files.
* The code uses only the authorized builtins (`input print len int str float bool`), has no `import`, and never calls a forbidden builtin.
* Function files contain only `def`s, with signatures exactly as in the subject. Functions return and never print.
* All 19 doctest examples return the exact `repr`. So do the rule boundaries (`is_safe(250, 250)`, `landing_grade(2)`, `landing_grade(5)`, `emoji_grade(2)`, `emoji_grade(5)`…).
* All 6 terminal sessions produce byte-exact stdout. Prompts keep their trailing spaces, and typed input is not echoed.
* `launch_sequence.py` and `access_code.py` run at top level. `bonus/countdown.py` uses a `main()` + `if __name__ == "__main__":` guard,
  so both script styles are exercised.

No check may be `fail` or `skipped`. Heuristic tests may only be `warning` (see the notes at the end).

## Buggy project: `demo/projects/mysteryinc_buggy`

The same project with 18 deliberate issues and nothing else. The sanity test checks that every buggy `.py` file equals the fixed
file plus the edits listed here. Expected verdict: **DO NOT SUBMIT YET**.

| # | Intentional issue | Where | Expected check id | Diagnosis | Status | Severity |
|---|---|---|---|---|---|---|
| 1 | No `.gitignore` at the repository root | `/` | `structure:gitignore` (a `structure:file:.gitignore` check may also appear) | `missing_gitignore` | fail | major or critical (not fixed by ARCHITECTURE) |
| 2 | `__pycache__` folder with `kelvin.cpython-312.pyc` | `MysteryInc/FirstLaunch/flight_functions/__pycache__/` | `structure:parasite:MysteryInc/FirstLaunch/flight_functions/__pycache__` (the dir, or the `.pyc` path below it) | `parasite_file` | fail (the subject forbids them, so `forbidden_patterns_are_errors`) | major |
| 3 | `.DS_Store` | `MysteryInc/.DS_Store` | `structure:parasite:MysteryInc/.DS_Store` | `parasite_file` | fail | major |
| 4 | `mission_clock.py` misplaced | found at `MysteryInc/FirstLaunch/mission_clock.py` instead of `route_math/` | `structure:file:MysteryInc/FirstLaunch/route_math/mission_clock.py` | `misplaced_file` | fail | critical |
| 5 | `mission_clock` prints instead of returning | `MysteryInc/FirstLaunch/mission_clock.py:6` | `returns:mission_clock:mission_clock` (static) | `prints_instead_of_returns` | fail | major |
|   | ↳ runtime (tests still run because `file_map` points to the misplaced file) | | `test:mission_clock#ex1`, `test:mission_clock#ex2` | `prints_instead_of_returns` (returns `None`, the call stdout contains `01:02:05`) | fail | major |
| 6 | `FIXME2.py` syntax error: missing `:` after `if hours == 0` | `FIXME2.py:3` | `syntax:MysteryInc/FirstLaunch/FIXME2.py` | `syntax_error` (`expected ':'`) | fail | critical |
|   | ↳ tests blocked | | `test:average_speed#ex1`, `test:average_speed#ex2` | — | skipped (`blocked_by` = the syntax check), still mandatory | — |
| 7 | `is_safe` returns `"True"` / `"False"` (strings) | `flight_functions/safe_speed.py:4,6` | `returns:safe_speed:is_safe` (static) | `str_instead_of_bool` | fail | major |
|   | ↳ runtime | | `test:is_safe#ex1`, `test:is_safe#ex2`, `test:is_safe#derived<n>` | `str_instead_of_bool` (`'True'` vs `True`) | fail | major |
| 8 | Leftover debug line `print(to_kelvin(25))` at top level | `flight_functions/kelvin.py:6` | `import_effects:kelvin` | `import_side_effects` (prints `298.15` at import) | warning | major |
|   | ↳ the function itself is right | | `test:to_kelvin#ex1..3` | — | **pass** | — |
| 9 | `landing_grade` uses `vertical_speed < 2` (boundary bug) | `flight_functions/grade_landing.py:3` | `test:landing_grade#derived<n>` (the `vertical_speed == 2` case: `'Hard landing'` instead of `'Perfect touchdown'`) | `wrong_string` (or `wrong_value`) | fail | major |
|   | ↳ the explicit examples 1 / 4 / 9 still pass | | `test:landing_grade#ex1..3` | — | **pass** | — |
| 10 | Bonus `emoji_grade` not implemented | `flight_functions/grade_landing.py` | `function:emoji_grade:emoji_grade` | `missing_function` or `bonus_not_implemented` | bonus | — |
| 11 | `fuel_share` uses the forbidden `round()` | `route_math/fuel_share.py:3` | `constraint:fuel_share:forbidden_builtin:round` (a `builtin_not_allowed` check may also appear) | `forbidden_builtin` | fail | critical |
|   | ↳ `round(500 / 3)` = 167, expected 166 (`fuel_share(400, 3)` = 133 still passes) | | `test:fuel_share#ex<n>` for `fuel_share(500, 3)` (`test:fuel_share#ex1` passes) | `wrong_value` | fail | major |
| 12 | `remaining_fuel` misnamed `remaining_fuels` (body correct) | `route_math/fuel_share.py:6` | `function:fuel_share:remaining_fuel` (the message names `remaining_fuels`) | `wrong_function_name` | fail | critical |
|   | ↳ test blocked | | `test:remaining_fuel#ex1` | — | skipped (`blocked_by` the function check) | — |
| 13 | `access_code` compares `code.upper() == "SCOOBY"`, so `scooby` is accepted | `access_code.py:4` | `test:access_code#session2` | `stdout_mismatch` (`Access granted. Welcome aboard!` instead of `Access denied.`) | fail | major |
|   | ↳ | | `test:access_code#session1` | — | **pass** | — |
| 14 | Prompt `"Pilot name:"` (missing trailing space) | `launch_sequence.py:1` | `prompt:launch_sequence:<n>` (1st prompt) | `prompt_mismatch` | fail | minor |
| 15 | Menu line `2 - The Older Mill` | `launch_sequence.py:6` | `test:launch_sequence#session1`, `#session2`, `#session3` (all three print the menu) | `stdout_mismatch` | fail | minor (typo) |
| 16 | Prompt `"Set a trap or callect evidence? (trap/evidence) "` | `launch_sequence.py:27` | `prompt:launch_sequence:<n>` (4th prompt), plus sessions 1 and 3 | `prompt_mismatch` | fail | minor |
| 17 | Bonus `max_altitude` uses the forbidden `max()` (results right) | `bonus/max_altitude.py:2` | `constraint:max_altitude:forbidden_builtin:max` | `forbidden_builtin` | bonus (bonus exercise: `mandatory=False`) | — |
|   | ↳ | | `test:max_altitude#ex1`, `#ex2` | — | pass (bonus) | — |
| 18 | Bonus `countdown.py` missing | `bonus/countdown.py` | `structure:file:MysteryInc/FirstLaunch/bonus/countdown.py` | `missing_bonus_file` | bonus | — |

Exact raw stdout of the buggy `launch_sequence.py` for session 1 (stdin `Camille\n400\n2\ntrap\n`):

```
Pilot name:Starting fuel: Where's the Mystery Machine headed today?
1 - Crystal Cove
2 - The Older Mill
3 - Spooky Swamp
Your choice: Destination: The Old Mill
Fuel after the trip: 280
Set a trap or callect evidence? (trap/evidence) Camille sets a trap at The Old Mill. Zoinks!
```

Checks that must still **pass** on the buggy project (each bug is isolated): `test:to_kelvin#ex*`, `test:landing_grade#ex*`,
`test:fuel_share#ex1`, `test:access_code#session1`, `test:max_altitude#ex*`, `function:kelvin:to_kelvin`,
`function:safe_speed:is_safe`, `function:fuel_share:fuel_share`.

## Fixture variants: `backend/tests/fixtures/projects/<variant>`

Each variant is generated by `backend/tests/fixtures/make_fixtures.py` from the fixed project, with exactly one mutation.
The script is idempotent and every replacement must match exactly once. After any change to `mysteryinc_fixed`, rerun it:

```
backend\.venv\Scripts\python.exe backend/tests/fixtures/make_fixtures.py
```

| Variant | Mutation | Expected check id | Diagnosis | Status | Severity | Verdict |
|---|---|---|---|---|---|---|
| `correct_project` | none | — (everything passes) | — | pass | — | ready, 100 % |
| `wrong_bool_type` | `safe_speed.py`: `return "True"` / `return "False"` | `returns:safe_speed:is_safe`, `test:is_safe#ex1`, `test:is_safe#ex2`, `test:is_safe#derived<n>` | `str_instead_of_bool` | fail | major | not ready |
| `wrong_prompt` | `launch_sequence.py`: `callect` typo in the trap prompt | `prompt:launch_sequence:<n>`, `test:launch_sequence#session1`, `test:launch_sequence#session3` (`#session2` passes) | `prompt_mismatch` / `stdout_mismatch` | fail | minor | not ready |
| `missing_file` | `route_math/fuel_share.py` deleted | `structure:file:MysteryInc/FirstLaunch/route_math/fuel_share.py`, then `test:fuel_share#ex*` and `test:remaining_fuel#ex1` skipped | `missing_file` | fail | critical | not ready |
| `syntax_error` | `FIXME2.py:3`: `if hours == 0` without `:` | `syntax:MysteryInc/FirstLaunch/FIXME2.py`, then `test:average_speed#ex*` skipped | `syntax_error` | fail | critical | not ready |
| `forbidden_builtin` | `kelvin.py:3`: `return celsius + 273.15 if abs(celsius) >= 0 else 0.0` (results unchanged) | `constraint:kelvin:forbidden_builtin:abs` (the `to_kelvin` tests still pass) | `forbidden_builtin` | fail | critical | not ready |
| `wrong_function_name` | `safe_speed.py`: `def is_save(` | `function:safe_speed:is_safe`, then `test:is_safe#ex*` skipped | `wrong_function_name` | fail | critical | not ready |
| `missing_bonus` | `emoji_grade` removed and `bonus/` deleted | `structure:file:MysteryInc/FirstLaunch/bonus/countdown.py`, `structure:file:MysteryInc/FirstLaunch/bonus/max_altitude.py`, `function:emoji_grade:emoji_grade` | `missing_bonus_file`, `missing_function` or `bonus_not_implemented` | bonus | — | **ready** (bonus completion 0 %) |

## Notes and assumptions

* Explicit test numbering is `<function>#ex<n>`, 1-based. Whether `<n>` counts per function or per subject section is an
  implementation detail, so `expected.json` uses prefixes such as `test:fuel_share#ex`. The first example
  (`fuel_share(400, 3)`) is `ex1` under both schemes. The same applies to prompt indices `prompt:<exercise_id>:<n>`.
* The subject says "You can assume `crew > 0`". A heuristic test with `crew=0` would raise `ZeroDivisionError` even on the
  fixed project. Heuristic tests are `warning` / `mandatory=False`, so the verdict is unaffected, but the generator should
  skip that case.
* The demo and fixture folders are **not** git repositories. Git checks should be absent or `info`. Snapshots live under
  `<repo>/.data/`, which is inside the PréMoulinette git repository, so `read_git_info` must not walk up to it.
  Use `GIT_CEILING_DIRECTORIES` or check `<root>/.git`.
* The repository `.gitignore` re-includes `demo/projects/**` and `backend/tests/fixtures/projects/**`. That keeps the deliberate
  parasites (`__pycache__`, `.DS_Store`) committed. Do not remove those negations.
