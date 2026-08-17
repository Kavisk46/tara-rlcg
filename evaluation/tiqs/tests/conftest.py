"""Shared builder helpers for the `evaluation.tiqs` test suite.

All content produced by these helpers is synthetic test fixture data,
never real annotation content -- mirrors the disclaimer in
`evaluation/tiqs/schema_example/README.md`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from evaluation.tiqs.models import (
    AdjudicationRecord,
    AnnotatorMetadata,
    AnnotatorRole,
    DatasetSplit,
    DisagreementField,
    PromptFraming,
    RelevanceTier,
    RelevantContextEntry,
    RelevantContextSet,
    RepositoryLicense,
    RepositoryManifest,
    RepositoryManifestEntry,
    SizeBucket,
    TaskTypeLabel,
    TIQSQueryRecord,
)
from tara.core.types import Language, TaskType

_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_annotator(
    *,
    annotator_id: str = "annotator-a",
    role: AnnotatorRole = AnnotatorRole.AUTHOR,
    timestamp: datetime = _TS,
) -> AnnotatorMetadata:
    return AnnotatorMetadata(annotator_id=annotator_id, role=role, timestamp=timestamp)


def make_manifest_entry(
    *,
    repository_id: str = "repo-a",
    commit_sha: str = "a" * 40,
    license: RepositoryLicense = RepositoryLicense.MIT,
    language: Language = Language.PYTHON,
    lines_of_code: int = 1_000,
    size_bucket: SizeBucket = SizeBucket.SMALL,
    domain: str = "example_domain",
    split: DatasetSplit = DatasetSplit.TRAIN,
    added_at: datetime = _TS,
    changelog_note: str | None = None,
) -> RepositoryManifestEntry:
    return RepositoryManifestEntry(
        repository_id=repository_id,
        source_url=f"https://example.invalid/{repository_id}.git",
        commit_sha=commit_sha,
        license=license,
        language=language,
        size_bucket=size_bucket,
        lines_of_code=lines_of_code,
        domain=domain,
        split=split,
        added_at=added_at,
        changelog_note=changelog_note,
    )


def make_manifest(entries: list[RepositoryManifestEntry] | None = None) -> RepositoryManifest:
    resolved_entries = entries if entries is not None else [make_manifest_entry()]
    return RepositoryManifest(schema_version="test-v1", entries=resolved_entries)


def make_task_type_label(
    *,
    task_type: TaskType = TaskType.BUG_FIX,
    annotator_id: str = "annotator-b",
    role: AnnotatorRole = AnnotatorRole.INDEPENDENT_LABELER,
) -> TaskTypeLabel:
    annotator = make_annotator(annotator_id=annotator_id, role=role)
    return TaskTypeLabel(task_type=task_type, annotator=annotator)


def make_relevant_context_entry(
    *, node_id: str = "file::app.py", relevance_tier: RelevanceTier | None = None
) -> RelevantContextEntry:
    return RelevantContextEntry(node_id=node_id, relevance_tier=relevance_tier)


def make_relevant_context_set(
    *,
    entries: list[RelevantContextEntry] | None = None,
    annotator_id: str = "annotator-b",
    role: AnnotatorRole = AnnotatorRole.INDEPENDENT_LABELER,
) -> RelevantContextSet:
    return RelevantContextSet(
        entries=entries if entries is not None else [make_relevant_context_entry()],
        annotator=make_annotator(annotator_id=annotator_id, role=role),
    )


def make_query(
    *,
    query_id: str = "repo-a-001",
    repository_id: str = "repo-a",
    query_text: str = "[TEST FIXTURE] Fix the crash in app.py.",
    prompt_framing: PromptFraming = PromptFraming.ISSUE_TRACKER,
    authored_by: AnnotatorMetadata | None = None,
    task_type_labels: list[TaskTypeLabel] | None = None,
    adjudicated_task_type: TaskType | None = None,
    relevant_context_sets: list[RelevantContextSet] | None = None,
    adjudicated_relevant_context: list[RelevantContextEntry] | None = None,
    adjudication_records: list[AdjudicationRecord] | None = None,
    notes: str | None = None,
) -> TIQSQueryRecord:
    return TIQSQueryRecord(
        query_id=query_id,
        repository_id=repository_id,
        query_text=query_text,
        prompt_framing=prompt_framing,
        authored_by=authored_by if authored_by is not None else make_annotator(),
        task_type_labels=(
            task_type_labels
            if task_type_labels is not None
            else [
                make_task_type_label(
                    annotator_id="annotator-b", role=AnnotatorRole.INDEPENDENT_LABELER
                ),
                make_task_type_label(annotator_id="annotator-a", role=AnnotatorRole.AUTHOR),
            ]
        ),
        adjudicated_task_type=adjudicated_task_type,
        relevant_context_sets=(
            relevant_context_sets
            if relevant_context_sets is not None
            else [make_relevant_context_set()]
        ),
        adjudicated_relevant_context=adjudicated_relevant_context,
        adjudication_records=adjudication_records if adjudication_records is not None else [],
        notes=notes,
    )


__all__ = [
    "DisagreementField",
    "make_annotator",
    "make_manifest",
    "make_manifest_entry",
    "make_query",
    "make_relevant_context_entry",
    "make_relevant_context_set",
    "make_task_type_label",
]
