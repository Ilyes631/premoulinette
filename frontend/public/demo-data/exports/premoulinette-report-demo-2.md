# PréMoulinette report — TP 1 — MysteryInc: First Launch

Analysis #2 · 2026-10-04 09:51 UTC · 2.2 s · sandbox: local

> **READY TO SUBMIT** — All requirements that could be verified from the subject passed. Hidden grader tests may still exist.

- Readiness Score: **100.0%** (103/103 mandatory checks passed)
- Mandatory failures: **0**
- Bonus completion: 100.0% (3/3 bonus exercises)
- Confidence: **medium**

Confidence notes:

- 1 mandatory function(s) have fewer than 2 explicit or derived tests: remaining_fuel.
- The subject parser left 2 note(s) about ambiguous or unformalized parts of the subject.
- Developer mode sandbox: student code ran locally with weaker isolation than Docker.

*Readiness Score is not an official grade. It only covers the requirements PréMoulinette could verify from the subject; the real grader may run hidden tests.*

In differences, `-` lines are expected and `+` lines are what the program produced. Invisible characters are shown as `·` (space), `→` (tab), `↵` (newline) and `␍` (carriage return).

## Repository

| Property | Value |
|---|---|
| Project | mysteryinc_buggy |
| Source | demo |
| Path | `demo/projects/mysteryinc_fixed` |
| Detected root | (top level) |
| Files | 11 (10 Python) |

### Git

Not a git repository (or git information unavailable).

## Subject

| Property | Value |
|---|---|
| Title | TP 1 — MysteryInc: First Launch |
| Source file | subject_demo.html |
| Parser | heuristic |
| Language | python |
| Reviewed by user | no |
| Exercises | 11 (8 mandatory, 3 bonus) |

### Global constraints

- Allowed builtins: `input`, `print`, `len`, `int`, `str`, `float`, `bool`
- Forbidden builtins: `abs`, `max`, `min`, `round`, `sorted`, `sum`, `eval`
- Allowed imports: no import allowed

### Exercises

| Id | Title | File | Kind | Requirement | Origin |
|---|---|---|---|---|---|
| `kelvin` | Exercise 1 — Kelvin | `MysteryInc/FirstLaunch/flight_functions/kelvin.py` | functions | mandatory | Explicit requirement |
| `safe_speed` | Exercise 2 — Safe speed | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | functions | mandatory | Explicit requirement |
| `grade_landing` | Exercise 3 — Landing grade | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | functions | mandatory | Explicit requirement |
| `fuel_share` | Exercise 4 — Fuel share | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | functions | mandatory | Explicit requirement |
| `mission_clock` | Exercise 5 — Mission clock | `MysteryInc/FirstLaunch/route_math/mission_clock.py` | functions | mandatory | Explicit requirement |
| `FIXME2` | Exercise 6 — FIXME | `MysteryInc/FirstLaunch/FIXME2.py` | functions | mandatory | Explicit requirement |
| `access_code` | Exercise 7 — Access code | `MysteryInc/FirstLaunch/access_code.py` | script | mandatory | Explicit requirement |
| `launch_sequence` | Exercise 8 — Launch sequence | `MysteryInc/FirstLaunch/launch_sequence.py` | script | mandatory | Explicit requirement |
| `emoji_grade` | Bonus 1 — Emoji grade | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | functions | bonus | Explicit requirement |
| `max_altitude` | Bonus 2 — Max altitude | `MysteryInc/FirstLaunch/bonus/max_altitude.py` | functions | bonus | Explicit requirement |
| `countdown` | Bonus 3 — Countdown | `MysteryInc/FirstLaunch/bonus/countdown.py` | script | bonus | Explicit requirement |

### Parser notes

- Files under 'bonus/' are optional (bonus): The files in bonus/ are optional. Your repository must contain a .gitignore file.
- Functions must return their result and must not print (may_print=False).

## Mandatory requirements

Readiness Score: **100.0%** — 103/103 mandatory checks passed, 0 failure(s).

### Score by category

| Category | Passed | Total | Score | Failed | Warnings |
|---|---|---|---|---|---|
| Structure | 9 | 9 | 100.0% | 0 | 0 |
| Compilation | 8 | 8 | 100.0% | 0 | 0 |
| Required functions | 21 | 21 | 100.0% | 0 | 0 |
| Known tests | 15 | 15 | 100.0% | 0 | 0 |
| Derived tests | 10 | 10 | 100.0% | 0 | 0 |
| Output matching | 10 | 10 | 100.0% | 0 | 0 |
| Constraints | 24 | 24 | 100.0% | 0 | 0 |
| Import safety | 6 | 6 | 100.0% | 0 | 0 |

### Mandatory exercises

| Exercise | File | Status | Checks passed | Score | Issues |
|---|---|---|---|---|---|
| Exercise 1 — Kelvin | `MysteryInc/FirstLaunch/flight_functions/kelvin.py` | **PASS** | 12/12 | 100.0% | 0 |
| Exercise 2 — Safe speed | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | **PASS** | 14/14 | 100.0% | 0 |
| Exercise 3 — Landing grade | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | **PASS** | 16/16 | 100.0% | 0 |
| Exercise 4 — Fuel share | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | **PASS** | 15/15 | 100.0% | 0 |
| Exercise 5 — Mission clock | `MysteryInc/FirstLaunch/route_math/mission_clock.py` | **PASS** | 11/11 | 100.0% | 0 |
| Exercise 6 — FIXME | `MysteryInc/FirstLaunch/FIXME2.py` | **PASS** | 14/14 | 100.0% | 0 |
| Exercise 7 — Access code | `MysteryInc/FirstLaunch/access_code.py` | **PASS** | 8/8 | 100.0% | 0 |
| Exercise 8 — Launch sequence | `MysteryInc/FirstLaunch/launch_sequence.py` | **PASS** | 12/12 | 100.0% | 0 |

### Blocking issues

No mandatory failure.

## Optional requirements

*No optional requirement.*

## Structure

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Explicit requirement | MysteryInc/FirstLaunch/flight_functions/grade_landing.py is at the expected path. |
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/flight_functions/kelvin.py` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py` | Explicit requirement | MysteryInc/FirstLaunch/flight_functions/kelvin.py is at the expected path. |
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | Explicit requirement | MysteryInc/FirstLaunch/flight_functions/safe_speed.py is at the expected path. |
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/route_math/fuel_share.py` | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | Explicit requirement | MysteryInc/FirstLaunch/route_math/fuel_share.py is at the expected path. |
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/route_math/mission_clock.py` | `MysteryInc/FirstLaunch/route_math/mission_clock.py` | Explicit requirement | MysteryInc/FirstLaunch/route_math/mission_clock.py is at the expected path. |
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/FIXME2.py` | `MysteryInc/FirstLaunch/FIXME2.py` | Explicit requirement | MysteryInc/FirstLaunch/FIXME2.py is at the expected path. |
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/access_code.py` | `MysteryInc/FirstLaunch/access_code.py` | Explicit requirement | MysteryInc/FirstLaunch/access_code.py is at the expected path. |
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/launch_sequence.py` | `MysteryInc/FirstLaunch/launch_sequence.py` | Explicit requirement | MysteryInc/FirstLaunch/launch_sequence.py is at the expected path. |
| **PASS** | .gitignore present · `structure:gitignore` | `.gitignore` | Explicit requirement | A .gitignore file is present at the repository root. |

## Functions

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | Function found · `function:kelvin:to_kelvin` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Explicit requirement | to_kelvin() is defined in kelvin.py (line 1). |
| **PASS** | Signature matches the subject · `signature:kelvin:to_kelvin` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Explicit requirement | to_kelvin() has the expected signature: def to_kelvin(celsius: float) -\> float. |
| **PASS** | Returns its result · `returns:kelvin:to_kelvin` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Explicit requirement | to_kelvin() returns its result with a return statement. |
| **PASS** | Function found · `function:safe_speed:is_safe` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:1` | Explicit requirement | is_safe() is defined in safe_speed.py (line 1). |
| **PASS** | Signature matches the subject · `signature:safe_speed:is_safe` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:1` | Explicit requirement | is_safe() has the expected signature: def is_safe(speed: int, limit: int) -\> bool. |
| **PASS** | Returns its result · `returns:safe_speed:is_safe` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:1` | Explicit requirement | is_safe() returns its result with a return statement. |
| **PASS** | Function found · `function:grade_landing:landing_grade` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Explicit requirement | landing_grade() is defined in grade_landing.py (line 1). |
| **PASS** | Signature matches the subject · `signature:grade_landing:landing_grade` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Explicit requirement | landing_grade() has the expected signature: def landing_grade(vertical_speed: int) -\> str. |
| **PASS** | Returns its result · `returns:grade_landing:landing_grade` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Explicit requirement | landing_grade() returns its result with a return statement. |
| **PASS** | Function found · `function:fuel_share:fuel_share` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Explicit requirement | fuel_share() is defined in fuel_share.py (line 1). |
| **PASS** | Signature matches the subject · `signature:fuel_share:fuel_share` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Explicit requirement | fuel_share() has the expected signature: def fuel_share(total_fuel: int, crew: int) -\> int. |
| **PASS** | Returns its result · `returns:fuel_share:fuel_share` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Explicit requirement | fuel_share() returns its result with a return statement. |
| **PASS** | Function found · `function:fuel_share:remaining_fuel` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:6` | Explicit requirement | remaining_fuel() is defined in fuel_share.py (line 6). |
| **PASS** | Signature matches the subject · `signature:fuel_share:remaining_fuel` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:6` | Explicit requirement | remaining_fuel() has the expected signature: def remaining_fuel(total_fuel: int, crew: int) -\> int. |
| **PASS** | Returns its result · `returns:fuel_share:remaining_fuel` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:6` | Explicit requirement | remaining_fuel() returns its result with a return statement. |
| **PASS** | Function found · `function:mission_clock:mission_clock` | `MysteryInc/FirstLaunch/route_math/mission_clock.py:1` | Explicit requirement | mission_clock() is defined in mission_clock.py (line 1). |
| **PASS** | Signature matches the subject · `signature:mission_clock:mission_clock` | `MysteryInc/FirstLaunch/route_math/mission_clock.py:1` | Explicit requirement | mission_clock() has the expected signature: def mission_clock(seconds: int) -\> str. |
| **PASS** | Returns its result · `returns:mission_clock:mission_clock` | `MysteryInc/FirstLaunch/route_math/mission_clock.py:1` | Explicit requirement | mission_clock() returns its result with a return statement. |
| **PASS** | Function found · `function:FIXME2:average_speed` | `MysteryInc/FirstLaunch/FIXME2.py:1` | Explicit requirement | average_speed() is defined in FIXME2.py (line 1). |
| **PASS** | Signature matches the subject · `signature:FIXME2:average_speed` | `MysteryInc/FirstLaunch/FIXME2.py:1` | Explicit requirement | average_speed() has the expected signature: def average_speed(distance: float, hours: float) -\> float. |
| **PASS** | Returns its result · `returns:FIXME2:average_speed` | `MysteryInc/FirstLaunch/FIXME2.py:1` | Explicit requirement | average_speed() returns its result with a return statement. |

## Scripts

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | python3 access_code.py: output matches · `test:access_code#session1` | `MysteryInc/FirstLaunch/access_code.py` | Explicit requirement | The output matches the subject exactly. |
| **PASS** | python3 access_code.py: output matches · `test:access_code#session2` | `MysteryInc/FirstLaunch/access_code.py` | Explicit requirement | The output matches the subject exactly. |
| **PASS** | Prompt 1: 'Enter access code: ' · `prompt:access_code:1` | `MysteryInc/FirstLaunch/access_code.py:1` | Explicit requirement | The input() prompt 1 matches the subject exactly (line 1 of MysteryInc/FirstLaunch/access_code.py). |
| **PASS** | python3 launch_sequence.py: output matches · `test:launch_sequence#session1` | `MysteryInc/FirstLaunch/launch_sequence.py` | Explicit requirement | The output matches the subject exactly. |
| **PASS** | python3 launch_sequence.py: output matches · `test:launch_sequence#session2` | `MysteryInc/FirstLaunch/launch_sequence.py` | Explicit requirement | The output matches the subject exactly. |
| **PASS** | python3 launch_sequence.py: output matches · `test:launch_sequence#session3` | `MysteryInc/FirstLaunch/launch_sequence.py` | Explicit requirement | The output matches the subject exactly. |
| **PASS** | Prompt 1: 'Pilot name: ' · `prompt:launch_sequence:1` | `MysteryInc/FirstLaunch/launch_sequence.py:1` | Explicit requirement | The input() prompt 1 matches the subject exactly (line 1 of MysteryInc/FirstLaunch/launch_sequence.py). |
| **PASS** | Prompt 2: 'Starting fuel: ' · `prompt:launch_sequence:2` | `MysteryInc/FirstLaunch/launch_sequence.py:2` | Explicit requirement | The input() prompt 2 matches the subject exactly (line 2 of MysteryInc/FirstLaunch/launch_sequence.py). |
| **PASS** | Prompt 3: 'Your choice: ' · `prompt:launch_sequence:3` | `MysteryInc/FirstLaunch/launch_sequence.py:8` | Explicit requirement | The input() prompt 3 matches the subject exactly (line 8 of MysteryInc/FirstLaunch/launch_sequence.py). |
| **PASS** | Prompt 4: 'Set a trap or collect evidence? (trap/evidence) ' · `prompt:launch_sequence:4` | `MysteryInc/FirstLaunch/launch_sequence.py:27` | Explicit requirement | The input() prompt 4 matches the subject exactly (line 27 of MysteryInc/FirstLaunch/launch_sequence.py). |

## Constraints

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | No forbidden builtin · `constraint:kelvin:forbidden_builtin:*` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py` | Explicit requirement | kelvin.py calls none of the forbidden builtins (abs, max, min, round, sorted, sum, eval). |
| **PASS** | Only authorized builtins · `constraint:kelvin:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py` | Explicit requirement | kelvin.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:kelvin:import:*` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py` | Explicit requirement | kelvin.py imports nothing, as required. |
| **PASS** | No forbidden builtin · `constraint:safe_speed:forbidden_builtin:*` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | Explicit requirement | safe_speed.py calls none of the forbidden builtins (abs, max, min, round, sorted, sum, eval). |
| **PASS** | Only authorized builtins · `constraint:safe_speed:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | Explicit requirement | safe_speed.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:safe_speed:import:*` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | Explicit requirement | safe_speed.py imports nothing, as required. |
| **PASS** | No forbidden builtin · `constraint:grade_landing:forbidden_builtin:*` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Explicit requirement | grade_landing.py calls none of the forbidden builtins (abs, max, min, round, sorted, sum, eval). |
| **PASS** | Only authorized builtins · `constraint:grade_landing:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Explicit requirement | grade_landing.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:grade_landing:import:*` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Explicit requirement | grade_landing.py imports nothing, as required. |
| **PASS** | No forbidden builtin · `constraint:fuel_share:forbidden_builtin:*` | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | Explicit requirement | fuel_share.py calls none of the forbidden builtins (abs, max, min, round, sorted, sum, eval). |
| **PASS** | Only authorized builtins · `constraint:fuel_share:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | Explicit requirement | fuel_share.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:fuel_share:import:*` | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | Explicit requirement | fuel_share.py imports nothing, as required. |
| **PASS** | No forbidden builtin · `constraint:mission_clock:forbidden_builtin:*` | `MysteryInc/FirstLaunch/route_math/mission_clock.py` | Explicit requirement | mission_clock.py calls none of the forbidden builtins (abs, max, min, round, sorted, sum, eval). |
| **PASS** | Only authorized builtins · `constraint:mission_clock:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/route_math/mission_clock.py` | Explicit requirement | mission_clock.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:mission_clock:import:*` | `MysteryInc/FirstLaunch/route_math/mission_clock.py` | Explicit requirement | mission_clock.py imports nothing, as required. |
| **PASS** | No forbidden builtin · `constraint:FIXME2:forbidden_builtin:*` | `MysteryInc/FirstLaunch/FIXME2.py` | Explicit requirement | FIXME2.py calls none of the forbidden builtins (abs, max, min, round, sorted, sum, eval). |
| **PASS** | Only authorized builtins · `constraint:FIXME2:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/FIXME2.py` | Explicit requirement | FIXME2.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:FIXME2:import:*` | `MysteryInc/FirstLaunch/FIXME2.py` | Explicit requirement | FIXME2.py imports nothing, as required. |
| **PASS** | No forbidden builtin · `constraint:access_code:forbidden_builtin:*` | `MysteryInc/FirstLaunch/access_code.py` | Explicit requirement | access_code.py calls none of the forbidden builtins (abs, max, min, round, sorted, sum, eval). |
| **PASS** | Only authorized builtins · `constraint:access_code:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/access_code.py` | Explicit requirement | access_code.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:access_code:import:*` | `MysteryInc/FirstLaunch/access_code.py` | Explicit requirement | access_code.py imports nothing, as required. |
| **PASS** | No forbidden builtin · `constraint:launch_sequence:forbidden_builtin:*` | `MysteryInc/FirstLaunch/launch_sequence.py` | Explicit requirement | launch_sequence.py calls none of the forbidden builtins (abs, max, min, round, sorted, sum, eval). |
| **PASS** | Only authorized builtins · `constraint:launch_sequence:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/launch_sequence.py` | Explicit requirement | launch_sequence.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:launch_sequence:import:*` | `MysteryInc/FirstLaunch/launch_sequence.py` | Explicit requirement | launch_sequence.py imports nothing, as required. |

## Static analysis

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Explicit requirement | grade_landing.py compiles without syntax errors. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/flight_functions/kelvin.py` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py` | Explicit requirement | kelvin.py compiles without syntax errors. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | Explicit requirement | safe_speed.py compiles without syntax errors. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/route_math/fuel_share.py` | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | Explicit requirement | fuel_share.py compiles without syntax errors. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/route_math/mission_clock.py` | `MysteryInc/FirstLaunch/route_math/mission_clock.py` | Explicit requirement | mission_clock.py compiles without syntax errors. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/FIXME2.py` | `MysteryInc/FirstLaunch/FIXME2.py` | Explicit requirement | FIXME2.py compiles without syntax errors. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/access_code.py` | `MysteryInc/FirstLaunch/access_code.py` | Explicit requirement | access_code.py compiles without syntax errors. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/launch_sequence.py` | `MysteryInc/FirstLaunch/launch_sequence.py` | Explicit requirement | launch_sequence.py compiles without syntax errors. |

## Runtime analysis

| Sandbox | Value |
|---|---|
| Mode | Local (developer mode) |
| Image | — |
| Python | 3.14.7 |
| Network | disabled |
| Limits | memory_mb=512, max_processes=32, isolation=windows-job-object, global_timeout_slack_s=15.0, network=blocked by audit hook, filesystem=temporary copy of the project (writes elsewhere blocked by audit hook) |

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | No side effects at import · `import_effects:kelvin` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py` | Explicit requirement | Importing the module prints nothing, asks for no input and does not crash. |
| **PASS** | No side effects at import · `import_effects:safe_speed` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | Explicit requirement | Importing the module prints nothing, asks for no input and does not crash. |
| **PASS** | No side effects at import · `import_effects:grade_landing` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Explicit requirement | Importing the module prints nothing, asks for no input and does not crash. |
| **PASS** | No side effects at import · `import_effects:fuel_share` | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | Explicit requirement | Importing the module prints nothing, asks for no input and does not crash. |
| **PASS** | No side effects at import · `import_effects:mission_clock` | `MysteryInc/FirstLaunch/route_math/mission_clock.py` | Explicit requirement | Importing the module prints nothing, asks for no input and does not crash. |
| **PASS** | No side effects at import · `import_effects:FIXME2` | `MysteryInc/FirstLaunch/FIXME2.py` | Explicit requirement | Importing the module prints nothing, asks for no input and does not crash. |

## Known tests

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | to_kelvin(0) · `test:to_kelvin#ex1` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Explicit requirement | Returned 273.15 as expected. |
| **PASS** | to_kelvin(100) · `test:to_kelvin#ex2` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Explicit requirement | Returned 373.15 as expected. |
| **PASS** | to_kelvin(-273.15) · `test:to_kelvin#ex3` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Explicit requirement | Returned 0.0 as expected. |
| **PASS** | is_safe(200, 250) · `test:is_safe#ex1` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:1` | Explicit requirement | Returned True as expected. |
| **PASS** | is_safe(300, 250) · `test:is_safe#ex2` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:1` | Explicit requirement | Returned False as expected. |
| **PASS** | landing_grade(1) · `test:landing_grade#ex1` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Explicit requirement | Returned 'Perfect touchdown' as expected. |
| **PASS** | landing_grade(4) · `test:landing_grade#ex2` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Explicit requirement | Returned 'Hard landing' as expected. |
| **PASS** | landing_grade(9) · `test:landing_grade#ex3` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Explicit requirement | Returned 'Crash!' as expected. |
| **PASS** | fuel_share(400, 3) · `test:fuel_share#ex1` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Explicit requirement | Returned 133 as expected. |
| **PASS** | fuel_share(500, 3) · `test:fuel_share#ex2` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Explicit requirement | Returned 166 as expected. |
| **PASS** | remaining_fuel(400, 3) · `test:remaining_fuel#ex1` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:6` | Explicit requirement | Returned 1 as expected. |
| **PASS** | mission_clock(3725) · `test:mission_clock#ex1` | `MysteryInc/FirstLaunch/route_math/mission_clock.py:1` | Explicit requirement | Returned '01:02:05' as expected. |
| **PASS** | mission_clock(0) · `test:mission_clock#ex2` | `MysteryInc/FirstLaunch/route_math/mission_clock.py:1` | Explicit requirement | Returned '00:00:00' as expected. |
| **PASS** | average_speed(150.0, 2.0) · `test:average_speed#ex1` | `MysteryInc/FirstLaunch/FIXME2.py:1` | Explicit requirement | Returned 75.0 as expected. |
| **PASS** | average_speed(10.0, 0.0) · `test:average_speed#ex2` | `MysteryInc/FirstLaunch/FIXME2.py:1` | Explicit requirement | Returned 0.0 as expected. |

## Derived tests

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | is_safe(250, 250) · `test:is_safe#derived1` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:1` | Derived test | Returned True as expected. |
| **PASS** | is_safe(251, 250) · `test:is_safe#derived2` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:1` | Derived test | Returned False as expected. |
| **PASS** | is_safe(249, 250) · `test:is_safe#derived3` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:1` | Derived test | Returned True as expected. |
| **PASS** | landing_grade(2) · `test:landing_grade#derived1` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Derived test | Returned 'Perfect touchdown' as expected. |
| **PASS** | landing_grade(3) · `test:landing_grade#derived2` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Derived test | Returned 'Hard landing' as expected. |
| **PASS** | landing_grade(5) · `test:landing_grade#derived3` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Derived test | Returned 'Hard landing' as expected. |
| **PASS** | landing_grade(6) · `test:landing_grade#derived4` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Derived test | Returned 'Crash!' as expected. |
| **PASS** | average_speed(150.0, 0.0) · `test:average_speed#derived1` | `MysteryInc/FirstLaunch/FIXME2.py:1` | Derived test | Returned 0.0 as expected. |
| **PASS** | average_speed(150.0, 0.5) · `test:average_speed#derived2` | `MysteryInc/FirstLaunch/FIXME2.py:1` | Derived test | Returned 300.0 as expected. |
| **PASS** | average_speed(150.0, -0.5) · `test:average_speed#derived3` | `MysteryInc/FirstLaunch/FIXME2.py:1` | Derived test | Returned -300.0 as expected. |

## Warnings

- Developer mode: the student code runs directly on this computer, under your user account, not inside a container.
- Network access, process creation and writes outside the temporary copy are blocked by Python audit hooks inside the harness. This is a best-effort guard, not a security boundary: the code can still read your files. Use Docker safe mode for code you do not trust.
- A Windows Job Object limits each run to 32 processes and 512 MB of memory and kills every remaining process at the end.

### Heuristic tests (not official)

Extra cases proposed by PréMoulinette. They are not requirements of the subject and never change the Readiness Score.

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | to_kelvin(-1.0) · `test:to_kelvin#heur1` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Heuristic (not official) | Returned 272.15 as expected. |
| **PASS** | to_kelvin(1000000.0) · `test:to_kelvin#heur2` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Heuristic (not official) | Returned 1000273.15 as expected. |
| **PASS** | is_safe(0, 250) · `test:is_safe#heur1` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:1` | Heuristic (not official) | Returned True as expected. |
| **PASS** | is_safe(-1, 250) · `test:is_safe#heur2` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:1` | Heuristic (not official) | Returned True as expected. |
| **PASS** | is_safe(1000000, 250) · `test:is_safe#heur3` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:1` | Heuristic (not official) | Returned False as expected. |
| **PASS** | landing_grade(0) · `test:landing_grade#heur1` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Heuristic (not official) | Returned 'Perfect touchdown' as expected. |
| **PASS** | landing_grade(-1) · `test:landing_grade#heur2` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Heuristic (not official) | Returned 'Perfect touchdown' as expected. |
| **PASS** | landing_grade(1000000) · `test:landing_grade#heur3` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Heuristic (not official) | Returned 'Crash!' as expected. |
| **PASS** | fuel_share(0, 3) · `test:fuel_share#heur1` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Heuristic (not official) | Returned 0 as expected. |
| **PASS** | fuel_share(-1, 3) · `test:fuel_share#heur2` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Heuristic (not official) | Returned -1 as expected. |
| **PASS** | fuel_share(1000000, 3) · `test:fuel_share#heur3` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Heuristic (not official) | Returned 333333 as expected. |
| **PASS** | remaining_fuel(0, 3) · `test:remaining_fuel#heur1` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:6` | Heuristic (not official) | Returned 0 as expected. |
| **PASS** | remaining_fuel(-1, 3) · `test:remaining_fuel#heur2` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:6` | Heuristic (not official) | Returned 2 as expected. |
| **PASS** | remaining_fuel(1000000, 3) · `test:remaining_fuel#heur3` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:6` | Heuristic (not official) | Returned 1 as expected. |
| **PASS** | mission_clock(-1) · `test:mission_clock#heur1` | `MysteryInc/FirstLaunch/route_math/mission_clock.py:1` | Heuristic (not official) | Returned '-1:59:59' as expected. |
| **PASS** | mission_clock(1000000) · `test:mission_clock#heur2` | `MysteryInc/FirstLaunch/route_math/mission_clock.py:1` | Heuristic (not official) | Returned '277:46:40' as expected. |
| **PASS** | average_speed(0.0, 2.0) · `test:average_speed#heur1` | `MysteryInc/FirstLaunch/FIXME2.py:1` | Heuristic (not official) | Returned 0.0 as expected. |
| **PASS** | average_speed(-1.0, 2.0) · `test:average_speed#heur2` | `MysteryInc/FirstLaunch/FIXME2.py:1` | Heuristic (not official) | Returned -0.5 as expected. |
| **PASS** | average_speed(1000000.0, 2.0) · `test:average_speed#heur3` | `MysteryInc/FirstLaunch/FIXME2.py:1` | Heuristic (not official) | Returned 500000.0 as expected. |
| **PASS** | emoji_grade(-1) · `test:emoji_grade#heur1` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:12` | Heuristic (not official) | Returned '🟢' as expected. |
| **PASS** | emoji_grade(1000000) · `test:emoji_grade#heur2` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:12` | Heuristic (not official) | Returned '🔴' as expected. |
| **PASS** | max_altitude(0, 450, 300) · `test:max_altitude#heur1` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Heuristic (not official) | The call returned 450 (int), as annotated. |
| **PASS** | max_altitude(-1, 450, 300) · `test:max_altitude#heur2` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Heuristic (not official) | The call returned 450 (int), as annotated. |
| **PASS** | max_altitude(1000000, 450, 300) · `test:max_altitude#heur3` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Heuristic (not official) | The call returned 1000000 (int), as annotated. |

## Bonus

Bonus completion: **100.0%** (3/3 bonus exercises fully passing). Bonus items never block the submission.

| Exercise | File | Status | Checks passed | Score | Issues |
|---|---|---|---|---|---|
| Bonus 1 — Emoji grade | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | **PASS** | 15/15 | 100.0% | 0 |
| Bonus 2 — Max altitude | `MysteryInc/FirstLaunch/bonus/max_altitude.py` | **PASS** | 11/11 | 100.0% | 0 |
| Bonus 3 — Countdown | `MysteryInc/FirstLaunch/bonus/countdown.py` | **PASS** | 7/7 | 100.0% | 0 |

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/bonus/countdown.py` | `MysteryInc/FirstLaunch/bonus/countdown.py` | Explicit requirement | MysteryInc/FirstLaunch/bonus/countdown.py is at the expected path. |
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/bonus/max_altitude.py` | `MysteryInc/FirstLaunch/bonus/max_altitude.py` | Explicit requirement | MysteryInc/FirstLaunch/bonus/max_altitude.py is at the expected path. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/bonus/countdown.py` | `MysteryInc/FirstLaunch/bonus/countdown.py` | Explicit requirement | countdown.py compiles without syntax errors. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/bonus/max_altitude.py` | `MysteryInc/FirstLaunch/bonus/max_altitude.py` | Explicit requirement | max_altitude.py compiles without syntax errors. |
| **PASS** | Function found · `function:emoji_grade:emoji_grade` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:12` | Explicit requirement | emoji_grade() is defined in grade_landing.py (line 12). |
| **PASS** | Signature matches the subject · `signature:emoji_grade:emoji_grade` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:12` | Explicit requirement | emoji_grade() has the expected signature: def emoji_grade(vertical_speed: int) -\> str. |
| **PASS** | Returns its result · `returns:emoji_grade:emoji_grade` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:12` | Explicit requirement | emoji_grade() returns its result with a return statement. |
| **PASS** | Function found · `function:max_altitude:max_altitude` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Explicit requirement | max_altitude() is defined in max_altitude.py (line 1). |
| **PASS** | Signature matches the subject · `signature:max_altitude:max_altitude` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Explicit requirement | max_altitude() has the expected signature: def max_altitude(a: int, b: int, c: int) -\> int. |
| **PASS** | Returns its result · `returns:max_altitude:max_altitude` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Explicit requirement | max_altitude() returns its result with a return statement. |
| **PASS** | No side effects at import · `import_effects:max_altitude` | `MysteryInc/FirstLaunch/bonus/max_altitude.py` | Explicit requirement | Importing the module prints nothing, asks for no input and does not crash. |
| **PASS** | emoji_grade(0) · `test:emoji_grade#ex1` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:12` | Explicit requirement | Returned '🟢' as expected. |
| **PASS** | emoji_grade(7) · `test:emoji_grade#ex2` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:12` | Explicit requirement | Returned '🔴' as expected. |
| **PASS** | max_altitude(120, 450, 300) · `test:max_altitude#ex1` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Explicit requirement | Returned 450 as expected. |
| **PASS** | max_altitude(-5, -2, -9) · `test:max_altitude#ex2` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Explicit requirement | Returned -2 as expected. |
| **PASS** | python3 countdown.py: output matches · `test:countdown#session1` | `MysteryInc/FirstLaunch/bonus/countdown.py` | Explicit requirement | The output matches the subject exactly. |
| **PASS** | Prompt 1: 'Countdown start: ' · `prompt:countdown:1` | `MysteryInc/FirstLaunch/bonus/countdown.py:2` | Explicit requirement | The input() prompt 1 matches the subject exactly (line 2 of MysteryInc/FirstLaunch/bonus/countdown.py). |
| **PASS** | emoji_grade(1) · `test:emoji_grade#derived1` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:12` | Derived test | Returned '🟢' as expected. |
| **PASS** | emoji_grade(2) · `test:emoji_grade#derived2` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:12` | Derived test | Returned '🟢' as expected. |
| **PASS** | emoji_grade(3) · `test:emoji_grade#derived3` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:12` | Derived test | Returned '🟡' as expected. |
| **PASS** | emoji_grade(4) · `test:emoji_grade#derived4` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:12` | Derived test | Returned '🟡' as expected. |
| **PASS** | emoji_grade(5) · `test:emoji_grade#derived5` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:12` | Derived test | Returned '🟡' as expected. |
| **PASS** | emoji_grade(6) · `test:emoji_grade#derived6` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:12` | Derived test | Returned '🔴' as expected. |
| **PASS** | emoji_grade(-1) · `test:emoji_grade#heur1` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:12` | Heuristic (not official) | Returned '🟢' as expected. |
| **PASS** | emoji_grade(1000000) · `test:emoji_grade#heur2` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:12` | Heuristic (not official) | Returned '🔴' as expected. |
| **PASS** | max_altitude(0, 450, 300) · `test:max_altitude#heur1` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Heuristic (not official) | The call returned 450 (int), as annotated. |
| **PASS** | max_altitude(-1, 450, 300) · `test:max_altitude#heur2` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Heuristic (not official) | The call returned 450 (int), as annotated. |
| **PASS** | max_altitude(1000000, 450, 300) · `test:max_altitude#heur3` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Heuristic (not official) | The call returned 1000000 (int), as annotated. |
| **PASS** | No forbidden builtin · `constraint:emoji_grade:forbidden_builtin:*` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Explicit requirement | grade_landing.py calls none of the forbidden builtins (abs, max, min, round, sorted, sum, eval). |
| **PASS** | Only authorized builtins · `constraint:emoji_grade:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Explicit requirement | grade_landing.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:emoji_grade:import:*` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Explicit requirement | grade_landing.py imports nothing, as required. |
| **PASS** | No forbidden builtin · `constraint:max_altitude:forbidden_builtin:*` | `MysteryInc/FirstLaunch/bonus/max_altitude.py` | Explicit requirement | max_altitude.py calls none of the forbidden builtins (abs, max, min, round, sorted, sum, eval). |
| **PASS** | Only authorized builtins · `constraint:max_altitude:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/bonus/max_altitude.py` | Explicit requirement | max_altitude.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:max_altitude:import:*` | `MysteryInc/FirstLaunch/bonus/max_altitude.py` | Explicit requirement | max_altitude.py imports nothing, as required. |
| **PASS** | No forbidden builtin · `constraint:countdown:forbidden_builtin:*` | `MysteryInc/FirstLaunch/bonus/countdown.py` | Explicit requirement | countdown.py calls none of the forbidden builtins (abs, max, min, round, sorted, sum, eval). |
| **PASS** | Only authorized builtins · `constraint:countdown:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/bonus/countdown.py` | Explicit requirement | countdown.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:countdown:import:*` | `MysteryInc/FirstLaunch/bonus/countdown.py` | Explicit requirement | countdown.py imports nothing, as required. |

---

*Readiness Score is not an official grade. It only covers the requirements PréMoulinette could verify from the subject; the real grader may run hidden tests.*
