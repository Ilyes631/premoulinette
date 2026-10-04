# PréMoulinette report — TP 1 — MysteryInc: First Launch

Analysis #2 · 2026-10-04 12:48 UTC · 1.3 s · sandbox: local

> **DO NOT SUBMIT YET** — 31 mandatory failure(s) remain. Fix critical issues first.

- Readiness Score: **68.0%** (66/97 mandatory checks passed)
- Mandatory failures: **31**
- Bonus completion: 0.0% (0/3 bonus exercises)
- Confidence: **medium**

Confidence notes:

- 1 mandatory function(s) have fewer than 2 explicit or derived tests: remaining_fuel.
- 6 heuristic test warning(s): extra cases that are not official requirements failed.
- The subject parser left 2 note(s) about ambiguous or unformalized parts of the subject.
- Developer mode sandbox: student code ran locally with weaker isolation than Docker.

*Readiness Score is not an official grade. It only covers the requirements PréMoulinette could verify from the subject; the real grader may run hidden tests.*

In differences, `-` lines are expected and `+` lines are what the program produced. Invisible characters are shown as `·` (space), `→` (tab), `↵` (newline) and `␍` (carriage return).

## Repository

| Property | Value |
|---|---|
| Project | mysteryinc_buggy |
| Source | demo |
| Path | `demo/projects/mysteryinc_buggy` |
| Detected root | (top level) |
| Files | 11 (9 Python) |

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

Readiness Score: **68.0%** — 66/97 mandatory checks passed, 31 failure(s).

### Score by category

| Category | Passed | Total | Score | Failed | Warnings |
|---|---|---|---|---|---|
| Structure | 7 | 11 | 63.6% | 4 | 0 |
| Compilation | 7 | 8 | 87.5% | 1 | 0 |
| Required functions | 13 | 17 | 76.5% | 4 | 0 |
| Known tests | 7 | 15 | 46.7% | 8 | 0 |
| Derived tests | 3 | 10 | 30.0% | 7 | 0 |
| Output matching | 4 | 10 | 40.0% | 6 | 0 |
| Constraints | 20 | 21 | 95.2% | 1 | 0 |
| Import safety | 5 | 5 | 100.0% | 0 | 1 |

### Mandatory exercises

| Exercise | File | Status | Checks passed | Score | Issues |
|---|---|---|---|---|---|
| Exercise 1 — Kelvin | `MysteryInc/FirstLaunch/flight_functions/kelvin.py` | **PASS (warnings)** | 12/12 | 100.0% | 1 |
| Exercise 2 — Safe speed | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | **FAIL** | 8/14 | 57.1% | 9 |
| Exercise 3 — Landing grade | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | **PARTIAL** | 15/16 | 93.8% | 1 |
| Exercise 4 — Fuel share | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | **PARTIAL** | 9/13 | 69.2% | 8 |
| Exercise 5 — Mission clock | `MysteryInc/FirstLaunch/route_math/mission_clock.py` | **FAIL** | 7/11 | 63.6% | 6 |
| Exercise 6 — FIXME | `MysteryInc/FirstLaunch/FIXME2.py` | **FAIL** | 1/8 | 12.5% | 10 |
| Exercise 7 — Access code | `MysteryInc/FirstLaunch/access_code.py` | **PARTIAL** | 7/8 | 87.5% | 1 |
| Exercise 8 — Launch sequence | `MysteryInc/FirstLaunch/launch_sequence.py` | **PARTIAL** | 7/12 | 58.3% | 5 |

### Blocking issues

- **FAIL** (critical) Forbidden builtin round() — round() is forbidden by the subject, but fuel_share.py calls it in fuel_share() (line 3). (`MysteryInc/FirstLaunch/route_math/fuel_share.py:3`)
- **FAIL** (critical) Wrong function name — Found def remaining_fuels() on line 6 — did you mean remaining_fuel()? The grader calls remaining_fuel() by its exact name, so it will not find your function. (`MysteryInc/FirstLaunch/route_math/fuel_share.py:6`)
- **FAIL** (critical) Misplaced file — Found at MysteryInc/FirstLaunch/mission_clock.py, expected at MysteryInc/FirstLaunch/route_math/mission_clock.py. The grader only looks at the exact path, so this file counts as missing until you move it. (`MysteryInc/FirstLaunch/mission_clock.py`)
- **FAIL** (critical) Syntax error — SyntaxError in FIXME2.py, line 3, column 18: expected ':'. Python cannot run this file, so none of its tests can run. (`MysteryInc/FirstLaunch/FIXME2.py:3`)
- **FAIL** (major) Prints instead of returning — mission_clock() prints its result (line 6) but never returns a value: the grader receives None. Use return instead of print(). (`MysteryInc/FirstLaunch/mission_clock.py:6`)
- **FAIL** (major) Returns a string instead of a boolean — is_safe() must return a bool (True / False), but line 4 has \`return "True"\` and line 6 has \`return "False"\`: quoted values are strings, not booleans. Remove the quotes. (`MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4`)
- **FAIL** (major) Missing .gitignore — The subject requires a .gitignore file at the repository root and none was found. (`.gitignore`)
- **FAIL** (major) Unwanted file — MysteryInc/.DS_Store should not be submitted: it matches the forbidden pattern .DS_Store. The subject forbids such files: remove it from git and list it in .gitignore. (`MysteryInc/.DS_Store`)
- **FAIL** (major) Unwanted folder — MysteryInc/FirstLaunch/flight_functions/\_\_pycache\_\_/ should not be submitted: it matches the forbidden pattern \_\_pycache\_\_/ (1 file inside). The subject forbids such files: remove it from git and list it in .gitignore. (`MysteryInc/FirstLaunch/flight_functions/__pycache__`)
- **FAIL** (major) python3 access_code.py: 1 line differs (line 1): different text — Output line 1 differs from the subject: different text: 'de' → 'gra' (col 27), typo: 'i' → 't' (col 30), extra text: ' Welcome aboard!' (col 34) (written by line 5 of MysteryInc/FirstLaunch/access_code.py). (`MysteryInc/FirstLaunch/access_code.py:5`)
- **FAIL** (major) fuel_share(500, 3) — Returned 167 instead of 166. (`MysteryInc/FirstLaunch/route_math/fuel_share.py:1`)
- **FAIL** (major) is_safe(250, 250) — Returned the string "True" (str) instead of the boolean True (bool). (`MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4`)
- **FAIL** (major) is_safe(251, 250) — Returned the string "False" (str) instead of the boolean False (bool). (`MysteryInc/FirstLaunch/flight_functions/safe_speed.py:6`)
- **FAIL** (major) is_safe(249, 250) — Returned the string "True" (str) instead of the boolean True (bool). (`MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4`)
- **FAIL** (major) is_safe(200, 250) — Returned the string "True" (str) instead of the boolean True (bool). (`MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4`)
- **FAIL** (major) is_safe(300, 250) — Returned the string "False" (str) instead of the boolean False (bool). (`MysteryInc/FirstLaunch/flight_functions/safe_speed.py:6`)
- **FAIL** (major) landing_grade(2) — Returned 'Hard landing' instead of 'Perfect touchdown'. (`MysteryInc/FirstLaunch/flight_functions/grade_landing.py:6`)
- **FAIL** (major) mission_clock(3725) — Returned None but printed '01:02:05': the function must return '01:02:05', not print it. (`MysteryInc/FirstLaunch/mission_clock.py:6`)
- **FAIL** (major) mission_clock(0) — Returned None but printed '00:00:00': the function must return '00:00:00', not print it. (`MysteryInc/FirstLaunch/mission_clock.py:6`)
- **FAIL** (minor) Prompt 1: 'Pilot name: ' — The input() prompt 1 differs from the subject: missing trailing space (line 1 of MysteryInc/FirstLaunch/launch_sequence.py). (`MysteryInc/FirstLaunch/launch_sequence.py:1`)
- **FAIL** (minor) Prompt 4: 'Set a trap or collect evidence? (trap/evidence) ' — The input() prompt 4 differs from the subject: typo: 'o' → 'a' (col 16) (line 27 of MysteryInc/FirstLaunch/launch_sequence.py). (`MysteryInc/FirstLaunch/launch_sequence.py:27`)
- **FAIL** (minor) python3 launch_sequence.py: 3 lines differ (lines 1, 3, 7): whitespace differs, typo — Output line 1 differs from the subject: missing space (col 12) (written by line 1 of MysteryInc/FirstLaunch/launch_sequence.py). (`MysteryInc/FirstLaunch/launch_sequence.py:1`)
- **FAIL** (minor) python3 launch_sequence.py: 2 lines differ (lines 1, 3): whitespace differs, typo — Output line 1 differs from the subject: missing space (col 12) (written by line 1 of MysteryInc/FirstLaunch/launch_sequence.py). (`MysteryInc/FirstLaunch/launch_sequence.py:1`)
- **FAIL** (minor) python3 launch_sequence.py: 3 lines differ (lines 1, 3, 7): whitespace differs, typo — Output line 1 differs from the subject: missing space (col 12) (written by line 1 of MysteryInc/FirstLaunch/launch_sequence.py). (`MysteryInc/FirstLaunch/launch_sequence.py:1`)
- **SKIPPED** Function not checked — average_speed() could not be checked because FIXME2.py does not compile (fix the syntax error first). (`MysteryInc/FirstLaunch/FIXME2.py`)
- **SKIPPED** average_speed(150.0, 0.0) — Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py. (`MysteryInc/FirstLaunch/FIXME2.py`)
- **SKIPPED** average_speed(150.0, 0.5) — Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py. (`MysteryInc/FirstLaunch/FIXME2.py`)
- **SKIPPED** average_speed(150.0, -0.5) — Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py. (`MysteryInc/FirstLaunch/FIXME2.py`)
- **SKIPPED** average_speed(150.0, 2.0) — Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py. (`MysteryInc/FirstLaunch/FIXME2.py`)
- **SKIPPED** average_speed(10.0, 0.0) — Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py. (`MysteryInc/FirstLaunch/FIXME2.py`)
- **SKIPPED** remaining_fuel(400, 3) — Not run: blocked by function:fuel_share:remaining_fuel. (`MysteryInc/FirstLaunch/route_math/fuel_share.py`)

## Optional requirements

*No optional requirement.*

## Structure

| Path | Kind | Status | Note |
|---|---|---|---|
| `.gitignore` | file | missing | missing |
| `MysteryInc/.DS_Store` | file | parasite | matches .DS_Store |
| `MysteryInc/FirstLaunch/bonus/countdown.py` | file | missing | missing |
| `MysteryInc/FirstLaunch/flight_functions/__pycache__` | directory | parasite | matches \_\_pycache\_\_/ |
| `MysteryInc/FirstLaunch/flight_functions/__pycache__/kelvin.cpython-312.pyc` | file | parasite | inside MysteryInc/FirstLaunch/flight_functions/\_\_pycache\_\_/ |
| `MysteryInc/FirstLaunch/mission_clock.py` | file | misplaced | expected at MysteryInc/FirstLaunch/route_math/mission_clock.py |
| `MysteryInc/FirstLaunch/route_math/mission_clock.py` | file | missing | missing here (found at MysteryInc/FirstLaunch/mission_clock.py) |

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Explicit requirement | MysteryInc/FirstLaunch/flight_functions/grade_landing.py is at the expected path. |
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/flight_functions/kelvin.py` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py` | Explicit requirement | MysteryInc/FirstLaunch/flight_functions/kelvin.py is at the expected path. |
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | Explicit requirement | MysteryInc/FirstLaunch/flight_functions/safe_speed.py is at the expected path. |
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/route_math/fuel_share.py` | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | Explicit requirement | MysteryInc/FirstLaunch/route_math/fuel_share.py is at the expected path. |
| **FAIL** (critical) | Misplaced file · `structure:file:MysteryInc/FirstLaunch/route_math/mission_clock.py` | `MysteryInc/FirstLaunch/mission_clock.py` | Explicit requirement | Found at MysteryInc/FirstLaunch/mission_clock.py, expected at MysteryInc/FirstLaunch/route_math/mission_clock.py. The grader only looks at the exact path, so this file counts as missing until you move it. |
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/FIXME2.py` | `MysteryInc/FirstLaunch/FIXME2.py` | Explicit requirement | MysteryInc/FirstLaunch/FIXME2.py is at the expected path. |
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/access_code.py` | `MysteryInc/FirstLaunch/access_code.py` | Explicit requirement | MysteryInc/FirstLaunch/access_code.py is at the expected path. |
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/launch_sequence.py` | `MysteryInc/FirstLaunch/launch_sequence.py` | Explicit requirement | MysteryInc/FirstLaunch/launch_sequence.py is at the expected path. |
| **FAIL** (major) | Missing .gitignore · `structure:gitignore` | `.gitignore` | Explicit requirement | The subject requires a .gitignore file at the repository root and none was found. |
| **FAIL** (major) | Unwanted file · `structure:parasite:MysteryInc/.DS_Store` | `MysteryInc/.DS_Store` | Explicit requirement | MysteryInc/.DS_Store should not be submitted: it matches the forbidden pattern .DS_Store. The subject forbids such files: remove it from git and list it in .gitignore. |
| **FAIL** (major) | Unwanted folder · `structure:parasite:MysteryInc/FirstLaunch/flight_functions/__pycache__/` | `MysteryInc/FirstLaunch/flight_functions/__pycache__` | Explicit requirement | MysteryInc/FirstLaunch/flight_functions/\_\_pycache\_\_/ should not be submitted: it matches the forbidden pattern \_\_pycache\_\_/ (1 file inside). The subject forbids such files: remove it from git and list it in .gitignore. |

#### FAIL — Misplaced file

`structure:file:MysteryInc/FirstLaunch/route_math/mission_clock.py` · severity: critical · Explicit requirement · `MysteryInc/FirstLaunch/mission_clock.py` · diagnosis: `misplaced_file`

Found at MysteryInc/FirstLaunch/mission_clock.py, expected at MysteryInc/FirstLaunch/route_math/mission_clock.py. The grader only looks at the exact path, so this file counts as missing until you move it.

**Suggested fix** (confidence: high): Move MysteryInc/FirstLaunch/mission_clock.py to MysteryInc/FirstLaunch/route_math/mission_clock.py with git mv, then commit.

- Before: *(empty)*
- After: `git mv MysteryInc/FirstLaunch/mission_clock.py MysteryInc/FirstLaunch/route_math/mission_clock.py`

#### FAIL — Missing .gitignore

`structure:gitignore` · severity: major · Explicit requirement · `.gitignore` · diagnosis: `missing_gitignore`

The subject requires a .gitignore file at the repository root and none was found.

**Suggested fix** (confidence: high): Create .gitignore at the repository root, then git add .gitignore and commit.

```diff
--- /dev/null
+++ b/.gitignore
@@ -0,0 +1,3 @@
+__pycache__/
+*.pyc
+.DS_Store
```

#### FAIL — Unwanted file

`structure:parasite:MysteryInc/.DS_Store` · severity: major · Explicit requirement · `MysteryInc/.DS_Store` · diagnosis: `parasite_file`

MysteryInc/.DS_Store should not be submitted: it matches the forbidden pattern .DS_Store. The subject forbids such files: remove it from git and list it in .gitignore.

**Suggested fix** (confidence: high): Stop tracking it without deleting your local copy: git rm -r --cached MysteryInc/.DS_Store, then add .DS_Store to .gitignore and commit.

#### FAIL — Unwanted folder

`structure:parasite:MysteryInc/FirstLaunch/flight_functions/__pycache__/` · severity: major · Explicit requirement · `MysteryInc/FirstLaunch/flight_functions/__pycache__` · diagnosis: `parasite_file`

MysteryInc/FirstLaunch/flight_functions/\_\_pycache\_\_/ should not be submitted: it matches the forbidden pattern \_\_pycache\_\_/ (1 file inside). The subject forbids such files: remove it from git and list it in .gitignore.

**Suggested fix** (confidence: high): Stop tracking it without deleting your local copy: git rm -r --cached MysteryInc/FirstLaunch/flight_functions/\_\_pycache\_\_/, then add \_\_pycache\_\_/ to .gitignore and commit.

## Functions

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | Function found · `function:kelvin:to_kelvin` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Explicit requirement | to_kelvin() is defined in kelvin.py (line 1). |
| **PASS** | Signature matches the subject · `signature:kelvin:to_kelvin` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Explicit requirement | to_kelvin() has the expected signature: def to_kelvin(celsius: float) -\> float. |
| **PASS** | Returns its result · `returns:kelvin:to_kelvin` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Explicit requirement | to_kelvin() returns its result with a return statement. |
| **PASS** | Function found · `function:safe_speed:is_safe` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:1` | Explicit requirement | is_safe() is defined in safe_speed.py (line 1). |
| **PASS** | Signature matches the subject · `signature:safe_speed:is_safe` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:1` | Explicit requirement | is_safe() has the expected signature: def is_safe(speed: int, limit: int) -\> bool. |
| **FAIL** (major) | Returns a string instead of a boolean · `returns:safe_speed:is_safe` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4` | Explicit requirement | is_safe() must return a bool (True / False), but line 4 has \`return "True"\` and line 6 has \`return "False"\`: quoted values are strings, not booleans. Remove the quotes. |
| **PASS** | Function found · `function:grade_landing:landing_grade` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Explicit requirement | landing_grade() is defined in grade_landing.py (line 1). |
| **PASS** | Signature matches the subject · `signature:grade_landing:landing_grade` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Explicit requirement | landing_grade() has the expected signature: def landing_grade(vertical_speed: int) -\> str. |
| **PASS** | Returns its result · `returns:grade_landing:landing_grade` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Explicit requirement | landing_grade() returns its result with a return statement. |
| **PASS** | Function found · `function:fuel_share:fuel_share` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Explicit requirement | fuel_share() is defined in fuel_share.py (line 1). |
| **PASS** | Signature matches the subject · `signature:fuel_share:fuel_share` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Explicit requirement | fuel_share() has the expected signature: def fuel_share(total_fuel: int, crew: int) -\> int. |
| **PASS** | Returns its result · `returns:fuel_share:fuel_share` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Explicit requirement | fuel_share() returns its result with a return statement. |
| **FAIL** (critical) | Wrong function name · `function:fuel_share:remaining_fuel` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:6` | Explicit requirement | Found def remaining_fuels() on line 6 — did you mean remaining_fuel()? The grader calls remaining_fuel() by its exact name, so it will not find your function. |
| **PASS** | Function found · `function:mission_clock:mission_clock` | `MysteryInc/FirstLaunch/mission_clock.py:1` | Explicit requirement | mission_clock() is defined in mission_clock.py (line 1). |
| **PASS** | Signature matches the subject · `signature:mission_clock:mission_clock` | `MysteryInc/FirstLaunch/mission_clock.py:1` | Explicit requirement | mission_clock() has the expected signature: def mission_clock(seconds: int) -\> str. |
| **FAIL** (major) | Prints instead of returning · `returns:mission_clock:mission_clock` | `MysteryInc/FirstLaunch/mission_clock.py:6` | Explicit requirement | mission_clock() prints its result (line 6) but never returns a value: the grader receives None. Use return instead of print(). |
| **SKIPPED** | Function not checked · `function:FIXME2:average_speed` | `MysteryInc/FirstLaunch/FIXME2.py` | Explicit requirement | average_speed() could not be checked because FIXME2.py does not compile (fix the syntax error first). |

#### FAIL — Wrong function name

`function:fuel_share:remaining_fuel` · severity: critical · Explicit requirement · `MysteryInc/FirstLaunch/route_math/fuel_share.py:6` · diagnosis: `wrong_function_name`

Found def remaining_fuels() on line 6 — did you mean remaining_fuel()? The grader calls remaining_fuel() by its exact name, so it will not find your function.

```text
# MysteryInc/FirstLaunch/route_math/fuel_share.py
  4 | 
  5 | 
> 6 | def remaining_fuels(total_fuel: int, crew: int) -> int:
  7 |     # What could not be shared stays in the tank
  8 |     return total_fuel % crew
```

**Suggested fix** (confidence: high): Rename the function remaining_fuels to remaining_fuel: the grader calls it by its exact name.

```diff
--- a/MysteryInc/FirstLaunch/route_math/fuel_share.py
+++ b/MysteryInc/FirstLaunch/route_math/fuel_share.py
@@ -5,3 +5,3 @@
 
-def remaining_fuels(total_fuel: int, crew: int) -> int:
+def remaining_fuel(total_fuel: int, crew: int) -> int:
     # What could not be shared stays in the tank
```

#### FAIL — Prints instead of returning

`returns:mission_clock:mission_clock` · severity: major · Explicit requirement · `MysteryInc/FirstLaunch/mission_clock.py:6` · diagnosis: `prints_instead_of_returns`

mission_clock() prints its result (line 6) but never returns a value: the grader receives None. Use return instead of print().

```text
# MysteryInc/FirstLaunch/mission_clock.py
  4 |     secs = seconds % 60
  5 |     # :02 pads each field with a leading zero
> 6 |     print(f"{hours:02}:{minutes:02}:{secs:02}")
```

**Suggested fix** (confidence: medium): Return the value instead of printing it in mission_clock.

```diff
--- a/MysteryInc/FirstLaunch/mission_clock.py
+++ b/MysteryInc/FirstLaunch/mission_clock.py
@@ -5,2 +5,2 @@
     # :02 pads each field with a leading zero
-    print(f"{hours:02}:{minutes:02}:{secs:02}")
+    return f"{hours:02}:{minutes:02}:{secs:02}"
```

#### FAIL — Returns a string instead of a boolean

`returns:safe_speed:is_safe` · severity: major · Explicit requirement · `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4` · diagnosis: `str_instead_of_bool`

is_safe() must return a bool (True / False), but line 4 has \`return "True"\` and line 6 has \`return "False"\`: quoted values are strings, not booleans. Remove the quotes.

```text
# MysteryInc/FirstLaunch/flight_functions/safe_speed.py
  2 |     # We are safe as long as we do not go over the limit
  3 |     if speed <= limit:
> 4 |         return "True"
  5 |     else:
> 6 |         return "False"
```

**Suggested fix** (confidence: high): Return the booleans True/False instead of the strings "True"/"False".

```diff
--- a/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
+++ b/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
@@ -3,4 +3,4 @@
     if speed <= limit:
-        return "True"
+        return True
     else:
-        return "False"
+        return False
```

#### SKIPPED — Function not checked

`function:FIXME2:average_speed` · Explicit requirement · `MysteryInc/FirstLaunch/FIXME2.py`

average_speed() could not be checked because FIXME2.py does not compile (fix the syntax error first).

Not run: blocked by `syntax:MysteryInc/FirstLaunch/FIXME2.py`.

## Scripts

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | python3 access_code.py: output matches · `test:access_code#session1` | `MysteryInc/FirstLaunch/access_code.py` | Explicit requirement | The output matches the subject exactly. |
| **FAIL** (major) | python3 access_code.py: 1 line differs (line 1): different text · `test:access_code#session2` | `MysteryInc/FirstLaunch/access_code.py:5` | Explicit requirement | Output line 1 differs from the subject: different text: 'de' → 'gra' (col 27), typo: 'i' → 't' (col 30), extra text: ' Welcome aboard!' (col 34) (written by line 5 of MysteryInc/FirstLaunch/access_code.py). |
| **PASS** | Prompt 1: 'Enter access code: ' · `prompt:access_code:1` | `MysteryInc/FirstLaunch/access_code.py:1` | Explicit requirement | The input() prompt 1 matches the subject exactly (line 1 of MysteryInc/FirstLaunch/access_code.py). |
| **FAIL** (minor) | python3 launch_sequence.py: 3 lines differ (lines 1, 3, 7): whitespace differs, typo · `test:launch_sequence#session1` | `MysteryInc/FirstLaunch/launch_sequence.py:1` | Explicit requirement | Output line 1 differs from the subject: missing space (col 12) (written by line 1 of MysteryInc/FirstLaunch/launch_sequence.py). |
| **FAIL** (minor) | python3 launch_sequence.py: 2 lines differ (lines 1, 3): whitespace differs, typo · `test:launch_sequence#session2` | `MysteryInc/FirstLaunch/launch_sequence.py:1` | Explicit requirement | Output line 1 differs from the subject: missing space (col 12) (written by line 1 of MysteryInc/FirstLaunch/launch_sequence.py). |
| **FAIL** (minor) | python3 launch_sequence.py: 3 lines differ (lines 1, 3, 7): whitespace differs, typo · `test:launch_sequence#session3` | `MysteryInc/FirstLaunch/launch_sequence.py:1` | Explicit requirement | Output line 1 differs from the subject: missing space (col 12) (written by line 1 of MysteryInc/FirstLaunch/launch_sequence.py). |
| **FAIL** (minor) | Prompt 1: 'Pilot name: ' · `prompt:launch_sequence:1` | `MysteryInc/FirstLaunch/launch_sequence.py:1` | Explicit requirement | The input() prompt 1 differs from the subject: missing trailing space (line 1 of MysteryInc/FirstLaunch/launch_sequence.py). |
| **PASS** | Prompt 2: 'Starting fuel: ' · `prompt:launch_sequence:2` | `MysteryInc/FirstLaunch/launch_sequence.py:2` | Explicit requirement | The input() prompt 2 matches the subject exactly (line 2 of MysteryInc/FirstLaunch/launch_sequence.py). |
| **PASS** | Prompt 3: 'Your choice: ' · `prompt:launch_sequence:3` | `MysteryInc/FirstLaunch/launch_sequence.py:8` | Explicit requirement | The input() prompt 3 matches the subject exactly (line 8 of MysteryInc/FirstLaunch/launch_sequence.py). |
| **FAIL** (minor) | Prompt 4: 'Set a trap or collect evidence? (trap/evidence) ' · `prompt:launch_sequence:4` | `MysteryInc/FirstLaunch/launch_sequence.py:27` | Explicit requirement | The input() prompt 4 differs from the subject: typo: 'o' → 'a' (col 16) (line 27 of MysteryInc/FirstLaunch/launch_sequence.py). |

#### FAIL — python3 access_code.py: 1 line differs (line 1): different text

`test:access_code#session2` · severity: major · Explicit requirement · `MysteryInc/FirstLaunch/access_code.py:5` · diagnosis: `stdout_mismatch`

Output line 1 differs from the subject: different text: 'de' → 'gra' (col 27), typo: 'i' → 't' (col 30), extra text: ' Welcome aboard!' (col 34) (written by line 5 of MysteryInc/FirstLaunch/access_code.py).

- Standard input: `scooby↵`
- Exit code: 0

**Output difference** — 1 line differs (line 1): different text

```diff
- Enter·access·code:·Access·denied.↵
+ Enter·access·code:·Access·granted.·Welcome·aboard!↵
```

- Actual line 1: different text: 'de' → 'gra' (col 27); typo: 'i' → 't' (col 30); extra text: ' Welcome aboard!' (col 34) (printed by `MysteryInc/FirstLaunch/access_code.py:5`)

```text
# MysteryInc/FirstLaunch/access_code.py
  2 | 
  3 | # Only the exact code opens the Mystery Machine
  4 | if code.upper() == "SCOOBY":
> 5 |     print("Access granted. Welcome aboard!")
  6 | else:
  7 |     print("Access denied.")
```

**Suggested fix** (confidence: high): Change the printed text on line 5 so it matches the subject exactly.

```diff
--- a/MysteryInc/FirstLaunch/access_code.py
+++ b/MysteryInc/FirstLaunch/access_code.py
@@ -4,3 +4,3 @@
 if code.upper() == "SCOOBY":
-    print("Access granted. Welcome aboard!")
+    print("Access denied.")
 else:
```

#### FAIL — Prompt 1: 'Pilot name: '

`prompt:launch_sequence:1` · severity: minor · Explicit requirement · `MysteryInc/FirstLaunch/launch_sequence.py:1` · diagnosis: `prompt_mismatch`

The input() prompt 1 differs from the subject: missing trailing space (line 1 of MysteryInc/FirstLaunch/launch_sequence.py).

- Standard input: `Camille↵400↵2↵trap↵`
- Expected: `'Pilot name: '` (str)
- Actual: `'Pilot name:'` (str)

**Value difference** — 1 line differs (line 1): trailing whitespace

```diff
- Pilot·name:·
+ Pilot·name:
```

- Actual line 1: missing trailing space

```text
# MysteryInc/FirstLaunch/launch_sequence.py
> 1 | pilot = input("Pilot name:")
  2 | fuel = int(input("Starting fuel: "))
  3 | 
  4 | print("Where's the Mystery Machine headed today?")
```

**Suggested fix** (confidence: high): Change the input() prompt on line 1 so it matches the subject exactly.

```diff
--- a/MysteryInc/FirstLaunch/launch_sequence.py
+++ b/MysteryInc/FirstLaunch/launch_sequence.py
@@ -1,2 +1,2 @@
-pilot = input("Pilot name:")
+pilot = input("Pilot name: ")
 fuel = int(input("Starting fuel: "))
```

#### FAIL — Prompt 4: 'Set a trap or collect evidence? (trap/evidence) '

`prompt:launch_sequence:4` · severity: minor · Explicit requirement · `MysteryInc/FirstLaunch/launch_sequence.py:27` · diagnosis: `prompt_mismatch`

The input() prompt 4 differs from the subject: typo: 'o' → 'a' (col 16) (line 27 of MysteryInc/FirstLaunch/launch_sequence.py).

- Standard input: `Camille↵400↵2↵trap↵`
- Expected: `'Set a trap or collect evidence? (trap/evidence) '` (str)
- Actual: `'Set a trap or callect evidence? (trap/evidence) '` (str)

**Value difference** — 1 line differs (line 1): typo

```diff
- Set·a·trap·or·collect·evidence?·(trap/evidence)·
+ Set·a·trap·or·callect·evidence?·(trap/evidence)·
```

- Actual line 1: typo: 'o' → 'a' (col 16)

```text
# MysteryInc/FirstLaunch/launch_sequence.py
  24 |     fuel = fuel - cost
  25 |     print("Destination: " + destination)
  26 |     print("Fuel after the trip: " + str(fuel))
> 27 |     action = input("Set a trap or callect evidence? (trap/evidence) ")
  28 |     if action == "trap":
  29 |         print(pilot + " sets a trap at " + destination + ". Zoinks!")
  30 |     else:
```

**Suggested fix** (confidence: high): Change the input() prompt on line 27 so it matches the subject exactly.

```diff
--- a/MysteryInc/FirstLaunch/launch_sequence.py
+++ b/MysteryInc/FirstLaunch/launch_sequence.py
@@ -26,3 +26,3 @@
     print("Fuel after the trip: " + str(fuel))
-    action = input("Set a trap or callect evidence? (trap/evidence) ")
+    action = input("Set a trap or collect evidence? (trap/evidence) ")
     if action == "trap":
```

#### FAIL — python3 launch_sequence.py: 3 lines differ (lines 1, 3, 7): whitespace differs, typo

`test:launch_sequence#session1` · severity: minor · Explicit requirement · `MysteryInc/FirstLaunch/launch_sequence.py:1` · diagnosis: `stdout_mismatch`

Output line 1 differs from the subject: missing space (col 12) (written by line 1 of MysteryInc/FirstLaunch/launch_sequence.py).

- Standard input: `Camille↵400↵2↵trap↵`
- Exit code: 0

**Output difference** — 3 lines differ (lines 1, 3, 7): whitespace differs, typo

```diff
- Pilot·name:·Starting·fuel:·Where's·the·Mystery·Machine·headed·today?↵
+ Pilot·name:Starting·fuel:·Where's·the·Mystery·Machine·headed·today?↵
  1·-·Crystal·Cove↵
- 2·-·The·Old·Mill↵
+ 2·-·The·Older·Mill↵
  3·-·Spooky·Swamp↵
  Your·choice:·Destination:·The·Old·Mill↵
  Fuel·after·the·trip:·280↵
- Set·a·trap·or·collect·evidence?·(trap/evidence)·Camille·sets·a·trap·at·The·Old·Mill.·Zoinks!↵
+ Set·a·trap·or·callect·evidence?·(trap/evidence)·Camille·sets·a·trap·at·The·Old·Mill.·Zoinks!↵
```

- Actual line 1: missing space (col 12) (printed by `MysteryInc/FirstLaunch/launch_sequence.py:1`)
- Actual line 3: extra text: 'er' (col 12) (printed by `MysteryInc/FirstLaunch/launch_sequence.py:6`)
- Actual line 7: typo: 'o' → 'a' (col 16) (printed by `MysteryInc/FirstLaunch/launch_sequence.py:27`)

```text
# MysteryInc/FirstLaunch/launch_sequence.py
> 1 | pilot = input("Pilot name:")
  2 | fuel = int(input("Starting fuel: "))
  3 | 
  4 | print("Where's the Mystery Machine headed today?")
```

#### FAIL — python3 launch_sequence.py: 2 lines differ (lines 1, 3): whitespace differs, typo

`test:launch_sequence#session2` · severity: minor · Explicit requirement · `MysteryInc/FirstLaunch/launch_sequence.py:1` · diagnosis: `stdout_mismatch`

Output line 1 differs from the subject: missing space (col 12) (written by line 1 of MysteryInc/FirstLaunch/launch_sequence.py).

- Standard input: `Fred↵100↵3↵`
- Exit code: 0

**Output difference** — 2 lines differ (lines 1, 3): whitespace differs, typo

```diff
- Pilot·name:·Starting·fuel:·Where's·the·Mystery·Machine·headed·today?↵
+ Pilot·name:Starting·fuel:·Where's·the·Mystery·Machine·headed·today?↵
  1·-·Crystal·Cove↵
- 2·-·The·Old·Mill↵
+ 2·-·The·Older·Mill↵
  3·-·Spooky·Swamp↵
  Your·choice:·Not·enough·fuel!·The·gang·stays·home.↵
```

- Actual line 1: missing space (col 12) (printed by `MysteryInc/FirstLaunch/launch_sequence.py:1`)
- Actual line 3: extra text: 'er' (col 12) (printed by `MysteryInc/FirstLaunch/launch_sequence.py:6`)

```text
# MysteryInc/FirstLaunch/launch_sequence.py
> 1 | pilot = input("Pilot name:")
  2 | fuel = int(input("Starting fuel: "))
  3 | 
  4 | print("Where's the Mystery Machine headed today?")
```

#### FAIL — python3 launch_sequence.py: 3 lines differ (lines 1, 3, 7): whitespace differs, typo

`test:launch_sequence#session3` · severity: minor · Explicit requirement · `MysteryInc/FirstLaunch/launch_sequence.py:1` · diagnosis: `stdout_mismatch`

Output line 1 differs from the subject: missing space (col 12) (written by line 1 of MysteryInc/FirstLaunch/launch_sequence.py).

- Standard input: `Velma↵250↵1↵evidence↵`
- Exit code: 0

**Output difference** — 3 lines differ (lines 1, 3, 7): whitespace differs, typo

```diff
- Pilot·name:·Starting·fuel:·Where's·the·Mystery·Machine·headed·today?↵
+ Pilot·name:Starting·fuel:·Where's·the·Mystery·Machine·headed·today?↵
  1·-·Crystal·Cove↵
- 2·-·The·Old·Mill↵
+ 2·-·The·Older·Mill↵
  3·-·Spooky·Swamp↵
  Your·choice:·Destination:·Crystal·Cove↵
  Fuel·after·the·trip:·200↵
- Set·a·trap·or·collect·evidence?·(trap/evidence)·Velma·collects·evidence·at·Crystal·Cove.·Jinkies!↵
+ Set·a·trap·or·callect·evidence?·(trap/evidence)·Velma·collects·evidence·at·Crystal·Cove.·Jinkies!↵
```

- Actual line 1: missing space (col 12) (printed by `MysteryInc/FirstLaunch/launch_sequence.py:1`)
- Actual line 3: extra text: 'er' (col 12) (printed by `MysteryInc/FirstLaunch/launch_sequence.py:6`)
- Actual line 7: typo: 'o' → 'a' (col 16) (printed by `MysteryInc/FirstLaunch/launch_sequence.py:27`)

```text
# MysteryInc/FirstLaunch/launch_sequence.py
> 1 | pilot = input("Pilot name:")
  2 | fuel = int(input("Starting fuel: "))
  3 | 
  4 | print("Where's the Mystery Machine headed today?")
```

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
| **FAIL** (critical) | Forbidden builtin round() · `constraint:fuel_share:forbidden_builtin:round` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:3` | Explicit requirement | round() is forbidden by the subject, but fuel_share.py calls it in fuel_share() (line 3). |
| **PASS** | Only authorized builtins · `constraint:fuel_share:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | Explicit requirement | fuel_share.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:fuel_share:import:*` | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | Explicit requirement | fuel_share.py imports nothing, as required. |
| **PASS** | No forbidden builtin · `constraint:mission_clock:forbidden_builtin:*` | `MysteryInc/FirstLaunch/mission_clock.py` | Explicit requirement | mission_clock.py calls none of the forbidden builtins (abs, max, min, round, sorted, sum, eval). |
| **PASS** | Only authorized builtins · `constraint:mission_clock:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/mission_clock.py` | Explicit requirement | mission_clock.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:mission_clock:import:*` | `MysteryInc/FirstLaunch/mission_clock.py` | Explicit requirement | mission_clock.py imports nothing, as required. |
| **PASS** | No forbidden builtin · `constraint:access_code:forbidden_builtin:*` | `MysteryInc/FirstLaunch/access_code.py` | Explicit requirement | access_code.py calls none of the forbidden builtins (abs, max, min, round, sorted, sum, eval). |
| **PASS** | Only authorized builtins · `constraint:access_code:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/access_code.py` | Explicit requirement | access_code.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:access_code:import:*` | `MysteryInc/FirstLaunch/access_code.py` | Explicit requirement | access_code.py imports nothing, as required. |
| **PASS** | No forbidden builtin · `constraint:launch_sequence:forbidden_builtin:*` | `MysteryInc/FirstLaunch/launch_sequence.py` | Explicit requirement | launch_sequence.py calls none of the forbidden builtins (abs, max, min, round, sorted, sum, eval). |
| **PASS** | Only authorized builtins · `constraint:launch_sequence:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/launch_sequence.py` | Explicit requirement | launch_sequence.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:launch_sequence:import:*` | `MysteryInc/FirstLaunch/launch_sequence.py` | Explicit requirement | launch_sequence.py imports nothing, as required. |

#### FAIL — Forbidden builtin round()

`constraint:fuel_share:forbidden_builtin:round` · severity: critical · Explicit requirement · `MysteryInc/FirstLaunch/route_math/fuel_share.py:3` · diagnosis: `forbidden_builtin`

round() is forbidden by the subject, but fuel_share.py calls it in fuel_share() (line 3).

```text
# MysteryInc/FirstLaunch/route_math/fuel_share.py
  1 | def fuel_share(total_fuel: int, crew: int) -> int:
  2 |     # Integer division: every crew member gets the same amount
> 3 |     return round(total_fuel / crew)
  4 | 
  5 | 
```

**Suggested fix** (confidence: low): Replace round() with your own logic: use integer arithmetic (int(), //, %).

## Static analysis

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Explicit requirement | grade_landing.py compiles without syntax errors. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/flight_functions/kelvin.py` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py` | Explicit requirement | kelvin.py compiles without syntax errors. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | Explicit requirement | safe_speed.py compiles without syntax errors. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/route_math/fuel_share.py` | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | Explicit requirement | fuel_share.py compiles without syntax errors. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/route_math/mission_clock.py` | `MysteryInc/FirstLaunch/mission_clock.py` | Explicit requirement | mission_clock.py compiles without syntax errors. |
| **FAIL** (critical) | Syntax error · `syntax:MysteryInc/FirstLaunch/FIXME2.py` | `MysteryInc/FirstLaunch/FIXME2.py:3` | Explicit requirement | SyntaxError in FIXME2.py, line 3, column 18: expected ':'. Python cannot run this file, so none of its tests can run. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/access_code.py` | `MysteryInc/FirstLaunch/access_code.py` | Explicit requirement | access_code.py compiles without syntax errors. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/launch_sequence.py` | `MysteryInc/FirstLaunch/launch_sequence.py` | Explicit requirement | launch_sequence.py compiles without syntax errors. |

#### FAIL — Syntax error

`syntax:MysteryInc/FirstLaunch/FIXME2.py` · severity: critical · Explicit requirement · `MysteryInc/FirstLaunch/FIXME2.py:3` · diagnosis: `syntax_error`

SyntaxError in FIXME2.py, line 3, column 18: expected ':'. Python cannot run this file, so none of its tests can run.

```text
# MysteryInc/FirstLaunch/FIXME2.py
  1 | def average_speed(distance: float, hours: float) -> float:
  2 |     # Shaggy forgot that we cannot divide by zero hours
> 3 |     if hours == 0
  4 |         return 0.0
  5 |     return distance / hours
```

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
| **WARNING** (major) | Prints when imported · `import_effects:kelvin` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:6` | Explicit requirement | Importing the module prints '298.15\\n' (line 6): functions files must not execute code at import. Remove the debug print or move it under \`if \_\_name\_\_ == "\_\_main\_\_":\`. |
| **PASS** | No side effects at import · `import_effects:safe_speed` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py` | Explicit requirement | Importing the module prints nothing, asks for no input and does not crash. |
| **PASS** | No side effects at import · `import_effects:grade_landing` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Explicit requirement | Importing the module prints nothing, asks for no input and does not crash. |
| **PASS** | No side effects at import · `import_effects:fuel_share` | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | Explicit requirement | Importing the module prints nothing, asks for no input and does not crash. |
| **PASS** | No side effects at import · `import_effects:mission_clock` | `MysteryInc/FirstLaunch/route_math/mission_clock.py` | Explicit requirement | Importing the module prints nothing, asks for no input and does not crash. |

#### WARNING — Prints when imported

`import_effects:kelvin` · severity: major · Explicit requirement · `MysteryInc/FirstLaunch/flight_functions/kelvin.py:6` · diagnosis: `import_side_effects`

Importing the module prints '298.15\\n' (line 6): functions files must not execute code at import. Remove the debug print or move it under \`if \_\_name\_\_ == "\_\_main\_\_":\`.

- Exit code: 0

```text
# MysteryInc/FirstLaunch/flight_functions/kelvin.py
  3 |     return celsius + 273.15
  4 | 
  5 | 
> 6 | print(to_kelvin(25))
```

## Known tests

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | to_kelvin(0) · `test:to_kelvin#ex1` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Explicit requirement | Returned 273.15 as expected. |
| **PASS** | to_kelvin(100) · `test:to_kelvin#ex2` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Explicit requirement | Returned 373.15 as expected. |
| **PASS** | to_kelvin(-273.15) · `test:to_kelvin#ex3` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Explicit requirement | Returned 0.0 as expected. |
| **FAIL** (major) | is_safe(200, 250) · `test:is_safe#ex1` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4` | Explicit requirement | Returned the string "True" (str) instead of the boolean True (bool). |
| **FAIL** (major) | is_safe(300, 250) · `test:is_safe#ex2` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:6` | Explicit requirement | Returned the string "False" (str) instead of the boolean False (bool). |
| **PASS** | landing_grade(1) · `test:landing_grade#ex1` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Explicit requirement | Returned 'Perfect touchdown' as expected. |
| **PASS** | landing_grade(4) · `test:landing_grade#ex2` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Explicit requirement | Returned 'Hard landing' as expected. |
| **PASS** | landing_grade(9) · `test:landing_grade#ex3` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Explicit requirement | Returned 'Crash!' as expected. |
| **PASS** | fuel_share(400, 3) · `test:fuel_share#ex1` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Explicit requirement | Returned 133 as expected. |
| **FAIL** (major) | fuel_share(500, 3) · `test:fuel_share#ex2` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Explicit requirement | Returned 167 instead of 166. |
| **SKIPPED** | remaining_fuel(400, 3) · `test:remaining_fuel#ex1` | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | Explicit requirement | Not run: blocked by function:fuel_share:remaining_fuel. |
| **FAIL** (major) | mission_clock(3725) · `test:mission_clock#ex1` | `MysteryInc/FirstLaunch/mission_clock.py:6` | Explicit requirement | Returned None but printed '01:02:05': the function must return '01:02:05', not print it. |
| **FAIL** (major) | mission_clock(0) · `test:mission_clock#ex2` | `MysteryInc/FirstLaunch/mission_clock.py:6` | Explicit requirement | Returned None but printed '00:00:00': the function must return '00:00:00', not print it. |
| **SKIPPED** | average_speed(150.0, 2.0) · `test:average_speed#ex1` | `MysteryInc/FirstLaunch/FIXME2.py` | Explicit requirement | Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py. |
| **SKIPPED** | average_speed(10.0, 0.0) · `test:average_speed#ex2` | `MysteryInc/FirstLaunch/FIXME2.py` | Explicit requirement | Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py. |

#### FAIL — fuel_share(500, 3)

`test:fuel_share#ex2` · severity: major · Explicit requirement · `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` · diagnosis: `wrong_value`

Returned 167 instead of 166.

- Call: `fuel_share(500, 3)`
- Expected: `166` (int)
- Actual: `167` (int)
- Rule from the subject: `returns total_fuel // crew`

```text
# MysteryInc/FirstLaunch/route_math/fuel_share.py
  1 | def fuel_share(total_fuel: int, crew: int) -> int:
  2 |     # Integer division: every crew member gets the same amount
  3 |     return round(total_fuel / crew)
```

#### FAIL — is_safe(200, 250)

`test:is_safe#ex1` · severity: major · Explicit requirement · `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4` · diagnosis: `str_instead_of_bool`

Returned the string "True" (str) instead of the boolean True (bool).

- Call: `is_safe(200, 250)`
- Expected: `True` (bool)
- Actual: `'True'` (str)
- Rule from the subject: `speed <= limit → True`

```text
# MysteryInc/FirstLaunch/flight_functions/safe_speed.py
  1 | def is_safe(speed: int, limit: int) -> bool:
  2 |     # We are safe as long as we do not go over the limit
  3 |     if speed <= limit:
> 4 |         return "True"
  5 |     else:
  6 |         return "False"
```

**Suggested fix** (confidence: high): Return the booleans True/False instead of the strings "True"/"False".

```diff
--- a/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
+++ b/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
@@ -3,4 +3,4 @@
     if speed <= limit:
-        return "True"
+        return True
     else:
-        return "False"
+        return False
```

#### FAIL — is_safe(300, 250)

`test:is_safe#ex2` · severity: major · Explicit requirement · `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:6` · diagnosis: `str_instead_of_bool`

Returned the string "False" (str) instead of the boolean False (bool).

- Call: `is_safe(300, 250)`
- Expected: `False` (bool)
- Actual: `'False'` (str)
- Rule from the subject: `otherwise → False`

```text
# MysteryInc/FirstLaunch/flight_functions/safe_speed.py
  1 | def is_safe(speed: int, limit: int) -> bool:
  2 |     # We are safe as long as we do not go over the limit
  3 |     if speed <= limit:
  4 |         return "True"
  5 |     else:
> 6 |         return "False"
```

**Suggested fix** (confidence: high): Return the booleans True/False instead of the strings "True"/"False".

```diff
--- a/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
+++ b/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
@@ -3,4 +3,4 @@
     if speed <= limit:
-        return "True"
+        return True
     else:
-        return "False"
+        return False
```

#### FAIL — mission_clock(3725)

`test:mission_clock#ex1` · severity: major · Explicit requirement · `MysteryInc/FirstLaunch/mission_clock.py:6` · diagnosis: `prints_instead_of_returns`

Returned None but printed '01:02:05': the function must return '01:02:05', not print it.

- Call: `mission_clock(3725)`
- Expected: `'01:02:05'` (str)
- Actual: `None` (NoneType)
- Rule from the subject: `returns f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"`

```text
# MysteryInc/FirstLaunch/mission_clock.py
  1 | def mission_clock(seconds: int) -> str:
  2 |     hours = seconds // 3600
  3 |     minutes = seconds % 3600 // 60
  4 |     secs = seconds % 60
  5 |     # :02 pads each field with a leading zero
> 6 |     print(f"{hours:02}:{minutes:02}:{secs:02}")
```

**Suggested fix** (confidence: medium): Return the value instead of printing it in mission_clock.

```diff
--- a/MysteryInc/FirstLaunch/mission_clock.py
+++ b/MysteryInc/FirstLaunch/mission_clock.py
@@ -5,2 +5,2 @@
     # :02 pads each field with a leading zero
-    print(f"{hours:02}:{minutes:02}:{secs:02}")
+    return f"{hours:02}:{minutes:02}:{secs:02}"
```

#### FAIL — mission_clock(0)

`test:mission_clock#ex2` · severity: major · Explicit requirement · `MysteryInc/FirstLaunch/mission_clock.py:6` · diagnosis: `prints_instead_of_returns`

Returned None but printed '00:00:00': the function must return '00:00:00', not print it.

- Call: `mission_clock(0)`
- Expected: `'00:00:00'` (str)
- Actual: `None` (NoneType)
- Rule from the subject: `returns f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"`

```text
# MysteryInc/FirstLaunch/mission_clock.py
  1 | def mission_clock(seconds: int) -> str:
  2 |     hours = seconds // 3600
  3 |     minutes = seconds % 3600 // 60
  4 |     secs = seconds % 60
  5 |     # :02 pads each field with a leading zero
> 6 |     print(f"{hours:02}:{minutes:02}:{secs:02}")
```

**Suggested fix** (confidence: medium): Return the value instead of printing it in mission_clock.

```diff
--- a/MysteryInc/FirstLaunch/mission_clock.py
+++ b/MysteryInc/FirstLaunch/mission_clock.py
@@ -5,2 +5,2 @@
     # :02 pads each field with a leading zero
-    print(f"{hours:02}:{minutes:02}:{secs:02}")
+    return f"{hours:02}:{minutes:02}:{secs:02}"
```

#### SKIPPED — average_speed(150.0, 2.0)

`test:average_speed#ex1` · Explicit requirement · `MysteryInc/FirstLaunch/FIXME2.py`

Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py.

Not run: blocked by `syntax:MysteryInc/FirstLaunch/FIXME2.py`.

- Call: `average_speed(150.0, 2.0)`
- Rule from the subject: `otherwise → distance / hours`

#### SKIPPED — average_speed(10.0, 0.0)

`test:average_speed#ex2` · Explicit requirement · `MysteryInc/FirstLaunch/FIXME2.py`

Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py.

Not run: blocked by `syntax:MysteryInc/FirstLaunch/FIXME2.py`.

- Call: `average_speed(10.0, 0.0)`
- Rule from the subject: `hours == 0 → 0.0`

#### SKIPPED — remaining_fuel(400, 3)

`test:remaining_fuel#ex1` · Explicit requirement · `MysteryInc/FirstLaunch/route_math/fuel_share.py`

Not run: blocked by function:fuel_share:remaining_fuel.

Not run: blocked by `function:fuel_share:remaining_fuel`.

- Call: `remaining_fuel(400, 3)`
- Rule from the subject: `returns total_fuel % crew`

## Derived tests

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **FAIL** (major) | is_safe(250, 250) · `test:is_safe#derived1` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4` | Derived test | Returned the string "True" (str) instead of the boolean True (bool). |
| **FAIL** (major) | is_safe(251, 250) · `test:is_safe#derived2` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:6` | Derived test | Returned the string "False" (str) instead of the boolean False (bool). |
| **FAIL** (major) | is_safe(249, 250) · `test:is_safe#derived3` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4` | Derived test | Returned the string "True" (str) instead of the boolean True (bool). |
| **FAIL** (major) | landing_grade(2) · `test:landing_grade#derived1` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:6` | Derived test | Returned 'Hard landing' instead of 'Perfect touchdown'. |
| **PASS** | landing_grade(3) · `test:landing_grade#derived2` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Derived test | Returned 'Hard landing' as expected. |
| **PASS** | landing_grade(5) · `test:landing_grade#derived3` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Derived test | Returned 'Hard landing' as expected. |
| **PASS** | landing_grade(6) · `test:landing_grade#derived4` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Derived test | Returned 'Crash!' as expected. |
| **SKIPPED** | average_speed(150.0, 0.0) · `test:average_speed#derived1` | `MysteryInc/FirstLaunch/FIXME2.py` | Derived test | Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py. |
| **SKIPPED** | average_speed(150.0, 0.5) · `test:average_speed#derived2` | `MysteryInc/FirstLaunch/FIXME2.py` | Derived test | Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py. |
| **SKIPPED** | average_speed(150.0, -0.5) · `test:average_speed#derived3` | `MysteryInc/FirstLaunch/FIXME2.py` | Derived test | Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py. |

#### FAIL — is_safe(250, 250)

`test:is_safe#derived1` · severity: major · Derived test · `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4` · diagnosis: `str_instead_of_bool`

Returned the string "True" (str) instead of the boolean True (bool).

- Call: `is_safe(250, 250)`
- Expected: `True` (bool)
- Actual: `'True'` (str)
- Rule from the subject: `speed <= limit → True`

```text
# MysteryInc/FirstLaunch/flight_functions/safe_speed.py
  1 | def is_safe(speed: int, limit: int) -> bool:
  2 |     # We are safe as long as we do not go over the limit
  3 |     if speed <= limit:
> 4 |         return "True"
  5 |     else:
  6 |         return "False"
```

**Suggested fix** (confidence: high): Return the booleans True/False instead of the strings "True"/"False".

```diff
--- a/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
+++ b/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
@@ -3,4 +3,4 @@
     if speed <= limit:
-        return "True"
+        return True
     else:
-        return "False"
+        return False
```

#### FAIL — is_safe(251, 250)

`test:is_safe#derived2` · severity: major · Derived test · `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:6` · diagnosis: `str_instead_of_bool`

Returned the string "False" (str) instead of the boolean False (bool).

- Call: `is_safe(251, 250)`
- Expected: `False` (bool)
- Actual: `'False'` (str)
- Rule from the subject: `otherwise → False`

```text
# MysteryInc/FirstLaunch/flight_functions/safe_speed.py
  1 | def is_safe(speed: int, limit: int) -> bool:
  2 |     # We are safe as long as we do not go over the limit
  3 |     if speed <= limit:
  4 |         return "True"
  5 |     else:
> 6 |         return "False"
```

**Suggested fix** (confidence: high): Return the booleans True/False instead of the strings "True"/"False".

```diff
--- a/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
+++ b/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
@@ -3,4 +3,4 @@
     if speed <= limit:
-        return "True"
+        return True
     else:
-        return "False"
+        return False
```

#### FAIL — is_safe(249, 250)

`test:is_safe#derived3` · severity: major · Derived test · `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4` · diagnosis: `str_instead_of_bool`

Returned the string "True" (str) instead of the boolean True (bool).

- Call: `is_safe(249, 250)`
- Expected: `True` (bool)
- Actual: `'True'` (str)
- Rule from the subject: `speed <= limit → True`

```text
# MysteryInc/FirstLaunch/flight_functions/safe_speed.py
  1 | def is_safe(speed: int, limit: int) -> bool:
  2 |     # We are safe as long as we do not go over the limit
  3 |     if speed <= limit:
> 4 |         return "True"
  5 |     else:
  6 |         return "False"
```

**Suggested fix** (confidence: high): Return the booleans True/False instead of the strings "True"/"False".

```diff
--- a/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
+++ b/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
@@ -3,4 +3,4 @@
     if speed <= limit:
-        return "True"
+        return True
     else:
-        return "False"
+        return False
```

#### FAIL — landing_grade(2)

`test:landing_grade#derived1` · severity: major · Derived test · `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:6` · diagnosis: `wrong_string`

Returned 'Hard landing' instead of 'Perfect touchdown'.

- Call: `landing_grade(2)`
- Expected: `'Perfect touchdown'` (str)
- Actual: `'Hard landing'` (str)
- Rule from the subject: `vertical_speed <= 2 → "Perfect touchdown"`

**Value difference** — 1 line missing (from line 1); 1 extra line at the end

```diff
- Perfect·touchdown
+ Hard·landing
```

```text
# MysteryInc/FirstLaunch/flight_functions/grade_landing.py
  1 | def landing_grade(vertical_speed: int) -> str:
  2 |     # The slower we touch the ground, the better the landing
  3 |     if vertical_speed < 2:
  4 |         return "Perfect touchdown"
  5 |     elif vertical_speed <= 5:
> 6 |         return "Hard landing"
  7 |     else:
  8 |         return "Crash!"
```

**Suggested fix** (confidence: high): Change the returned string on line 6 so it matches the subject exactly.

```diff
--- a/MysteryInc/FirstLaunch/flight_functions/grade_landing.py
+++ b/MysteryInc/FirstLaunch/flight_functions/grade_landing.py
@@ -5,3 +5,3 @@
     elif vertical_speed <= 5:
-        return "Hard landing"
+        return "Perfect touchdown"
     else:
```

#### SKIPPED — average_speed(150.0, 0.0)

`test:average_speed#derived1` · Derived test · `MysteryInc/FirstLaunch/FIXME2.py`

Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py.

Not run: blocked by `syntax:MysteryInc/FirstLaunch/FIXME2.py`.

- Call: `average_speed(150.0, 0.0)`
- Rule from the subject: `hours == 0 → 0.0`

#### SKIPPED — average_speed(150.0, 0.5)

`test:average_speed#derived2` · Derived test · `MysteryInc/FirstLaunch/FIXME2.py`

Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py.

Not run: blocked by `syntax:MysteryInc/FirstLaunch/FIXME2.py`.

- Call: `average_speed(150.0, 0.5)`
- Rule from the subject: `otherwise → distance / hours`

#### SKIPPED — average_speed(150.0, -0.5)

`test:average_speed#derived3` · Derived test · `MysteryInc/FirstLaunch/FIXME2.py`

Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py.

Not run: blocked by `syntax:MysteryInc/FirstLaunch/FIXME2.py`.

- Call: `average_speed(150.0, -0.5)`
- Rule from the subject: `otherwise → distance / hours`

## Warnings

- Developer mode: the student code runs directly on this computer, under your user account, not inside a container.
- Network access, process creation and writes outside the temporary copy are blocked by Python audit hooks inside the harness. This is a best-effort guard, not a security boundary: the code can still read your files. Use Docker safe mode for code you do not trust.
- A Windows Job Object limits each run to 32 processes and 512 MB of memory and kills every remaining process at the end.

Warnings do not block the submission but deserve a look (details in their sections):

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **WARNING** (major) | Prints when imported · `import_effects:kelvin` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:6` | Explicit requirement | Importing the module prints '298.15\\n' (line 6): functions files must not execute code at import. Remove the debug print or move it under \`if \_\_name\_\_ == "\_\_main\_\_":\`. |

### Heuristic tests (not official)

Extra cases proposed by PréMoulinette. They are not requirements of the subject and never change the Readiness Score.

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **PASS** | to_kelvin(-1.0) · `test:to_kelvin#heur1` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Heuristic (not official) | Returned 272.15 as expected. |
| **PASS** | to_kelvin(1000000.0) · `test:to_kelvin#heur2` | `MysteryInc/FirstLaunch/flight_functions/kelvin.py:1` | Heuristic (not official) | Returned 1000273.15 as expected. |
| **WARNING** (minor) | is_safe(0, 250) · `test:is_safe#heur1` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4` | Heuristic (not official) | Returned the string "True" (str) instead of the boolean True (bool). |
| **WARNING** (minor) | is_safe(-1, 250) · `test:is_safe#heur2` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4` | Heuristic (not official) | Returned the string "True" (str) instead of the boolean True (bool). |
| **WARNING** (minor) | is_safe(1000000, 250) · `test:is_safe#heur3` | `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:6` | Heuristic (not official) | Returned the string "False" (str) instead of the boolean False (bool). |
| **PASS** | landing_grade(0) · `test:landing_grade#heur1` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Heuristic (not official) | Returned 'Perfect touchdown' as expected. |
| **PASS** | landing_grade(-1) · `test:landing_grade#heur2` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Heuristic (not official) | Returned 'Perfect touchdown' as expected. |
| **PASS** | landing_grade(1000000) · `test:landing_grade#heur3` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py:1` | Heuristic (not official) | Returned 'Crash!' as expected. |
| **PASS** | fuel_share(0, 3) · `test:fuel_share#heur1` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Heuristic (not official) | Returned 0 as expected. |
| **WARNING** (minor) | fuel_share(-1, 3) · `test:fuel_share#heur2` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Heuristic (not official) | Returned 0 instead of -1. |
| **PASS** | fuel_share(1000000, 3) · `test:fuel_share#heur3` | `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` | Heuristic (not official) | Returned 333333 as expected. |
| **SKIPPED** | remaining_fuel(0, 3) · `test:remaining_fuel#heur1` | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | Heuristic (not official) | Not run: blocked by function:fuel_share:remaining_fuel. |
| **SKIPPED** | remaining_fuel(-1, 3) · `test:remaining_fuel#heur2` | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | Heuristic (not official) | Not run: blocked by function:fuel_share:remaining_fuel. |
| **SKIPPED** | remaining_fuel(1000000, 3) · `test:remaining_fuel#heur3` | `MysteryInc/FirstLaunch/route_math/fuel_share.py` | Heuristic (not official) | Not run: blocked by function:fuel_share:remaining_fuel. |
| **WARNING** (minor) | mission_clock(-1) · `test:mission_clock#heur1` | `MysteryInc/FirstLaunch/mission_clock.py:6` | Heuristic (not official) | Returned None but printed '-1:59:59': the function must return '-1:59:59', not print it. |
| **WARNING** (minor) | mission_clock(1000000) · `test:mission_clock#heur2` | `MysteryInc/FirstLaunch/mission_clock.py:6` | Heuristic (not official) | Returned None but printed '277:46:40': the function must return '277:46:40', not print it. |
| **SKIPPED** | average_speed(0.0, 2.0) · `test:average_speed#heur1` | `MysteryInc/FirstLaunch/FIXME2.py` | Heuristic (not official) | Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py. |
| **SKIPPED** | average_speed(-1.0, 2.0) · `test:average_speed#heur2` | `MysteryInc/FirstLaunch/FIXME2.py` | Heuristic (not official) | Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py. |
| **SKIPPED** | average_speed(1000000.0, 2.0) · `test:average_speed#heur3` | `MysteryInc/FirstLaunch/FIXME2.py` | Heuristic (not official) | Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py. |
| **SKIPPED** | emoji_grade(-1) · `test:emoji_grade#heur1` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Heuristic (not official) | Not run: blocked by function:emoji_grade:emoji_grade. |
| **SKIPPED** | emoji_grade(1000000) · `test:emoji_grade#heur2` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Heuristic (not official) | Not run: blocked by function:emoji_grade:emoji_grade. |
| **PASS** | max_altitude(0, 450, 300) · `test:max_altitude#heur1` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Heuristic (not official) | The call returned 450 (int), as annotated. |
| **PASS** | max_altitude(-1, 450, 300) · `test:max_altitude#heur2` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Heuristic (not official) | The call returned 450 (int), as annotated. |
| **PASS** | max_altitude(1000000, 450, 300) · `test:max_altitude#heur3` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Heuristic (not official) | The call returned 1000000 (int), as annotated. |

#### SKIPPED — average_speed(0.0, 2.0)

`test:average_speed#heur1` · Heuristic (not official) · `MysteryInc/FirstLaunch/FIXME2.py`

Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py.

Not run: blocked by `syntax:MysteryInc/FirstLaunch/FIXME2.py`.

- Call: `average_speed(0.0, 2.0)`
- Rule from the subject: `otherwise → distance / hours`

#### SKIPPED — average_speed(-1.0, 2.0)

`test:average_speed#heur2` · Heuristic (not official) · `MysteryInc/FirstLaunch/FIXME2.py`

Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py.

Not run: blocked by `syntax:MysteryInc/FirstLaunch/FIXME2.py`.

- Call: `average_speed(-1.0, 2.0)`
- Rule from the subject: `otherwise → distance / hours`

#### SKIPPED — average_speed(1000000.0, 2.0)

`test:average_speed#heur3` · Heuristic (not official) · `MysteryInc/FirstLaunch/FIXME2.py`

Not run: blocked by syntax:MysteryInc/FirstLaunch/FIXME2.py.

Not run: blocked by `syntax:MysteryInc/FirstLaunch/FIXME2.py`.

- Call: `average_speed(1000000.0, 2.0)`
- Rule from the subject: `otherwise → distance / hours`

#### SKIPPED — emoji_grade(-1)

`test:emoji_grade#heur1` · Heuristic (not official) · `MysteryInc/FirstLaunch/flight_functions/grade_landing.py`

Not run: blocked by function:emoji_grade:emoji_grade.

Not run: blocked by `function:emoji_grade:emoji_grade`.

- Call: `emoji_grade(-1)`
- Rule from the subject: `vertical_speed <= 2 → "🟢"`

#### SKIPPED — emoji_grade(1000000)

`test:emoji_grade#heur2` · Heuristic (not official) · `MysteryInc/FirstLaunch/flight_functions/grade_landing.py`

Not run: blocked by function:emoji_grade:emoji_grade.

Not run: blocked by `function:emoji_grade:emoji_grade`.

- Call: `emoji_grade(1000000)`
- Rule from the subject: `vertical_speed > 5 → "🔴"`

#### SKIPPED — remaining_fuel(0, 3)

`test:remaining_fuel#heur1` · Heuristic (not official) · `MysteryInc/FirstLaunch/route_math/fuel_share.py`

Not run: blocked by function:fuel_share:remaining_fuel.

Not run: blocked by `function:fuel_share:remaining_fuel`.

- Call: `remaining_fuel(0, 3)`
- Rule from the subject: `returns total_fuel % crew`

#### SKIPPED — remaining_fuel(-1, 3)

`test:remaining_fuel#heur2` · Heuristic (not official) · `MysteryInc/FirstLaunch/route_math/fuel_share.py`

Not run: blocked by function:fuel_share:remaining_fuel.

Not run: blocked by `function:fuel_share:remaining_fuel`.

- Call: `remaining_fuel(-1, 3)`
- Rule from the subject: `returns total_fuel % crew`

#### SKIPPED — remaining_fuel(1000000, 3)

`test:remaining_fuel#heur3` · Heuristic (not official) · `MysteryInc/FirstLaunch/route_math/fuel_share.py`

Not run: blocked by function:fuel_share:remaining_fuel.

Not run: blocked by `function:fuel_share:remaining_fuel`.

- Call: `remaining_fuel(1000000, 3)`
- Rule from the subject: `returns total_fuel % crew`

#### WARNING — fuel_share(-1, 3)

`test:fuel_share#heur2` · severity: minor · Heuristic (not official) · `MysteryInc/FirstLaunch/route_math/fuel_share.py:1` · diagnosis: `wrong_value`

Returned 0 instead of -1.

- Call: `fuel_share(-1, 3)`
- Expected: `-1` (int)
- Actual: `0` (int)
- Rule from the subject: `returns total_fuel // crew`

```text
# MysteryInc/FirstLaunch/route_math/fuel_share.py
  1 | def fuel_share(total_fuel: int, crew: int) -> int:
  2 |     # Integer division: every crew member gets the same amount
  3 |     return round(total_fuel / crew)
```

#### WARNING — is_safe(0, 250)

`test:is_safe#heur1` · severity: minor · Heuristic (not official) · `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4` · diagnosis: `str_instead_of_bool`

Returned the string "True" (str) instead of the boolean True (bool).

- Call: `is_safe(0, 250)`
- Expected: `True` (bool)
- Actual: `'True'` (str)
- Rule from the subject: `speed <= limit → True`

```text
# MysteryInc/FirstLaunch/flight_functions/safe_speed.py
  1 | def is_safe(speed: int, limit: int) -> bool:
  2 |     # We are safe as long as we do not go over the limit
  3 |     if speed <= limit:
> 4 |         return "True"
  5 |     else:
  6 |         return "False"
```

**Suggested fix** (confidence: high): Return the booleans True/False instead of the strings "True"/"False".

```diff
--- a/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
+++ b/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
@@ -3,4 +3,4 @@
     if speed <= limit:
-        return "True"
+        return True
     else:
-        return "False"
+        return False
```

#### WARNING — is_safe(-1, 250)

`test:is_safe#heur2` · severity: minor · Heuristic (not official) · `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:4` · diagnosis: `str_instead_of_bool`

Returned the string "True" (str) instead of the boolean True (bool).

- Call: `is_safe(-1, 250)`
- Expected: `True` (bool)
- Actual: `'True'` (str)
- Rule from the subject: `speed <= limit → True`

```text
# MysteryInc/FirstLaunch/flight_functions/safe_speed.py
  1 | def is_safe(speed: int, limit: int) -> bool:
  2 |     # We are safe as long as we do not go over the limit
  3 |     if speed <= limit:
> 4 |         return "True"
  5 |     else:
  6 |         return "False"
```

**Suggested fix** (confidence: high): Return the booleans True/False instead of the strings "True"/"False".

```diff
--- a/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
+++ b/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
@@ -3,4 +3,4 @@
     if speed <= limit:
-        return "True"
+        return True
     else:
-        return "False"
+        return False
```

#### WARNING — is_safe(1000000, 250)

`test:is_safe#heur3` · severity: minor · Heuristic (not official) · `MysteryInc/FirstLaunch/flight_functions/safe_speed.py:6` · diagnosis: `str_instead_of_bool`

Returned the string "False" (str) instead of the boolean False (bool).

- Call: `is_safe(1000000, 250)`
- Expected: `False` (bool)
- Actual: `'False'` (str)
- Rule from the subject: `otherwise → False`

```text
# MysteryInc/FirstLaunch/flight_functions/safe_speed.py
  1 | def is_safe(speed: int, limit: int) -> bool:
  2 |     # We are safe as long as we do not go over the limit
  3 |     if speed <= limit:
  4 |         return "True"
  5 |     else:
> 6 |         return "False"
```

**Suggested fix** (confidence: high): Return the booleans True/False instead of the strings "True"/"False".

```diff
--- a/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
+++ b/MysteryInc/FirstLaunch/flight_functions/safe_speed.py
@@ -3,4 +3,4 @@
     if speed <= limit:
-        return "True"
+        return True
     else:
-        return "False"
+        return False
```

#### WARNING — mission_clock(-1)

`test:mission_clock#heur1` · severity: minor · Heuristic (not official) · `MysteryInc/FirstLaunch/mission_clock.py:6` · diagnosis: `prints_instead_of_returns`

Returned None but printed '-1:59:59': the function must return '-1:59:59', not print it.

- Call: `mission_clock(-1)`
- Expected: `'-1:59:59'` (str)
- Actual: `None` (NoneType)
- Rule from the subject: `returns f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"`

```text
# MysteryInc/FirstLaunch/mission_clock.py
  1 | def mission_clock(seconds: int) -> str:
  2 |     hours = seconds // 3600
  3 |     minutes = seconds % 3600 // 60
  4 |     secs = seconds % 60
  5 |     # :02 pads each field with a leading zero
> 6 |     print(f"{hours:02}:{minutes:02}:{secs:02}")
```

**Suggested fix** (confidence: medium): Return the value instead of printing it in mission_clock.

```diff
--- a/MysteryInc/FirstLaunch/mission_clock.py
+++ b/MysteryInc/FirstLaunch/mission_clock.py
@@ -5,2 +5,2 @@
     # :02 pads each field with a leading zero
-    print(f"{hours:02}:{minutes:02}:{secs:02}")
+    return f"{hours:02}:{minutes:02}:{secs:02}"
```

#### WARNING — mission_clock(1000000)

`test:mission_clock#heur2` · severity: minor · Heuristic (not official) · `MysteryInc/FirstLaunch/mission_clock.py:6` · diagnosis: `prints_instead_of_returns`

Returned None but printed '277:46:40': the function must return '277:46:40', not print it.

- Call: `mission_clock(1000000)`
- Expected: `'277:46:40'` (str)
- Actual: `None` (NoneType)
- Rule from the subject: `returns f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"`

```text
# MysteryInc/FirstLaunch/mission_clock.py
  1 | def mission_clock(seconds: int) -> str:
  2 |     hours = seconds // 3600
  3 |     minutes = seconds % 3600 // 60
  4 |     secs = seconds % 60
  5 |     # :02 pads each field with a leading zero
> 6 |     print(f"{hours:02}:{minutes:02}:{secs:02}")
```

**Suggested fix** (confidence: medium): Return the value instead of printing it in mission_clock.

```diff
--- a/MysteryInc/FirstLaunch/mission_clock.py
+++ b/MysteryInc/FirstLaunch/mission_clock.py
@@ -5,2 +5,2 @@
     # :02 pads each field with a leading zero
-    print(f"{hours:02}:{minutes:02}:{secs:02}")
+    return f"{hours:02}:{minutes:02}:{secs:02}"
```

## Bonus

Bonus completion: **0.0%** (0/3 bonus exercises fully passing). Bonus items never block the submission.

| Exercise | File | Status | Checks passed | Score | Issues |
|---|---|---|---|---|---|
| Bonus 1 — Emoji grade | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | **NOT IMPLEMENTED** | 1/10 | 10.0% | 11 |
| Bonus 2 — Max altitude | `MysteryInc/FirstLaunch/bonus/max_altitude.py` | **PARTIAL** | 10/11 | 90.9% | 1 |
| Bonus 3 — Countdown | `MysteryInc/FirstLaunch/bonus/countdown.py` | **NOT IMPLEMENTED** | 0/3 | 0.0% | 3 |

| Status | Check | Location | Origin | Result |
|---|---|---|---|---|
| **BONUS** | Bonus file not found · `structure:file:MysteryInc/FirstLaunch/bonus/countdown.py` | `MysteryInc/FirstLaunch/bonus/countdown.py` | Explicit requirement | Bonus file MysteryInc/FirstLaunch/bonus/countdown.py was not found (optional: it does not affect the mandatory score). |
| **PASS** | File present · `structure:file:MysteryInc/FirstLaunch/bonus/max_altitude.py` | `MysteryInc/FirstLaunch/bonus/max_altitude.py` | Explicit requirement | MysteryInc/FirstLaunch/bonus/max_altitude.py is at the expected path. |
| **PASS** | Valid Python syntax · `syntax:MysteryInc/FirstLaunch/bonus/max_altitude.py` | `MysteryInc/FirstLaunch/bonus/max_altitude.py` | Explicit requirement | max_altitude.py compiles without syntax errors. |
| **BONUS** | Bonus not implemented · `function:emoji_grade:emoji_grade` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Explicit requirement | Bonus function emoji_grade() is not implemented in grade_landing.py (optional). |
| **PASS** | Function found · `function:max_altitude:max_altitude` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Explicit requirement | max_altitude() is defined in max_altitude.py (line 1). |
| **PASS** | Signature matches the subject · `signature:max_altitude:max_altitude` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Explicit requirement | max_altitude() has the expected signature: def max_altitude(a: int, b: int, c: int) -\> int. |
| **PASS** | Returns its result · `returns:max_altitude:max_altitude` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Explicit requirement | max_altitude() returns its result with a return statement. |
| **PASS** | No side effects at import · `import_effects:max_altitude` | `MysteryInc/FirstLaunch/bonus/max_altitude.py` | Explicit requirement | Importing the module prints nothing, asks for no input and does not crash. |
| **SKIPPED** | emoji_grade(0) · `test:emoji_grade#ex1` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Explicit requirement | Not run: blocked by function:emoji_grade:emoji_grade. |
| **SKIPPED** | emoji_grade(7) · `test:emoji_grade#ex2` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Explicit requirement | Not run: blocked by function:emoji_grade:emoji_grade. |
| **PASS** | max_altitude(120, 450, 300) · `test:max_altitude#ex1` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Explicit requirement | Returned 450 as expected. |
| **PASS** | max_altitude(-5, -2, -9) · `test:max_altitude#ex2` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Explicit requirement | Returned -2 as expected. |
| **SKIPPED** | python3 countdown.py: not run · `test:countdown#session1` | `MysteryInc/FirstLaunch/bonus/countdown.py` | Explicit requirement | Not run: blocked by structure:file:MysteryInc/FirstLaunch/bonus/countdown.py. |
| **SKIPPED** | Prompt 1: 'Countdown start: ' · `prompt:countdown:1` | `MysteryInc/FirstLaunch/bonus/countdown.py` | Explicit requirement | Not run: blocked by structure:file:MysteryInc/FirstLaunch/bonus/countdown.py. |
| **SKIPPED** | emoji_grade(1) · `test:emoji_grade#derived1` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Derived test | Not run: blocked by function:emoji_grade:emoji_grade. |
| **SKIPPED** | emoji_grade(2) · `test:emoji_grade#derived2` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Derived test | Not run: blocked by function:emoji_grade:emoji_grade. |
| **SKIPPED** | emoji_grade(3) · `test:emoji_grade#derived3` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Derived test | Not run: blocked by function:emoji_grade:emoji_grade. |
| **SKIPPED** | emoji_grade(4) · `test:emoji_grade#derived4` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Derived test | Not run: blocked by function:emoji_grade:emoji_grade. |
| **SKIPPED** | emoji_grade(5) · `test:emoji_grade#derived5` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Derived test | Not run: blocked by function:emoji_grade:emoji_grade. |
| **SKIPPED** | emoji_grade(6) · `test:emoji_grade#derived6` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Derived test | Not run: blocked by function:emoji_grade:emoji_grade. |
| **SKIPPED** | emoji_grade(-1) · `test:emoji_grade#heur1` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Heuristic (not official) | Not run: blocked by function:emoji_grade:emoji_grade. |
| **SKIPPED** | emoji_grade(1000000) · `test:emoji_grade#heur2` | `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` | Heuristic (not official) | Not run: blocked by function:emoji_grade:emoji_grade. |
| **PASS** | max_altitude(0, 450, 300) · `test:max_altitude#heur1` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Heuristic (not official) | The call returned 450 (int), as annotated. |
| **PASS** | max_altitude(-1, 450, 300) · `test:max_altitude#heur2` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Heuristic (not official) | The call returned 450 (int), as annotated. |
| **PASS** | max_altitude(1000000, 450, 300) · `test:max_altitude#heur3` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:1` | Heuristic (not official) | The call returned 1000000 (int), as annotated. |
| **BONUS** (critical) | Forbidden builtin max() · `constraint:max_altitude:forbidden_builtin:max` | `MysteryInc/FirstLaunch/bonus/max_altitude.py:2` | Explicit requirement | max() is forbidden by the subject, but max_altitude.py calls it in max_altitude() (line 2). (Bonus exercise: this does not block your submission.) |
| **PASS** | Only authorized builtins · `constraint:max_altitude:builtin_not_allowed:*` | `MysteryInc/FirstLaunch/bonus/max_altitude.py` | Explicit requirement | max_altitude.py only uses authorized builtins (input, print, len, int, str, float, bool). |
| **PASS** | No forbidden import · `constraint:max_altitude:import:*` | `MysteryInc/FirstLaunch/bonus/max_altitude.py` | Explicit requirement | max_altitude.py imports nothing, as required. |

#### SKIPPED — Prompt 1: 'Countdown start: '

`prompt:countdown:1` · Explicit requirement · `MysteryInc/FirstLaunch/bonus/countdown.py`

Not run: blocked by structure:file:MysteryInc/FirstLaunch/bonus/countdown.py.

Not run: blocked by `structure:file:MysteryInc/FirstLaunch/bonus/countdown.py`.

#### SKIPPED — python3 countdown.py: not run

`test:countdown#session1` · Explicit requirement · `MysteryInc/FirstLaunch/bonus/countdown.py`

Not run: blocked by structure:file:MysteryInc/FirstLaunch/bonus/countdown.py.

Not run: blocked by `structure:file:MysteryInc/FirstLaunch/bonus/countdown.py`.

- Standard input: `3↵`

#### SKIPPED — emoji_grade(1)

`test:emoji_grade#derived1` · Derived test · `MysteryInc/FirstLaunch/flight_functions/grade_landing.py`

Not run: blocked by function:emoji_grade:emoji_grade.

Not run: blocked by `function:emoji_grade:emoji_grade`.

- Call: `emoji_grade(1)`
- Rule from the subject: `vertical_speed <= 2 → "🟢"`

#### SKIPPED — emoji_grade(2)

`test:emoji_grade#derived2` · Derived test · `MysteryInc/FirstLaunch/flight_functions/grade_landing.py`

Not run: blocked by function:emoji_grade:emoji_grade.

Not run: blocked by `function:emoji_grade:emoji_grade`.

- Call: `emoji_grade(2)`
- Rule from the subject: `vertical_speed <= 2 → "🟢"`

#### SKIPPED — emoji_grade(3)

`test:emoji_grade#derived3` · Derived test · `MysteryInc/FirstLaunch/flight_functions/grade_landing.py`

Not run: blocked by function:emoji_grade:emoji_grade.

Not run: blocked by `function:emoji_grade:emoji_grade`.

- Call: `emoji_grade(3)`
- Rule from the subject: `2 < vertical_speed <= 5 → "🟡"`

#### SKIPPED — emoji_grade(4)

`test:emoji_grade#derived4` · Derived test · `MysteryInc/FirstLaunch/flight_functions/grade_landing.py`

Not run: blocked by function:emoji_grade:emoji_grade.

Not run: blocked by `function:emoji_grade:emoji_grade`.

- Call: `emoji_grade(4)`
- Rule from the subject: `2 < vertical_speed <= 5 → "🟡"`

#### SKIPPED — emoji_grade(5)

`test:emoji_grade#derived5` · Derived test · `MysteryInc/FirstLaunch/flight_functions/grade_landing.py`

Not run: blocked by function:emoji_grade:emoji_grade.

Not run: blocked by `function:emoji_grade:emoji_grade`.

- Call: `emoji_grade(5)`
- Rule from the subject: `2 < vertical_speed <= 5 → "🟡"`

#### SKIPPED — emoji_grade(6)

`test:emoji_grade#derived6` · Derived test · `MysteryInc/FirstLaunch/flight_functions/grade_landing.py`

Not run: blocked by function:emoji_grade:emoji_grade.

Not run: blocked by `function:emoji_grade:emoji_grade`.

- Call: `emoji_grade(6)`
- Rule from the subject: `vertical_speed > 5 → "🔴"`

#### SKIPPED — emoji_grade(0)

`test:emoji_grade#ex1` · Explicit requirement · `MysteryInc/FirstLaunch/flight_functions/grade_landing.py`

Not run: blocked by function:emoji_grade:emoji_grade.

Not run: blocked by `function:emoji_grade:emoji_grade`.

- Call: `emoji_grade(0)`
- Rule from the subject: `vertical_speed <= 2 → "🟢"`

#### SKIPPED — emoji_grade(7)

`test:emoji_grade#ex2` · Explicit requirement · `MysteryInc/FirstLaunch/flight_functions/grade_landing.py`

Not run: blocked by function:emoji_grade:emoji_grade.

Not run: blocked by `function:emoji_grade:emoji_grade`.

- Call: `emoji_grade(7)`
- Rule from the subject: `vertical_speed > 5 → "🔴"`

#### SKIPPED — emoji_grade(-1)

`test:emoji_grade#heur1` · Heuristic (not official) · `MysteryInc/FirstLaunch/flight_functions/grade_landing.py`

Not run: blocked by function:emoji_grade:emoji_grade.

Not run: blocked by `function:emoji_grade:emoji_grade`.

- Call: `emoji_grade(-1)`
- Rule from the subject: `vertical_speed <= 2 → "🟢"`

#### SKIPPED — emoji_grade(1000000)

`test:emoji_grade#heur2` · Heuristic (not official) · `MysteryInc/FirstLaunch/flight_functions/grade_landing.py`

Not run: blocked by function:emoji_grade:emoji_grade.

Not run: blocked by `function:emoji_grade:emoji_grade`.

- Call: `emoji_grade(1000000)`
- Rule from the subject: `vertical_speed > 5 → "🔴"`

#### BONUS — Forbidden builtin max()

`constraint:max_altitude:forbidden_builtin:max` · severity: critical · Explicit requirement · `MysteryInc/FirstLaunch/bonus/max_altitude.py:2` · diagnosis: `forbidden_builtin`

max() is forbidden by the subject, but max_altitude.py calls it in max_altitude() (line 2). (Bonus exercise: this does not block your submission.)

```text
# MysteryInc/FirstLaunch/bonus/max_altitude.py
  1 | def max_altitude(a: int, b: int, c: int) -> int:
> 2 |     return max(a, b, c)
```

**Suggested fix** (confidence: low): Replace max() with your own logic: compare the values two by two and keep the largest in a variable.

#### BONUS — Bonus not implemented

`function:emoji_grade:emoji_grade` · Explicit requirement · `MysteryInc/FirstLaunch/flight_functions/grade_landing.py` · diagnosis: `bonus_not_implemented`

Bonus function emoji_grade() is not implemented in grade_landing.py (optional).

#### BONUS — Bonus file not found

`structure:file:MysteryInc/FirstLaunch/bonus/countdown.py` · Explicit requirement · `MysteryInc/FirstLaunch/bonus/countdown.py` · diagnosis: `missing_bonus_file`

Bonus file MysteryInc/FirstLaunch/bonus/countdown.py was not found (optional: it does not affect the mandatory score).

---

*Readiness Score is not an official grade. It only covers the requirements PréMoulinette could verify from the subject; the real grader may run hidden tests.*
