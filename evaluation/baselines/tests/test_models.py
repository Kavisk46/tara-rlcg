"""Unit tests for `evaluation.baselines.models`."""
from __future__ import annotations

import pytest

from evaluation.baselines.definitions import BaselineId
from evaluation.baselines.models import (
    EvaluationConfig,
    GenerationConfig,
    RetrievalResultRecord,
    build_retrieval_result_record,
)
from tara.context.models import NodeType
from tara.core.types import RetrieverKind
from tara.generation.prompt import PromptTemplate
from tara.retrieval.models import RetrievalScore, RetrievedChunk, RetrievedContext
from tara.routing.models import RetrievalPlan
from tara.routing.strategy import RoutingStrategy

# ============================================================================
# GenerationConfig
# ============================================================================


def test_generation_config_accepts_valid_values() -> None:
    config = GenerationConfig(model="fake-model", temperature=0.0, max_tokens=1024)
    assert config.prompt_template is PromptTemplate.BASELINE


def test_generation_config_rejects_negative_temperature() -> None:
    with pytest.raises(ValueError, match="temperature"):
        GenerationConfig(model="m", temperature=-0.1, max_tokens=100)


def test_generation_config_rejects_non_positive_max_tokens() -> None:
    with pytest.raises(ValueError, match="max_tokens"):
        GenerationConfig(model="m", temperature=0.0, max_tokens=0)


def test_generation_config_rejects_a_non_baseline_prompt_template() -> None:
    with pytest.raises(ValueError, match="prompt_template"):
        GenerationConfig(
            model="m",
            temperature=0.0,
            max_tokens=100,
            prompt_template=PromptTemplate.WITH_TASK_CLASSIFICATION,
        )


def test_generation_config_is_immutable() -> None:
    config = GenerationConfig(model="m", temperature=0.0, max_tokens=100)
    with pytest.raises(AttributeError):
        config.model = "other"  # type: ignore[misc]


# ============================================================================
# EvaluationConfig
# ============================================================================


def test_evaluation_config_accepts_valid_values() -> None:
    config = EvaluationConfig(
        evaluator="retrieval-metrics-v1",
        metrics=("recall@10", "mrr"),
        scoring_protocol="matched-k",
        output_schema="retrieval-result-record-v1",
        query_set_id="tiqs-dev",
        corpus_id="tara-rlcg@HEAD",
    )
    assert config.metrics == ("recall@10", "mrr")


def test_evaluation_config_rejects_empty_metrics() -> None:
    with pytest.raises(ValueError, match="metrics"):
        EvaluationConfig(
            evaluator="e",
            metrics=(),
            scoring_protocol="p",
            output_schema="s",
            query_set_id="q",
            corpus_id="c",
        )


def test_evaluation_config_is_immutable() -> None:
    """The "same evaluation configuration for every baseline" fairness invariant is guaranteed
    structurally: one instance, frozen, cannot diverge across baselines because it cannot be
    mutated at all."""
    config = EvaluationConfig(
        evaluator="e", metrics=("recall@10",), scoring_protocol="p",
        output_schema="s", query_set_id="q", corpus_id="c",
    )
    with pytest.raises(AttributeError):
        config.evaluator = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    "field_name", ["evaluator", "query_set_id", "corpus_id"]
)
def test_evaluation_config_rejects_empty_required_strings(field_name: str) -> None:
    kwargs = {
        "evaluator": "e",
        "metrics": ("recall@10",),
        "scoring_protocol": "p",
        "output_schema": "s",
        "query_set_id": "q",
        "corpus_id": "c",
    }
    kwargs[field_name] = ""
    with pytest.raises(ValueError, match=field_name):
        EvaluationConfig(**kwargs)  # type: ignore[arg-type]


# ============================================================================
# RetrievalResultRecord / build_retrieval_result_record
# ============================================================================


def _chunk(chunk_id: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        retriever_kind=RetrieverKind.LEXICAL,
        node_type=NodeType.FUNCTION,
        name=chunk_id,
        file_path="app.py",
        content="def f(): ...",
        score=RetrievalScore(raw_score=score, normalized_score=score),
    )


def test_build_retrieval_result_record_flattens_chunks_in_order() -> None:
    context = RetrievedContext(
        retriever_kind=RetrieverKind.LEXICAL,
        query="q",
        chunks=[_chunk("a", 0.9), _chunk("b", 0.5)],
        total_candidates=2,
    )
    plan = RetrievalPlan(
        strategy=RoutingStrategy.LEXICAL_ONLY,
        retrievers=[RetrieverKind.LEXICAL],
        execution_order=[RetrieverKind.LEXICAL],
        parallel=False,
        rerank=False,
        top_k=10,
        candidate_limit=10,
        reason="test",
    )

    record = build_retrieval_result_record(BaselineId.B2, "query-1", plan, [context])

    assert record.baseline_id is BaselineId.B2
    assert record.query_id == "query-1"
    assert record.retrieved_document_ids == ("a", "b")
    assert record.scores == (0.9, 0.5)
    assert record.ranks == (0, 1)
    assert record.retrieval_mode == "lexical_only"


def test_build_retrieval_result_record_for_b0_has_no_documents_and_no_mode() -> None:
    record = build_retrieval_result_record(BaselineId.B0, "query-1", None, [])
    assert record.retrieved_document_ids == ()
    assert record.retrieval_mode is None


def test_retrieval_result_record_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        RetrievalResultRecord(
            baseline_id=BaselineId.B1,
            query_id="q",
            retrieved_document_ids=("a", "b"),
            retrieval_mode="semantic_only",
            scores=(0.9,),
            ranks=(0, 1),
            metadata={},
        )


def test_retrieval_result_record_never_carries_a_generated_answer_field() -> None:
    """Structural proof of "Do not put generated answers into the retrieval result":
    there is no field on this type that could hold one."""
    field_names = set(RetrievalResultRecord.__dataclass_fields__)
    assert "generated_code" not in field_names
    assert "answer" not in field_names
    assert "text" not in field_names
