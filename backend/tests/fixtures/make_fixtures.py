"""Regenerate ``backend/tests/fixtures/projects/<variant>/`` from ``demo/projects/mysteryinc_fixed``.

Each variant is a byte-exact copy of the fixed demo project with exactly ONE deliberate mutation.
The script is idempotent: every variant directory is deleted and recreated. Every string
replacement must match exactly once, so the script fails loudly if the fixed project drifts.

Usage (from the repository root)::

    backend\\.venv\\Scripts\\python.exe backend/tests/fixtures/make_fixtures.py

Stdlib only; never imports ``premoulinette``.
"""
from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent
REPO = FIXTURES_DIR.parents[2]
SOURCE_PROJECT = REPO / "demo" / "projects" / "mysteryinc_fixed"
PROJECTS_DIR = FIXTURES_DIR / "projects"

BASE = "MysteryInc/FirstLaunch"
KELVIN = f"{BASE}/flight_functions/kelvin.py"
SAFE_SPEED = f"{BASE}/flight_functions/safe_speed.py"
GRADE_LANDING = f"{BASE}/flight_functions/grade_landing.py"
FUEL_SHARE = f"{BASE}/route_math/fuel_share.py"
FIXME2 = f"{BASE}/FIXME2.py"
LAUNCH_SEQUENCE = f"{BASE}/launch_sequence.py"
BONUS_DIR = f"{BASE}/bonus"

# Exact text of the bonus function at the end of grade_landing.py (removed by `missing_bonus`).
EMOJI_GRADE_BLOCK = (
    "\n"
    "\n"
    "# Bonus\n"
    "def emoji_grade(vertical_speed: int) -> str:\n"
    "    if vertical_speed <= 2:\n"
    '        return "🟢"\n'
    "    elif vertical_speed <= 5:\n"
    '        return "🟡"\n'
    "    else:\n"
    '        return "🔴"\n'
)

PARASITE_NAMES = frozenset({"__pycache__", ".DS_Store", "Thumbs.db"})


class MutationError(RuntimeError):
    """A mutation could not be applied exactly as declared."""


@dataclass(frozen=True)
class Replace:
    """Replace ``old`` by ``new`` in ``path``; ``old`` must occur exactly once."""

    path: str
    old: str
    new: str


@dataclass(frozen=True)
class Delete:
    """Delete a file or a whole directory (must exist)."""

    path: str


Mutation = Replace | Delete


@dataclass(frozen=True)
class Variant:
    name: str
    description: str
    mutations: tuple[Mutation, ...]


VARIANTS: tuple[Variant, ...] = (
    Variant("correct_project", "Unmodified copy of the fixed demo project.", ()),
    Variant(
        "wrong_bool_type",
        'is_safe returns the strings "True"/"False" instead of booleans.',
        (
            Replace(SAFE_SPEED, "return True", 'return "True"'),
            Replace(SAFE_SPEED, "return False", 'return "False"'),
        ),
    ),
    Variant(
        "wrong_prompt",
        'launch_sequence trap prompt has a typo ("callect").',
        (
            Replace(
                LAUNCH_SEQUENCE,
                '"Set a trap or collect evidence? (trap/evidence) "',
                '"Set a trap or callect evidence? (trap/evidence) "',
            ),
        ),
    ),
    Variant("missing_file", "route_math/fuel_share.py is missing.", (Delete(FUEL_SHARE),)),
    Variant(
        "syntax_error",
        "FIXME2.py: missing colon at the end of the if line.",
        (Replace(FIXME2, "    if hours == 0:\n", "    if hours == 0\n"),),
    ),
    Variant(
        "forbidden_builtin",
        "kelvin.py calls the forbidden builtin abs() (results unchanged).",
        (
            Replace(
                KELVIN,
                "    return celsius + 273.15\n",
                "    return celsius + 273.15 if abs(celsius) >= 0 else 0.0\n",
            ),
        ),
    ),
    Variant(
        "wrong_function_name",
        "safe_speed.py defines is_save instead of is_safe.",
        (Replace(SAFE_SPEED, "def is_safe(", "def is_save("),),
    ),
    Variant(
        "missing_bonus",
        "No bonus: emoji_grade removed from grade_landing.py and bonus/ folder removed.",
        (Replace(GRADE_LANDING, EMOJI_GRADE_BLOCK, ""), Delete(BONUS_DIR)),
    ),
)


def _read_text(path: Path) -> str:
    # Bytes + explicit UTF-8: no newline translation on Windows.
    return path.read_bytes().decode("utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def find_parasites(root: Path) -> list[str]:
    """Return POSIX paths (relative to ``root``) of temporary files that must never be copied."""
    found = []
    for p in root.rglob("*"):
        if p.name in PARASITE_NAMES or p.suffix in (".pyc", ".pyo"):
            found.append(p.relative_to(root).as_posix())
    return sorted(found)


def apply_mutation(root: Path, mutation: Mutation) -> None:
    target = root / mutation.path
    if not target.exists():
        raise MutationError(f"{mutation.path}: does not exist")
    if isinstance(mutation, Delete):
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return
    text = _read_text(target)
    count = text.count(mutation.old)
    if count != 1:
        raise MutationError(f"{mutation.path}: expected exactly 1 occurrence of {mutation.old!r}, found {count}")
    _write_text(target, text.replace(mutation.old, mutation.new))


def build_variant(variant: Variant, dest_root: Path, source: Path = SOURCE_PROJECT) -> Path:
    dest = dest_root / variant.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)
    for mutation in variant.mutations:
        apply_mutation(dest, mutation)
    return dest


def build_all(dest_root: Path = PROJECTS_DIR, source: Path = SOURCE_PROJECT) -> list[Path]:
    """Recreate every variant under ``dest_root``. Refuses a dirty source project."""
    if not source.is_dir():
        raise MutationError(f"source project not found: {source}")
    parasites = find_parasites(source)
    if parasites:
        raise MutationError(f"source project contains parasite files, clean it first: {parasites}")
    dest_root.mkdir(parents=True, exist_ok=True)
    return [build_variant(v, dest_root, source) for v in VARIANTS]


def main() -> int:
    try:
        built = build_all()
    except MutationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for path in built:
        print(f"built {path.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
