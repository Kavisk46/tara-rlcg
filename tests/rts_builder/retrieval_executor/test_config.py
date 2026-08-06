"""Unit tests for `evaluation.rts_builder.retrieval_executor.config.RetrievalExecutorSettings`."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings


def test_default_settings_construct_without_error() -> None:
    settings = RetrievalExecutorSettings()
    assert settings.top_k > 0


def test_lexical_weights_must_sum_to_one() -> None:
    with pytest.raises(ValidationError):
        RetrievalExecutorSettings(
            lexical_bm25_weight=0.5, lexical_identifier_weight=0.5, lexical_keyword_overlap_weight=0.5
        )


def test_hybrid_weights_must_sum_to_one() -> None:
    with pytest.raises(ValidationError):
        RetrievalExecutorSettings(hybrid_lexical_weight=0.5, hybrid_dense_weight=0.5, hybrid_graph_weight=0.5)


def test_valid_custom_weights_are_accepted() -> None:
    settings = RetrievalExecutorSettings(
        lexical_bm25_weight=0.6, lexical_identifier_weight=0.2, lexical_keyword_overlap_weight=0.2,
        hybrid_lexical_weight=0.5, hybrid_dense_weight=0.3, hybrid_graph_weight=0.2,
    )
    assert settings.lexical_bm25_weight == 0.6
