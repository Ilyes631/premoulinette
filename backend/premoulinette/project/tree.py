"""Listing of a snapshot as :class:`TreeEntry` rows (``.git`` excluded, links never followed)."""
from __future__ import annotations

import os
from pathlib import Path

from premoulinette.project.paths import is_link_like, join_rel, tree_sort_key
from premoulinette.results.models import TreeEntry

MAX_TREE_ENTRIES = 20_000


def list_tree(root: Path) -> list[TreeEntry]:
    """Every directory and file below ``root`` as POSIX relative paths, in hierarchical order.

    ``.git`` (directory or gitlink file) is skipped entirely; git state is reported separately.
    """
    root = Path(root)
    entries: list[TreeEntry] = []
    pending = [""]
    while pending and len(entries) < MAX_TREE_ENTRIES:
        rel_dir = pending.pop()
        try:
            with os.scandir(root / rel_dir if rel_dir else root) as it:
                children = sorted(it, key=lambda e: e.name)
        except OSError:
            continue
        for entry in children:
            if entry.name == ".git" or is_link_like(entry):
                continue
            rel = join_rel(rel_dir, entry.name)
            try:
                if entry.is_dir(follow_symlinks=False):
                    entries.append(TreeEntry(path=rel, kind="directory"))
                    pending.append(rel)
                elif entry.is_file(follow_symlinks=False):
                    size = entry.stat(follow_symlinks=False).st_size
                    entries.append(TreeEntry(path=rel, kind="file", size=size))
            except OSError:
                continue
    entries.sort(key=lambda e: tree_sort_key(e.path))
    return entries
