"""Rendering context shared by every explanation template: language switch + evidence shortcuts."""
from __future__ import annotations

import re
from typing import Literal

from premoulinette.explain._evidence import detail, evidence
from premoulinette.explain._markdown import bullets, code, display_value
from premoulinette.results.models import CheckResult, ValueSnapshot

Lang = Literal["fr", "en"]

_COMPARISON = re.compile(r"<=|>=|<|>|==|!=")

TYPE_NAMES: dict[str, tuple[str, str]] = {
    "int": ("un nombre entier", "an integer"),
    "float": ("un nombre à virgule", "a floating-point number"),
    "str": ("une chaîne de caractères", "a string"),
    "bool": ("un booléen (`True` ou `False`)", "a boolean (`True` or `False`)"),
    "NoneType": ("`None` (rien)", "`None` (nothing)"),
    "list": ("une liste", "a list"),
    "tuple": ("un tuple", "a tuple"),
    "dict": ("un dictionnaire", "a dictionary"),
    "set": ("un ensemble", "a set"),
}


class Ctx:
    """Everything a template needs: the check, its evidence and the target language."""

    def __init__(self, check: CheckResult, lang: Lang) -> None:
        self.check = check
        self.lang: Lang = lang
        self.ev = evidence(check)

    def t(self, fr: str, en: str) -> str:
        return fr if self.lang == "fr" else en

    # ---- identity ---------------------------------------------------------------------------
    @property
    def fn(self) -> str | None:
        return self.check.function

    @property
    def file(self) -> str | None:
        loc = self.check.location
        return (loc.file if loc else None) or self.check.file or (self.ev.code.file if self.ev.code else None)

    @property
    def line(self) -> int | None:
        loc = self.check.location
        if loc and loc.line:
            return loc.line
        if self.ev.exception and self.ev.exception.location:
            return self.ev.exception.location.line
        return None

    def where(self) -> str:
        """```file`, ligne 12`` / ```file`, line 12`` or "" when unknown."""
        if not self.file:
            return ""
        if self.line:
            return self.t(f"{code(self.file)}, ligne {self.line}", f"{code(self.file)}, line {self.line}")
        return code(self.file)

    def at_line(self) -> str:
        """`` (ligne 12 de `file`)`` or ""."""
        if self.line and self.file:
            return self.t(f" (ligne {self.line} de {code(self.file)})", f" (line {self.line} of {code(self.file)})")
        if self.line:
            return self.t(f" (ligne {self.line})", f" (line {self.line})")
        return ""

    def fn_code(self, default_fr: str = "ta fonction", default_en: str = "your function") -> str:
        return code(self.fn) if self.fn else self.t(default_fr, default_en)

    def the_function(self) -> str:
        """``La fonction `f``` / ``The function `f``` (or a neutral phrase when the name is unknown)."""
        if self.fn:
            return self.t(f"La fonction {code(self.fn)}", f"The function {code(self.fn)}")
        return self.t("La fonction demandée", "The required function")

    def file_code(self, default_fr: str = "ce fichier", default_en: str = "this file") -> str:
        return code(self.file) if self.file else self.t(default_fr, default_en)

    def source_line(self) -> str | None:
        """Raw source text of the location line, when the evidence carries a code excerpt."""
        excerpt = self.ev.code
        if excerpt is None or self.line is None:
            return None
        index = self.line - excerpt.start_line
        if 0 <= index < len(excerpt.lines):
            return excerpt.lines[index]
        return None

    def detail(self, *keys: str) -> object:
        return detail(self.check, *keys)

    # ---- values -----------------------------------------------------------------------------
    @staticmethod
    def value(snap: ValueSnapshot) -> str:
        return code(display_value(snap.repr, snap.type))

    def typed(self, snap: ValueSnapshot) -> str:
        return f"{self.value(snap)} ({code(snap.type)})"

    def type_name(self, type_name: str) -> str:
        names = TYPE_NAMES.get(type_name)
        if names is None:
            return code(type_name)
        return self.t(*names)

    def is_boundary_case(self) -> bool:
        derived = self.check.category == "derived_tests" or "#derived" in (self.check.test_id or self.check.id)
        return derived and bool(self.ev.rule and _COMPARISON.search(self.ev.rule))

    def facts(self, *, call: bool = True, values: bool = True, where: bool = True) -> str:
        """Bullet list of the concrete facts of a test: call, expected, received, location."""
        items: list[str] = []
        if call and self.ev.call:
            items.append(self.t("appel testé : ", "tested call: ") + code(self.ev.call))
        if values and self.ev.expected_value:
            items.append(self.t("attendu : ", "expected: ") + self.typed(self.ev.expected_value))
        if values and self.ev.actual_value:
            items.append(self.t("obtenu : ", "received: ") + self.typed(self.ev.actual_value))
        if where and self.where():
            items.append(self.t("où regarder : ", "where to look: ") + self.where())
        return bullets(items)

    def stdin_facts(self) -> str:
        lines = self.ev.stdin.splitlines() if self.ev.stdin else []
        if not lines:
            return ""
        shown = ", ".join(code(line) for line in lines[:12])
        return self.t(f"Saisies envoyées au programme, dans l'ordre : {shown}.", f"Inputs sent to the program, in order: {shown}.")
