"""Registries filled by the ``_tpl_*`` modules: one explanation template and one fix hint per diagnosis."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from premoulinette.explain._context import Ctx

Body = Callable[[Ctx], str]
Steps = Callable[[Ctx], list[str]]


@dataclass(frozen=True)
class Template:
    code: str
    title_fr: str
    title_en: str
    body: Body

    def title(self, ctx: Ctx) -> str:
        return ctx.t(self.title_fr, self.title_en)


TEMPLATES: dict[str, Template] = {}
HINTS: dict[str, Steps] = {}


def template(code: str, title_fr: str, title_en: str) -> Callable[[Body], Body]:
    def register(body: Body) -> Body:
        if code in TEMPLATES:
            raise ValueError(f"duplicate explanation template for {code!r}")
        TEMPLATES[code] = Template(code, title_fr, title_en, body)
        return body

    return register


def hint(*codes: str) -> Callable[[Steps], Steps]:
    """Register step-by-step fix hints (used by ``how_to_fix`` when no deterministic fix exists)."""

    def register(steps: Steps) -> Steps:
        for code in codes:
            if code in HINTS:
                raise ValueError(f"duplicate fix hint for {code!r}")
            HINTS[code] = steps
        return steps

    return register
