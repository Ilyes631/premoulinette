"""Structure checks (exact-case paths, misplaced files, unwanted files, .gitignore) and git checks.

Correctness rules:
* existence is tested with **exact case** through directory listings (``DirIndex``): Windows and macOS
  file systems are case-insensitive, the grader's is not;
* a misplaced or wrongly-cased file is a critical FAIL, but ``file_map`` points to the file that was
  found so the other checks (syntax, tests) can still run on it and give useful feedback;
* bonus files never block (status ``bonus``), optional files only warn.

Stable ids: ``structure:file:<spec_path>``, ``structure:parasite:<path>`` (trailing ``/`` for folders),
``structure:gitignore``, ``structure:extra:<path>``, ``git:untracked:<spec_path>``,
``git:ignored:<spec_path>``, ``git:dirty``.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Literal

from premoulinette.project.diagnostics import is_mandatory, plural, requirement_outcome, severity_for, short_list
from premoulinette.project.ingest import SKIP_DIRS
from premoulinette.project.paths import (
    DirIndex,
    basename,
    is_under,
    normalize_rel,
    parent_dirs,
    strip_base,
    tree_sort_key,
)
from premoulinette.project.root_detect import RootDetection, resolve
from premoulinette.results.models import CheckResult, Evidence, GitInfo, Location, Severity, TreeEntry
from premoulinette.spec.models import FileRequirement, PracticalSpec

MAX_PARASITE_CHECKS = 100
MAX_EXTRA_CHECKS = 50
MAX_LISTED_GIT_FILES = 50
_IGNORED_CANDIDATE_DIRS = frozenset({"__MACOSX", ".git"}) | SKIP_DIRS

How = Literal["exact", "case", "misplaced"]


@dataclass
class _Req:
    req: FileRequirement
    path: str                 # spec path as written in the spec (file_map key, check id)
    norm: str                 # normalized spec path
    expected: str             # snapshot-relative path where it must be
    exercise_id: str | None
    found: str | None = None  # snapshot-relative path actually found
    how: How | None = None

    @property
    def label(self) -> str:
        return "folder" if self.req.kind == "directory" else "file"

    @property
    def mandatory(self) -> bool:
        return is_mandatory(self.req.required, self.req.bonus)


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------


def repo_path(actual: str, det: RootDetection) -> str:
    """Snapshot-relative path -> path as seen from the repository root (what the student types)."""
    if det.root and not is_under(actual, det.root):
        return actual
    rel = strip_base(actual, det.root) if det.root else actual
    prefix = det.strip_prefix or ""
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return (prefix + rel) if rel else prefix.rstrip("/")


def _exercise_for(spec: PracticalSpec, path: str) -> str | None:
    matches = [e for e in spec.exercises if normalize_rel(e.file_path) == normalize_rel(path)]
    if not matches:
        return None
    mandatory = [e for e in matches if not e.bonus]
    return (mandatory or matches)[0].id


def _requirements(spec: PracticalSpec, det: RootDetection) -> list[_Req]:
    out: list[_Req] = []
    seen: set[str] = set()
    for req in spec.expected_files():
        norm = normalize_rel(req.path)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(_Req(req=req, path=req.path, norm=norm, expected=resolve(norm, det),
                        exercise_id=_exercise_for(spec, norm)))
    return out


def _in_ignored_dir(path: str) -> bool:
    return any(part in _IGNORED_CANDIDATE_DIRS for part in path.split("/")[:-1])


def _dir_patterns(patterns: list[str]) -> list[str]:
    return [p.strip().rstrip("/") for p in patterns if p.strip().endswith("/")]


def _inside_forbidden_dir(path: str, dir_patterns: list[str]) -> bool:
    return any(fnmatchcase(part, p) for part in path.split("/")[:-1] for p in dir_patterns if "/" not in p)


def match_forbidden(patterns: list[str], rel: str, kind: str) -> str | None:
    """First forbidden pattern matching ``rel`` (repository-relative), gitignore-like, case-sensitive.

    ``x/`` matches folders only; a pattern without ``/`` matches the base name at any depth;
    a pattern with an inner ``/`` is anchored at the repository root.
    """
    name = basename(rel)
    for raw in patterns:
        p = raw.strip()
        if not p or p.startswith(("#", "!")):
            continue
        dir_only = p.endswith("/")
        p = p.rstrip("/")
        if dir_only and kind != "directory":
            continue
        if p.startswith("**/"):
            p = p[3:]
        if "/" in p:
            if fnmatchcase(rel, p.lstrip("/")):
                return raw
        elif fnmatchcase(name, p):
            return raw
    return None


def _first_missing_dir(index: DirIndex, expected: str) -> str | None:
    for parent in parent_dirs(expected):
        if index.kind(parent) != "directory":
            return parent
    return None


def _case_difference(found: str, expected: str) -> str:
    f_parts, e_parts = found.split("/"), expected.split("/")
    diffs = [f"'{f}' instead of '{e}'" for f, e in zip(f_parts, e_parts) if f != e]
    return ", ".join(diffs[:3])


# ---------------------------------------------------------------------------------------------
# check_structure
# ---------------------------------------------------------------------------------------------


def check_structure(
    spec: PracticalSpec, snapshot_root: Path, det: RootDetection, tree: list[TreeEntry]
) -> tuple[list[CheckResult], list[TreeEntry], dict[str, str | None]]:
    """(checks, annotated tree, file_map spec_path -> actual snapshot-relative path or None)."""
    index = DirIndex(Path(snapshot_root))
    reqs = _requirements(spec, det)
    dir_patterns = _dir_patterns(spec.structure.forbidden_patterns)
    _locate(reqs, index, tree, det, dir_patterns)

    checks: list[CheckResult] = []
    dedicated_gitignore = spec.structure.require_gitignore
    for r in reqs:
        if dedicated_gitignore and r.norm == ".gitignore":
            continue  # reported once, by structure:gitignore
        checks.append(_file_check(r, det, index, tree))
    if dedicated_gitignore:
        checks.append(_gitignore_check(spec, reqs, index, tree, det))

    claimed = {r.found for r in reqs if r.found}
    parasites, parasite_paths = _parasite_checks(spec, tree, det, claimed)
    checks.extend(parasites)
    extras, extra_paths = _extra_checks(spec, tree, det, claimed, parasite_paths, reqs)
    checks.extend(extras)

    annotated = _annotate(tree, reqs, det, parasite_paths, extra_paths)
    file_map: dict[str, str | None] = {r.path: r.found for r in reqs}
    return checks, annotated, file_map


def _locate(reqs: list[_Req], index: DirIndex, tree: list[TreeEntry], det: RootDetection,
            dir_patterns: list[str]) -> None:
    for r in reqs:
        if index.kind(r.expected) == r.req.kind:
            r.found, r.how = r.expected, "exact"
    claimed = {r.found for r in reqs if r.found}
    for r in reqs:
        if r.found:
            continue
        alt = index.find_case_insensitive(r.expected)
        if alt and alt not in claimed and index.kind(alt) == r.req.kind:
            r.found, r.how = alt, "case"
            claimed.add(alt)
    for r in reqs:
        if r.found:
            continue
        cand = _best_candidate(r, tree, claimed, det, dir_patterns)
        if cand:
            r.found, r.how = cand, "misplaced"
            claimed.add(cand)


def _best_candidate(r: _Req, tree: list[TreeEntry], claimed: set[str], det: RootDetection,
                    dir_patterns: list[str]) -> str | None:
    """Same base name elsewhere (exact name first, then case-insensitive), closest to the expected place."""
    name = basename(r.norm)
    folded = name.casefold()
    expected_parts = r.expected.split("/")[:-1]
    options: list[tuple[tuple[int, int, int, int, str], str]] = []
    for e in tree:
        if e.kind != r.req.kind or e.path in claimed:
            continue
        cand_name = basename(e.path)
        if cand_name.casefold() != folded:
            continue
        if _in_ignored_dir(e.path) or _inside_forbidden_dir(e.path, dir_patterns):
            continue
        parts = e.path.split("/")[:-1]
        common = 0
        for a, b in zip(parts, expected_parts):
            if a != b:
                break
            common += 1
        rank = (
            0 if cand_name == name else 1,
            0 if is_under(e.path, det.root) else 1,
            -common,
            len(parts),
            e.path,
        )
        options.append((rank, e.path))
    return min(options)[1] if options else None


def _missing_outcome(r: _Req) -> tuple[str, bool, Severity | None]:
    """(status, mandatory, severity) for an expected file that is not at its exact path."""
    status, mandatory = requirement_outcome(r.req.required, r.req.bonus)
    return status, mandatory, severity_for(status, "critical" if mandatory else "minor")


def _file_check(r: _Req, det: RootDetection, index: DirIndex, tree: list[TreeEntry]) -> CheckResult:
    base = dict(
        id=f"structure:file:{r.path}", category="structure", file=r.path, exercise_id=r.exercise_id,
        origin=r.req.origin, bonus=r.req.bonus,
    )
    label = r.label
    is_gitignore = basename(r.norm) == ".gitignore"
    if r.how == "exact":
        return CheckResult(
            **base, status="pass", mandatory=r.mandatory,
            title=f"{label.capitalize()} present", message=f"{r.path} is at the expected path.",
            location=Location(file=r.found),
        )
    status, mandatory, severity = _missing_outcome(r)
    bonus_note = " This is a bonus item: it does not affect the mandatory score." if r.req.bonus else ""
    if r.how in ("case", "misplaced") and r.found:
        found = repo_path(r.found, det)
        details = {"expected_path": r.path, "found_path": found, "actual_path": r.found}
        if r.how == "case":
            diagnosis = "wrong_case_path"
            title = "Wrong letter case in path"
            message = (
                f"Found at {found}, expected at {r.path}: only the letter case differs "
                f"({_case_difference(found, r.norm)}). The grader runs on Linux, where these are different paths, "
                f"so it will not find this {label}."
            )
        else:
            diagnosis = "misplaced_file"
            title = f"Misplaced {label}"
            case_note = " The letter case of its name differs too." if basename(found) != basename(r.norm) else ""
            message = (
                f"Found at {found}, expected at {r.path}.{case_note} The grader only looks at the exact path, "
                f"so this {label} counts as missing until you move it."
            )
        return CheckResult(
            **base, status=status, severity=severity, mandatory=mandatory, diagnosis=diagnosis,
            title=title, message=message + bonus_note, location=Location(file=r.found),
            evidence=Evidence(details=details),
        )
    # missing
    details: dict[str, object] = {"expected_path": r.path}
    hints: list[str] = []
    missing_dir = _first_missing_dir(index, r.expected)
    if missing_dir:
        shown = repo_path(missing_dir, det)
        details["missing_folder"] = shown
        hints.append(f"The folder {shown}/ does not exist.")
    similar = _similar_name(r, tree, det)
    if similar:
        details["similar"] = similar
        hints.append(f"A {label} with a similar name exists: {similar}.")
    if r.req.bonus:
        diagnosis = "missing_bonus_file"
        title = f"Bonus {label} not found"
        message = f"Bonus {label} {r.path} was not found (optional: it does not affect the mandatory score)."
    else:
        diagnosis = "missing_gitignore" if is_gitignore else "missing_file"
        title = f"Missing {label}"
        message = f"{r.path} was not found."
        if mandatory and r.req.kind == "file":
            message += " Nothing in this file can be tested until it exists at this exact path."
    if hints:
        message += " " + " ".join(hints)
    return CheckResult(
        **base, status=status, severity=severity, mandatory=mandatory, diagnosis=diagnosis,
        title=title, message=message, evidence=Evidence(details=details),
    )


def _similar_name(r: _Req, tree: list[TreeEntry], det: RootDetection) -> str | None:
    name = basename(r.norm)
    suffix = name.rsplit(".", 1)[-1] if "." in name else None
    by_name: dict[str, str] = {}
    for e in tree:
        if e.kind != r.req.kind or _in_ignored_dir(e.path) or not is_under(e.path, det.root):
            continue
        cand = basename(e.path)
        if suffix and not cand.endswith("." + suffix):
            continue
        by_name.setdefault(cand.lower(), e.path)
    close = difflib.get_close_matches(name.lower(), list(by_name), n=1, cutoff=0.75)
    return repo_path(by_name[close[0]], det) if close else None


# ---------------------------------------------------------------------------------------------
# .gitignore
# ---------------------------------------------------------------------------------------------


def _gitignore_check(spec: PracticalSpec, reqs: list[_Req], index: DirIndex, tree: list[TreeEntry],
                     det: RootDetection) -> CheckResult:
    req = next((r for r in reqs if r.norm == ".gitignore"), None)
    origin = req.req.origin if req else spec.structure.origin
    expected = req.expected if req else resolve(".gitignore", det)
    base = dict(id="structure:gitignore", category="structure", file=".gitignore", origin=origin)
    if index.kind(expected) == "file":
        return CheckResult(**base, status="pass", title=".gitignore present",
                           message="A .gitignore file is present at the repository root.",
                           location=Location(file=expected))
    hint = ""
    alt = index.find_case_insensitive(expected)
    root_dir = expected.rsplit("/", 1)[0] if "/" in expected else ""
    if alt and index.kind(alt) == "file":
        hint = f" Found {repo_path(alt, det)}: the name must be exactly .gitignore (lower case)."
    else:
        listing = index.listing(root_dir)
        lookalike = next((n for n in sorted(listing) if not listing[n] and n.lower() in
                          ("gitignore", "gitignore.txt", ".gitignore.txt", "_gitignore", ".gitingore", ".gitingnore")), None)
        if lookalike:
            hint = f" Found '{lookalike}' instead: the file must be named exactly .gitignore (starting with a dot, no extension)."
        else:
            nested = sorted(e.path for e in tree if e.kind == "file" and basename(e.path) == ".gitignore"
                            and e.path != expected and not _in_ignored_dir(e.path))
            if nested:
                hint = (f" There is one at {repo_path(nested[0], det)}, but the subject expects it at the repository root"
                        " (a nested .gitignore only applies to its own folder).")
    return CheckResult(
        **base, status="fail", severity="major", mandatory=True, diagnosis="missing_gitignore",
        title="Missing .gitignore",
        message="The subject requires a .gitignore file at the repository root and none was found." + hint,
        evidence=Evidence(details={"expected_path": ".gitignore"}),
    )


# ---------------------------------------------------------------------------------------------
# Unwanted files and extra files
# ---------------------------------------------------------------------------------------------


def _is_placeholder(entry: TreeEntry, children: dict[str, int]) -> bool:
    """Empty dependency/cache folder left by ingestion in place of a folder that was not copied."""
    return entry.kind == "directory" and basename(entry.path) in SKIP_DIRS and children.get(entry.path, 0) == 0


def _parasite_checks(spec: PracticalSpec, tree: list[TreeEntry], det: RootDetection,
                     claimed: set[str]) -> tuple[list[CheckResult], dict[str, str]]:
    """Checks + {snapshot path: note} for every unwanted entry (a folder's content included)."""
    patterns = spec.structure.forbidden_patterns
    errors = spec.structure.forbidden_patterns_are_errors
    ordered = sorted(tree, key=lambda e: tree_sort_key(e.path))
    file_counts: dict[str, int] = {}
    children: dict[str, int] = {}
    for e in ordered:
        for parent in parent_dirs(e.path):
            children[parent] = children.get(parent, 0) + 1
            if e.kind == "file":
                file_counts[parent] = file_counts.get(parent, 0) + 1
    checks: list[CheckResult] = []
    marked: dict[str, str] = {}
    flagged_dirs: list[str] = []
    for e in ordered:
        if det.root and (e.path == det.root or not is_under(e.path, det.root)):
            continue
        if any(is_under(e.path, d) for d in flagged_dirs):
            marked[e.path] = f"inside {repo_path(next(d for d in flagged_dirs if is_under(e.path, d)), det)}/"
            continue
        if e.path in claimed:
            continue
        rel = strip_base(e.path, det.root) if det.root else e.path
        pattern = match_forbidden(patterns, rel, e.kind)
        if pattern is None:
            continue
        shown = repo_path(e.path, det)
        is_dir = e.kind == "directory"
        if is_dir:
            flagged_dirs.append(e.path)
        marked[e.path] = f"matches {pattern}"
        if len(checks) >= MAX_PARASITE_CHECKS:
            continue
        placeholder = _is_placeholder(e, children)
        what = f"{shown}/" if is_dir else shown
        detail_files = file_counts.get(e.path, 0)
        content = ""
        if is_dir:
            content = (" (its content was not copied into the analysis)" if placeholder
                       else f" ({plural(detail_files, 'file')} inside)")
        verdict = "The subject forbids such files" if errors else "Graders usually penalize such files"
        status: Literal["fail", "warning"] = "fail" if errors else "warning"
        checks.append(CheckResult(
            id=f"structure:parasite:{what}", category="structure", status=status,
            severity="major" if errors else "minor", mandatory=errors, diagnosis="parasite_file",
            title="Unwanted folder" if is_dir else "Unwanted file",
            message=(f"{what} should not be submitted: it matches the forbidden pattern {pattern}{content}. "
                     f"{verdict}: remove it from git and list it in .gitignore."),
            file=what, location=Location(file=e.path), origin=spec.structure.origin,
            evidence=Evidence(details={"path": what, "pattern": pattern, "kind": e.kind,
                                       "files": detail_files if is_dir else 1}),
        ))
    return checks, marked


def _extra_checks(spec: PracticalSpec, tree: list[TreeEntry], det: RootDetection, claimed: set[str],
                  parasites: dict[str, str], reqs: list[_Req]) -> tuple[list[CheckResult], set[str]]:
    allow = spec.structure.allow_extra_files
    missing = {basename(r.norm).lower(): r for r in reqs if r.found is None and r.req.kind == "file"}
    checks: list[CheckResult] = []
    extra_paths: set[str] = set()
    for e in sorted(tree, key=lambda x: tree_sort_key(x.path)):
        if e.kind != "file" or not e.path.endswith(".py") or e.path in claimed or e.path in parasites:
            continue
        if not is_under(e.path, det.root) or _in_ignored_dir(e.path):
            continue
        extra_paths.add(e.path)
        if len(checks) >= MAX_EXTRA_CHECKS:
            continue
        shown = repo_path(e.path, det)
        message = f"{shown} is not required by the subject."
        details: dict[str, object] = {"path": shown}
        close = difflib.get_close_matches(basename(e.path).lower(), list(missing), n=1, cutoff=0.8)
        if close:
            target = missing[close[0]]
            details["did_you_mean"] = target.path
            message += f" Did you mean {target.path}? That file is missing."
        elif allow:
            message += " That is fine if it is a helper file; the grader will ignore it."
        status: Literal["info", "warning"] = "info" if allow else "warning"
        checks.append(CheckResult(
            id=f"structure:extra:{shown}", category="structure", status=status,
            severity=None if allow else "minor", mandatory=False, diagnosis="extra_file",
            title="Unexpected file", message=message, file=shown, location=Location(file=e.path),
            origin=spec.structure.origin, evidence=Evidence(details=details),
        ))
    return checks, extra_paths


# ---------------------------------------------------------------------------------------------
# Annotated tree
# ---------------------------------------------------------------------------------------------


def _annotate(tree: list[TreeEntry], reqs: list[_Req], det: RootDetection, parasites: dict[str, str],
              extras: set[str]) -> list[TreeEntry]:
    rows: dict[str, TreeEntry] = {e.path: e.model_copy() for e in tree}
    children = {p for e in tree for p in parent_dirs(e.path)}
    for path, row in rows.items():
        if path in parasites:
            row.status, row.note = "parasite", parasites[path]
        elif path in extras:
            row.status, row.note = "extra", "not required by the subject"
        elif row.kind == "directory" and basename(path) in SKIP_DIRS and path not in children:
            row.note = "not copied (dependency/cache folder)"
    for r in reqs:
        required = r.mandatory
        if r.found and r.found in rows:
            row = rows[r.found]
            row.required, row.bonus = required, r.req.bonus
            if r.how == "exact":
                row.status, row.note = "expected", None
            else:
                row.status, row.note = "misplaced", f"expected at {r.path}"
        if r.how == "exact":
            continue
        if r.expected not in rows:
            note = "missing" if not r.found else f"missing here (found at {repo_path(r.found, det)})"
            rows[r.expected] = TreeEntry(path=r.expected, kind=r.req.kind, status="missing", required=required,
                                         bonus=r.req.bonus, note=note)
        for parent in parent_dirs(r.expected):
            if parent not in rows:
                rows[parent] = TreeEntry(path=parent, kind="directory", status="missing", required=required,
                                         bonus=r.req.bonus, note="folder missing")
    return sorted(rows.values(), key=lambda e: tree_sort_key(e.path))


# ---------------------------------------------------------------------------------------------
# check_git
# ---------------------------------------------------------------------------------------------


def check_git(spec: PracticalSpec, git: GitInfo | None, file_map: dict[str, str | None]) -> list[CheckResult]:
    """Tracking of expected files (paths in ``git`` and ``file_map`` are snapshot-relative) + dirty tree."""
    if git is None or not git.is_repo or git.error:
        return []
    checks: list[CheckResult] = []
    untracked = set(git.untracked)
    ignored = set(git.ignored_required)
    staged = set(git.staged)
    no_commit = git.head is None
    seen: set[str] = set()
    for req in spec.expected_files():
        if req.kind != "file" or req.path in seen:
            continue
        seen.add(req.path)
        actual = file_map.get(req.path)
        if actual is None:
            continue
        where = "" if normalize_rel(actual) == normalize_rel(req.path) else f" (found at {actual})"
        base = dict(category="git", file=req.path, exercise_id=_exercise_for(spec, req.path),
                    location=Location(file=actual), origin=req.origin, bonus=req.bonus)
        status, mandatory = requirement_outcome(req.required, req.bonus)
        if actual in ignored:
            checks.append(CheckResult(
                id=f"git:ignored:{req.path}", **base, status=status, mandatory=mandatory,
                severity=severity_for(status, "critical" if mandatory else "minor"), diagnosis="ignored_file",
                title="Ignored by .gitignore",
                message=(f"{req.path}{where} is ignored by your .gitignore: git will not add it, so it will not be "
                         "submitted. Fix the .gitignore pattern that matches it, then git add and commit it."),
                evidence=Evidence(details={"path": actual}),
            ))
            continue
        if actual in untracked or no_commit:
            message = (
                f"Your repository has no commit yet: {req.path}{where} will not be submitted until you commit it."
                if no_commit and actual not in untracked else
                f"{req.path}{where} is not tracked by git: it will not be submitted. Add it with git add, then commit."
            )
            checks.append(CheckResult(
                id=f"git:untracked:{req.path}", **base, status=status, mandatory=mandatory,
                severity=severity_for(status, "major" if mandatory else "minor"), diagnosis="untracked_file",
                title="Not committed" if no_commit and actual not in untracked else "Not tracked by git",
                message=message, evidence=Evidence(details={"path": actual}),
            ))
            continue
        note = " It has staged changes that are not committed yet." if actual in staged else ""
        checks.append(CheckResult(
            id=f"git:untracked:{req.path}", **base, status="pass", mandatory=is_mandatory(req.required, req.bonus),
            title="Tracked by git", message=f"{req.path}{where} is tracked by git.{note}",
        ))
    checks.append(_dirty_check(git))
    return checks


def _dirty_check(git: GitInfo) -> CheckResult:
    if not git.dirty:
        return CheckResult(
            id="git:dirty", category="git", status="pass", mandatory=False, title="Working tree clean",
            message="Everything is committed: the grader will see exactly this version (once pushed).",
        )
    changed = sorted(set(git.modified) | set(git.staged) | set(git.untracked))
    parts = []
    if git.modified:
        parts.append(f"{len(git.modified)} modified")
    if git.staged:
        parts.append(f"{len(git.staged)} staged")
    if git.untracked:
        parts.append(f"{len(git.untracked)} untracked")
    return CheckResult(
        id="git:dirty", category="git", status="warning", severity="minor", mandatory=False,
        diagnosis="dirty_tree", title="Uncommitted changes",
        message=(f"{plural(len(changed), 'file')} with uncommitted changes ({', '.join(parts)}): "
                 f"{short_list(changed, 4)}. The grader only sees what is committed and pushed."),
        evidence=Evidence(details={
            "files": changed[:MAX_LISTED_GIT_FILES],
            "modified": git.modified[:MAX_LISTED_GIT_FILES],
            "staged": git.staged[:MAX_LISTED_GIT_FILES],
            "untracked": git.untracked[:MAX_LISTED_GIT_FILES],
        }),
    )
