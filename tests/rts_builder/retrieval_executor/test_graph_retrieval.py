"""Unit tests for `evaluation.rts_builder.retrieval_executor.graph_retrieval.GraphRetriever`."""
from __future__ import annotations

import pytest

from evaluation.rts_builder.parser.models import ImportEdge, NormalizedFile, NormalizedFunction, RepositoryModel
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings
from evaluation.rts_builder.retrieval_executor.graph_retrieval import GraphRetriever
from evaluation.rts_builder.retrieval_executor.models import RetrievalStrategyName


def _chain_repository_model() -> RepositoryModel:
    """Three files, chained a.py -> b.py -> c.py by import edges, for hop-limit testing."""
    files = [
        NormalizedFile(path=name, size_bytes=100, content_hash=f"hash-{name}", module_docstring=None, function_count=1, class_count=0, import_count=1)
        for name in ("a.py", "b.py", "c.py")
    ]
    functions = [
        NormalizedFunction(
            symbol_id=f"{name}::seed_target::1", name="seed_target", qualified_name="seed_target",
            file_path=name, is_method=False, parent_class=None, is_async=False, decorators=[],
            docstring=None, start_line=1, end_line=1,
        )
        for name in ("a.py",)
    ]
    return RepositoryModel(
        repository_id="chain-repo", commit_sha="a" * 40, root_path="/does-not-matter",
        files=files, functions=functions, classes=[], imports=[],
        import_graph=[
            ImportEdge(source_file="a.py", target_file="b.py", line=1),
            ImportEdge(source_file="b.py", target_file="c.py", line=1),
        ],
        call_graph=[], inheritance_graph=[], parse_errors=[],
    )


def test_seed_file_itself_scores_highest(
    retrieval_settings: RetrievalExecutorSettings, sample_repository_model: RepositoryModel
) -> None:
    retriever = GraphRetriever(settings=retrieval_settings)
    result = retriever.retrieve(sample_repository_model, "Dog", top_k=10)

    assert result.strategy_name is RetrievalStrategyName.GRAPH
    assert result.retrieved_files[0].file_path == "app.py"
    assert result.retrieved_files[0].score == 1.0


def test_one_hop_neighbor_scores_lower_than_the_seed(
    retrieval_settings: RetrievalExecutorSettings, sample_repository_model: RepositoryModel
) -> None:
    retriever = GraphRetriever(settings=retrieval_settings)
    result = retriever.retrieve(sample_repository_model, "Dog", top_k=10)

    by_path = {f.file_path: f.score for f in result.retrieved_files}
    # Dog(Animal) is an inheritance edge to pkg/base.py -- one hop from the seed.
    assert "pkg/base.py" in by_path
    assert by_path["pkg/base.py"] < by_path["app.py"]
    assert by_path["pkg/base.py"] == 0.5


def test_max_graph_hops_bounds_expansion() -> None:
    model = _chain_repository_model()

    unbounded = GraphRetriever(settings=RetrievalExecutorSettings(max_graph_hops=2)).retrieve(
        model, "seed_target", top_k=10
    )
    bounded = GraphRetriever(settings=RetrievalExecutorSettings(max_graph_hops=1)).retrieve(
        model, "seed_target", top_k=10
    )

    unbounded_paths = {f.file_path for f in unbounded.retrieved_files}
    bounded_paths = {f.file_path for f in bounded.retrieved_files}

    # a.py (seed, hop 0) -> b.py (hop 1) -> c.py (hop 2).
    assert unbounded_paths == {"a.py", "b.py", "c.py"}
    assert bounded_paths == {"a.py", "b.py"}
    assert "c.py" not in bounded_paths

    unbounded_scores = {f.file_path: f.score for f in unbounded.retrieved_files}
    assert unbounded_scores["a.py"] == 1.0
    assert unbounded_scores["b.py"] == 0.5
    assert unbounded_scores["c.py"] == pytest.approx(1 / 3)


def test_query_naming_no_symbol_yields_empty_result(
    retrieval_settings: RetrievalExecutorSettings, sample_repository_model: RepositoryModel
) -> None:
    retriever = GraphRetriever(settings=retrieval_settings)
    result = retriever.retrieve(sample_repository_model, "NoSuchSymbolAnywhere", top_k=10)

    assert result.retrieved_files == []
    assert result.retrieval_score == 0.0


def test_empty_query_yields_empty_result(
    retrieval_settings: RetrievalExecutorSettings, sample_repository_model: RepositoryModel
) -> None:
    retriever = GraphRetriever(settings=retrieval_settings)
    result = retriever.retrieve(sample_repository_model, "", top_k=10)

    assert result.retrieved_files == []


def test_empty_repository_yields_empty_result(
    retrieval_settings: RetrievalExecutorSettings, empty_repository_model: RepositoryModel
) -> None:
    retriever = GraphRetriever(settings=retrieval_settings)
    result = retriever.retrieve(empty_repository_model, "Dog", top_k=10)

    assert result.retrieved_files == []


def test_result_is_deterministic_across_repeated_calls(
    retrieval_settings: RetrievalExecutorSettings, sample_repository_model: RepositoryModel
) -> None:
    retriever = GraphRetriever(settings=retrieval_settings)
    first = retriever.retrieve(sample_repository_model, "Dog", top_k=10)
    second = retriever.retrieve(sample_repository_model, "Dog", top_k=10)

    assert first.retrieved_files == second.retrieved_files
