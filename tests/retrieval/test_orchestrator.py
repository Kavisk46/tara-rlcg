"""Unit tests for `tara.retrieval.orchestrator.RetrievalOrchestrator`.

Uses small, deterministic fake `Retriever` implementations (`_FakeRetriever`)
rather than the real Lexical/Dense/Graph retrievers -- the orchestrator's
job is pure execution mechanics (ordering, concurrency, error isolation),
which is independent of any specific retriever's internal logic. "lexical
only" / "dense only" / "graph only" are exercised by tagging each fake
retriever with the real `RetrieverKind` it stands in for, so the plan
shapes used in these tests are identical to what the real router would
actually produce.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Mapping

import networkx as nx
import pytest

from tara.context.models import NodeType, RepositoryContext, build_repository_node_id
from tara.context.symbol_index import SymbolIndex
from tara.core.exceptions import OrchestrationError, RetrievalError
from tara.core.types import RetrieverKind
from tara.interfaces.retriever import Retriever
from tara.retrieval.models import RetrievedContext
from tara.retrieval.orchestrator import RetrievalOrchestrator
from tara.routing.models import RetrievalPlan
from tara.routing.strategy import RoutingStrategy

ROOT_PATH = "/repo"


class _FakeRetriever(Retriever):
    """A minimal, controllable `Retriever` for orchestration tests.

    Not concerned with real retrieval logic at all: returns a fixed,
    empty `RetrievedContext` tagged with its own `kind`, optionally after
    sleeping `delay` seconds (to make concurrent-vs-sequential dispatch
    observable via wall-clock time) and/or raising `RetrievalError`
    (to test failure isolation).
    """

    def __init__(self, kind: RetrieverKind, delay: float = 0.0, raises: bool = False) -> None:
        self.kind = kind
        self.delay = delay
        self.raises = raises
        self.call_count = 0

    def retrieve(
        self, query: str, plan: RetrievalPlan, context: RepositoryContext
    ) -> RetrievedContext:
        self.call_count += 1
        if self.delay:
            time.sleep(self.delay)
        if self.raises:
            raise RetrievalError(f"{self.kind.value} retriever failed")
        return RetrievedContext(
            retriever_kind=self.kind, query=query, chunks=[], total_candidates=0
        )


class _BarrierRetriever(Retriever):
    """A `Retriever` that blocks on a shared `threading.Barrier` until every party arrives.

    Proves genuine concurrent dispatch deterministically, without relying
    on wall-clock timing thresholds (unreliable on a loaded/throttled
    environment -- confirmed via a standalone diagnostic during this
    milestone's implementation, where even a bare `ThreadPoolExecutor` +
    `time.sleep(0.1)` showed individual sleeps inflated up to 4x and
    total overhead inflated far beyond that). A `Barrier(n)` only
    releases once all `n` parties have called `.wait()`; if the
    orchestrator dispatched retrievers one at a time instead of
    concurrently, the first one would block until it times out, failing
    the test fast and unambiguously instead of via a flaky duration
    comparison.
    """

    def __init__(
        self, kind: RetrieverKind, barrier: threading.Barrier, timeout: float = 5.0
    ) -> None:
        self.kind = kind
        self._barrier = barrier
        self._timeout = timeout

    def retrieve(
        self, query: str, plan: RetrievalPlan, context: RepositoryContext
    ) -> RetrievedContext:
        self._barrier.wait(timeout=self._timeout)
        return RetrievedContext(
            retriever_kind=self.kind, query=query, chunks=[], total_candidates=0
        )


@pytest.fixture
def context() -> RepositoryContext:
    graph = nx.DiGraph()
    repo_id = build_repository_node_id(ROOT_PATH)
    graph.add_node(repo_id, type=NodeType.REPOSITORY.value, name=ROOT_PATH, file_path=None)
    return RepositoryContext(
        root_path=ROOT_PATH,
        graph=graph,
        symbol_index=SymbolIndex.from_graph(graph),
        file_count=0,
        symbol_count=0,
    )


def _make_plan(
    retrievers: list[RetrieverKind],
    execution_order: list[RetrieverKind] | None = None,
    parallel: bool = False,
) -> RetrievalPlan:
    return RetrievalPlan(
        strategy=RoutingStrategy.HYBRID,
        retrievers=retrievers,
        execution_order=execution_order if execution_order is not None else list(retrievers),
        parallel=parallel,
        rerank=False,
        top_k=10,
        candidate_limit=10,
        reason="test",
    )


def _orchestrator(*fakes: _FakeRetriever) -> RetrievalOrchestrator:
    mapping: Mapping[RetrieverKind, Retriever] = {fake.kind: fake for fake in fakes}
    return RetrievalOrchestrator(mapping)


# ============================================================================
# Single-retriever plans: lexical only / dense only / graph only
# ============================================================================


def test_lexical_only_plan_runs_only_lexical(context: RepositoryContext) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL)
    dense = _FakeRetriever(RetrieverKind.DENSE)
    orchestrator = _orchestrator(lexical, dense)
    plan = _make_plan([RetrieverKind.LEXICAL])

    results = orchestrator.execute("query", plan, context)

    assert [r.retriever_kind for r in results] == [RetrieverKind.LEXICAL]
    assert lexical.call_count == 1
    assert dense.call_count == 0


def test_dense_only_plan_runs_only_dense(context: RepositoryContext) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL)
    dense = _FakeRetriever(RetrieverKind.DENSE)
    orchestrator = _orchestrator(lexical, dense)
    plan = _make_plan([RetrieverKind.DENSE])

    results = orchestrator.execute("query", plan, context)

    assert [r.retriever_kind for r in results] == [RetrieverKind.DENSE]
    assert dense.call_count == 1
    assert lexical.call_count == 0


def test_graph_only_plan_runs_only_graph(context: RepositoryContext) -> None:
    graph_retriever = _FakeRetriever(RetrieverKind.GRAPH)
    lexical = _FakeRetriever(RetrieverKind.LEXICAL)
    orchestrator = _orchestrator(graph_retriever, lexical)
    plan = _make_plan([RetrieverKind.GRAPH])

    results = orchestrator.execute("query", plan, context)

    assert [r.retriever_kind for r in results] == [RetrieverKind.GRAPH]
    assert graph_retriever.call_count == 1
    assert lexical.call_count == 0


# ============================================================================
# Multi-retriever: sequential
# ============================================================================


def test_multi_retriever_sequential_runs_all_in_execution_order(context: RepositoryContext) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL)
    dense = _FakeRetriever(RetrieverKind.DENSE)
    graph_retriever = _FakeRetriever(RetrieverKind.GRAPH)
    orchestrator = _orchestrator(lexical, dense, graph_retriever)
    order = [RetrieverKind.GRAPH, RetrieverKind.LEXICAL, RetrieverKind.DENSE]
    plan = _make_plan(order, execution_order=order, parallel=False)

    results = orchestrator.execute("query", plan, context)

    assert [r.retriever_kind for r in results] == order
    assert lexical.call_count == dense.call_count == graph_retriever.call_count == 1


def test_multi_retriever_sequential_dispatch_is_not_concurrent(context: RepositoryContext) -> None:
    """The inverse of the parallel-dispatch proof below: a 2-party barrier must NOT
    release under sequential dispatch, since only one retriever ever runs at a time.
    Asserts the resulting timeout error, rather than depending on wall-clock duration.
    """
    # A short timeout suffices: the second party either arrives (sequential
    # dispatch is broken) or never arrives at all (correct) -- this is not a
    # question of how fast, so a generous-but-short bound is not flaky.
    barrier = threading.Barrier(2)
    kinds = (RetrieverKind.LEXICAL, RetrieverKind.DENSE)
    retrievers = [_BarrierRetriever(kind, barrier, timeout=0.5) for kind in kinds]
    orchestrator = _orchestrator(*retrievers)
    order = [r.kind for r in retrievers]
    plan = _make_plan(order, parallel=False)

    with pytest.raises(threading.BrokenBarrierError):
        orchestrator.execute("query", plan, context)


# ============================================================================
# Multi-retriever: parallel
# ============================================================================


def test_multi_retriever_parallel_runs_all_and_preserves_execution_order(
    context: RepositoryContext,
) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL, delay=0.02)
    dense = _FakeRetriever(RetrieverKind.DENSE, delay=0.02)
    graph_retriever = _FakeRetriever(RetrieverKind.GRAPH, delay=0.02)
    orchestrator = _orchestrator(lexical, dense, graph_retriever)
    order = [RetrieverKind.GRAPH, RetrieverKind.LEXICAL, RetrieverKind.DENSE]
    plan = _make_plan(order, execution_order=order, parallel=True)

    results = orchestrator.execute("query", plan, context)

    # Output order always matches execution_order, never real completion order.
    assert [r.retriever_kind for r in results] == order


def test_multi_retriever_parallel_dispatch_is_genuinely_concurrent(
    context: RepositoryContext,
) -> None:
    """All three retrievers must be simultaneously in flight for the barrier to release
    at all -- proof by construction, not by wall-clock duration (see `_BarrierRetriever`).
    """
    barrier = threading.Barrier(3)
    kinds = (RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH)
    retrievers = [_BarrierRetriever(kind, barrier) for kind in kinds]
    orchestrator = _orchestrator(*retrievers)
    order = [r.kind for r in retrievers]
    plan = _make_plan(order, parallel=True)

    results = orchestrator.execute("query", plan, context)

    assert {r.retriever_kind for r in results} == set(order)


def test_parallel_execution_output_is_deterministic_across_repeated_calls(
    context: RepositoryContext,
) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL, delay=0.01)
    dense = _FakeRetriever(RetrieverKind.DENSE, delay=0.03)
    graph_retriever = _FakeRetriever(RetrieverKind.GRAPH, delay=0.02)
    orchestrator = _orchestrator(lexical, dense, graph_retriever)
    order = [RetrieverKind.DENSE, RetrieverKind.GRAPH, RetrieverKind.LEXICAL]
    plan = _make_plan(order, execution_order=order, parallel=True)

    first = [r.retriever_kind for r in orchestrator.execute("query", plan, context)]
    second = [r.retriever_kind for r in orchestrator.execute("query", plan, context)]

    assert first == second == order


# ============================================================================
# Unavailable retriever
# ============================================================================


def test_unavailable_retriever_is_skipped_not_raised(context: RepositoryContext) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL)
    orchestrator = _orchestrator(lexical)  # DENSE never registered
    plan = _make_plan([RetrieverKind.LEXICAL, RetrieverKind.DENSE])

    results = orchestrator.execute("query", plan, context)

    assert [r.retriever_kind for r in results] == [RetrieverKind.LEXICAL]


def test_unavailable_retriever_logs_a_warning(
    context: RepositoryContext, caplog: pytest.LogCaptureFixture
) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL)
    orchestrator = _orchestrator(lexical)
    plan = _make_plan([RetrieverKind.LEXICAL, RetrieverKind.GRAPH])

    with caplog.at_level(logging.WARNING):
        orchestrator.execute("query", plan, context)

    assert any("graph" in record.message.lower() for record in caplog.records)


def test_unavailable_retriever_in_parallel_mode_is_also_skipped_cleanly(
    context: RepositoryContext,
) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL)
    orchestrator = _orchestrator(lexical)
    plan = _make_plan([RetrieverKind.LEXICAL, RetrieverKind.DENSE], parallel=True)

    results = orchestrator.execute("query", plan, context)

    assert [r.retriever_kind for r in results] == [RetrieverKind.LEXICAL]


def test_retriever_that_raises_is_skipped_not_propagated(context: RepositoryContext) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL)
    broken_dense = _FakeRetriever(RetrieverKind.DENSE, raises=True)
    orchestrator = _orchestrator(lexical, broken_dense)
    plan = _make_plan([RetrieverKind.LEXICAL, RetrieverKind.DENSE])

    results = orchestrator.execute("query", plan, context)

    assert [r.retriever_kind for r in results] == [RetrieverKind.LEXICAL]


def test_retriever_that_raises_in_parallel_mode_is_skipped_not_propagated(
    context: RepositoryContext,
) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL)
    broken_dense = _FakeRetriever(RetrieverKind.DENSE, raises=True)
    orchestrator = _orchestrator(lexical, broken_dense)
    plan = _make_plan([RetrieverKind.LEXICAL, RetrieverKind.DENSE], parallel=True)

    results = orchestrator.execute("query", plan, context)

    assert [r.retriever_kind for r in results] == [RetrieverKind.LEXICAL]


# ============================================================================
# Empty plan
# ============================================================================


def test_empty_plan_returns_empty_list(context: RepositoryContext) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL)
    orchestrator = _orchestrator(lexical)
    plan = _make_plan([], execution_order=[])

    results = orchestrator.execute("query", plan, context)

    assert results == []
    assert lexical.call_count == 0


def test_orchestrator_with_no_registered_retrievers_and_empty_plan_returns_empty_list(
    context: RepositoryContext,
) -> None:
    orchestrator = RetrievalOrchestrator({})
    plan = _make_plan([], execution_order=[])
    assert orchestrator.execute("query", plan, context) == []


# ============================================================================
# Invalid plan
# ============================================================================


def test_invalid_plan_with_mismatched_execution_order_raises(context: RepositoryContext) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL)
    dense = _FakeRetriever(RetrieverKind.DENSE)
    orchestrator = _orchestrator(lexical, dense)
    plan = _make_plan(
        [RetrieverKind.LEXICAL], execution_order=[RetrieverKind.LEXICAL, RetrieverKind.DENSE]
    )

    with pytest.raises(OrchestrationError):
        orchestrator.execute("query", plan, context)


def test_invalid_plan_does_not_execute_any_retriever(context: RepositoryContext) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL)
    dense = _FakeRetriever(RetrieverKind.DENSE)
    orchestrator = _orchestrator(lexical, dense)
    plan = _make_plan(
        [RetrieverKind.LEXICAL], execution_order=[RetrieverKind.LEXICAL, RetrieverKind.DENSE]
    )

    with pytest.raises(OrchestrationError):
        orchestrator.execute("query", plan, context)

    assert lexical.call_count == 0
    assert dense.call_count == 0


def test_invalid_plan_missing_a_declared_retriever_from_execution_order_raises(
    context: RepositoryContext,
) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL)
    dense = _FakeRetriever(RetrieverKind.DENSE)
    orchestrator = _orchestrator(lexical, dense)
    plan = _make_plan(
        [RetrieverKind.LEXICAL, RetrieverKind.DENSE], execution_order=[RetrieverKind.LEXICAL]
    )

    with pytest.raises(OrchestrationError):
        orchestrator.execute("query", plan, context)


def test_orchestration_error_is_a_retrieval_error() -> None:
    assert issubclass(OrchestrationError, RetrievalError)


# ============================================================================
# Retriever identity preservation
# ============================================================================


def test_each_result_reports_the_kind_that_produced_it(context: RepositoryContext) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL)
    dense = _FakeRetriever(RetrieverKind.DENSE)
    graph_retriever = _FakeRetriever(RetrieverKind.GRAPH)
    orchestrator = _orchestrator(lexical, dense, graph_retriever)
    order = [RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH]
    plan = _make_plan(order, parallel=True)

    results = orchestrator.execute("some query", plan, context)

    for result in results:
        assert result.query == "some query"
    assert {r.retriever_kind for r in results} == set(order)


# ============================================================================
# Plan is not mutated
# ============================================================================


def test_execute_does_not_mutate_the_plan(context: RepositoryContext) -> None:
    lexical = _FakeRetriever(RetrieverKind.LEXICAL)
    orchestrator = _orchestrator(lexical)
    plan = _make_plan([RetrieverKind.LEXICAL])
    snapshot = plan.model_copy(deep=True)

    orchestrator.execute("query", plan, context)

    assert plan == snapshot
