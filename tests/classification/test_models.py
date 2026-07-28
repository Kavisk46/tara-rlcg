"""Unit tests for `tara.classification.models.TaskClassification`."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from tara.classification.models import TaskClassification
from tara.core.types import Language, RetrievalStrategy, TaskType


def test_construct_minimal_classification() -> None:
    classification = TaskClassification(
        task_type=TaskType.SEARCH,
        retriever_kind=RetrievalStrategy.LEXICAL,
        confidence=1.0,
    )

    assert classification.task_type is TaskType.SEARCH
    assert classification.retriever_kind is RetrievalStrategy.LEXICAL
    assert classification.graph_required is False
    assert classification.extracted_keywords == []
    assert classification.language_hint is None
    assert classification.metadata == {}


def test_construct_full_classification() -> None:
    classification = TaskClassification(
        task_type=TaskType.ARCHITECTURE,
        retriever_kind=RetrievalStrategy.GRAPH,
        confidence=0.8,
        graph_required=True,
        semantic_required=False,
        lexical_required=False,
        reasoning_required=False,
        extracted_keywords=["trace", "flow"],
        detected_symbols=["GraphBuilder"],
        detected_file_paths=["utils.py"],
        language_hint=Language.PYTHON,
        metadata={"fired_rules": ["graph_trigger_keyword"]},
    )

    assert classification.detected_symbols == ["GraphBuilder"]
    assert classification.language_hint is Language.PYTHON
    assert classification.metadata["fired_rules"] == ["graph_trigger_keyword"]


@pytest.mark.parametrize("confidence", [-0.1, 1.1, 2.0])
def test_confidence_out_of_bounds_raises(confidence: float) -> None:
    with pytest.raises(ValidationError):
        TaskClassification(
            task_type=TaskType.UNKNOWN,
            retriever_kind=RetrievalStrategy.SEMANTIC,
            confidence=confidence,
        )


@pytest.mark.parametrize("confidence", [0.0, 1.0, 0.5])
def test_confidence_boundary_values_are_valid(confidence: float) -> None:
    classification = TaskClassification(
        task_type=TaskType.UNKNOWN,
        retriever_kind=RetrievalStrategy.SEMANTIC,
        confidence=confidence,
    )
    assert classification.confidence == confidence
