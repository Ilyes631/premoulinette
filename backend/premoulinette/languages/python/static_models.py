"""Static (AST) analysis model for one Python module. Produced WITHOUT executing student code
(``ast.parse`` only). Consumed by function/constraint checks, source mapping and fix builders."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SyntaxErrorInfo(BaseModel):
    message: str                     # e.g. "expected ':'"
    line: int | None = None
    col: int | None = None           # 1-based offset as reported by SyntaxError.offset
    end_col: int | None = None
    text: str | None = None          # offending source line
    kind: str = "SyntaxError"        # SyntaxError / IndentationError / TabError


class ParamInfo(BaseModel):
    name: str
    annotation: str | None = None    # ast.unparse of the annotation
    default: str | None = None       # ast.unparse of the default
    kind: Literal["posonly", "positional", "vararg", "kwonly", "varkw"] = "positional"


class CallSite(BaseModel):
    name: str                        # "abs" for abs(x); "sort" for xs.sort(); dotted "math.sqrt" for module attr
    kind: Literal["builtin", "local", "method", "module_attr", "unknown"]
    line: int
    col: int
    end_col: int | None = None
    in_function: str | None = None   # enclosing top-level function name (None = module level)
    referenced_only: bool = False    # name used without being called (e.g. f = abs)


class ImportInfo(BaseModel):
    module: str                      # "math" ; for "from x import y" -> "x"
    names: list[str] = Field(default_factory=list)
    line: int
    in_function: str | None = None


class ConstructUse(BaseModel):
    name: str                        # one of spec.models.Construct
    line: int
    in_function: str | None = None


class StringLiteral(BaseModel):
    value: str                       # literal value (for f-strings: the static parts joined, {} for fields)
    line: int
    end_line: int
    col: int
    end_col: int
    is_fstring: bool = False
    in_call: str | None = None       # "print" / "input" if the literal is a direct argument of that call
    in_function: str | None = None


class ReturnInfo(BaseModel):
    line: int
    value_src: str | None            # ast.unparse(value) ; None for bare `return`
    value_kind: Literal["none", "constant", "name", "expression", "call"] = "expression"
    constant_type: str | None = None # for constants: "str", "bool", "int", "float", "NoneType"


class FunctionInfo(BaseModel):
    name: str
    line: int
    end_line: int
    params: list[ParamInfo] = Field(default_factory=list)
    return_annotation: str | None = None
    returns: list[ReturnInfo] = Field(default_factory=list)
    has_value_return: bool = False   # at least one `return <expr>` with expr not None
    prints: list[int] = Field(default_factory=list)       # lines of print() calls inside
    inputs: list[int] = Field(default_factory=list)       # lines of input() calls inside
    is_recursive: bool = False
    nested: bool = False             # defined inside another function/class
    decorators: list[str] = Field(default_factory=list)
    docstring: str | None = None


class TopLevelEffect(BaseModel):
    """Statement executed at import time that has observable effects (outside `if __name__ == '__main__':`)."""
    kind: Literal["print", "input", "call", "loop", "other"]
    line: int
    src: str                         # short source excerpt


class ModuleInfo(BaseModel):
    path: str                        # project-relative POSIX path
    ok: bool                         # parsed successfully
    syntax_error: SyntaxErrorInfo | None = None
    encoding_error: str | None = None
    line_count: int = 0
    functions: list[FunctionInfo] = Field(default_factory=list)       # top-level functions only
    nested_functions: list[FunctionInfo] = Field(default_factory=list)
    classes: list[str] = Field(default_factory=list)
    imports: list[ImportInfo] = Field(default_factory=list)
    calls: list[CallSite] = Field(default_factory=list)
    constructs: list[ConstructUse] = Field(default_factory=list)
    strings: list[StringLiteral] = Field(default_factory=list)
    top_level_effects: list[TopLevelEffect] = Field(default_factory=list)
    has_main_guard: bool = False
    defined_names: list[str] = Field(default_factory=list)   # module-level names that shadow builtins etc.

    def function(self, name: str) -> FunctionInfo | None:
        return next((f for f in self.functions if f.name == name), None)
