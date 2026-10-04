"""Expected repository structure: directory trees, optional folders, .gitignore and forbidden files."""
from __future__ import annotations

import re
from dataclasses import dataclass

from premoulinette.spec.models import DEFAULT_FORBIDDEN_PATTERNS, FileRequirement, Origin, StructureSpec, explicit
from premoulinette.subject.document import Block, SubjectDocument
from premoulinette.subject.textutil import excerpt, mark, sentences

_TREE_MARKERS = ("├", "└", "│", "|--", "`--", "+--", "|__", "\\--")
_PREFIX_RE = re.compile(r"^[\s│|├└┬┼─`+\\\-]*")
_NAME_RE = re.compile(r"[\w.\-+@~]+(?:/[\w.\-+@~]+)*/?")
_COMMENT_SPLIT_RE = re.compile(r"\s{2,}|\s#|\s<-|\s←|\s\(|\s—|\s--\s")
_OPTIONAL_RE = re.compile(
    r"(?i)\b(?:optional|optionnel(?:le)?s?|facultati(?:f|ve|fs|ves)|not\s+(?:mandatory|required)|pas\s+obligatoires?)\b"
)
_NEGATIVE_RE = re.compile(
    r"(?i)\b(?:do\s+not|don'?t|must\s+not|never|forbidden|prohibited|not\s+allowed|penali[sz]ed|interdit\w*|"
    r"ne\s+(?:pas|jamais)|pas\s+de|p[ée]nalis\w*|aucun\w*)\b"
)
_MUST_RE = re.compile(r"(?i)\b(?:must|should|required|requires?|need|needs|doit|doivent|obligatoire|contain|include)\b")
_KNOWN_DIRS = {"__pycache__", ".idea", ".vscode", ".venv", "venv", "node_modules", ".ipynb_checkpoints"}


@dataclass(frozen=True)
class TreeEntry:
    path: str
    is_dir: bool
    has_children: bool
    line_offset: int      # 0-based line inside the code block
    raw: str


def _entry_name(line: str) -> tuple[int, str] | None:
    expanded = line.replace("\t", "    ")
    prefix = _PREFIX_RE.match(expanded)
    width = prefix.end() if prefix else 0
    rest = expanded[width:]
    name = _COMMENT_SPLIT_RE.split(rest, maxsplit=1)[0].strip()
    if not name or name in {".", "..", "...", "…"}:
        return None
    if not _NAME_RE.fullmatch(name):
        return None
    return width, name


def parse_tree(code: str) -> list[TreeEntry] | None:
    """Parse a directory listing (``tree`` output or indented listing) into POSIX paths.

    Returns None if the block does not look like a tree.
    """
    raw_lines = [ln for ln in code.split("\n")]
    rows: list[tuple[int, int, str, str]] = []   # (line_offset, width, name, raw)
    content_lines = 0
    invalid = 0
    for idx, line in enumerate(raw_lines):
        if not line.strip():
            continue
        content_lines += 1
        stripped = line.strip()
        if stripped in {".", "...", "…"}:
            continue
        parsed = _entry_name(line)
        if parsed is None:
            invalid += 1
            continue
        rows.append((idx, parsed[0], parsed[1], line))
    if len(rows) < 2 or invalid > max(0, content_lines // 10):
        return None
    has_markers = any(m in code for m in _TREE_MARKERS)
    has_dir_hint = any(n.endswith("/") or "/" in n for _, _, n, _ in rows)
    has_file = any(re.search(r"\.\w+$", n) for _, _, n, _ in rows)
    if not has_file or not (has_markers or has_dir_hint):
        return None

    entries: list[TreeEntry] = []
    stack: list[tuple[int, str]] = []
    for i, (offset, width, name, raw) in enumerate(rows):
        while stack and stack[-1][0] >= width:
            stack.pop()
        next_width = rows[i + 1][1] if i + 1 < len(rows) else -1
        has_children = next_width > width
        is_dir = name.endswith("/") or has_children
        clean = name.rstrip("/")
        path = "/".join([s for _, s in stack] + [clean])
        entries.append(TreeEntry(path=path, is_dir=is_dir, has_children=has_children, line_offset=offset, raw=raw))
        if is_dir:
            stack.append((width, clean))
    return entries


def find_tree_blocks(doc: SubjectDocument) -> list[tuple[Block, list[TreeEntry]]]:
    found: list[tuple[Block, list[TreeEntry]]] = []
    for block in doc.blocks:
        if block.kind != "code" or block.lang in ("python", "terminal"):
            continue
        entries = parse_tree(block.text)
        if entries:
            found.append((block, entries))
    return found


def _optional_folders(doc: SubjectDocument, dir_names: set[str]) -> list[tuple[str, Block]]:
    out: list[tuple[str, Block]] = []
    for block in doc.blocks:
        if block.kind == "code":
            continue
        marked = mark(block.text, block.inline_code)
        for sent in sentences(marked.text):
            if not _OPTIONAL_RE.search(sent):
                continue
            text = marked.unmark(sent)
            candidates = [c.strip() for c in block.inline_code if c.strip() and c in text]
            candidates += re.findall(r"(?<![\w/.])([\w.\-]+(?:/[\w.\-]+)*)/(?![\w])", text)
            for cand in candidates:
                name = cand
                while name.startswith("./"):
                    name = name[2:]
                name = name.rstrip("/")
                if name and any(d == name or d.endswith("/" + name) for d in dir_names):
                    if all(name != n for n, _ in out):
                        out.append((name, block))
    return out


def _forbidden_mentions(doc: SubjectDocument) -> tuple[bool, list[str], Block | None]:
    """(forbidden files explicitly penalized?, explicitly mentioned patterns, first matching block)."""
    explicit_forbid = False
    patterns: list[str] = []
    first: Block | None = None
    for block in doc.blocks:
        if block.kind == "code":
            continue
        marked = mark(block.text, block.inline_code)
        for sent in sentences(marked.text):
            text = marked.unmark(sent)
            if not _NEGATIVE_RE.search(text):
                continue
            if not re.search(r"(?i)__pycache__|\.pyc\b|temporary\s+files?|fichiers?\s+temporaires?", text):
                continue
            explicit_forbid = True
            first = first or block
            codes = [c for c in block.inline_code if c in text]
            for code in codes:
                pat = _pattern_from_mention(code)
                if pat and pat not in patterns:
                    patterns.append(pat)
    return explicit_forbid, patterns, first


def _pattern_from_mention(token: str) -> str | None:
    t = token.strip().strip("`")
    if not t or " " in t or t in {".gitignore"} or len(t) > 60:
        return None
    if t.rstrip("/") in _KNOWN_DIRS:
        return t.rstrip("/") + "/"
    if t.endswith("/"):
        return t
    if re.fullmatch(r"\.[a-z0-9]{1,4}", t):
        return "*" + t
    if re.fullmatch(r"[\w.*~\-]+", t):
        return t
    return None


def _gitignore_required(doc: SubjectDocument) -> Block | None:
    for block in doc.blocks:
        if block.kind == "code":
            continue
        marked = mark(block.text, block.inline_code)
        for sent in sentences(marked.text):
            text = marked.unmark(sent)
            if ".gitignore" in text and _MUST_RE.search(text) and not _NEGATIVE_RE.search(text):
                return block
    return None


def _origin(block: Block, text: str, line_offset: int = 0) -> Origin:
    return explicit(excerpt(text), block.section or None, block.line + line_offset)


def build_structure(doc: SubjectDocument, notes: list[str]) -> tuple[StructureSpec, list[str]]:
    """Return (structure spec, list of tree file paths)."""
    trees = find_tree_blocks(doc)
    files: dict[str, FileRequirement] = {}
    dir_names: set[str] = set()
    tree_files: list[str] = []
    if len(trees) > 1:
        notes.append(f"{len(trees)} directory trees found in the subject; their entries were merged.")
    for block, entries in trees:
        for entry in entries:
            if entry.is_dir:
                dir_names.add(entry.path)
                if entry.has_children:
                    continue
                kind = "directory"
            else:
                kind = "file"
                tree_files.append(entry.path)
            if entry.path not in files:
                files[entry.path] = FileRequirement(
                    path=entry.path, kind=kind, origin=_origin(block, entry.raw.strip(), entry.line_offset)
                )

    for folder, block in _optional_folders(doc, dir_names):
        matched = 0
        for path, req in files.items():
            parent = path.rsplit("/", 1)[0] if "/" in path else ""
            components = parent.split("/") if parent else []
            if parent == folder or parent.endswith("/" + folder) or folder in components:
                req.required = False
                req.bonus = True
                matched += 1
        if matched:
            notes.append(f"Files under '{folder}/' are optional (bonus): {excerpt(block.text, 120)}")

    structure = StructureSpec(files=list(files.values()))
    if trees:
        structure.origin = _origin(trees[0][0], trees[0][0].text.split("\n")[0])

    gi_block = _gitignore_required(doc)
    if gi_block is not None:
        structure.require_gitignore = True
        if ".gitignore" not in files:
            structure.files.insert(0, FileRequirement(path=".gitignore", origin=_origin(gi_block, gi_block.text)))
        else:
            files[".gitignore"].required = True
            files[".gitignore"].bonus = False
    elif ".gitignore" in files:
        structure.require_gitignore = True

    forbid, patterns, fb_block = _forbidden_mentions(doc)
    if forbid:
        structure.forbidden_patterns_are_errors = True
        required_paths = {f.path.rsplit("/", 1)[-1] for f in structure.files}
        for pat in patterns:
            if pat not in structure.forbidden_patterns and pat not in DEFAULT_FORBIDDEN_PATTERNS \
                    and pat not in required_paths:
                structure.forbidden_patterns.append(pat)
    return structure, tree_files
