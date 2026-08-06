"""Shared ranking, token-estimation, and result-assembly helpers used by every strategy.

Centralizing these guarantees all four strategies rank ties the same
way (deterministic execution) and assemble their `StrategyResult` the
same way (`retrieval_score` and `context_token_count` always mean the
same thing regardless of which strategy computed them).
"""
from __future__ import annotations

import time
from collections.abc import Mapping

from evaluation.rts_builder.parser.models import RepositoryModel
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings
from evaluation.rts_builder.retrieval_executor.models import RetrievalStrategyName, RetrievedFile, StrategyResult


def rank_scores(scores: Mapping[str, float], top_k: int) -> list[RetrievedFile]:
    """Rank `{file_path: score}` into the top `top_k` `RetrievedFile`s.

    Ties are broken by `file_path` ascending -- required for
    deterministic execution: `dict`/`set` iteration order is not itself
    guaranteed to be stable input to input (e.g. across two dicts built
    by different code paths with the same logical content), so relying
    on insertion order alone would not guarantee the same ranking on
    every run.

    Args:
        scores: `file_path -> raw or normalized score`. Files with a
            zero score are still included (ranked last, unless other
            zero-score files sort after them alphabetically).
        top_k: Maximum number of files to return.

    Returns:
        Up to `top_k` `RetrievedFile`s, highest score first.
    """
    ordered = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
    return [RetrievedFile(file_path=file_path, score=score) for file_path, score in ordered[:top_k]]


def estimate_context_tokens(
    model: RepositoryModel, retrieved_files: list[RetrievedFile], chars_per_token_estimate: float
) -> int:
    """Estimate the LLM context-token cost of including every retrieved file's content.

    Args:
        model: Used to look up each retrieved file's `size_bytes`.
        retrieved_files: The files to estimate the combined cost of.
        chars_per_token_estimate: Characters-per-token ratio (see
            `RetrievalExecutorSettings.chars_per_token_estimate`).

    Returns:
        `round(total_size_bytes / chars_per_token_estimate)`, `0` if
        `retrieved_files` is empty.
    """
    size_by_path = {normalized_file.path: normalized_file.size_bytes for normalized_file in model.files}
    total_bytes = sum(size_by_path.get(retrieved.file_path, 0) for retrieved in retrieved_files)
    return round(total_bytes / chars_per_token_estimate)


def build_strategy_result(
    strategy_name: RetrievalStrategyName,
    model: RepositoryModel,
    query_text: str,
    retrieved_files: list[RetrievedFile],
    latency_ms: float,
    settings: RetrievalExecutorSettings,
) -> StrategyResult:
    """Assemble a `StrategyResult` from a strategy's ranked output and measured latency."""
    retrieval_score = max((retrieved.score for retrieved in retrieved_files), default=0.0)
    context_token_count = estimate_context_tokens(model, retrieved_files, settings.chars_per_token_estimate)
    return StrategyResult(
        strategy_name=strategy_name,
        repository_id=model.repository_id,
        commit_sha=model.commit_sha,
        query_text=query_text,
        retrieved_files=retrieved_files,
        retrieval_score=retrieval_score,
        retrieval_latency_ms=latency_ms,
        context_token_count=context_token_count,
    )


def elapsed_ms(start: float) -> float:
    """Return milliseconds elapsed since `start` (a `time.perf_counter()` reading)."""
    return (time.perf_counter() - start) * 1000.0


class LatencyAccumulator:
    """Sums elapsed time across one or more possibly-discontiguous "included" spans.

    Exists because the frozen latency protocol (`latency_protocol.py`)
    requires *excluding* index-construction time even though, in this
    milestone's current (uncached) architecture, index construction
    happens inside the same `retrieve()` call as the included work --
    see README.md's "Design Rationale: Revision 2". A single contiguous
    `time.perf_counter()` span cannot skip over a excluded step in the
    middle; this accumulator can, by calling `start()`/`stop()` around
    only the included sub-steps and leaving excluded code in between
    untimed.

    Usage::

        timer = LatencyAccumulator()
        timer.start()
        ...included work...
        timer.stop()
        ...excluded work (e.g. index construction)...
        timer.start()
        ...more included work...
        timer.stop()
        latency_ms = timer.total_ms
    """

    def __init__(self) -> None:
        """Construct an accumulator with zero elapsed time."""
        self._total_seconds = 0.0
        self._span_start: float | None = None

    def start(self) -> None:
        """Begin timing an included span.

        Raises:
            RuntimeError: If a span is already open (`start()` called
                twice without an intervening `stop()`).
        """
        if self._span_start is not None:
            raise RuntimeError("LatencyAccumulator.start() called while a span is already open.")
        self._span_start = time.perf_counter()

    def stop(self) -> None:
        """End the current included span, adding its duration to the running total.

        Raises:
            RuntimeError: If no span is open (`stop()` called without a
                matching `start()`).
        """
        if self._span_start is None:
            raise RuntimeError("LatencyAccumulator.stop() called without a matching start().")
        self._total_seconds += time.perf_counter() - self._span_start
        self._span_start = None

    @property
    def total_ms(self) -> float:
        """Total elapsed time across every completed span, in milliseconds."""
        return self._total_seconds * 1000.0
