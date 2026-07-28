"""Unit tests for `tara.routing.strategy`."""
from __future__ import annotations

from tara.core.types import RetrieverKind
from tara.routing.strategy import RETRIEVER_EXECUTION_PRIORITY, STRATEGY_RETRIEVERS, RoutingStrategy


def test_seven_routing_strategies_defined() -> None:
    assert len(list(RoutingStrategy)) == 7


def test_every_routing_strategy_has_a_retriever_mapping() -> None:
    assert set(STRATEGY_RETRIEVERS) == set(RoutingStrategy)


def test_strategy_retriever_mappings_are_non_empty_and_unique() -> None:
    for retrievers in STRATEGY_RETRIEVERS.values():
        assert len(retrievers) > 0
        assert len(retrievers) == len(set(retrievers))


def test_full_pipeline_includes_all_three_core_retrievers() -> None:
    retrievers = set(STRATEGY_RETRIEVERS[RoutingStrategy.FULL_PIPELINE])
    assert retrievers == {RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH}


def test_hybrid_excludes_graph() -> None:
    assert RetrieverKind.GRAPH not in STRATEGY_RETRIEVERS[RoutingStrategy.HYBRID]


def test_retriever_execution_priority_covers_every_retriever_kind() -> None:
    assert set(RETRIEVER_EXECUTION_PRIORITY) == set(RetrieverKind)


def test_retriever_execution_priority_puts_lexical_before_dense() -> None:
    assert RETRIEVER_EXECUTION_PRIORITY.index(RetrieverKind.LEXICAL) < RETRIEVER_EXECUTION_PRIORITY.index(
        RetrieverKind.DENSE
    )
