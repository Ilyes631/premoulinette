"""Detection of the repository root inside a snapshot.

A snapshot may be the repository itself, contain it in a sub-folder (zip with a top folder,
webkitdirectory upload) or be a sub-folder of it (user selected ``MysteryInc/FirstLaunch``).
Candidates (every directory up to depth 3, optionally stripping leading components of the spec
paths) are ranked by the number of expected paths that exist there with the exact case.

Rules that keep the structure diagnosis honest:
* a directory holding ``.git`` is a real repository root: spec paths are never stripped there, so a
  missing folder level is reported as misplaced files instead of being silently accepted;
* a git root wins as soon as it matches something, or when the best match lies inside it;
* stripping a prefix is only allowed when no expected path outside that prefix exists at the
  candidate (otherwise the candidate *is* the repository root and the files are misplaced).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from premoulinette.project.paths import DirIndex, EntryKind, is_under, join_rel, normalize_rel
from premoulinette.spec.models import PracticalSpec

MAX_DEPTH = 3
MAX_CANDIDATES = 500
_NOT_ROOTS = frozenset({
    ".git", "__pycache__", "__MACOSX", "node_modules", ".venv", "venv", "env", ".tox", ".mypy_cache",
    ".pytest_cache", ".idea", ".vscode",
})


class RootDetection(BaseModel):
    root: str = ""              # "" = snapshot top, else POSIX sub-path of the snapshot
    strip_prefix: str = ""      # spec path prefix to strip (ends with "/"), "" if none
    matched: int = 0
    expected: int = 0
    note: str | None = None
    confident: bool = False


@dataclass(frozen=True)
class _Option:
    root: str
    prefix: str
    matched: int


def under_prefix(spec_path: str, prefix: str) -> bool:
    """True if ``spec_path`` lies inside the stripped ``prefix`` (or is that directory itself)."""
    path = normalize_rel(spec_path)
    return not prefix or path.startswith(prefix) or path + "/" == prefix


def _strip(path: str, prefix: str) -> str:
    if not prefix:
        return path
    if path + "/" == prefix:
        return ""
    return path[len(prefix):]


def resolve(spec_path: str, det: RootDetection) -> str:
    """Spec path (relative to the repository root) -> snapshot-relative path."""
    path = normalize_rel(spec_path)
    if det.strip_prefix and under_prefix(path, det.strip_prefix):
        path = _strip(path, det.strip_prefix)
    return join_rel(det.root, path)


def _expected_paths(spec: PracticalSpec) -> list[tuple[str, EntryKind]]:
    out: list[tuple[str, EntryKind]] = []
    seen: set[str] = set()
    for req in spec.expected_files():
        path = normalize_rel(req.path)
        if path and path not in seen:
            seen.add(path)
            out.append((path, req.kind))
    return out


def _prefixes(expected: list[tuple[str, EntryKind]]) -> list[str]:
    found: set[str] = set()
    for path, _ in expected:
        parts = path.split("/")
        for i in range(1, len(parts)):
            found.add("/".join(parts[:i]) + "/")
    return sorted(found, key=lambda p: (p.count("/"), p))


def _candidates(index: DirIndex) -> list[str]:
    out = [""]
    frontier = [""]
    for _ in range(MAX_DEPTH):
        nxt: list[str] = []
        for parent in frontier:
            for name, is_dir in sorted(index.listing(parent).items()):
                if not is_dir or name in _NOT_ROOTS:
                    continue
                rel = join_rel(parent, name)
                out.append(rel)
                nxt.append(rel)
                if len(out) >= MAX_CANDIDATES:
                    return out
        frontier = nxt
    return out


def _score(index: DirIndex, root: str, prefix: str, expected: list[tuple[str, EntryKind]]) -> int | None:
    matched = 0
    for path, kind in expected:
        if not under_prefix(path, prefix):
            if index.kind(join_rel(root, path)) == kind:
                return None  # a file outside the prefix exists here: this is the real root
            continue
        if index.kind(join_rel(root, _strip(path, prefix))) == kind:
            matched += 1
    return matched


def _rank(option: _Option) -> tuple[int, int, int, str]:
    depth = option.root.count("/") + 1 if option.root else 0
    return (-option.matched, len(option.prefix), depth, option.root)


def _single_top_dir(index: DirIndex) -> str | None:
    listing = {n: d for n, d in index.listing("").items() if n not in ("__MACOSX", ".DS_Store")}
    if len(listing) == 1:
        name, is_dir = next(iter(listing.items()))
        if is_dir and name != ".git":
            return name
    return None


def detect_root(snapshot_root: Path, spec: PracticalSpec) -> RootDetection:
    index = DirIndex(Path(snapshot_root))
    expected = _expected_paths(spec)
    candidates = _candidates(index)
    git_roots = [c for c in candidates if index.listing(c).get(".git") is True]
    prefixes = [""] + _prefixes(expected)

    options: list[_Option] = []
    for cand in candidates:
        for prefix in ([""] if cand in git_roots else prefixes):
            matched = _score(index, cand, prefix, expected)
            if matched is not None:
                options.append(_Option(cand, prefix, matched))
    best = min(options, key=_rank) if options else _Option("", "", 0)

    chosen, note = best, None
    if git_roots:
        best_git = min((o for o in options if o.root in git_roots), key=_rank)
        enclosing = [g for g in git_roots if is_under(best.root, g)]
        if best_git.matched > 0:
            chosen = best_git
        elif enclosing and best.matched > 0:
            git_root = max(enclosing, key=len)
            chosen = _Option(git_root, "", 0)
            note = (
                f"The git repository root is '{git_root or '.'}', but the expected files were found under "
                f"'{best.root or '.'}/{best.prefix}': paths are checked from the repository root."
            )
        elif best.matched == 0:
            chosen = _Option(min(git_roots, key=lambda g: (g.count("/"), len(g))), "", 0)
        # else: the only repository is an unrelated nested one; keep the best match
    elif chosen.matched == 0:
        top = _single_top_dir(index)
        if top is not None:
            chosen = _Option(top, "", 0)

    ties = [o for o in options if o.matched == chosen.matched and o.prefix == chosen.prefix and o.root != chosen.root]
    if note is None:
        note = _note(chosen, len(expected), ties)
    confident = (
        chosen.matched > 0 and not chosen.prefix and 2 * chosen.matched >= len(expected) and not ties
        and (not git_roots or chosen.root in git_roots)
    )
    return RootDetection(
        root=chosen.root, strip_prefix=chosen.prefix, matched=chosen.matched, expected=len(expected),
        note=note, confident=confident,
    )


def _note(chosen: _Option, expected: int, ties: list[_Option]) -> str | None:
    parts: list[str] = []
    if expected and chosen.matched == 0:
        parts.append("None of the expected files were found at their expected paths.")
    elif chosen.prefix:
        parts.append(
            f"The analyzed folder looks like '{chosen.prefix}' of your repository, not its root: "
            f"files are checked relative to it ({chosen.matched}/{expected} expected paths found)."
        )
    elif chosen.root:
        parts.append(
            f"Using '{chosen.root}/' as the repository root ({chosen.matched}/{expected} expected paths found there)."
        )
    elif expected and 2 * chosen.matched < expected:
        parts.append(f"Only {chosen.matched}/{expected} expected paths were found at the repository root.")
    if ties and chosen.matched > 0:
        others = ", ".join(f"'{t.root or '.'}/'" for t in ties[:3])
        parts.append(f"Other folders match equally well ({others}).")
    return " ".join(parts) or None
