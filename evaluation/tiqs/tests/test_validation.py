"""Unit tests for `evaluation.tiqs.validation`.

Covers every check category this milestone's instructions enumerate:
schema correctness, missing fields, duplicate queries, repository
leakage, invalid file references, invalid TaskType values, and
malformed annotations. Every test uses synthetic in-memory or
temp-directory fixtures -- no network, no real repository clone
required (file-existence checking is exercised separately via a
temp directory standing in for `repositories_root`).
"""
from __future__ import annotations

import json
from pathlib import Path

from evaluation.tiqs.models import (
    AdjudicationRecord,
    AnnotatorRole,
    DatasetSplit,
    DisagreementField,
    RepositoryManifest,
)
from evaluation.tiqs.tests.conftest import (
    make_annotator,
    make_manifest,
    make_manifest_entry,
    make_query,
    make_relevant_context_entry,
    make_relevant_context_set,
    make_task_type_label,
)
from evaluation.tiqs.validation import (
    Severity,
    check_duplicate_query_ids,
    check_duplicate_query_text,
    check_invalid_file_references,
    check_malformed_annotations,
    check_query_repository_references,
    check_repository_manifest_integrity,
    load_manifest_file,
    load_queries_file,
    validate_dataset,
)
from tara.core.types import TaskType


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ============================================================================
# Schema correctness / missing fields (loading)
# ============================================================================


def test_load_manifest_file_valid(tmp_path: Path) -> None:
    manifest_path = _write(
        tmp_path / "manifest.json",
        json.dumps(
            {
                "schema_version": "v1",
                "entries": [json.loads(make_manifest_entry().model_dump_json())],
            }
        ),
    )
    manifest, issues = load_manifest_file(manifest_path)
    assert issues == []
    assert len(manifest.entries) == 1


def test_load_manifest_file_reports_missing_field(tmp_path: Path) -> None:
    manifest_path = _write(
        tmp_path / "manifest.json",
        json.dumps({"schema_version": "v1", "entries": [{"repository_id": "r"}]}),
    )
    manifest, issues = load_manifest_file(manifest_path)
    assert manifest.entries == []
    assert any(issue.category == "schema_correctness" for issue in issues)
    assert any(issue.severity == Severity.ERROR for issue in issues)


def test_load_manifest_file_invalid_json(tmp_path: Path) -> None:
    manifest_path = _write(tmp_path / "manifest.json", "{not valid json")
    manifest, issues = load_manifest_file(manifest_path)
    assert manifest.entries == []
    assert len(issues) == 1
    assert issues[0].severity == Severity.ERROR


def test_load_manifest_file_missing_file(tmp_path: Path) -> None:
    manifest, issues = load_manifest_file(tmp_path / "does_not_exist.json")
    assert manifest.entries == []
    assert len(issues) == 1


def test_load_manifest_file_partial_failure_keeps_valid_entries(tmp_path: Path) -> None:
    good = json.loads(make_manifest_entry(repository_id="good").model_dump_json())
    bad = {"repository_id": "bad"}  # missing every other required field
    manifest_path = _write(
        tmp_path / "manifest.json", json.dumps({"schema_version": "v1", "entries": [good, bad]})
    )
    manifest, issues = load_manifest_file(manifest_path)
    assert [e.repository_id for e in manifest.entries] == ["good"]
    assert len(issues) >= 1


def test_load_queries_file_valid(tmp_path: Path) -> None:
    queries_path = _write(tmp_path / "queries.jsonl", make_query().model_dump_json() + "\n")
    queries, issues = load_queries_file(queries_path)
    assert issues == []
    assert len(queries) == 1


def test_load_queries_file_reports_invalid_json_line(tmp_path: Path) -> None:
    queries_path = _write(tmp_path / "queries.jsonl", "{not valid json}\n")
    queries, issues = load_queries_file(queries_path)
    assert queries == []
    assert issues[0].severity == Severity.ERROR
    assert "queries.jsonl:1" in issues[0].location


def test_load_queries_file_reports_missing_field(tmp_path: Path) -> None:
    queries_path = _write(tmp_path / "queries.jsonl", json.dumps({"query_id": "q-1"}) + "\n")
    queries, issues = load_queries_file(queries_path)
    assert queries == []
    assert any(issue.category == "schema_correctness" for issue in issues)


def test_load_queries_file_skips_blank_lines(tmp_path: Path) -> None:
    first = make_query(query_id="q-1").model_dump_json()
    second = make_query(query_id="q-2").model_dump_json()
    queries_path = _write(tmp_path / "queries.jsonl", f"{first}\n\n{second}")
    queries, issues = load_queries_file(queries_path)
    assert issues == []
    assert [q.query_id for q in queries] == ["q-1", "q-2"]


def test_load_queries_file_reports_invalid_task_type_value(tmp_path: Path) -> None:
    record = json.loads(make_query().model_dump_json())
    record["task_type_labels"][0]["task_type"] = "not_a_real_task_type"
    queries_path = _write(tmp_path / "queries.jsonl", json.dumps(record) + "\n")
    queries, issues = load_queries_file(queries_path)
    assert queries == []
    assert any("task_type" in issue.message for issue in issues)


# ============================================================================
# Duplicate queries
# ============================================================================


def test_check_duplicate_query_ids_flags_repeat() -> None:
    queries = [
        make_query(query_id="dup"),
        make_query(query_id="dup"),
        make_query(query_id="unique"),
    ]
    issues = check_duplicate_query_ids(queries)
    assert len(issues) == 1
    assert issues[0].severity == Severity.ERROR


def test_check_duplicate_query_ids_empty_when_all_unique() -> None:
    queries = [make_query(query_id="a"), make_query(query_id="b")]
    assert check_duplicate_query_ids(queries) == []


def test_check_duplicate_query_text_flags_exact_duplicate_within_repository() -> None:
    queries = [
        make_query(query_id="a", repository_id="repo-a", query_text="same text"),
        make_query(query_id="b", repository_id="repo-a", query_text="same text"),
    ]
    issues = check_duplicate_query_text(queries)
    assert len(issues) == 1
    assert issues[0].severity == Severity.ERROR


def test_check_duplicate_query_text_allows_same_text_across_different_repositories() -> None:
    queries = [
        make_query(query_id="a", repository_id="repo-a", query_text="same text"),
        make_query(query_id="b", repository_id="repo-b", query_text="same text"),
    ]
    assert check_duplicate_query_text(queries) == []


# ============================================================================
# Repository leakage
# ============================================================================


def test_check_repository_manifest_integrity_flags_conflicting_split_duplicate() -> None:
    manifest = RepositoryManifest(
        schema_version="v1",
        entries=[
            make_manifest_entry(repository_id="repo-a", split=DatasetSplit.TRAIN),
            make_manifest_entry(repository_id="repo-a", split=DatasetSplit.TEST),
        ],
    )
    issues = check_repository_manifest_integrity(manifest)
    assert len(issues) == 1
    assert issues[0].category == "repository_leakage"
    assert issues[0].severity == Severity.ERROR
    assert "leakage" in issues[0].message.lower()


def test_check_repository_manifest_integrity_flags_same_split_duplicate() -> None:
    manifest = RepositoryManifest(
        schema_version="v1",
        entries=[
            make_manifest_entry(repository_id="repo-a", split=DatasetSplit.TRAIN),
            make_manifest_entry(repository_id="repo-a", split=DatasetSplit.TRAIN),
        ],
    )
    issues = check_repository_manifest_integrity(manifest)
    assert len(issues) == 1
    assert issues[0].severity == Severity.ERROR


def test_check_repository_manifest_integrity_passes_for_unique_repositories() -> None:
    manifest = make_manifest(
        [make_manifest_entry(repository_id="repo-a"), make_manifest_entry(repository_id="repo-b")]
    )
    assert check_repository_manifest_integrity(manifest) == []


def test_check_query_repository_references_flags_missing_repository() -> None:
    manifest = make_manifest([make_manifest_entry(repository_id="repo-a")])
    queries = [make_query(repository_id="repo-does-not-exist")]
    issues = check_query_repository_references(queries, manifest)
    assert len(issues) == 1
    assert issues[0].category == "repository_leakage"


def test_check_query_repository_references_passes_for_valid_reference() -> None:
    manifest = make_manifest([make_manifest_entry(repository_id="repo-a")])
    queries = [make_query(repository_id="repo-a")]
    assert check_query_repository_references(queries, manifest) == []


# ============================================================================
# Invalid file references
# ============================================================================


def test_check_invalid_file_references_flags_malformed_node_id() -> None:
    query = make_query(
        relevant_context_sets=[
            make_relevant_context_set(entries=[make_relevant_context_entry(node_id="not-a-valid-node-id")])
        ]
    )
    issues = check_invalid_file_references([query])
    errors = [i for i in issues if i.severity == Severity.ERROR]
    assert len(errors) == 1
    assert errors[0].category == "invalid_file_reference"


def test_check_invalid_file_references_accepts_well_formed_file_id() -> None:
    query = make_query(
        relevant_context_sets=[
            make_relevant_context_set(entries=[make_relevant_context_entry(node_id="file::app.py")])
        ]
    )
    issues = check_invalid_file_references([query])
    assert all(i.severity != Severity.ERROR for i in issues)


def test_check_invalid_file_references_accepts_well_formed_symbol_id() -> None:
    query = make_query(
        relevant_context_sets=[
            make_relevant_context_set(
                entries=[make_relevant_context_entry(node_id="file::app.py::greet::5")]
            )
        ]
    )
    issues = check_invalid_file_references([query])
    assert all(i.severity != Severity.ERROR for i in issues)


def test_check_invalid_file_references_warns_when_no_repositories_root_given() -> None:
    query = make_query()
    issues = check_invalid_file_references([query], repositories_root=None)
    assert any(i.severity == Severity.WARNING for i in issues)


def test_check_invalid_file_references_verifies_existence_on_disk(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo-a"
    repo_dir.mkdir()
    (repo_dir / "app.py").write_text("print('hi')", encoding="utf-8")

    query = make_query(
        repository_id="repo-a",
        relevant_context_sets=[
            make_relevant_context_set(entries=[make_relevant_context_entry(node_id="file::app.py")])
        ],
    )
    issues = check_invalid_file_references([query], repositories_root=tmp_path)
    assert issues == []


def test_check_invalid_file_references_flags_nonexistent_file_on_disk(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo-a"
    repo_dir.mkdir()

    query = make_query(
        repository_id="repo-a",
        relevant_context_sets=[
            make_relevant_context_set(
                entries=[make_relevant_context_entry(node_id="file::does_not_exist.py")]
            )
        ],
    )
    issues = check_invalid_file_references([query], repositories_root=tmp_path)
    errors = [i for i in issues if i.severity == Severity.ERROR]
    assert len(errors) == 1
    assert "does not exist" in errors[0].message


# ============================================================================
# Malformed annotations
# ============================================================================


def test_check_malformed_annotations_flags_non_independent_task_type_labels() -> None:
    query = make_query(
        task_type_labels=[
            make_task_type_label(
                annotator_id="same-annotator", role=AnnotatorRole.INDEPENDENT_LABELER
            ),
            make_task_type_label(annotator_id="same-annotator", role=AnnotatorRole.AUTHOR),
        ]
    )
    issues = check_malformed_annotations([query])
    errors = [i for i in issues if i.severity == Severity.ERROR]
    assert any("independent" in e.message.lower() for e in errors)


def test_check_malformed_annotations_passes_for_independent_labels() -> None:
    query = make_query()  # default fixture already uses two distinct annotator_ids
    issues = check_malformed_annotations([query])
    assert all(i.severity != Severity.ERROR for i in issues)


def test_check_malformed_annotations_warns_on_single_task_type_label() -> None:
    query = make_query(task_type_labels=[make_task_type_label()])
    issues = check_malformed_annotations([query])
    assert any(i.severity == Severity.WARNING and "double-labeled" in i.message for i in issues)


def test_check_malformed_annotations_warns_on_unadjudicated_disagreement() -> None:
    query = make_query(
        task_type_labels=[
            make_task_type_label(
                task_type=TaskType.BUG_FIX, annotator_id="a", role=AnnotatorRole.INDEPENDENT_LABELER
            ),
            make_task_type_label(
                task_type=TaskType.REFACTOR, annotator_id="b", role=AnnotatorRole.AUTHOR
            ),
        ]
    )
    issues = check_malformed_annotations([query])
    assert any(i.severity == Severity.WARNING and "disagree" in i.message.lower() for i in issues)


def test_check_malformed_annotations_no_warning_when_disagreement_adjudicated() -> None:
    query = make_query(
        task_type_labels=[
            make_task_type_label(
                task_type=TaskType.BUG_FIX, annotator_id="a", role=AnnotatorRole.INDEPENDENT_LABELER
            ),
            make_task_type_label(
                task_type=TaskType.REFACTOR, annotator_id="b", role=AnnotatorRole.AUTHOR
            ),
        ],
        adjudicated_task_type=TaskType.BUG_FIX,
        adjudication_records=[
            AdjudicationRecord(
                field=DisagreementField.TASK_TYPE,
                adjudicator=make_annotator(annotator_id="c", role=AnnotatorRole.ADJUDICATOR),
                resolved_task_type=TaskType.BUG_FIX,
                rationale="r",
            )
        ],
    )
    issues = check_malformed_annotations([query])
    assert not any("disagree" in i.message.lower() for i in issues)


def test_check_malformed_annotations_flags_non_independent_relevant_context_sets() -> None:
    query = make_query(
        relevant_context_sets=[
            make_relevant_context_set(annotator_id="same", role=AnnotatorRole.INDEPENDENT_LABELER),
            make_relevant_context_set(annotator_id="same", role=AnnotatorRole.SPOT_CHECKER),
        ]
    )
    issues = check_malformed_annotations([query])
    errors = [i for i in issues if i.severity == Severity.ERROR]
    assert any(
        "spot-check" in e.message.lower() or "independently" in e.message.lower() for e in errors
    )


def test_check_malformed_annotations_flags_wrong_author_role() -> None:
    query = make_query(authored_by=make_annotator(role=AnnotatorRole.ADJUDICATOR))
    issues = check_malformed_annotations([query])
    errors = [i for i in issues if i.severity == Severity.ERROR]
    assert any("authored_by.role" in e.message for e in errors)


# ============================================================================
# Top-level orchestration
# ============================================================================


def test_validate_dataset_passes_for_the_schema_example() -> None:
    example_dir = Path(__file__).resolve().parents[1] / "schema_example"
    report = validate_dataset(
        example_dir / "repository_manifest.json", example_dir / "queries.jsonl"
    )
    assert report.passed
    assert report.error_count == 0


def test_validate_dataset_empty_queries_file_passes(tmp_path: Path) -> None:
    entry = json.loads(make_manifest_entry().model_dump_json())
    manifest_path = _write(
        tmp_path / "manifest.json", json.dumps({"schema_version": "v1", "entries": [entry]})
    )
    queries_path = _write(tmp_path / "queries.jsonl", "")
    report = validate_dataset(manifest_path, queries_path)
    assert report.passed


def test_validate_dataset_empty_manifest_flags_every_query_as_leakage(tmp_path: Path) -> None:
    manifest_path = _write(
        tmp_path / "manifest.json", json.dumps({"schema_version": "v1", "entries": []})
    )
    queries_path = _write(tmp_path / "queries.jsonl", make_query().model_dump_json() + "\n")
    report = validate_dataset(manifest_path, queries_path)
    assert not report.passed
    assert any(i.category == "repository_leakage" for i in report.issues)


def test_validate_dataset_aggregates_issues_across_all_checks(tmp_path: Path) -> None:
    entry = json.loads(make_manifest_entry(repository_id="repo-a").model_dump_json())
    manifest_path = _write(
        tmp_path / "manifest.json", json.dumps({"schema_version": "v1", "entries": [entry]})
    )
    duplicate_id_query = make_query(query_id="dup", repository_id="repo-a").model_dump_json()
    queries_path = _write(
        tmp_path / "queries.jsonl", duplicate_id_query + "\n" + duplicate_id_query
    )

    report = validate_dataset(manifest_path, queries_path)
    assert not report.passed
    assert any(i.category == "duplicate_queries" for i in report.issues)
