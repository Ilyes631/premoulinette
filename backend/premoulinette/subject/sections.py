"""Section tree of a subject document and exercise detection (sections that name a source file)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from premoulinette.subject.document import Block, SubjectDocument
from premoulinette.subject.textutil import mark

SOURCE_EXTENSIONS = (".py",)
_LABEL_RE = re.compile(
    r"(?i)(?:\b(?:files?|fichiers?|filename|file\s+name|nom\s+du\s+fichier|source\s+file)"
    r"(?:\s+(?:to\s+(?:submit|hand\s+in|create)|à\s+rendre|à\s+créer))?|\bà\s+rendre)\s*:\s*"
)
_PATH_TOKEN_RE = re.compile(r"[\w.\-/\\]*[\w\-]\.[A-Za-z0-9]{1,8}")
_PLAIN_PY_RE = re.compile(r"(?<![\w/.\\-])((?:[\w\-]+/)*[\w\-]+\.py)(?![\w])")
BONUS_WORDS_RE = re.compile(
    r"(?i)\b(?:bonus|optional|optionnel(?:le)?s?|facultati(?:f|ve|fs|ves)|extra|going\s+further|pour\s+aller\s+plus\s+loin)\b"
)
_EXERCISE_IS_BONUS_RE = re.compile(
    r"(?i)\b(?:this\s+exercise\s+is\s+(?:a\s+)?(?:bonus|optional)|cet\s+exercice\s+est\s+(?:un\s+)?(?:bonus|facultatif|optionnel))\b"
)


@dataclass
class Section:
    heading: Block | None          # None for the preamble (content before the first heading)
    blocks: list[Block] = field(default_factory=list)
    is_title: bool = False         # the unique leading h1 (document title)

    @property
    def level(self) -> int:
        return (self.heading.level or 1) if self.heading else 0

    @property
    def title(self) -> str:
        return self.heading.text if self.heading else ""

    def all_blocks(self) -> list[Block]:
        return ([self.heading] if self.heading else []) + self.blocks


@dataclass
class FileRef:
    path: str
    block: Block
    labeled: bool


@dataclass
class ExerciseDraft:
    sections: list[Section]
    file_ref: FileRef
    bonus: bool

    @property
    def heading(self) -> Block | None:
        return self.sections[0].heading

    @property
    def title(self) -> str:
        return self.sections[0].title or self.file_ref.path

    @property
    def level(self) -> int:
        return self.sections[0].level

    def blocks(self) -> list[Block]:
        out: list[Block] = []
        for i, s in enumerate(self.sections):
            out += s.blocks if i == 0 else s.all_blocks()
        return out


def build_sections(doc: SubjectDocument) -> list[Section]:
    sections = [Section(heading=None)]
    headings = doc.headings()
    h1_count = sum(1 for h in headings if h.level == 1)
    for block in doc.blocks:
        if block.kind == "heading":
            is_title = block is headings[0] and block.level == 1 and h1_count == 1
            sections.append(Section(heading=block, is_title=is_title))
        else:
            sections[-1].blocks.append(block)
    return sections


def normalize_path(raw: str) -> str:
    p = raw.strip().strip("`'\"").replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.rstrip(".,;:)")


def _valid_path(p: str) -> bool:
    return bool(p) and not p.startswith(("*", "/")) and re.fullmatch(r"[\w.\-/]+", p) is not None


def _labeled_ref(block: Block) -> str | None:
    marked = mark(block.text, block.inline_code)
    m = _LABEL_RE.search(marked.text)
    if not m:
        return None
    after = marked.text[m.end():].lstrip()
    code = marked.single_code(after[: after.index("⟧") + 1]) if after.startswith("⟦") else None
    candidates = [code] if code else []
    tok = _PATH_TOKEN_RE.match(marked.unmark(after))
    if tok:
        candidates.append(tok.group(0))
    for cand in candidates:
        p = normalize_path(cand)
        if _valid_path(p) and re.search(r"\.\w+$", p):
            return p
    return None


def find_file_ref(section: Section) -> FileRef | None:
    """The file an exercise section asks for: labeled ("File: x.py"), inline code, then plain text.

    The preamble and the document-title section only count when the file is labeled.
    """
    content = [b for b in section.all_blocks() if b.kind != "code"]
    for block in content:
        p = _labeled_ref(block)
        if p:
            return FileRef(p, block, labeled=True)
    if section.heading is None or section.is_title:
        return None
    for block in content:
        for code in block.inline_code:
            p = normalize_path(code)
            if _valid_path(p) and p.endswith(SOURCE_EXTENSIONS):
                return FileRef(p, block, labeled=False)
    for block in content:
        m = _PLAIN_PY_RE.search(block.text)
        if m and _valid_path(m.group(1)):
            return FileRef(normalize_path(m.group(1)), block, labeled=False)
    return None


def detect_exercises(sections: list[Section]) -> tuple[list[ExerciseDraft], list[Section]]:
    """Group sections into exercises; return (exercises, non-exercise sections).

    A section naming a file starts an exercise; following deeper sections without their own file are
    merged into it. A non-exercise heading containing a bonus word opens a "bonus context" for the
    deeper exercises that follow.
    """
    exercises: list[ExerciseDraft] = []
    others: list[Section] = []
    current: ExerciseDraft | None = None
    bonus_level: int | None = None
    for sec in sections:
        level = sec.level
        if bonus_level is not None and sec.heading is not None and level <= bonus_level:
            bonus_level = None
        ref = find_file_ref(sec)
        if ref is not None:
            heading_text = sec.title
            body_text = " ".join(b.text for b in sec.blocks)
            bonus = (bonus_level is not None and level > bonus_level) or bool(BONUS_WORDS_RE.search(heading_text)) \
                or bool(_EXERCISE_IS_BONUS_RE.search(body_text))
            current = ExerciseDraft(sections=[sec], file_ref=ref, bonus=bonus)
            exercises.append(current)
            continue
        if current is not None and sec.heading is not None and level > current.level:
            current.sections.append(sec)
            continue
        current = None
        others.append(sec)
        if sec.heading is not None and BONUS_WORDS_RE.search(sec.title):
            bonus_level = level
    return exercises, others
