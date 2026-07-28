"""Unit tests for `tara.classification.heuristics`."""
from __future__ import annotations

import pytest

from tara.classification import heuristics as h
from tara.core.types import Language


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Find parse_repository", ["Find", "parse_repository"]),
        ("utils.py", ["utils.py"]),
        ("src/tara/parsing/repository_parser.py", ["src/tara/parsing/repository_parser.py"]),
        ("", []),
        ("   ", []),
        ("??? !!! ...", []),
    ],
)
def test_tokenize(text: str, expected: list[str]) -> None:
    assert h.tokenize(text) == expected


def test_is_stop_word() -> None:
    assert h.is_stop_word("the")
    assert h.is_stop_word("The")
    assert not h.is_stop_word("RepositoryParser")


@pytest.mark.parametrize(
    "token",
    ["RepositoryParser", "TreeSitterRepositoryParser", "GraphBuilder", "SentenceTransformerEmbedder", "SymbolIndex"],
)
def test_is_pascal_case_true(token: str) -> None:
    assert h.is_pascal_case(token)


@pytest.mark.parametrize("token", ["Find", "The", "Show", "Ok", "JWT", "API", "parser"])
def test_is_pascal_case_false(token: str) -> None:
    assert not h.is_pascal_case(token)


@pytest.mark.parametrize("token", ["parseRepository", "getUserById", "toString"])
def test_is_camel_case_true(token: str) -> None:
    assert h.is_camel_case(token)


@pytest.mark.parametrize("token", ["parse", "Parse", "parse_repository", "JWT"])
def test_is_camel_case_false(token: str) -> None:
    assert not h.is_camel_case(token)


@pytest.mark.parametrize("token", ["parse_repository", "max_file_size_bytes", "get_by_id"])
def test_is_snake_case_true(token: str) -> None:
    assert h.is_snake_case(token)


@pytest.mark.parametrize("token", ["parse", "ParseRepository", "MAX_SIZE"])
def test_is_snake_case_false(token: str) -> None:
    assert not h.is_snake_case(token)


@pytest.mark.parametrize("token", ["MAX_FILE_SIZE_BYTES", "API_KEY"])
def test_is_constant_case_true(token: str) -> None:
    assert h.is_constant_case(token)


@pytest.mark.parametrize("token", ["JWT", "MaxSize", "max_size"])
def test_is_constant_case_false(token: str) -> None:
    assert not h.is_constant_case(token)


@pytest.mark.parametrize("token", ["JWT", "API", "SQL", "CVE", "OK"])
def test_is_acronym_true(token: str) -> None:
    assert h.is_acronym(token)


@pytest.mark.parametrize("token", ["I", "RepositoryParser", "parse", "MAX_SIZE"])
def test_is_acronym_false(token: str) -> None:
    assert not h.is_acronym(token)


def test_looks_like_identifier_covers_every_convention() -> None:
    assert h.looks_like_identifier("RepositoryParser")
    assert h.looks_like_identifier("parseRepository")
    assert h.looks_like_identifier("parse_repository")
    assert h.looks_like_identifier("MAX_SIZE")
    assert h.looks_like_identifier("JWT")
    assert not h.looks_like_identifier("the")
    assert not h.looks_like_identifier("Find")


def test_extract_quoted_handles_multiple_quote_styles() -> None:
    text = """What is "get user by id" and 'SymbolIndex' and `GraphBuilder`?"""
    assert h.extract_quoted(text) == ["get user by id", "SymbolIndex", "GraphBuilder"]


def test_extract_quoted_returns_empty_list_when_none_present() -> None:
    assert h.extract_quoted("no quotes here") == []


@pytest.mark.parametrize(
    "token", ["utils.py", "repository_parser.py", "src/tara/parsing/repository_parser.py", "README.md"]
)
def test_looks_like_file_path_true(token: str) -> None:
    assert h.looks_like_file_path(token)


@pytest.mark.parametrize("token", ["parse_repository", "RepositoryParser", "GraphBuilder"])
def test_looks_like_file_path_false(token: str) -> None:
    assert not h.looks_like_file_path(token)


def test_extract_extension() -> None:
    assert h.extract_extension("utils.py") == "py"
    assert h.extract_extension("README.md") == "md"
    assert h.extract_extension("parse_repository") is None
    assert h.extract_extension("archive.zip") is None  # not a known source/config extension


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        (["How", "do", "I", "write", "this", "in", "Python"], Language.PYTHON),
        (["convert", "to", "TypeScript"], Language.TYPESCRIPT),
        (["a", "Rust", "implementation"], Language.RUST),
        (["golang", "goroutines"], Language.GO),
        (["no", "language", "here"], None),
    ],
)
def test_detect_language(tokens: list[str], expected: Language | None) -> None:
    assert h.detect_language(tokens) == expected


def test_detect_language_returns_first_match_only() -> None:
    assert h.detect_language(["python", "go"]) == Language.PYTHON


@pytest.mark.parametrize(
    "token_set",
    [
        frozenset({"what", "does", "repositoryparser", "do"}),
        frozenset({"how", "does", "the", "parser", "work"}),
        frozenset({"what", "is", "graphbuilder"}),
    ],
)
def test_looks_like_explain_question_true(token_set: frozenset[str]) -> None:
    assert h.looks_like_explain_question(token_set)


def test_looks_like_explain_question_false() -> None:
    assert not h.looks_like_explain_question(frozenset({"find", "parse_repository"}))
