"""Normalize the language of a code block ("python", "terminal" or the declared language)."""
from __future__ import annotations

import re

from premoulinette.subject.transcript import has_prompt_lines

TERMINAL_ALWAYS = frozenset({
    "terminal", "console", "shell", "shell-session", "sh-session", "shellsession", "session", "pycon-shell",
})
SHELLISH = frozenset({"bash", "sh", "zsh", "powershell", "ps1", "ps", "cmd", "bat", "fish"})
PYTHON_ALIASES = frozenset({"python", "py", "python3", "py3", "pycon", "pytb", "ipython", "doctest"})
UNDECLARED = frozenset({"", "text", "txt", "plaintext", "plain", "none", "nohighlight", "output", "default"})

_DEF_RE = re.compile(r"^\s*(?:def|class)\s+\w+", re.M)


def _first_content_line(content: str) -> str:
    return next((line.strip() for line in content.split("\n") if line.strip()), "")


def detect_code_lang(declared: str | None, content: str, *, has_kbd: bool = False) -> str | None:
    """Return "terminal", "python", another declared language, or None."""
    d = (declared or "").strip().lower()
    if d in TERMINAL_ALWAYS:
        return "terminal"
    if d in SHELLISH:
        return "terminal" if has_prompt_lines(content) else d
    first = _first_content_line(content)
    if d in PYTHON_ALIASES:
        if has_prompt_lines(content) and not first.startswith(">>>") and not _DEF_RE.search(content):
            return "terminal"
        return "python"
    if d not in UNDECLARED:
        return d
    if first.startswith(">>>"):
        return "python"
    if has_prompt_lines(content) or has_kbd:
        return "terminal"
    if _DEF_RE.search(content):
        return "python"
    return None


def lang_from_classes(classes: list[str]) -> str | None:
    """Declared language from HTML classes: language-xxx / lang-xxx / bare known names."""
    for cls in classes:
        c = cls.lower()
        for prefix in ("language-", "lang-", "highlight-source-", "highlight-"):
            if c.startswith(prefix) and len(c) > len(prefix):
                return c[len(prefix):]
    for cls in classes:
        c = cls.lower()
        if c in TERMINAL_ALWAYS or c in SHELLISH or c in PYTHON_ALIASES:
            return c
    return None
