"""Symbol-level regions for Python source, using the standard library AST.

Tree-sitter can replace this later for multi-language support; the interface
(name, line span, referenced names) is what the rest of the system depends on.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SymbolSpan:
    name: str
    start_line: int
    end_line: int
    references: frozenset[str]


def _referenced_names(node: ast.AST) -> frozenset[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return frozenset(names)


def _collect(node: ast.AST, prefix: str, out: list[SymbolSpan]) -> None:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = f"{prefix}{child.name}"
            end = child.end_lineno if child.end_lineno is not None else child.lineno
            out.append(SymbolSpan(name, child.lineno, end, _referenced_names(child)))
            _collect(child, f"{name}.", out)


def python_symbols(source: str) -> list[SymbolSpan]:
    """Return every top-level and nested function/class with its line span.

    A file that does not parse yields an empty list rather than raising, because
    an agent mid-edit routinely leaves files in a non-parsing state.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    spans: list[SymbolSpan] = []
    _collect(tree, "", spans)
    return spans


def resolve_symbol(source: str, name: str) -> Optional[SymbolSpan]:
    for span in python_symbols(source):
        if span.name == name:
            return span
    return None


def symbols_in_lines(source: str, start_line: int, end_line: int) -> list[SymbolSpan]:
    """Symbols whose span intersects the given 1-based inclusive line range."""
    return [s for s in python_symbols(source)
            if s.start_line <= end_line and start_line <= s.end_line]
