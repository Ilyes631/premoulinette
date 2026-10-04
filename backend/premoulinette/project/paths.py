"""POSIX relative path helpers and an exact-case directory index.

Every project path handled by PréMoulinette is a POSIX string relative to a snapshot root.
Existence checks are **exact-case** on purpose: Windows and macOS file systems are case-insensitive,
the grading server is not, so ``os.path.exists("Kelvin.py")`` would happily lie about ``kelvin.py``.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Literal

EntryKind = Literal["file", "directory"]


def normalize_rel(path: str) -> str:
    """``'./a\\\\b//c/'`` -> ``'a/b/c'``. Does not resolve ``..`` (callers validate separately)."""
    parts = [part for part in path.strip().replace("\\", "/").split("/") if part not in ("", ".")]
    return "/".join(parts)


def join_rel(base: str, rel: str) -> str:
    if not base:
        return rel
    if not rel:
        return base
    return f"{base}/{rel}"


def is_under(path: str, base: str) -> bool:
    """True if ``path`` is ``base`` itself or inside it (``base == ""`` means the snapshot top)."""
    return not base or path == base or path.startswith(base + "/")


def strip_base(path: str, base: str) -> str:
    """Path relative to ``base`` (``path`` must be under ``base``)."""
    if not base:
        return path
    if path == base:
        return ""
    if path.startswith(base + "/"):
        return path[len(base) + 1:]
    raise ValueError(f"{path!r} is not under {base!r}")


def basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def parent_dirs(path: str) -> list[str]:
    """``'a/b/c.py'`` -> ``['a', 'a/b']``."""
    parts = path.split("/")
    return ["/".join(parts[:i]) for i in range(1, len(parts))]


def tree_sort_key(path: str) -> list[tuple[str, str]]:
    """Hierarchical, case-insensitive order (children right after their parent directory)."""
    return [(part.lower(), part) for part in path.split("/")]


def is_link_like(entry: os.DirEntry[str]) -> bool:
    """Symlinks, junctions and any other reparse point: never followed nor copied."""
    try:
        if entry.is_symlink():
            return True
        is_junction = getattr(entry, "is_junction", None)
        if is_junction is not None and is_junction():
            return True
        if os.name == "nt":
            attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
            return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except OSError:
        return True
    return False


class DirIndex:
    """Cached, exact-case view of a directory tree. Links are treated as absent."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._cache: dict[str, dict[str, bool]] = {}

    def listing(self, rel_dir: str) -> dict[str, bool]:
        """Exact entry names of ``rel_dir`` mapped to ``is_dir``."""
        cached = self._cache.get(rel_dir)
        if cached is not None:
            return cached
        entries: dict[str, bool] = {}
        target = self.root / rel_dir if rel_dir else self.root
        try:
            with os.scandir(target) as it:
                for entry in it:
                    if is_link_like(entry):
                        continue
                    try:
                        entries[entry.name] = entry.is_dir(follow_symlinks=False)
                    except OSError:
                        continue
        except OSError:
            pass
        self._cache[rel_dir] = entries
        return entries

    def kind(self, rel: str) -> EntryKind | None:
        """Kind of the entry at ``rel`` if it exists with exactly this case, else None."""
        rel = normalize_rel(rel)
        if not rel:
            return "directory"
        parts = rel.split("/")
        parent = ""
        for i, part in enumerate(parts):
            listing = self.listing(parent)
            if part not in listing:
                return None
            is_dir = listing[part]
            if i == len(parts) - 1:
                return "directory" if is_dir else "file"
            if not is_dir:
                return None
            parent = join_rel(parent, part)
        return None  # pragma: no cover - loop always returns

    def find_case_insensitive(self, rel: str) -> str | None:
        """Actual path matching ``rel`` when components are compared case-insensitively."""
        rel = normalize_rel(rel)
        if not rel:
            return ""
        parts = rel.split("/")
        current = ""
        for i, part in enumerate(parts):
            listing = self.listing(current)
            last = i == len(parts) - 1
            if part in listing and (last or listing[part]):
                match = part
            else:
                options = sorted(n for n, is_dir in listing.items() if n.lower() == part.lower() and (last or is_dir))
                if not options:
                    return None
                match = options[0]
            current = join_rel(current, match)
        return current
