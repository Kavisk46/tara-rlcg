"""Validation for TIQS dataset files.

Implements exactly the checks this milestone's instructions enumerate:
schema correctness, missing fields, duplicate queries, repository
leakage, invalid file references, invalid `TaskType` values, and
malformed annotations. Every check is best-effort and non-fatal: a
malformed record is reported as an issue and skipped, not a reason to
abort the whole run -- so a single validation pass surfaces every
problem in a file at once, which is what someone cleaning up a large
annotation batch actually needs (contrast with letting the first bad
JSON line raise and stop the entire load).

No check here requires a live LLM, network access, or any TARA pipeline
stage to run -- this module only reads JSON/JSONL files and, optionally,
checks local filesystem paths.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from evaluation.tiqs.models import (
    AnnotatorRole,
    DisagreementField,
    RepositoryManifest,
    RepositoryManifestEntry,
    TIQSQueryRecord,
)

_NODE_ID_FILE_PREFIX = "file::"


class Severity:
    """Issue severity levels. Not an enum: kept as plain string constants so a `ValidationReport`
    can be trivially JSON-serialized without an enum-encoding decision."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    """One concrete problem found in a TIQS dataset file."""

    severity: str
    category: str
    location: str
    message: str


@dataclass
class ValidationReport:
    """The complete result of a `validate_dataset` run."""

    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True iff no `Severity.ERROR`-level issue was found. Warnings do not fail a report."""
        return not any(issue.severity == Severity.ERROR for issue in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == Severity.WARNING)

    def extend(self, issues: list[ValidationIssue]) -> None:
        self.issues.extend(issues)


# ============================================================================
# Loading (schema correctness + missing fields)
# ============================================================================


def load_manifest_file(path: Path) -> tuple[RepositoryManifest, list[ValidationIssue]]:
    """Load and validate `repository_manifest.json`, one entry at a time.

    Args:
        path: Path to the manifest JSON file.

    Returns:
        `(manifest, issues)`: `manifest.entries` contains only the
        entries that parsed successfully; every entry that failed
        schema validation (missing/invalid field, wrong type, a failed
        cross-field check like §4's size-bucket/LOC consistency) is
        reported as an `ERROR` issue and omitted, not silently dropped
        without a trace.
    """
    issues: list[ValidationIssue] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(
            ValidationIssue(
                Severity.ERROR, "schema_correctness", str(path), f"Could not read/parse JSON: {exc}"
            )
        )
        return RepositoryManifest(schema_version="unknown", entries=[]), issues

    schema_version = raw.get("schema_version", "") if isinstance(raw, dict) else ""
    raw_entries = raw.get("entries", []) if isinstance(raw, dict) else []
    if not isinstance(raw_entries, list):
        issues.append(
            ValidationIssue(
                Severity.ERROR, "schema_correctness", str(path), "'entries' must be a JSON array."
            )
        )
        raw_entries = []

    entries: list[RepositoryManifestEntry] = []
    for index, raw_entry in enumerate(raw_entries):
        location = f"{path}:entries[{index}]"
        try:
            entries.append(RepositoryManifestEntry.model_validate(raw_entry))
        except ValidationError as exc:
            issues.extend(_pydantic_errors_to_issues(exc, location, "schema_correctness"))

    return RepositoryManifest(schema_version=schema_version, entries=entries), issues


def load_queries_file(path: Path) -> tuple[list[TIQSQueryRecord], list[ValidationIssue]]:
    """Load and validate `queries.jsonl`, one line at a time.

    Args:
        path: Path to the JSON Lines query file.

    Returns:
        `(queries, issues)`: `queries` contains only the lines that
        parsed successfully; every malformed line (invalid JSON, a
        missing required field, an invalid `TaskType` value, a failed
        cross-field check such as an adjudication record mismatch) is
        reported as an `ERROR` issue with its 1-indexed line number and
        omitted, not silently skipped.
    """
    issues: list[ValidationIssue] = []
    queries: list[TIQSQueryRecord] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        issues.append(
            ValidationIssue(
                Severity.ERROR, "schema_correctness", str(path), f"Could not read file: {exc}"
            )
        )
        return queries, issues

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        location = f"{path}:{line_number}"
        try:
            raw_record = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(
                ValidationIssue(
                    Severity.ERROR, "schema_correctness", location, f"Invalid JSON: {exc}"
                )
            )
            continue
        try:
            queries.append(TIQSQueryRecord.model_validate(raw_record))
        except ValidationError as exc:
            issues.extend(_pydantic_errors_to_issues(exc, location, "schema_correctness"))

    return queries, issues


def _pydantic_errors_to_issues(
    exc: ValidationError, location: str, category: str
) -> list[ValidationIssue]:
    issues = []
    for error in exc.errors():
        field_path = ".".join(str(part) for part in error["loc"]) or "<root>"
        message = f"{field_path}: {error['msg']} (got {error.get('input')!r})"
        issues.append(ValidationIssue(Severity.ERROR, category, location, message))
    return issues


# ============================================================================
# Duplicate queries
# ============================================================================


def check_duplicate_query_ids(queries: list[TIQSQueryRecord]) -> list[ValidationIssue]:
    """Flag every `query_id` that appears more than once across the dataset."""
    counts = Counter(query.query_id for query in queries)
    return [
        ValidationIssue(
            Severity.ERROR,
            "duplicate_queries",
            f"query_id={query_id!r}",
            f"query_id appears {count} times; every query_id must be globally unique.",
        )
        for query_id, count in counts.items()
        if count > 1
    ]


def check_duplicate_query_text(queries: list[TIQSQueryRecord]) -> list[ValidationIssue]:
    """Flag exact-text duplicate queries authored against the same repository.

    Exact-text matching only -- this does not attempt near-duplicate
    (paraphrase) detection, which would require a similarity model and
    a chosen threshold; DATASET_PLAN.md §12 check 6 names near-duplicate
    detection as a manual-review step, not a mechanical one this
    validator claims to fully automate.
    """
    seen: dict[tuple[str, str], list[str]] = defaultdict(list)
    for query in queries:
        seen[(query.repository_id, query.query_text)].append(query.query_id)

    return [
        ValidationIssue(
            Severity.ERROR,
            "duplicate_queries",
            f"repository_id={repository_id!r}",
            f"Identical query_text shared by query_ids {query_ids} -- exact-duplicate query.",
        )
        for (repository_id, _text), query_ids in seen.items()
        if len(query_ids) > 1
    ]


# ============================================================================
# Repository leakage
# ============================================================================


def check_repository_manifest_integrity(manifest: RepositoryManifest) -> list[ValidationIssue]:
    """Flag duplicate `repository_id` entries in the manifest, especially split conflicts.

    Since a query's split is resolved solely by looking up its
    `repository_id` in the manifest (`evaluation.tiqs.models.resolve_split`),
    the entire repository-level leakage guarantee DATASET_PLAN.md §6-§9
    depends on rests on this one invariant: each `repository_id` appears
    in the manifest exactly once. A duplicate entry with two different
    `split` values would silently make a subset of that repository's
    queries resolve to one split and the rest to another, depending on
    which duplicate a given lookup happened to hit first -- the exact
    leakage failure mode this check exists to catch before it can occur.
    """
    issues: list[ValidationIssue] = []
    by_id: dict[str, list[RepositoryManifestEntry]] = defaultdict(list)
    for entry in manifest.entries:
        by_id[entry.repository_id].append(entry)

    for repository_id, entries in by_id.items():
        if len(entries) <= 1:
            continue
        splits = {entry.split for entry in entries}
        if len(splits) > 1:
            issues.append(
                ValidationIssue(
                    Severity.ERROR,
                    "repository_leakage",
                    f"repository_id={repository_id!r}",
                    f"Repository appears in the manifest {len(entries)} times with conflicting "
                    f"splits {sorted(s.value for s in splits)} -- this is the exact "
                    f"repository-level leakage DATASET_PLAN.md §6-§9 requires be prevented.",
                )
            )
        else:
            issues.append(
                ValidationIssue(
                    Severity.ERROR,
                    "repository_leakage",
                    f"repository_id={repository_id!r}",
                    f"Repository appears in the manifest {len(entries)} times (duplicate entries, "
                    f"same split) -- repository_id must be unique even when splits agree.",
                )
            )
    return issues


def check_query_repository_references(
    queries: list[TIQSQueryRecord], manifest: RepositoryManifest
) -> list[ValidationIssue]:
    """Flag every query whose `repository_id` does not resolve to exactly one manifest entry."""
    manifest_ids = {entry.repository_id for entry in manifest.entries}
    return [
        ValidationIssue(
            Severity.ERROR,
            "repository_leakage",
            f"query_id={query.query_id!r}",
            f"repository_id={query.repository_id!r} does not appear in the repository manifest; "
            f"this query's split cannot be resolved.",
        )
        for query in queries
        if query.repository_id not in manifest_ids
    ]


# ============================================================================
# Invalid file references
# ============================================================================


def check_invalid_file_references(
    queries: list[TIQSQueryRecord], repositories_root: Path | None = None
) -> list[ValidationIssue]:
    """Flag malformed or (optionally) non-existent relevant-context file/symbol references.

    Args:
        queries: Queries to check.
        repositories_root: If given, `<repositories_root>/<repository_id>/<file_path>`
            is checked for actual existence on disk, for every referenced
            node id (per DATASET_PLAN.md §11/§12's "every file path /
            symbol id is mechanically verified to exist in the pinned
            repository"). If omitted (the default), only the node id's
            *format* is checked -- existence checking is skipped with a
            `WARNING`, not silently treated as passing, since a
            validation run without a local checkout genuinely cannot
            confirm existence.

    Returns:
        One issue per malformed node id, plus one `WARNING` per query
        (not per entry) when existence-checking was skipped for it.
    """
    issues: list[ValidationIssue] = []
    for query in queries:
        entries = [entry for rel_set in query.relevant_context_sets for entry in rel_set.entries]
        if query.adjudicated_relevant_context:
            entries.extend(query.adjudicated_relevant_context)

        skipped_existence_check = False
        for entry in entries:
            file_path = _parse_file_path_from_node_id(entry.node_id)
            if file_path is None:
                issues.append(
                    ValidationIssue(
                        Severity.ERROR,
                        "invalid_file_reference",
                        f"query_id={query.query_id!r}",
                        f"node_id={entry.node_id!r} does not match the 'file::<path>' or "
                        f"'file::<path>::<qualified_name>::<line>' scheme.",
                    )
                )
                continue
            if repositories_root is None:
                skipped_existence_check = True
                continue
            candidate = repositories_root / query.repository_id / file_path
            if not candidate.exists():
                issues.append(
                    ValidationIssue(
                        Severity.ERROR,
                        "invalid_file_reference",
                        f"query_id={query.query_id!r}",
                        f"node_id={entry.node_id!r} references {candidate}, which does not exist.",
                    )
                )
        if skipped_existence_check:
            issues.append(
                ValidationIssue(
                    Severity.WARNING,
                    "invalid_file_reference",
                    f"query_id={query.query_id!r}",
                    "repositories_root not provided -- file/symbol existence was not checked, only "
                    "node_id format.",
                )
            )
    return issues


def _parse_file_path_from_node_id(node_id: str) -> str | None:
    """Extract the file path from a `file::`-prefixed node id, or None if malformed.

    Mirrors `tara.context.models.build_file_node_id`/`build_symbol_node_id`'s
    exact format (`file::{file_path}` or
    `file::{file_path}::{qualified_name}::{start_line}`) without importing
    a parser from that module, since none exists there -- both builders
    are one-way. Both id families begin identically, so the file path is
    always the second `::`-delimited segment.
    """
    if not node_id.startswith(_NODE_ID_FILE_PREFIX):
        return None
    remainder = node_id[len(_NODE_ID_FILE_PREFIX) :]
    if not remainder:
        return None
    # For a symbol id, remainder is "{file_path}::{qualified_name}::{start_line}";
    # for a file id, remainder is just "{file_path}" with no further "::". Either way,
    # the file path itself never contains "::", so splitting once is sufficient.
    file_path = remainder.split("::", 1)[0]
    return file_path or None


# ============================================================================
# Malformed annotations (independence, role consistency, adjudication)
# ============================================================================


def check_malformed_annotations(queries: list[TIQSQueryRecord]) -> list[ValidationIssue]:
    """Flag annotation records that are internally well-typed but violate the annotation protocol.

    Distinct from schema correctness: every record checked here already
    passed Pydantic validation (loading succeeded). These checks enforce
    DATASET_PLAN.md §10's *process* requirements -- independence between
    the two labels/sets, and correct annotator roles -- which no amount
    of per-field type checking alone can catch.
    """
    issues: list[ValidationIssue] = []
    for query in queries:
        issues.extend(_check_author_role(query))
        issues.extend(_check_task_type_label_independence(query))
        issues.extend(_check_relevant_context_independence(query))
        issues.extend(_check_unresolved_disagreement(query))
    return issues


def _check_author_role(query: TIQSQueryRecord) -> list[ValidationIssue]:
    if query.authored_by.role is not AnnotatorRole.AUTHOR:
        return [
            ValidationIssue(
                Severity.ERROR,
                "malformed_annotation",
                f"query_id={query.query_id!r}",
                f"authored_by.role={query.authored_by.role.value!r}, expected 'author'.",
            )
        ]
    return []


def _check_task_type_label_independence(query: TIQSQueryRecord) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    labels = query.task_type_labels

    for label in labels:
        if label.annotator.role not in (AnnotatorRole.AUTHOR, AnnotatorRole.INDEPENDENT_LABELER):
            issues.append(
                ValidationIssue(
                    Severity.ERROR,
                    "malformed_annotation",
                    f"query_id={query.query_id!r}",
                    f"task_type_labels contains an entry with role={label.annotator.role.value!r}; "
                    f"only 'author' (self-relabel) or 'independent_labeler' is valid here.",
                )
            )

    if len(labels) == 1:
        issues.append(
            ValidationIssue(
                Severity.WARNING,
                "malformed_annotation",
                f"query_id={query.query_id!r}",
                "Only 1 TaskType label present -- not yet double-labeled per DATASET_PLAN.md §10 "
                "steps 2-3; inter-annotator agreement (§13) cannot be computed for this query yet.",
            )
        )
    elif len(labels) == 2:
        annotator_ids = {label.annotator.annotator_id for label in labels}
        if len(annotator_ids) == 1:
            issues.append(
                ValidationIssue(
                    Severity.ERROR,
                    "malformed_annotation",
                    f"query_id={query.query_id!r}",
                    "Both TaskType labels share the same annotator_id -- this is not independent "
                    "labeling (DATASET_PLAN.md §10 steps 2-3 require two distinct annotators).",
                )
            )
    elif len(labels) > 2:
        issues.append(
            ValidationIssue(
                Severity.WARNING,
                "malformed_annotation",
                f"query_id={query.query_id!r}",
                f"{len(labels)} TaskType labels present; DATASET_PLAN.md §10 expects exactly 2 "
                f"(independent labeler + author self-relabel) before adjudication.",
            )
        )

    task_types = {label.task_type for label in labels}
    if len(labels) == 2 and len(task_types) > 1 and query.adjudicated_task_type is None:
        issues.append(
            ValidationIssue(
                Severity.WARNING,
                "malformed_annotation",
                f"query_id={query.query_id!r}",
                "The two TaskType labels disagree and no adjudicated_task_type is recorded -- "
                "this query needs adjudication per DATASET_PLAN.md §10 step 4.",
            )
        )
    return issues


def _check_relevant_context_independence(query: TIQSQueryRecord) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    sets_ = query.relevant_context_sets

    valid_context_roles = (
        AnnotatorRole.AUTHOR,
        AnnotatorRole.INDEPENDENT_LABELER,
        AnnotatorRole.SPOT_CHECKER,
    )
    for rel_set in sets_:
        if rel_set.annotator.role not in valid_context_roles:
            issues.append(
                ValidationIssue(
                    Severity.ERROR,
                    "malformed_annotation",
                    f"query_id={query.query_id!r}",
                    f"relevant_context_sets contains an entry with role="
                    f"{rel_set.annotator.role.value!r}, which is not a valid role for deriving "
                    f"relevant-context ground truth.",
                )
            )

    if len(sets_) >= 2:
        annotator_ids = [rel_set.annotator.annotator_id for rel_set in sets_]
        if len(set(annotator_ids)) != len(annotator_ids):
            issues.append(
                ValidationIssue(
                    Severity.ERROR,
                    "malformed_annotation",
                    f"query_id={query.query_id!r}",
                    "Two relevant_context_sets share the same annotator_id -- the spot-check "
                    "(DATASET_PLAN.md §11-§12) requires an independently-derived second set.",
                )
            )
    return issues


def _check_unresolved_disagreement(query: TIQSQueryRecord) -> list[ValidationIssue]:
    """Flag a query with 2 disagreeing relevant-context sets and no adjudication record."""
    if len(query.relevant_context_sets) != 2:
        return []
    first, second = (frozenset(e.node_id for e in s.entries) for s in query.relevant_context_sets)
    has_adjudication = any(
        record.field is DisagreementField.RELEVANT_CONTEXT for record in query.adjudication_records
    )
    if first != second and not has_adjudication:
        return [
            ValidationIssue(
                Severity.WARNING,
                "malformed_annotation",
                f"query_id={query.query_id!r}",
                "The two relevant-context sets disagree (different node_id sets) and no "
                "adjudication record resolves the disagreement.",
            )
        ]
    return []


# ============================================================================
# Top-level orchestration
# ============================================================================


def validate_dataset(
    manifest_path: Path, queries_path: Path, repositories_root: Path | None = None
) -> ValidationReport:
    """Run every TIQS validation check against `manifest_path`/`queries_path`.

    Args:
        manifest_path: Path to `repository_manifest.json`.
        queries_path: Path to `queries.jsonl`.
        repositories_root: Optional local directory containing each
            repository's clone (`<repositories_root>/<repository_id>/...`),
            for real file-existence checking. See
            `check_invalid_file_references`.

    Returns:
        A `ValidationReport` aggregating every check's issues. Loading
        failures for individual malformed records do not prevent the
        remaining, well-formed records from being checked against every
        other rule.
    """
    report = ValidationReport()

    manifest, manifest_issues = load_manifest_file(manifest_path)
    report.extend(manifest_issues)

    queries, query_issues = load_queries_file(queries_path)
    report.extend(query_issues)

    report.extend(check_repository_manifest_integrity(manifest))
    report.extend(check_query_repository_references(queries, manifest))
    report.extend(check_duplicate_query_ids(queries))
    report.extend(check_duplicate_query_text(queries))
    report.extend(check_invalid_file_references(queries, repositories_root))
    report.extend(check_malformed_annotations(queries))

    return report


def _report_to_dict(report: ValidationReport) -> dict[str, Any]:
    return {
        "passed": report.passed,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
        "issues": [
            {
                "severity": issue.severity,
                "category": issue.category,
                "location": issue.location,
                "message": issue.message,
            }
            for issue in report.issues
        ],
    }


def main() -> None:
    """CLI entry point.

    Usage: `python -m evaluation.tiqs.validation <manifest.json> <queries.jsonl> \
        [repositories_root]`
    """
    import sys

    if len(sys.argv) not in (3, 4):
        print(
            "Usage: python -m evaluation.tiqs.validation <manifest.json> <queries.jsonl> "
            "[repositories_root]",
            file=sys.stderr,
        )
        raise SystemExit(2)

    manifest_path = Path(sys.argv[1])
    queries_path = Path(sys.argv[2])
    repositories_root = Path(sys.argv[3]) if len(sys.argv) == 4 else None

    report = validate_dataset(manifest_path, queries_path, repositories_root)
    print(json.dumps(_report_to_dict(report), indent=2, default=str))
    raise SystemExit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
