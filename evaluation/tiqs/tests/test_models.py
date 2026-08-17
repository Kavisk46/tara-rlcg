"""Unit tests for `evaluation.tiqs.models`.

Pure data-contract tests: field constraints and cross-field validators.
No validation-script logic (`evaluation.tiqs.validation`) is exercised
here.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from evaluation.tiqs.models import (
    AdjudicationRecord,
    AnnotatorRole,
    DatasetSplit,
    DisagreementField,
    ReferenceOutput,
    ReferenceOutputKind,
    RelevanceTier,
    SizeBucket,
    resolve_split,
)
from evaluation.tiqs.tests.conftest import (
    make_annotator,
    make_manifest,
    make_manifest_entry,
    make_query,
    make_relevant_context_entry,
    make_task_type_label,
)
from tara.core.types import Language, TaskType

# ============================================================================
# RepositoryManifestEntry
# ============================================================================


def test_manifest_entry_round_trips_fields() -> None:
    entry = make_manifest_entry(repository_id="repo-x", split=DatasetSplit.TEST)
    assert entry.repository_id == "repo-x"
    assert entry.split is DatasetSplit.TEST


def test_manifest_entry_rejects_short_commit_sha() -> None:
    with pytest.raises(ValidationError, match="commit_sha"):
        make_manifest_entry(commit_sha="abc123")


def test_manifest_entry_rejects_uppercase_commit_sha() -> None:
    with pytest.raises(ValidationError):
        make_manifest_entry(commit_sha="A" * 40)


@pytest.mark.parametrize(
    "loc,expected",
    [
        (0, SizeBucket.SMALL),
        (4_999, SizeBucket.SMALL),
        (5_000, SizeBucket.MEDIUM),
        (49_999, SizeBucket.MEDIUM),
        (50_000, SizeBucket.LARGE),
        (200_000, SizeBucket.LARGE),
    ],
)
def test_manifest_entry_size_bucket_boundaries(loc: int, expected: SizeBucket) -> None:
    entry = make_manifest_entry(lines_of_code=loc, size_bucket=expected)
    assert entry.size_bucket is expected


def test_manifest_entry_rejects_mismatched_size_bucket() -> None:
    with pytest.raises(ValidationError, match="size_bucket"):
        make_manifest_entry(lines_of_code=100, size_bucket=SizeBucket.LARGE)


def test_manifest_entry_rejects_loc_above_200k() -> None:
    with pytest.raises(ValidationError):
        make_manifest_entry(lines_of_code=200_001, size_bucket=SizeBucket.LARGE)


def test_manifest_entry_rejects_invalid_license() -> None:
    # "GPL-3.0" is deliberately not in the closed RepositoryLicense enum -- this test asserts
    # Pydantic rejects it at runtime, even though it fails static typing too.
    from evaluation.tiqs.models import RepositoryManifestEntry

    with pytest.raises(ValidationError):
        RepositoryManifestEntry(
            repository_id="r",
            source_url="https://example.invalid/r.git",
            commit_sha="a" * 40,
            license="GPL-3.0",  # type: ignore[arg-type]
            language=Language.PYTHON,
            size_bucket=SizeBucket.SMALL,
            lines_of_code=100,
            domain="d",
            split=DatasetSplit.TRAIN,
            added_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )


def test_manifest_entry_rejects_unknown_language() -> None:
    with pytest.raises(ValidationError):
        make_manifest_entry(language=Language.UNKNOWN)


# ============================================================================
# RelevantContextEntry / ReferenceOutput
# ============================================================================


def test_relevant_context_entry_relevance_tier_defaults_to_none() -> None:
    entry = make_relevant_context_entry()
    assert entry.relevance_tier is None


def test_relevant_context_entry_accepts_graded_tier() -> None:
    entry = make_relevant_context_entry(relevance_tier=RelevanceTier.PRIMARY)
    assert entry.relevance_tier is RelevanceTier.PRIMARY


def test_reference_output_acceptance_criteria_allows_multiple_entries() -> None:
    ref = ReferenceOutput(kind=ReferenceOutputKind.ACCEPTANCE_CRITERIA, content=["a", "b", "c"])
    assert len(ref.content) == 3


def test_reference_output_canonical_code_requires_exactly_one_entry() -> None:
    with pytest.raises(ValidationError, match="CANONICAL_CODE"):
        ReferenceOutput(kind=ReferenceOutputKind.CANONICAL_CODE, content=["a", "b"])


def test_reference_output_canonical_code_accepts_single_entry() -> None:
    ref = ReferenceOutput(kind=ReferenceOutputKind.CANONICAL_CODE, content=["def f(): ..."])
    assert ref.content == ["def f(): ..."]


# ============================================================================
# AdjudicationRecord
# ============================================================================


def test_adjudication_record_task_type_requires_resolved_task_type() -> None:
    with pytest.raises(ValidationError, match="TASK_TYPE"):
        AdjudicationRecord(
            field=DisagreementField.TASK_TYPE,
            adjudicator=make_annotator(role=AnnotatorRole.ADJUDICATOR),
            rationale="r",
        )


def test_adjudication_record_task_type_rejects_unknown() -> None:
    with pytest.raises(ValidationError, match="UNKNOWN"):
        AdjudicationRecord(
            field=DisagreementField.TASK_TYPE,
            adjudicator=make_annotator(role=AnnotatorRole.ADJUDICATOR),
            resolved_task_type=TaskType.UNKNOWN,
            rationale="r",
        )


def test_adjudication_record_task_type_accepts_valid_resolution() -> None:
    record = AdjudicationRecord(
        field=DisagreementField.TASK_TYPE,
        adjudicator=make_annotator(role=AnnotatorRole.ADJUDICATOR),
        resolved_task_type=TaskType.BUG_FIX,
        rationale="r",
    )
    assert record.resolved_task_type is TaskType.BUG_FIX


def test_adjudication_record_relevant_context_requires_resolved_context() -> None:
    with pytest.raises(ValidationError, match="RELEVANT_CONTEXT"):
        AdjudicationRecord(
            field=DisagreementField.RELEVANT_CONTEXT,
            adjudicator=make_annotator(role=AnnotatorRole.ADJUDICATOR),
            rationale="r",
        )


def test_adjudication_record_rejects_both_resolved_fields_set() -> None:
    with pytest.raises(ValidationError):
        AdjudicationRecord(
            field=DisagreementField.TASK_TYPE,
            adjudicator=make_annotator(role=AnnotatorRole.ADJUDICATOR),
            resolved_task_type=TaskType.BUG_FIX,
            resolved_relevant_context=[make_relevant_context_entry()],
            rationale="r",
        )


# ============================================================================
# TIQSQueryRecord
# ============================================================================


def test_query_record_round_trips_basic_fields() -> None:
    query = make_query(query_id="q-1", repository_id="repo-a")
    assert query.query_id == "q-1"
    assert query.repository_id == "repo-a"


def test_query_record_rejects_unknown_task_type_label() -> None:
    with pytest.raises(ValidationError, match="UNKNOWN"):
        make_query(task_type_labels=[make_task_type_label(task_type=TaskType.UNKNOWN)])


def test_query_record_accepts_single_task_type_label() -> None:
    query = make_query(task_type_labels=[make_task_type_label()])
    assert len(query.task_type_labels) == 1


def test_query_record_rejects_adjudicated_task_type_without_record() -> None:
    with pytest.raises(ValidationError, match="adjudicated_task_type"):
        make_query(adjudicated_task_type=TaskType.BUG_FIX, adjudication_records=[])


def test_query_record_accepts_adjudicated_task_type_with_matching_record() -> None:
    query = make_query(
        adjudicated_task_type=TaskType.BUG_FIX,
        adjudication_records=[
            AdjudicationRecord(
                field=DisagreementField.TASK_TYPE,
                adjudicator=make_annotator(role=AnnotatorRole.ADJUDICATOR),
                resolved_task_type=TaskType.BUG_FIX,
                rationale="r",
            )
        ],
    )
    assert query.adjudicated_task_type is TaskType.BUG_FIX


def test_query_record_rejects_adjudicated_relevant_context_without_record() -> None:
    with pytest.raises(ValidationError, match="adjudicated_relevant_context"):
        make_query(
            adjudicated_relevant_context=[make_relevant_context_entry()], adjudication_records=[]
        )


def test_query_record_rejects_empty_query_text() -> None:
    with pytest.raises(ValidationError):
        make_query(query_text="")


def test_query_record_rejects_empty_task_type_labels() -> None:
    with pytest.raises(ValidationError):
        make_query(task_type_labels=[])


def test_query_record_rejects_empty_relevant_context_sets() -> None:
    with pytest.raises(ValidationError):
        make_query(relevant_context_sets=[])


# ============================================================================
# resolve_split
# ============================================================================


def test_resolve_split_finds_matching_repository() -> None:
    manifest = make_manifest([make_manifest_entry(repository_id="repo-a", split=DatasetSplit.TEST)])
    query = make_query(repository_id="repo-a")
    assert resolve_split(query, manifest) is DatasetSplit.TEST


def test_resolve_split_raises_for_unknown_repository() -> None:
    manifest = make_manifest([make_manifest_entry(repository_id="repo-a")])
    query = make_query(repository_id="repo-does-not-exist")
    with pytest.raises(KeyError):
        resolve_split(query, manifest)
