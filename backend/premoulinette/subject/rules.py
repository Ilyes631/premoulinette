"""Behaviour rules (``cond → value``, "Return X if C, otherwise Y") and reference expressions."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from premoulinette.spec.models import BehaviorRule, FunctionSignature, Origin, explicit
from premoulinette.spec.validate import restricted_names
from premoulinette.subject.document import Block
from premoulinette.subject.textutil import PLACEHOLDER_RE, Marked, excerpt, mark, sentences

_ARROWS = ("→", "⟶", "⇒", "->", "=>")
_IF_PREFIX_RE = re.compile(r"(?i)^(?:if|when|si|lorsque|quand|for|pour|whenever)\s+")
_OTHERWISE_RE = re.compile(
    r"(?i)^(?:otherwise|else|sinon|default|par\s+d[ée]faut|autrement|in\s+(?:all\s+)?other\s+cases|"
    r"dans\s+(?:tous\s+)?les\s+autres\s+cas|any\s+other\s+(?:case|value)s?)$"
)
_RET = r"(?:returns?|renvoie|retourne|renvoyer|retourner|should\s+return|must\s+return|doit\s+(?:renvoyer|retourner))"
_IF = r"(?:if|when|si|lorsque|quand)"
_ELSE = r"(?:otherwise|else|sinon|in\s+all\s+other\s+cases|dans\s+(?:tous\s+)?les\s+autres\s+cas)"
_SLOT = r"(⟦\d+⟧|[^,;⟦]+?)"
_RET_IF_ELSE_RE = re.compile(
    rf"(?i)\b{_RET}\s+{_SLOT}\s+{_IF}\s+{_SLOT}\s*(?:[,;]\s*|\s+)(?:and\s+|et\s+)?{_ELSE}\s*[,;]?\s*"
    rf"(?:(?:it\s+|elle\s+|il\s+)?{_RET}\s+)?{_SLOT}\s*(?:[.;]|$)"
)
_RET_IF_RE = re.compile(rf"(?i)\b{_RET}\s+{_SLOT}\s+{_IF}\s+{_SLOT}\s*(?:[.;,]|$)")
_IF_RET_RE = re.compile(rf"(?i)\b{_IF}\s+{_SLOT}\s*,?\s*(?:then\s+|alors\s+)?{_RET}\s+{_SLOT}\s*(?:[.;,]|$)")
_REF_PRECEDER_RE = re.compile(rf"(?i)(?:\b{_RET}|:|=)\s*$")
_AFTER_IS_CONDITION_RE = re.compile(r"(?i)^\s*(?:if|when|si|lorsque|quand|unless|sauf|only\s+if)\b")
_RAISES_RE = re.compile(r"(?i)^(?:raises?|l[èe]ve|raise|throws?)\s+(?:an?\s+|une?\s+)?`?(?P<name>[A-Za-z_]\w*)`?")


@dataclass
class RuleDraft:
    function: str
    rule: BehaviorRule


@dataclass
class ReferenceDraft:
    function: str
    expr: str
    origin: Origin


@dataclass
class RuleFindings:
    rules: list[RuleDraft] = field(default_factory=list)
    references: list[ReferenceDraft] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _params(sig: FunctionSignature) -> set[str]:
    return {p.name for p in sig.params}


def _valid_condition(src: str, params: set[str]) -> bool:
    names = restricted_names(src)
    return names is not None and bool(names) and names <= params


def _valid_value(src: str, params: set[str]) -> bool:
    names = restricted_names(src)
    return names is not None and names <= params


def _slot_text(marked: Marked, fragment: str) -> str:
    code = marked.single_code(fragment)
    return code.strip() if code is not None else marked.unmark(fragment).strip().strip("`").strip()


def _clean_condition(text: str) -> str:
    text = text.strip().strip("`").strip()
    text = re.sub(r"^[-*•]\s+", "", text)
    text = _IF_PREFIX_RE.sub("", text)
    return re.sub(r"(?i)[\s,:]*(?:then|alors)?[\s,:]*$", "", text).strip()


def _clean_value(text: str) -> str:
    text = text.strip()
    text = re.sub(rf"(?i)^(?:{_RET}|it\s+{_RET})\s+", "", text)
    return text.rstrip(".;,").strip().strip("`").strip()


def _first_arrow(text: str) -> tuple[int, str] | None:
    best: tuple[int, str] | None = None
    for arrow in _ARROWS:
        idx = text.find(arrow)
        if idx >= 0 and (best is None or idx < best[0]):
            best = (idx, arrow)
    return best


class _RuleExtractor:
    def __init__(self, functions: list[FunctionSignature]) -> None:
        self.functions = functions
        self.by_name = {f.name: f for f in functions}
        self.out = RuleFindings()
        self.context_fn: str | None = functions[0].name if len(functions) == 1 else None

    # ---- function attribution -----------------------------------------------------------------
    def mentioned(self, text: str) -> list[str]:
        return [f.name for f in self.functions if re.search(rf"\b{re.escape(f.name)}\b", text)]

    def target(self, text: str) -> str | None:
        if len(self.functions) == 1:
            return self.functions[0].name
        names = self.mentioned(text)
        if len(names) == 1:
            return names[0]
        return self.context_fn

    def update_context(self, block: Block) -> None:
        if len(self.functions) > 1:
            names = self.mentioned(block.text)
            if len(names) == 1:
                self.context_fn = names[0]

    # ---- rules --------------------------------------------------------------------------------
    def add_rule(self, fn: str | None, when: str | None, returns: str | None, raises: str | None,
                 block: Block, text: str, offset: int = 0) -> bool:
        if fn is None:
            self.out.notes.append(f"Rule could not be attached to a function: {excerpt(text, 160)}")
            return False
        params = _params(self.by_name[fn])
        if when is not None and not _valid_condition(when, params):
            return False
        if returns is not None and not _valid_value(returns, params):
            return False
        rule = BehaviorRule(
            when=when, returns=returns, raises=raises, description=excerpt(text),
            origin=explicit(excerpt(text), block.section or None, block.line + offset),
        )
        key = (fn, when, returns, raises)
        if any((r.function, r.rule.when, r.rule.returns, r.rule.raises) == key for r in self.out.rules):
            return True
        self.out.rules.append(RuleDraft(fn, rule))
        return True

    def arrow_rule(self, block: Block, marked: Marked, line: str, offset: int) -> None:
        found = _first_arrow(line)
        if not found:
            return
        pos, arrow = found
        left, right = line[:pos], line[pos + len(arrow):]
        cond_text = _clean_condition(_slot_text(marked, _clean_condition(left)))
        value_text = _clean_value(right)
        value = _slot_text(marked, value_text)
        if not cond_text or not value:
            return
        raises = None
        m = _RAISES_RE.match(marked.unmark(value_text))
        if m:
            raises, value = m.group("name"), None
        when: str | None = None if _OTHERWISE_RE.match(cond_text) else cond_text
        fn = self.target(marked.unmark(line))
        self.add_rule(fn, when, value, raises, block, marked.unmark(line), offset)

    def sentence_rules(self, block: Block, marked: Marked, sent: str) -> None:
        fn = self.target(marked.unmark(sent))
        m = _RET_IF_ELSE_RE.search(sent)
        if m:
            v1, cond, v2 = (_slot_text(marked, g) for g in m.groups())
            if self.add_rule(fn, _clean_condition(cond), _clean_value(v1), None, block, marked.unmark(sent)):
                self.add_rule(fn, None, _clean_value(v2), None, block, marked.unmark(sent))
            return
        m = _RET_IF_RE.search(sent) or None
        if m:
            v1, cond = (_slot_text(marked, g) for g in m.groups())
            self.add_rule(fn, _clean_condition(cond), _clean_value(v1), None, block, marked.unmark(sent))
            return
        m = _IF_RET_RE.search(sent)
        if m:
            cond, v1 = (_slot_text(marked, g) for g in m.groups())
            self.add_rule(fn, _clean_condition(cond), _clean_value(v1), None, block, marked.unmark(sent))

    # ---- references ---------------------------------------------------------------------------
    def references(self, block: Block, marked: Marked, sent: str) -> None:
        for m in PLACEHOLDER_RE.finditer(sent):
            before, after = sent[: m.start()], sent[m.end():]
            if not _REF_PRECEDER_RE.search(before) or _AFTER_IS_CONDITION_RE.match(after):
                continue
            if _first_arrow(before[-4:]):
                continue
            code = marked.codes[int(m.group(1))].strip()
            fn = self._closest_function(marked, before) or (self.functions[0].name if len(self.functions) == 1 else None)
            if fn is None:
                continue
            params = _params(self.by_name[fn])
            names = restricted_names(code)
            if names is None or not names or not names <= params:
                continue
            if any(r.function == fn for r in self.out.references):
                self.out.notes.append(f"Several reference expressions for '{fn}'; kept the first one.")
                continue
            self.out.references.append(ReferenceDraft(
                fn, code, explicit(excerpt(marked.unmark(sent)), block.section or None, block.line)
            ))

    def _closest_function(self, marked: Marked, before: str) -> str | None:
        best: tuple[int, str] | None = None
        unmarked_positions: list[tuple[int, str]] = []
        for m in PLACEHOLDER_RE.finditer(before):
            code = marked.codes[int(m.group(1))].strip()
            name = re.sub(r"\(.*$", "", code)
            if name in self.by_name:
                unmarked_positions.append((m.start(), name))
        for f in self.functions:
            for m in re.finditer(rf"\b{re.escape(f.name)}\b", before):
                unmarked_positions.append((m.start(), f.name))
        for pos, name in unmarked_positions:
            if best is None or pos > best[0]:
                best = (pos, name)
        return best[1] if best else None

    # ---- driver -------------------------------------------------------------------------------
    def run(self, blocks: list[Block]) -> RuleFindings:
        for block in blocks:
            if block.kind == "code":
                if block.lang == "terminal":
                    continue
                for offset, line in enumerate(block.text.split("\n")):
                    s = line.strip()
                    if s and not s.startswith((">>>", "def ", "#")):
                        self.arrow_rule(block, Marked(s, ()), s, offset)
                continue
            if block.kind == "heading":
                self.update_context(block)
                continue
            marked = mark(block.text, block.inline_code)
            self.update_context(block)
            if block.kind in ("list_item", "table_row"):
                self.arrow_rule(block, marked, marked.text.replace("\n", " "), 0)
            else:
                for offset, line in enumerate(marked.text.split("\n")):
                    if _first_arrow(line) and not _RET_IF_ELSE_RE.search(line):
                        self.arrow_rule(block, marked, line, offset)
            for sent in sentences(marked.text):
                self.sentence_rules(block, marked, sent)
                self.references(block, marked, sent)
        return self.out


def extract_rules(blocks: list[Block], functions: list[FunctionSignature]) -> RuleFindings:
    if not functions:
        return RuleFindings()
    return _RuleExtractor(functions).run(blocks)
