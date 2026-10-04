"""Static constraints stated in the subject: builtins, imports, methods, constructs, print/import rules."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from premoulinette.spec.models import Constraints, Construct, Origin, explicit
from premoulinette.subject.document import Block
from premoulinette.subject.textutil import Marked, PLACEHOLDER_RE, excerpt, is_identifier, mark, sentences, strip_call_parens

_FN = r"(?:built-?in\s+functions?|built-?ins?|functions?|fonctions?(?:\s+(?:natives?|built-?ins?|pr[ée]d[ée]finies))?)"
_OK = r"(?:authori[sz]ed|allowed|permitted|autoris[ée]+s?)"
_KO = r"(?:forbidden|prohibited|banned|not\s+allowed|interdit[es]*|non\s+autoris[ée]+s?)"
_MOD = r"(?:modules?|imports?|libraries|librairies|biblioth[èe]ques?)"
_METH = r"(?:methods?|m[ée]thodes?)"

ALLOWED_BUILTINS_RE = re.compile(
    rf"(?i)\b(?:{_OK}\s+{_FN}|{_FN}\s+{_OK}|you\s+(?:may|can)\s+(?:only\s+)?use(?:\s+only)?\s+(?:the\s+following\s+)?{_FN}"
    rf"|only\s+(?:the\s+following\s+)?{_FN}\s+(?:are|is)\s+{_OK})"
)
FORBIDDEN_BUILTINS_RE = re.compile(
    rf"(?i)\b(?:{_KO}\s+{_FN}|{_FN}\s+{_KO}|you\s+(?:must|may|can)\s*not\s+use\s+(?:the\s+following\s+)?{_FN})"
)
ALLOWED_IMPORTS_RE = re.compile(rf"(?i)\b(?:{_OK}\s+{_MOD}|{_MOD}\s+{_OK})")
FORBIDDEN_IMPORTS_RE = re.compile(rf"(?i)\b(?:{_KO}\s+{_MOD}|{_MOD}\s+{_KO})")
FORBIDDEN_METHODS_RE = re.compile(rf"(?i)\b(?:{_KO}\s+{_METH}|{_METH}\s+{_KO})")
NO_IMPORT_RE = re.compile(
    r"(?i)\b(?:no\s+imports?\s+(?:is\s+|are\s+)?(?:allowed|authori[sz]ed|permitted)|imports?\s+(?:is|are)\s+(?:forbidden|not\s+allowed|prohibited)"
    r"|you\s+(?:may|must|can)\s*not\s+import|(?:do\s+not|don'?t)\s+import|aucun\s+import|(?:les\s+)?imports?\s+(?:sont\s+|est\s+)?interdits?"
    r"|pas\s+d'imports?|without\s+(?:any\s+)?imports?)\b"
)
_INLINE_FORBIDDEN_RE = re.compile(
    rf"(?i)(?P<codes>(?:⟦\d+⟧\s*(?:,|and|et|or|ou|/)?\s*)+)\s*(?:is|are|est|sont)\s+(?:strictly\s+|formellement\s+)?{_KO}"
)
MUST_NOT_PRINT_RE = re.compile(
    r"(?i)\b(?:must\s+not\s+(?:print|display)|should\s+not\s+(?:print|display)|must\s+never\s+print"
    r"|ne\s+doi(?:t|vent)\s+(?:rien\s+)?(?:pas\s+|jamais\s+)?(?:rien\s+)?afficher)\b"
)
NO_IMPORT_EFFECTS_RE = re.compile(
    r"(?i)(?:must\s+not\s+(?:execute|run)\s+(?:any\s+)?code\s+when\s+(?:they\s+are\s+|it\s+is\s+)?imported"
    r"|no\s+code\s+(?:at|on)\s+(?:the\s+)?top[\s-]level|ne\s+doi(?:t|vent)\s+(?:pas\s+)?ex[ée]cuter\s+(?:aucun\s+)?code)"
)
_CONSTRUCT_PATTERNS: list[tuple[re.Pattern[str], Construct]] = [
    (re.compile(r"(?i)\bfor\s+loops?\b|\bboucles?\s+for\b"), "for"),
    (re.compile(r"(?i)\bwhile\s+loops?\b|\bboucles?\s+while\b"), "while"),
    (re.compile(r"(?i)\b(?:list\s+)?comprehensions?\b|\bcompr[ée]hensions?\b"), "comprehension"),
    (re.compile(r"(?i)\blambdas?\b"), "lambda"),
    (re.compile(r"(?i)\brecursi(?:on|ve)\b|\br[ée]cursivit[ée]\b"), "recursion"),
]
_CALL_THEN_TEXT_RE = re.compile(r"^\s*(?P<name>\.?[A-Za-z_][\w.]*\s*\(\s*\))(?P<rest>.*)$", re.S)
_CONSTRUCT_KO_RE = re.compile(rf"(?i){_KO}|\bmust\s+not\s+use\b|\bne\s+doi(?:t|vent)\s+pas\s+utiliser\b")
_CONSTRUCT_REQUIRED_RE = re.compile(r"(?i)\b(?:must\s+(?:be\s+)?(?:use|recursive)|required|obligatoire|doit\s+(?:utiliser|[êe]tre))\b")


@dataclass
class ConstraintFindings:
    allowed_builtins: list[str] | None = None
    forbidden_builtins: list[str] = field(default_factory=list)
    allowed_imports: list[str] | None = None
    forbidden_imports: list[str] = field(default_factory=list)
    forbidden_methods: list[str] = field(default_factory=list)
    forbidden_constructs: list[Construct] = field(default_factory=list)
    required_constructs: list[Construct] = field(default_factory=list)
    must_not_print: bool = False
    no_import_effects: bool = False
    origin_block: Block | None = None
    notes: list[str] = field(default_factory=list)

    def to_constraints(self) -> Constraints | None:
        c = Constraints(
            allowed_builtins=self.allowed_builtins,
            forbidden_builtins=self.forbidden_builtins,
            allowed_imports=self.allowed_imports,
            forbidden_imports=self.forbidden_imports,
            forbidden_methods=self.forbidden_methods,
            forbidden_constructs=self.forbidden_constructs,
            required_constructs=self.required_constructs,
        )
        if c.is_empty():
            return None
        b = self.origin_block
        c.origin = explicit(excerpt(b.text), b.section or None, b.line) if b else Origin()
        return c


def _names_after(marked: Marked, sentence: str, label_end: int, *, methods: bool = False) -> list[str]:
    """Names listed after a label in one sentence: inline codes first, else comma-separated words."""
    tail = sentence[label_end:]
    codes = [marked.codes[int(m.group(1))] for m in PLACEHOLDER_RE.finditer(tail)]
    raw = codes
    if not raw:
        text = tail.split(":", 1)[1] if ":" in tail else ""
        raw = [w for w in re.split(r"[,;]|\s+(?:and|et|or|ou)\s+", text.strip().rstrip(".")) if w.strip()]
    names: list[str] = []
    for item in raw:
        if not codes:
            # Plain text: sentences() joined the lines, so the last item may run into the next
            # sentence ("sum() Aucun import n'est autorisé"). A call-looking name followed by
            # other words ends the list.
            m = _CALL_THEN_TEXT_RE.match(item)
            if m and m.group("rest").strip() and not m.group("rest").lstrip().startswith("("):
                name = strip_call_parens(m.group("name"))
                if is_identifier(name) and name not in names:
                    names.append(name)
                break
        name = strip_call_parens(item) if methods or "(" in item or "." in item.strip(".") else item.strip().strip(".")
        if is_identifier(name) and name not in names:
            names.append(name)
    return names


def _list_names(blocks: list[Block], start: int, *, methods: bool = False) -> list[str]:
    names: list[str] = []
    for block in blocks[start:]:
        if block.kind != "list_item":
            break
        sources = block.inline_code or [block.text]
        for src in sources:
            for part in re.split(r"[,;]", src):
                name = strip_call_parens(part) if methods or "(" in part else part.strip().strip(".")
                if is_identifier(name) and name not in names:
                    names.append(name)
    return names


def _extend(target: list, values: list) -> None:
    for v in values:
        if v not in target:
            target.append(v)


_LABELS: tuple[tuple[re.Pattern[str], str], ...] = (
    (FORBIDDEN_METHODS_RE, "forbidden_methods"),
    (FORBIDDEN_IMPORTS_RE, "forbidden_imports"),
    (ALLOWED_IMPORTS_RE, "allowed_imports"),
    (FORBIDDEN_BUILTINS_RE, "forbidden_builtins"),
    (ALLOWED_BUILTINS_RE, "allowed_builtins"),
)


def _label_matches(sentence: str) -> list[tuple[int, int, str]]:
    """Non-overlapping constraint labels of a sentence, in order: (start, end, kind).

    A sentence may hold several statements ("Allowed: a, b  Forbidden: c" on two lines of a
    plain-text paragraph); each label owns the text up to the next label.
    """
    found = sorted(
        ((m.start(), -(m.end() - m.start()), prio, kind)
         for prio, (rx, kind) in enumerate(_LABELS) for m in rx.finditer(sentence)),
    )
    out: list[tuple[int, int, str]] = []
    for start, neg_len, _prio, kind in found:
        if out and start < out[-1][1]:
            continue
        out.append((start, start - neg_len, kind))
    return out


def extract_constraints(blocks: list[Block]) -> ConstraintFindings:
    """Scan blocks (in order) for constraint statements."""
    f = ConstraintFindings()

    def note_origin(block: Block) -> None:
        if f.origin_block is None:
            f.origin_block = block

    for i, block in enumerate(blocks):
        if block.kind == "code":
            continue
        marked = mark(block.text, block.inline_code)
        for sent in sentences(marked.text):
            plain = marked.unmark(sent)
            labels = _label_matches(sent)
            handled = bool(labels)
            for idx, (_start, end, kind) in enumerate(labels):
                limit = labels[idx + 1][0] if idx + 1 < len(labels) else len(sent)
                segment = sent[:limit]
                methods = kind == "forbidden_methods"
                names = _names_after(marked, segment, end, methods=methods)
                if not names and idx == len(labels) - 1 and sent.rstrip().endswith(":"):
                    names = _list_names(blocks, i + 1, methods=methods)
                if not names:
                    f.notes.append(f"Constraint statement without a parsable list: {excerpt(marked.unmark(segment), 160)}")
                    continue
                note_origin(block)
                if kind in ("allowed_builtins", "allowed_imports"):
                    current = getattr(f, kind) or []
                    _extend(current, names)
                    setattr(f, kind, current)
                else:
                    _extend(getattr(f, kind), names)
            if not handled:
                m = _INLINE_FORBIDDEN_RE.search(sent)
                if m:
                    codes = [marked.codes[int(x)] for x in PLACEHOLDER_RE.findall(m.group("codes"))]
                    for code in codes:
                        c = code.strip()
                        if c.endswith(")") and c.startswith("."):
                            _extend(f.forbidden_methods, [strip_call_parens(c)])
                        elif c.endswith(")") and is_identifier(strip_call_parens(c)):
                            _extend(f.forbidden_builtins, [strip_call_parens(c)])
                    note_origin(block)
            if NO_IMPORT_RE.search(plain):
                f.allowed_imports = []
                note_origin(block)
            if MUST_NOT_PRINT_RE.search(plain):
                f.must_not_print = True
            if NO_IMPORT_EFFECTS_RE.search(plain):
                f.no_import_effects = True
            for rx, construct in _CONSTRUCT_PATTERNS:
                if not rx.search(plain):
                    continue
                if _CONSTRUCT_KO_RE.search(plain):
                    _extend(f.forbidden_constructs, [construct])
                    note_origin(block)
                elif construct == "recursion" and _CONSTRUCT_REQUIRED_RE.search(plain):
                    _extend(f.required_constructs, [construct])
                    note_origin(block)
    return f
