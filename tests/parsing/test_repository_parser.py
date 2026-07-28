"""Unit tests for `TreeSitterRepositoryParser`."""
from __future__ import annotations

from pathlib import Path

import pytest

from tara.core.exceptions import RepositoryParsingError
from tara.core.types import Language
from tara.parsing.models import SymbolKind
from tara.parsing.repository_parser import TreeSitterRepositoryParser


def test_parse_raises_for_missing_path(tmp_path: Path) -> None:
    parser = TreeSitterRepositoryParser()
    with pytest.raises(RepositoryParsingError):
        parser.parse(tmp_path / "does-not-exist")


def test_parse_discovers_python_files(sample_repository: Path) -> None:
    parser = TreeSitterRepositoryParser()
    result = parser.parse(sample_repository)

    parsed_paths = {f.path for f in result.files}
    assert parsed_paths == {"app.py", "utils.py"}
    assert result.errors == []


def test_parse_records_commit_sha(sample_repository: Path) -> None:
    parser = TreeSitterRepositoryParser()
    result = parser.parse(sample_repository)

    assert result.commit_sha is not None
    assert len(result.commit_sha) == 40


def test_parse_extracts_class_and_function_symbols(sample_repository: Path) -> None:
    parser = TreeSitterRepositoryParser()
    result = parser.parse(sample_repository)

    app_file = result.get_file("app.py")
    assert app_file is not None
    assert app_file.language is Language.PYTHON

    symbol_names = {(s.name, s.kind) for s in app_file.symbols}
    assert ("Greeter", SymbolKind.CLASS) in symbol_names
    assert ("greet", SymbolKind.FUNCTION) in symbol_names
    assert ("main", SymbolKind.FUNCTION) in symbol_names

    greet_symbol = next(s for s in app_file.symbols if s.name == "greet")
    assert greet_symbol.parent == "Greeter"


def test_parse_extracts_imports(sample_repository: Path) -> None:
    parser = TreeSitterRepositoryParser()
    result = parser.parse(sample_repository)

    app_file = result.get_file("app.py")
    assert app_file is not None
    assert len(app_file.imports) == 2
    assert all(not imp.is_relative for imp in app_file.imports)


def test_parse_extracts_docstrings(sample_repository: Path) -> None:
    parser = TreeSitterRepositoryParser()
    result = parser.parse(sample_repository)

    app_file = result.get_file("app.py")
    assert app_file is not None
    greeter_symbol = next(s for s in app_file.symbols if s.name == "Greeter")
    assert greeter_symbol.docstring == "Greets users by name."


def test_parse_skips_non_source_files(sample_repository: Path) -> None:
    parser = TreeSitterRepositoryParser()
    result = parser.parse(sample_repository)

    assert result.get_file("README.md") is None


def test_parse_utils_file_has_no_class_symbols(sample_repository: Path) -> None:
    parser = TreeSitterRepositoryParser()
    result = parser.parse(sample_repository)

    utils_file = result.get_file("utils.py")
    assert utils_file is not None
    assert len(utils_file.symbols) == 1
    assert utils_file.symbols[0].name == "add"
    assert utils_file.symbols[0].kind is SymbolKind.FUNCTION
