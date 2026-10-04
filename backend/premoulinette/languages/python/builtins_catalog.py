"""Stable catalogue of Python builtin names.

The lists are written out explicitly (instead of ``dir(builtins)``) so that the analysis does not
depend on the host interpreter version or platform (``WindowsError`` only exists on Windows,
``PythonFinalizationError`` only on 3.13+...). They cover Python 3.11 to 3.14.
"""
from __future__ import annotations

BUILTIN_FUNCTIONS: frozenset[str] = frozenset({
    "abs", "aiter", "all", "anext", "any", "ascii", "bin", "breakpoint", "callable", "chr", "compile",
    "copyright", "credits", "delattr", "dir", "divmod", "eval", "exec", "exit", "format", "getattr",
    "globals", "hasattr", "hash", "help", "hex", "id", "input", "isinstance", "issubclass", "iter", "len",
    "license", "locals", "max", "min", "next", "oct", "open", "ord", "pow", "print", "quit", "repr",
    "round", "setattr", "sorted", "sum", "vars", "__import__",
})

BUILTIN_TYPES: frozenset[str] = frozenset({
    "bool", "bytearray", "bytes", "classmethod", "complex", "dict", "enumerate", "filter", "float",
    "frozenset", "int", "list", "map", "memoryview", "object", "property", "range", "reversed", "set",
    "slice", "staticmethod", "str", "super", "tuple", "type", "zip",
})

BUILTIN_EXCEPTIONS: frozenset[str] = frozenset({
    "ArithmeticError", "AssertionError", "AttributeError", "BaseException", "BaseExceptionGroup",
    "BlockingIOError", "BrokenPipeError", "BufferError", "BytesWarning", "ChildProcessError",
    "ConnectionAbortedError", "ConnectionError", "ConnectionRefusedError", "ConnectionResetError",
    "DeprecationWarning", "EOFError", "EncodingWarning", "EnvironmentError", "Exception", "ExceptionGroup",
    "FileExistsError", "FileNotFoundError", "FloatingPointError", "FutureWarning", "GeneratorExit",
    "IOError", "ImportError", "ImportWarning", "IndentationError", "IndexError", "InterruptedError",
    "IsADirectoryError", "KeyError", "KeyboardInterrupt", "LookupError", "MemoryError",
    "ModuleNotFoundError", "NameError", "NotADirectoryError", "NotImplementedError", "OSError",
    "OverflowError", "PendingDeprecationWarning", "PermissionError", "ProcessLookupError",
    "PythonFinalizationError", "RecursionError", "ReferenceError", "ResourceWarning", "RuntimeError",
    "RuntimeWarning", "StopAsyncIteration", "StopIteration", "SyntaxError", "SyntaxWarning", "SystemError",
    "SystemExit", "TabError", "TimeoutError", "TypeError", "UnboundLocalError", "UnicodeDecodeError",
    "UnicodeEncodeError", "UnicodeError", "UnicodeTranslateError", "UnicodeWarning", "UserWarning",
    "ValueError", "Warning", "ZeroDivisionError",
})

PYTHON_BUILTINS: frozenset[str] = BUILTIN_FUNCTIONS | BUILTIN_TYPES | BUILTIN_EXCEPTIONS
"""Every callable builtin name (functions, types and exception classes)."""

BYPASS_BUILTINS: frozenset[str] = frozenset({"eval", "exec", "compile", "__import__"})
"""Builtins that can run arbitrary code, hence circumvent any builtin restriction."""

PURE_BUILTINS: frozenset[str] = frozenset({
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes", "callable", "chr", "complex", "dict",
    "divmod", "enumerate", "filter", "float", "format", "frozenset", "hash", "hex", "id", "int",
    "isinstance", "issubclass", "iter", "len", "list", "map", "max", "min", "object", "oct", "ord", "pow",
    "range", "repr", "reversed", "round", "set", "slice", "sorted", "str", "sum", "tuple", "type", "zip",
}) | BUILTIN_EXCEPTIONS
"""Builtins whose call has no observable effect (no I/O, no exit): used to classify import-time code."""
