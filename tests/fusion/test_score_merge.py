"""Unit tests for `tara.fusion.score_merge.ScoreMerger`.

Covers the weighted-average baseline PROJECT_SPEC.md §20.2 specifies
should be implemented and used ahead of any cross-encoder.
"""
from __future__ import annotations

import pytest

from tara.core.exceptions import ContextFusionError
from tara.core.types import RetrieverKind
from tara.fusion.score_merge import ScoreMerger


def test_merge_single_source_returns_that_source_score() -> None:
    merger = ScoreMerger()
    assert merger.merge({"lexical": 0.7}) == pytest.approx(0.7)


def test_merge_two_equally_weighted_sources_averages_them() -> None:
    merger = ScoreMerger()
    result = merger.merge({"lexical": 0.4, "dense": 0.8})
    assert result == pytest.approx(0.6)


def test_merge_is_an_average_not_a_sum() -> None:
    # A candidate found by two retrievers is not automatically scored higher purely
    # for being found more often -- the merge stays within the range of its inputs.
    merger = ScoreMerger()
    result = merger.merge({"lexical": 0.5, "dense": 0.5})
    assert result == pytest.approx(0.5)
    assert result <= 1.0


def test_merge_respects_configured_weights() -> None:
    merger = ScoreMerger(retriever_weights={"lexical": 3.0, "dense": 1.0})
    result = merger.merge({"lexical": 1.0, "dense": 0.0})
    # weighted average: (3.0*1.0 + 1.0*0.0) / (3.0 + 1.0) == 0.75
    assert result == pytest.approx(0.75)


def test_merge_unweighted_source_defaults_to_weight_one() -> None:
    merger = ScoreMerger(retriever_weights={"lexical": 3.0})
    result = merger.merge({"lexical": 1.0, "dense": 1.0})
    # dense defaults to weight 1.0: (3.0*1.0 + 1.0*1.0) / (3.0 + 1.0) == 1.0
    assert result == pytest.approx(1.0)


def test_merge_all_weights_zero_returns_zero_without_dividing_by_zero() -> None:
    merger = ScoreMerger(retriever_weights={"lexical": 0.0, "dense": 0.0})
    assert merger.merge({"lexical": 0.9, "dense": 0.9}) == 0.0


def test_merge_empty_source_scores_raises() -> None:
    with pytest.raises(ContextFusionError):
        ScoreMerger().merge({})


def test_merge_three_sources_weighted_average() -> None:
    merger = ScoreMerger()
    result = merger.merge({"lexical": 0.3, "dense": 0.6, "graph": 0.9})
    assert result == pytest.approx(0.6)


def test_merge_is_deterministic_across_repeated_calls() -> None:
    merger = ScoreMerger(retriever_weights={"lexical": 2.0})
    scores = {RetrieverKind.LEXICAL.value: 0.3, RetrieverKind.DENSE.value: 0.7}
    assert merger.merge(scores) == merger.merge(scores)
