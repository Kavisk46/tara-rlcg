"""Unit tests for `LexicalRetriever`'s exact symbol/file lookup methods.

Scope: `find_symbol`, `find_function`, `find_class`, `find_method`,
`find_file`, `find_path`. Ranked keyword search is covered separately in
`test_lexical.py`.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo

from tara.context.graph_builder import GraphBuilder
from tara.context.models import NodeType, RepositoryContext
from tara.context.symbol_index import SymbolIndexBuilder
from tara.parsing.repository_parser import TreeSitterRepositoryParser
from tara.retrieval.lexical_retriever import LexicalRetriever
from tara.retrieval.models import MatchedField
from tara.retrieval.ranking import RankingEngine


@pytest.fixture
def retriever() -> LexicalRetriever:
    return LexicalRetriever(RankingEngine())


def _init_repo(repo_path: Path) -> Repo:
    repo_path.mkdir()
    repo = Repo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "TARA Test Suite")
        config.set_value("user", "email", "tara-tests@example.com")
    return repo


def _build_context(repo_path: Path) -> RepositoryContext:
    parsed = TreeSitterRepositoryParser().parse(repo_path)
    graph = GraphBuilder().build(parsed)
    symbol_index = SymbolIndexBuilder().build(graph)
    return RepositoryContext(
        root_path=str(repo_path),
        commit_sha=parsed.commit_sha,
        graph=graph,
        symbol_index=symbol_index,
        file_count=len(parsed.files),
        symbol_count=sum(len(f.symbols) for f in parsed.files),
    )


@pytest.fixture(scope="module")
def duplicate_name_context(tmp_path_factory: pytest.TempPathFactory) -> RepositoryContext:
    """A repository with the same function name defined in two different files."""
    repo_path = tmp_path_factory.mktemp("duplicate_name_repo") / "repo"
    repo = _init_repo(repo_path)

    (repo_path / "module_a.py").write_text(
        "def handler(event: dict) -> None:\n    pass\n", encoding="utf-8"
    )
    (repo_path / "module_b.py").write_text(
        "def handler(event: dict) -> None:\n    pass\n", encoding="utf-8"
    )
    repo.index.add(["module_a.py", "module_b.py"])
    repo.index.commit("init")
    return _build_context(repo_path)


@pytest.fixture(scope="module")
def duplicate_basename_context(tmp_path_factory: pytest.TempPathFactory) -> RepositoryContext:
    """A repository with two files sharing a basename in different directories."""
    repo_path = tmp_path_factory.mktemp("duplicate_basename_repo") / "repo"
    repo = _init_repo(repo_path)

    (repo_path / "utils.py").write_text("def top_level_util() -> None:\n    pass\n", encoding="utf-8")
    sub_dir = repo_path / "sub"
    sub_dir.mkdir()
    (sub_dir / "utils.py").write_text("def nested_util() -> None:\n    pass\n", encoding="utf-8")

    repo.index.add(["utils.py", "sub/utils.py"])
    repo.index.commit("init")
    return _build_context(repo_path)


# ============================================================================
# find_symbol -- matches any symbol type
# ============================================================================


def test_find_symbol_matches_a_function(retriever: LexicalRetriever, retrieval_context: RepositoryContext) -> None:
    results = retriever.find_symbol("main", retrieval_context)
    assert len(results) == 1
    assert results[0].node_type is NodeType.FUNCTION


def test_find_symbol_matches_a_class(retriever: LexicalRetriever, retrieval_context: RepositoryContext) -> None:
    results = retriever.find_symbol("Greeter", retrieval_context)
    assert len(results) == 1
    assert results[0].node_type is NodeType.CLASS


def test_find_symbol_matches_a_method(retriever: LexicalRetriever, retrieval_context: RepositoryContext) -> None:
    results = retriever.find_symbol("greet", retrieval_context)
    assert len(results) == 1
    assert results[0].node_type is NodeType.METHOD


def test_find_symbol_unknown_name_returns_empty(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    assert retriever.find_symbol("does_not_exist_xyz", retrieval_context) == []


def test_find_symbol_result_has_exact_match_score(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    result = retriever.find_symbol("main", retrieval_context)[0]
    assert result.score.raw_score == pytest.approx(1.0)
    assert result.score.normalized_score == pytest.approx(1.0)
    assert result.matched_field == MatchedField.NAME
    assert result.score.matched_terms == ("main",)


def test_find_symbol_returns_every_match_for_a_name_defined_in_multiple_files(
    retriever: LexicalRetriever, duplicate_name_context: RepositoryContext
) -> None:
    results = retriever.find_symbol("handler", duplicate_name_context)
    assert len(results) == 2
    assert {r.file_path for r in results} == {"module_a.py", "module_b.py"}


# ============================================================================
# find_function -- type-filtered exact lookup
# ============================================================================


def test_find_function_matches_a_top_level_function(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    results = retriever.find_function("parse_repository", retrieval_context)
    assert len(results) == 1
    assert results[0].node_type is NodeType.FUNCTION
    assert results[0].name == "parse_repository"


def test_find_function_does_not_match_a_class(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    assert retriever.find_function("Greeter", retrieval_context) == []


def test_find_function_does_not_match_a_method(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    assert retriever.find_function("greet", retrieval_context) == []


def test_find_function_unknown_name_returns_empty(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    assert retriever.find_function("does_not_exist_xyz", retrieval_context) == []


# ============================================================================
# find_class -- type-filtered exact lookup
# ============================================================================


def test_find_class_matches_a_class(retriever: LexicalRetriever, retrieval_context: RepositoryContext) -> None:
    results = retriever.find_class("Greeter", retrieval_context)
    assert len(results) == 1
    assert results[0].node_type is NodeType.CLASS


def test_find_class_does_not_match_a_function(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    assert retriever.find_class("main", retrieval_context) == []


def test_find_class_does_not_match_a_method(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    assert retriever.find_class("greet", retrieval_context) == []


def test_find_class_unknown_name_returns_empty(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    assert retriever.find_class("does_not_exist_xyz", retrieval_context) == []


# ============================================================================
# find_method -- type-filtered exact lookup
# ============================================================================


def test_find_method_matches_a_method(retriever: LexicalRetriever, retrieval_context: RepositoryContext) -> None:
    results = retriever.find_method("greet", retrieval_context)
    assert len(results) == 1
    assert results[0].node_type is NodeType.METHOD


def test_find_method_does_not_match_a_top_level_function(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    assert retriever.find_method("parse_repository", retrieval_context) == []
    assert retriever.find_method("main", retrieval_context) == []


def test_find_method_does_not_match_a_class(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    assert retriever.find_method("Greeter", retrieval_context) == []


def test_find_method_unknown_name_returns_empty(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    assert retriever.find_method("does_not_exist_xyz", retrieval_context) == []


# ============================================================================
# find_file -- basename lookup
# ============================================================================


def test_find_file_matches_by_basename(retriever: LexicalRetriever, retrieval_context: RepositoryContext) -> None:
    results = retriever.find_file("utils.py", retrieval_context)
    assert len(results) == 1
    assert results[0].node_type is NodeType.FILE
    assert results[0].file_path == "utils.py"


def test_find_file_unknown_name_returns_empty(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    assert retriever.find_file("does_not_exist.py", retrieval_context) == []


def test_find_file_returns_every_file_sharing_a_basename(
    retriever: LexicalRetriever, duplicate_basename_context: RepositoryContext
) -> None:
    results = retriever.find_file("utils.py", duplicate_basename_context)
    assert len(results) == 2
    assert {r.file_path for r in results} == {"utils.py", "sub/utils.py"}


def test_find_file_result_has_exact_match_score(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    result = retriever.find_file("utils.py", retrieval_context)[0]
    assert result.score.raw_score == pytest.approx(1.0)
    assert result.matched_field == MatchedField.PATH


# ============================================================================
# find_path -- full repository-relative path lookup
# ============================================================================


def test_find_path_matches_full_relative_path(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    results = retriever.find_path("utils.py", retrieval_context)
    assert len(results) == 1
    assert results[0].file_path == "utils.py"


def test_find_path_matches_a_nested_file_by_its_full_path(
    retriever: LexicalRetriever, duplicate_basename_context: RepositoryContext
) -> None:
    results = retriever.find_path("sub/utils.py", duplicate_basename_context)
    assert len(results) == 1
    assert results[0].file_path == "sub/utils.py"


def test_find_path_disambiguates_files_sharing_a_basename(
    retriever: LexicalRetriever, duplicate_basename_context: RepositoryContext
) -> None:
    top_level = retriever.find_path("utils.py", duplicate_basename_context)
    nested = retriever.find_path("sub/utils.py", duplicate_basename_context)

    assert len(top_level) == 1 and len(nested) == 1
    assert top_level[0].file_path != nested[0].file_path


def test_find_path_unknown_path_returns_empty(
    retriever: LexicalRetriever, retrieval_context: RepositoryContext
) -> None:
    assert retriever.find_path("does/not/exist.py", retrieval_context) == []


def test_find_path_does_not_match_on_basename_alone_for_a_nested_file(
    retriever: LexicalRetriever, duplicate_basename_context: RepositoryContext
) -> None:
    """`find_path` requires the *full* path; a bare basename must not match a nested file."""
    results = retriever.find_path("utils.py", duplicate_basename_context)
    assert all(r.file_path == "utils.py" for r in results)
    assert not any(r.file_path == "sub/utils.py" for r in results)


# ============================================================================
# Empty repository
# ============================================================================


def test_all_exact_lookups_on_empty_repository_return_empty(
    retriever: LexicalRetriever, empty_context: RepositoryContext
) -> None:
    assert retriever.find_symbol("anything", empty_context) == []
    assert retriever.find_function("anything", empty_context) == []
    assert retriever.find_class("anything", empty_context) == []
    assert retriever.find_method("anything", empty_context) == []
    assert retriever.find_file("anything.py", empty_context) == []
    assert retriever.find_path("anything.py", empty_context) == []
