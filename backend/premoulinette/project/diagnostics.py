"""Small helpers shared by the structure / static / git check builders."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from premoulinette.results.models import Severity, Status

FailStatus = Literal["fail", "bonus", "warning"]


def requirement_outcome(required: bool, bonus: bool) -> tuple[FailStatus, bool]:
    """(status, mandatory) for a requirement that is NOT met.

    Bonus items never block (status ``bonus``), optional non-bonus items only warn, required ones fail.
    """
    if bonus:
        return "bonus", False
    if not required:
        return "warning", False
    return "fail", True


def is_mandatory(required: bool, bonus: bool) -> bool:
    return required and not bonus


def severity_for(status: Status, severity: Severity) -> Severity | None:
    """Severity is only meaningful for fail/warning (bonus items never block)."""
    return severity if status in ("fail", "warning") else None


def plural(count: int, word: str, plural_word: str | None = None) -> str:
    return f"{count} {word if count == 1 else (plural_word or word + 's')}"


def short_list(items: Iterable[object], limit: int = 5) -> str:
    values = [str(i) for i in items]
    if len(values) <= limit:
        return ", ".join(values)
    return ", ".join(values[:limit]) + f" (+{len(values) - limit} more)"


def lines_text(lines: list[int]) -> str:
    """``[3]`` -> ``'line 3'`` ; ``[3, 7, 9]`` -> ``'lines 3, 7, 9'``."""
    unique = sorted(set(lines))
    if len(unique) == 1:
        return f"line {unique[0]}"
    return "lines " + short_list(unique, limit=8)
