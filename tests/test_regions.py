import textwrap
from coedit.regions import python_symbols, resolve_symbol, SymbolSpan

SRC = textwrap.dedent('''
    import os

    def alpha(x):
        return x + 1

    class Beta:
        def method(self):
            return alpha(2)

    def gamma():
        return Beta().method()
''')


def test_python_symbols_lists_functions_and_classes_with_lines():
    spans = python_symbols(SRC)
    names = {s.name for s in spans}
    assert {"alpha", "Beta", "Beta.method", "gamma"} <= names
    alpha = next(s for s in spans if s.name == "alpha")
    assert alpha.start_line == 4 and alpha.end_line == 5


def test_resolve_symbol_returns_span_or_none():
    assert resolve_symbol(SRC, "gamma") is not None
    assert resolve_symbol(SRC, "nope") is None


def test_symbol_references_found():
    spans = python_symbols(SRC)
    gamma = next(s for s in spans if s.name == "gamma")
    assert "Beta" in gamma.references


def test_python_symbols_on_syntax_error_returns_empty():
    assert python_symbols("def broken(:\n") == []
