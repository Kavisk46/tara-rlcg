"""Efficiency metrics, per `EXPERIMENT_PLAN.md` §3.

Latency numbers themselves are *measured*, not computed, by
`evaluation.harness.runner.ExperimentRunner` (one `time.perf_counter()`
window per pipeline stage, per query, per variant) -- this module only
aggregates already-measured values (percentiles across a run) and
derives the small set of retrieval-cost proxies that follow mechanically
from a `RetrievalPlan`, rather than needing their own measurement.

**"Estimated retrieval cost" is not computed by default.** TARA's
default embedding model (`sentence-transformers`, local inference, per
`TaraSettings.embedding_model_name`) has no per-call dollar cost, and no
pricing table for any LLM provider exists anywhere in this project (no
real provider is even wired up yet, per M8) -- inventing a cost figure
without a real price would be exactly the "fabricate missing metrics"
this milestone's instructions prohibit. `estimate_cost` accepts an
optional, caller-supplied price table and returns `None` without one.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tara.core.types import RetrieverKind
from tara.routing.models import RetrievalPlan


def percentile(values: Sequence[float], p: float) -> float:
    """The `p`-th percentile of `values`, via the nearest-rank method.

    Args:
        values: Non-empty sequence of measurements (e.g. latencies in ms).
        p: Percentile in `[0, 100]`.

    Returns:
        `sorted(values)[ceil(p/100 * len(values)) - 1]`, clamped to a
        valid index -- a simple, deterministic, dependency-free
        percentile estimate. Not interpolated between ranks; for the
        p50/p95/p99 reporting granularity `EXPERIMENT_PLAN.md` §3 asks
        for, nearest-rank is standard and sufficient.

    Raises:
        ValueError: If `values` is empty or `p` is outside `[0, 100]`.
    """
    if not values:
        raise ValueError("values is empty -- cannot compute a percentile of nothing.")
    if not (0 <= p <= 100):
        raise ValueError(f"p must be in [0, 100], got {p!r}.")

    sorted_values = sorted(values)
    index = math.ceil(p / 100 * len(sorted_values)) - 1
    index = max(0, min(index, len(sorted_values) - 1))
    return sorted_values[index]


@dataclass(frozen=True)
class LatencyPercentiles:
    """p50/p95/p99 summary of a set of latency measurements, in milliseconds."""

    p50: float
    p95: float
    p99: float
    count: int


def summarize_latencies(values: Sequence[float]) -> LatencyPercentiles:
    """Compute `LatencyPercentiles` for `values`.

    Args:
        values: Non-empty sequence of latency measurements, in milliseconds.

    Returns:
        The p50/p95/p99 summary, plus `count` (`len(values)`) so a
        report can flag a percentile computed from very few samples as
        low-confidence rather than presenting it with false precision.

    Raises:
        ValueError: If `values` is empty.
    """
    return LatencyPercentiles(
        p50=percentile(values, 50),
        p95=percentile(values, 95),
        p99=percentile(values, 99),
        count=len(values),
    )


def retriever_invocation_count(plan: RetrievalPlan | None) -> int:
    """Number of retriever invocations a plan represents.

    Args:
        plan: The `RetrievalPlan` that was executed, or `None` for a
            no-retrieval variant (e.g. baseline B0).

    Returns:
        `len(plan.retrievers)`, or `0` if `plan` is `None`.
    """
    return len(plan.retrievers) if plan is not None else 0


def embedding_call_count(plan: RetrievalPlan | None) -> int:
    """Number of query-embedding calls a plan implies.

    Args:
        plan: The `RetrievalPlan` that was executed, or `None`.

    Returns:
        `1` if `RetrieverKind.DENSE` is in `plan.retrievers` (dense
        retrieval embeds the query exactly once per call; every
        symbol's own embedding is precomputed and stored on
        `RepositoryContext`, not recomputed per query), else `0`.
    """
    if plan is None:
        return 0
    return 1 if RetrieverKind.DENSE in plan.retrievers else 0


def estimate_cost(
    embedding_calls: int,
    generation_prompt_tokens: int,
    generation_completion_tokens: int,
    *,
    price_table: Mapping[str, float] | None = None,
) -> float | None:
    """Estimate a query's retrieval + generation dollar cost, if a price table is supplied.

    Args:
        embedding_calls: From `embedding_call_count`.
        generation_prompt_tokens: From `GeneratedCode.prompt_tokens`.
        generation_completion_tokens: From `GeneratedCode.completion_tokens`.
        price_table: Optional, caller-supplied prices, keyed
            `"embedding_call"`, `"prompt_token"`, `"completion_token"`
            (dollars per unit). Missing keys are treated as `0.0`.
            `None` (the default) means no real pricing is known.

    Returns:
        `None` if `price_table` is not supplied -- "not measurable,"
        not a fabricated `0.0`. Otherwise the linear cost estimate
        `embedding_calls * price_table.get("embedding_call", 0.0) + ...`.
    """
    if price_table is None:
        return None
    return (
        embedding_calls * price_table.get("embedding_call", 0.0)
        + generation_prompt_tokens * price_table.get("prompt_token", 0.0)
        + generation_completion_tokens * price_table.get("completion_token", 0.0)
    )
