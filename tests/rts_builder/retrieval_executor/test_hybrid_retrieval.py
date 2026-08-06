"""Unit tests for `evaluation.rts_builder.retrieval_executor.hybrid_retrieval.HybridRetriever`."""
from __future__ import annotations

import pytest

from evaluation.rts_builder.parser.models import RepositoryModel
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings
from evaluation.rts_builder.retrieval_executor.hybrid_retrieval import HybridRetriever
from evaluation.rts_builder.retrieval_executor.models import (
    RetrievalStrategyName,
    RetrievedFile,
    StrategyResult,
)


def _strategy_result(strategy_name: RetrievalStrategyName, scores: dict[str, float]) -> StrategyResult:
    retrieved_files = [RetrievedFile(file_path=path, score=score) for path, score in scores.items()]
    return StrategyResult(
        strategy_name=strategy_name, repository_id="repo", commit_sha="a" * 40, query_text="q",
        retrieved_files=retrieved_files, retrieval_score=max(scores.values(), default=0.0),
        retrieval_latency_ms=1.0, context_token_count=0,
    )


def test_hybrid_combines_scores_with_configured_weights(empty_repository_model: RepositoryModel) -> None:
    settings = RetrievalExecutorSettings(hybrid_lexical_weight=0.5, hybrid_dense_weight=0.25, hybrid_graph_weight=0.25)
    lexical = _strategy_result(RetrievalStrategyName.LEXICAL, {"a.py": 10.0, "b.py": 0.0})
    dense = _strategy_result(RetrievalStrategyName.DENSE, {"a.py": 1.0, "b.py": 1.0})
    graph = _strategy_result(RetrievalStrategyName.GRAPH, {"a.py": 0.0, "b.py": 0.0})

    result = HybridRetriever(settings=settings).combine(empty_repository_model, "q", lexical, dense, graph, top_k=10)

    by_path = {f.file_path: f.score for f in result.retrieved_files}
    # After min-max normalization: lexical a.py=1.0,b.py=0.0; dense a.py=1.0,b.py=1.0 (tie -> both 1.0); graph both 0.0 (all-equal).
    # a.py = 0.5*1.0 + 0.25*1.0 + 0.25*? ; graph all-equal maps every entry to 1.0 too (normalize_scores convention).
    assert result.strategy_name is RetrievalStrategyName.HYBRID
    assert by_path["a.py"] > by_path["b.py"]


def test_hybrid_includes_files_found_by_only_one_strategy(empty_repository_model: RepositoryModel) -> None:
    settings = RetrievalExecutorSettings()
    lexical = _strategy_result(RetrievalStrategyName.LEXICAL, {"only_lexical.py": 5.0})
    dense = _strategy_result(RetrievalStrategyName.DENSE, {})
    graph = _strategy_result(RetrievalStrategyName.GRAPH, {})

    result = HybridRetriever(settings=settings).combine(empty_repository_model, "q", lexical, dense, graph, top_k=10)

    assert any(f.file_path == "only_lexical.py" for f in result.retrieved_files)


def test_hybrid_with_all_empty_inputs_is_empty(empty_repository_model: RepositoryModel) -> None:
    empty = _strategy_result(RetrievalStrategyName.LEXICAL, {})
    result = HybridRetriever().combine(empty_repository_model, "q", empty, empty, empty, top_k=10)

    assert result.retrieved_files == []
    assert result.retrieval_score == 0.0


def test_hybrid_weights_must_sum_to_one() -> None:
    with pytest.raises(Exception):  # noqa: B017,PT011 - pydantic ValidationError, exact type asserted in test_config.py
        RetrievalExecutorSettings(hybrid_lexical_weight=0.9, hybrid_dense_weight=0.9, hybrid_graph_weight=0.9)


def test_hybrid_is_deterministic_across_repeated_calls(empty_repository_model: RepositoryModel) -> None:
    lexical = _strategy_result(RetrievalStrategyName.LEXICAL, {"a.py": 3.0, "b.py": 1.0})
    dense = _strategy_result(RetrievalStrategyName.DENSE, {"a.py": 0.5, "c.py": 0.9})
    graph = _strategy_result(RetrievalStrategyName.GRAPH, {"b.py": 1.0})

    retriever = HybridRetriever()
    first = retriever.combine(empty_repository_model, "q", lexical, dense, graph, top_k=10)
    second = retriever.combine(empty_repository_model, "q", lexical, dense, graph, top_k=10)

    assert first.retrieved_files == second.retrieved_files
