"""Shell/git command snippets shared by templates and fix builders (never executed, only displayed)."""
from __future__ import annotations

import posixpath

GITIGNORE_LINES = ("__pycache__/", "*.pyc", ".DS_Store")

_SHELL_SPECIAL = set(" \t'\"$`&|;()<>*?!\\")


def sh_path(path: str) -> str:
    """Path quoted for a POSIX shell / Git Bash command when it contains special characters."""
    if any(ch in _SHELL_SPECIAL for ch in path):
        return "'" + path.replace("'", "'\\''") + "'"
    return path


def gitignore_pattern(path: str) -> str:
    """The .gitignore pattern that covers an unwanted path (``__pycache__/``, ``*.pyc``, ``.DS_Store``...)."""
    parts = path.rstrip("/").split("/")
    if "__pycache__" in parts:
        return "__pycache__/"
    for ext in (".pyc", ".pyo"):
        if path.endswith(ext):
            return "*" + ext
    name = posixpath.basename(path.rstrip("/"))
    return name + "/" if path.endswith("/") else name
