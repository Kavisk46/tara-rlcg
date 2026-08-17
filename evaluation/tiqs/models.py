"""Data contracts for the Task-Intent Query Set (TIQS).

Every model here formalizes a design decision already made in
`DATASET_PLAN.md` into a concrete, Pydantic-validated shape; each field's
docstring cites the exact section it derives from. Three top-level
records, stored as three separate files (per `DATASET_PLAN.md` §14's
diffability requirement):

- `repository_manifest.json` -- a `RepositoryManifest` (one entry per
  corpus repository, §2-§8, §14).
- `queries.jsonl` -- one `TIQSQueryRecord` per line (§9-§13).
- `reproducibility.json` -- one `ReproducibilityMetadata` object per
  dataset version (§14).

**Design decision: split lives only on the repository, not the query.**
`TIQSQueryRecord` deliberately has no `split` field of its own. Per
`DATASET_PLAN.md` §9, a query "inherits" its repository's split; giving
the query its own, independently-settable `split` field would create a
second source of truth that could drift from the manifest and reopen
exactly the leakage channel §9 exists to close. A query's split is
always resolved by joining `TIQSQueryRecord.repository_id` against
`RepositoryManifest` -- see `resolve_split` at the bottom of this
module.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from tara.core.types import Language, TaskType


class RepositoryLicense(str, Enum):
    """Corpus-eligible licenses, per `DATASET_PLAN.md` §2's exact eligibility list.

    A closed enum, not a free string: §2 states repository eligibility
    requires "MIT, Apache-2.0, or BSD (2- or 3-clause)" -- an explicit,
    closed list. Encoding it as an enum enforces that eligibility rule
    at the schema level rather than relying on a validator to re-check a
    free-text field against the same list.
    """

    MIT = "MIT"
    APACHE_2_0 = "Apache-2.0"
    BSD_2_CLAUSE = "BSD-2-Clause"
    BSD_3_CLAUSE = "BSD-3-Clause"


class SizeBucket(str, Enum):
    """Repository size tier by lines of code, per `DATASET_PLAN.md` §4's exact thresholds."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class DatasetSplit(str, Enum):
    """Repository-level train/validation/test assignment, per `DATASET_PLAN.md` §6-§8.

    Assigned once per repository (`RepositoryManifestEntry.split`), never
    per query -- see this module's docstring.
    """

    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


class PromptFraming(str, Enum):
    """The three rotated query-authoring framings, per `DATASET_PLAN.md` §10 step 1."""

    ISSUE_TRACKER = "issue_tracker"
    CODE_REVIEW_COMMENT = "code_review_comment"
    ONBOARDING_QUESTION = "onboarding_question"


class AnnotatorRole(str, Enum):
    """Which step of `DATASET_PLAN.md` §10/§12's workflow an `AnnotatorMetadata` records.

    Distinct roles, not a single generic "annotator" tag, so the
    double-labeling and adjudication structure the agreement measures in
    §13 depend on is visible directly in the data rather than needing to
    be inferred from field position.
    """

    AUTHOR = "author"
    """Wrote the query (§10 step 1) and, later, blind-relabeled it (§10 step 3)."""
    INDEPENDENT_LABELER = "independent_labeler"
    """Labeled the query without seeing the author's identity or label (§10 step 2)."""
    SPOT_CHECKER = "spot_checker"
    """Independently re-derived a relevant-context set for the 20% spot-check sample (§11-§12)."""
    ADJUDICATOR = "adjudicator"
    """Resolved a disagreement between two labels (§10 step 4)."""


class RelevanceTier(str, Enum):
    """Graded relevance, per `DATASET_PLAN.md` §11's optional tiering scheme.

    §11 marks graded (vs. binary) relevance as **TBD**. Modeling it as an
    enum used through an `Optional` field (see
    `RelevantContextEntry.relevance_tier`) reflects that TBD status
    honestly: `None` means "this annotation only recorded binary
    relevance," not "this file has no relevance." §11 also requires that
    *if* tiering is adopted, the scheme is fixed before the calibration
    round -- once adopted, it must be applied consistently within a
    dataset version, which `evaluation.tiqs.validation` checks for.
    """

    PRIMARY = "primary"
    SECONDARY = "secondary"


class ReferenceOutputKind(str, Enum):
    """Which reference-output format a query uses, per `DATASET_PLAN.md` §11."""

    ACCEPTANCE_CRITERIA = "acceptance_criteria"
    """A rubric: a checkable list of properties a correct output must satisfy (the default)."""
    CANONICAL_CODE = "canonical_code"
    """A single canonical code string -- used only where the query has one clear correct answer."""


class DisagreementField(str, Enum):
    """Which part of a query's annotation an `AdjudicationRecord` resolves, per §10 step 4."""

    TASK_TYPE = "task_type"
    RELEVANT_CONTEXT = "relevant_context"


class AnnotatorMetadata(BaseModel):
    """Who performed an annotation action, in what role, and when.

    Embedded (composition, not inline `annotator_id`/`timestamp` pairs)
    into every record an annotator produces (`TaskTypeLabel`,
    `RelevantContextSet`, `AdjudicationRecord`, and query authorship) so
    the same shape is validated identically everywhere it appears,
    satisfying `DATASET_PLAN.md` §10's tooling requirement to capture
    "annotator identifier, and timestamp" on every annotation action.
    """

    annotator_id: str = Field(
        ..., min_length=1, description="Stable, pseudonymous identifier for the annotator."
    )
    role: AnnotatorRole = Field(..., description="Which workflow step this action corresponds to.")
    timestamp: datetime = Field(..., description="UTC timestamp this action was recorded.")


class RepositoryManifestEntry(BaseModel):
    """One corpus repository's identity, eligibility properties, and split assignment.

    Per `DATASET_PLAN.md` §14: "every corpus repository's identity
    (source URL, pinned commit SHA, license, language, size bucket,
    domain category, assigned split) is recorded in a single
    version-controlled manifest file."
    """

    repository_id: str = Field(
        ..., min_length=1, description="Stable identifier, unique across the manifest."
    )
    source_url: str = Field(..., min_length=1, description="The repository's canonical clone URL.")
    commit_sha: str = Field(
        ...,
        pattern=r"^[0-9a-f]{40}$",
        description="The pinned commit, a full 40-character lowercase hex SHA (§8 sealing protocol "
        "step 1: pinned before any TIQS annotation on that repository begins).",
    )
    license: RepositoryLicense = Field(..., description="Corpus eligibility requirement, §2.")
    language: Language = Field(
        ..., description="The repository's dominant supported language, for the per-split, "
        "per-language coverage requirement (§3). `Language.UNKNOWN` is not a valid manifest "
        "entry -- corpus eligibility requires a determinate, supported language."
    )
    size_bucket: SizeBucket = Field(
        ..., description="Derived from `lines_of_code`; see the validator below."
    )
    lines_of_code: int = Field(
        ...,
        ge=0,
        le=200_000,
        description="Lines of code. Repositories above 200,000 LOC are out of scope for v1 (§4).",
    )
    domain: str = Field(
        ...,
        min_length=1,
        description="The repository's general purpose/subject area (§5). Deliberately a free "
        "string, not a closed enum -- §5 states its working taxonomy (e.g. 'web_frameworks', "
        "'cli_tools', 'data_processing', 'systems_infrastructure', 'general_libraries', "
        "'research_tooling') is 'not a claim of completeness'; closing it here would overstate "
        "that taxonomy's finality.",
    )
    split: DatasetSplit = Field(
        ..., description="This repository's train/validation/test assignment (§6-§8). Every query "
        "authored against this repository inherits this split -- see this module's docstring."
    )
    added_at: datetime = Field(
        ..., description="UTC timestamp this entry was added to the manifest."
    )
    changelog_note: str | None = Field(
        default=None,
        description="Required when this entry represents a re-pin of a previously-selected "
        "repository (§14: 'the reason recorded in the manifest's changelog, never a silent "
        "substitution'). None for a repository's original, first-ever manifest entry.",
    )

    @model_validator(mode="after")
    def _validate_size_bucket_matches_loc(self) -> RepositoryManifestEntry:
        expected = _size_bucket_for_loc(self.lines_of_code)
        if self.size_bucket is not expected:
            raise ValueError(
                f"size_bucket={self.size_bucket.value!r} does not match lines_of_code="
                f"{self.lines_of_code} (expected {expected.value!r} per DATASET_PLAN.md §4's "
                f"thresholds: small <5,000, medium 5,000-50,000, large 50,000-200,000)."
            )
        return self

    @model_validator(mode="after")
    def _validate_language_is_determinate(self) -> RepositoryManifestEntry:
        if self.language is Language.UNKNOWN:
            raise ValueError(
                f"repository_id={self.repository_id!r}: language must not be Language.UNKNOWN -- "
                f"corpus eligibility (DATASET_PLAN.md §3) requires a determinate, supported "
                f"language so the per-split, per-language coverage requirement can be checked."
            )
        return self


def _size_bucket_for_loc(lines_of_code: int) -> SizeBucket:
    if lines_of_code < 5_000:
        return SizeBucket.SMALL
    if lines_of_code < 50_000:
        return SizeBucket.MEDIUM
    return SizeBucket.LARGE


class RepositoryManifest(BaseModel):
    """The complete, version-controlled corpus manifest (`repository_manifest.json`)."""

    schema_version: str = Field(
        ..., min_length=1, description="Schema version of this manifest file."
    )
    entries: list[RepositoryManifestEntry] = Field(
        default_factory=list, description="One entry per corpus repository, order-independent."
    )


class RelevantContextEntry(BaseModel):
    """One ground-truth relevant-context item: a file or symbol a competent developer would need.

    Per `DATASET_PLAN.md` §11: "Symbol-level entries use the same
    node-id scheme already implemented by
    `tara.context.models.build_symbol_node_id`" -- and, by direct
    extension, file-level entries use `build_file_node_id`. Both id
    families begin with the literal prefix `file::`, which is what lets
    `evaluation.tiqs.validation` distinguish and existence-check them
    without a third, TIQS-specific identity scheme.
    """

    node_id: str = Field(
        ...,
        min_length=1,
        description="A `tara.context.models.build_file_node_id` or `build_symbol_node_id` value.",
    )
    relevance_tier: RelevanceTier | None = Field(
        default=None, description="Graded relevance, if this dataset version adopted tiering; "
        "None for binary-only relevance. See `RelevanceTier`'s docstring."
    )


class RelevantContextSet(BaseModel):
    """One annotator's complete relevant-context judgment for a query.

    A `TIQSQueryRecord` holds one or more of these: the original
    annotator's set, plus, for the 20% spot-check sample (§11-§12), a
    second, independently-derived set from a `SPOT_CHECKER`.
    """

    entries: list[RelevantContextEntry] = Field(
        ..., min_length=1, description="The minimal set of files/symbols needed to address the "
        "query, per §11. Non-empty: every query has at least one relevant location by definition "
        "of being answerable against the repository."
    )
    annotator: AnnotatorMetadata = Field(..., description="Who derived this set, and when.")


class TaskTypeLabel(BaseModel):
    """One independent `TaskType` assignment for a query, per `DATASET_PLAN.md` §10 steps 2-3."""

    task_type: TaskType = Field(..., description="The assigned category.")
    annotator: AnnotatorMetadata = Field(..., description="Who assigned it, and when.")


class ReferenceOutput(BaseModel):
    """An optional generation-quality reference, per `DATASET_PLAN.md` §11."""

    kind: ReferenceOutputKind = Field(..., description="Which reference format `content` uses.")
    content: list[str] = Field(
        ...,
        min_length=1,
        description="Rubric items (one checkable property per entry) when `kind` is "
        "ACCEPTANCE_CRITERIA; exactly one entry (the canonical code string) when `kind` is "
        "CANONICAL_CODE.",
    )

    @model_validator(mode="after")
    def _validate_canonical_code_is_single_entry(self) -> ReferenceOutput:
        if self.kind is ReferenceOutputKind.CANONICAL_CODE and len(self.content) != 1:
            raise ValueError(
                f"ReferenceOutput.kind=CANONICAL_CODE requires exactly one `content` entry "
                f"(the canonical code string), got {len(self.content)}."
            )
        return self


class AdjudicationRecord(BaseModel):
    """The resolution of a disagreement between two independent labels, per §10 step 4.

    Exactly one of `resolved_task_type` / `resolved_relevant_context` is
    set, matching `field`. `DATASET_PLAN.md` §10 allows an adjudicator
    to "select one, merge them, or escalate to a guideline revision" --
    all three outcomes are represented as a resolved value plus
    `rationale`; a guideline-revision escalation is recorded as free text
    in `rationale` with `resolved_task_type`/`resolved_relevant_context`
    left at the adjudicator's best-current resolution (adjudication must
    still leave the query with a concrete label, per §12 check 4's
    downstream existence-check requirement).
    """

    field: DisagreementField = Field(..., description="Which part of the annotation this resolves.")
    adjudicator: AnnotatorMetadata = Field(..., description="Who adjudicated, and when.")
    resolved_task_type: TaskType | None = Field(
        default=None, description="Set iff `field` is TASK_TYPE."
    )
    resolved_relevant_context: list[RelevantContextEntry] | None = Field(
        default=None, description="Set iff `field` is RELEVANT_CONTEXT."
    )
    rationale: str = Field(
        ...,
        min_length=1,
        description="Why this resolution was chosen over the two disagreeing labels.",
    )

    @model_validator(mode="after")
    def _validate_resolved_value_matches_field(self) -> AdjudicationRecord:
        if self.field is DisagreementField.TASK_TYPE:
            if self.resolved_task_type is None or self.resolved_relevant_context is not None:
                raise ValueError(
                    "AdjudicationRecord.field=TASK_TYPE requires resolved_task_type set and "
                    "resolved_relevant_context unset."
                )
            if self.resolved_task_type is TaskType.UNKNOWN:
                raise ValueError(
                    "AdjudicationRecord.resolved_task_type must not be TaskType.UNKNOWN -- an "
                    "adjudicator has full context and must resolve to a substantive category."
                )
        else:
            if self.resolved_relevant_context is None or self.resolved_task_type is not None:
                raise ValueError(
                    "AdjudicationRecord.field=RELEVANT_CONTEXT requires resolved_relevant_context "
                    "set and resolved_task_type unset."
                )
            if len(self.resolved_relevant_context) == 0:
                raise ValueError("AdjudicationRecord.resolved_relevant_context must be non-empty.")
        return self


class TIQSQueryRecord(BaseModel):
    """One fully-annotated TIQS query: `queries.jsonl`'s per-line record.

    Deliberately self-contained: every field a downstream consumer needs
    (query text, both independent labels, both relevant-context sets
    where a spot-check exists, any adjudication, an optional reference
    output) lives on this one record, so consuming `queries.jsonl` never
    requires joining against a second file except `repository_manifest.json`
    for split resolution (see this module's docstring).
    """

    query_id: str = Field(
        ..., min_length=1, description="Globally unique across the dataset, e.g. "
        "'<repository_id>-<NNN>'. Uniqueness is a whole-dataset property, checked by "
        "`evaluation.tiqs.validation`, not by this model in isolation."
    )
    repository_id: str = Field(
        ..., min_length=1, description="Must match a `RepositoryManifestEntry.repository_id`."
    )
    query_text: str = Field(..., min_length=1, description="The realistic developer query itself.")
    prompt_framing: PromptFraming = Field(
        ...,
        description="Which of the three rotated authoring framings produced this query "
        "(§10 step 1).",
    )
    authored_by: AnnotatorMetadata = Field(
        ..., description="The query's original author (role=AUTHOR, §10 step 1)."
    )
    task_type_labels: list[TaskTypeLabel] = Field(
        default=..., min_length=1, description="Independent TaskType labels -- 2 expected during "
        "full-scale annotation (§10 steps 2-3: the independent labeler's label, then the author's "
        "own blind self-relabel). A single-entry list is valid but flagged by the validator as "
        "'not yet double-labeled', since §13's agreement measure requires exactly 2."
    )
    adjudicated_task_type: TaskType | None = Field(
        default=None, description="Set only if the two `task_type_labels` disagreed and an "
        "AdjudicationRecord resolved it (§10 step 4). None when the two labels already agreed."
    )
    relevant_context_sets: list[RelevantContextSet] = Field(
        default=..., min_length=1, description="1 set from the original annotator, plus a 2nd from "
        "a SPOT_CHECKER for the ~20% spot-checked sample (§11-§12)."
    )
    adjudicated_relevant_context: list[RelevantContextEntry] | None = Field(
        default=None, description="Set only if this query was spot-checked and the two "
        "relevant-context sets disagreed materially enough to require adjudication."
    )
    adjudication_records: list[AdjudicationRecord] = Field(
        default_factory=list,
        description="Every adjudication performed for this query (0, 1, or 2 -- at most one per "
        "disagreement field).",
    )
    reference_output: ReferenceOutput | None = Field(
        default=None,
        description="Present only where a generation-quality reference is feasible (§11).",
    )
    notes: str | None = Field(
        default=None, description="Free-text annotator notes, e.g. grounding rationale."
    )

    @model_validator(mode="after")
    def _validate_task_type_labels_not_unknown(self) -> TIQSQueryRecord:
        for label in self.task_type_labels:
            if label.task_type is TaskType.UNKNOWN:
                raise ValueError(
                    f"query_id={self.query_id!r}: a human-assigned TaskTypeLabel must not be "
                    f"TaskType.UNKNOWN -- an annotator has full query context and must assign a "
                    f"substantive category (UNKNOWN is reserved for the automated classifier's own "
                    f"low-confidence output, not for ground-truth annotation)."
                )
        return self

    @model_validator(mode="after")
    def _validate_adjudicated_task_type_requires_record(self) -> TIQSQueryRecord:
        has_task_type_adjudication = any(
            record.field is DisagreementField.TASK_TYPE for record in self.adjudication_records
        )
        if self.adjudicated_task_type is not None and not has_task_type_adjudication:
            raise ValueError(
                f"query_id={self.query_id!r}: adjudicated_task_type is set but no "
                f"AdjudicationRecord with field=TASK_TYPE exists in adjudication_records."
            )
        return self

    @model_validator(mode="after")
    def _validate_adjudicated_relevant_context_requires_record(self) -> TIQSQueryRecord:
        has_context_adjudication = any(
            record.field is DisagreementField.RELEVANT_CONTEXT
            for record in self.adjudication_records
        )
        if self.adjudicated_relevant_context is not None and not has_context_adjudication:
            raise ValueError(
                f"query_id={self.query_id!r}: adjudicated_relevant_context is set but no "
                f"AdjudicationRecord with field=RELEVANT_CONTEXT exists in adjudication_records."
            )
        return self


class ChangelogEntry(BaseModel):
    """One dataset-version changelog entry.

    Per `DATASET_PLAN.md` §14's immutable-versioning rule.
    """

    version: str = Field(..., min_length=1, description="The dataset version this entry describes.")
    date: datetime = Field(..., description="UTC timestamp this version was tagged.")
    description: str = Field(
        ..., min_length=1, description="What changed relative to the prior version."
    )
    changed_repository_ids: list[str] = Field(
        default_factory=list, description="Repository ids added, removed, or re-pinned in this "
        "version, if any (§14: any re-pin is itself a version bump with the reason recorded here)."
    )


class ReproducibilityMetadata(BaseModel):
    """`reproducibility.json`: the version, provenance, and changelog for one TIQS release.

    Per `DATASET_PLAN.md` §14: every tagged version is immutable; a
    later-discovered error is corrected by publishing a new version with
    a changelog entry, never by silently editing a previously tagged
    version. This model's `changelog` is append-only by convention (not
    itself enforced here, since enforcing "never remove an entry" is a
    property of *how this file is edited over time*, not of any single
    snapshot of it).
    """

    dataset_version: str = Field(
        ..., min_length=1, description="e.g. 'v0.1-pilot' (calibration round only, never released, "
        "§10) or 'v1.0' (first frozen version used for paper results, §14)."
    )
    guideline_version: str = Field(
        ..., min_length=1, description="Version of the annotation guideline document this dataset "
        "version was produced under (§14: guideline documents are versioned alongside the dataset)."
    )
    tara_git_commit: str | None = Field(
        default=None, description="The TARA repository commit this dataset version's tooling "
        "(this schema, the validator) was produced against, if known."
    )
    created_at: datetime = Field(..., description="UTC timestamp this version was created.")
    changelog: list[ChangelogEntry] = Field(
        default_factory=list,
        description="Every version's changelog entry, in chronological order, including this one.",
    )


def resolve_split(query: TIQSQueryRecord, manifest: RepositoryManifest) -> DatasetSplit:
    """Return `query`'s train/validation/test split, resolved via its repository.

    Args:
        query: The query to resolve.
        manifest: The repository manifest `query.repository_id` must
            appear in exactly once (see `evaluation.tiqs.validation` for
            the dataset-wide checks that guarantee this).

    Returns:
        The `DatasetSplit` of the manifest entry whose `repository_id`
        matches `query.repository_id`.

    Raises:
        KeyError: If no manifest entry matches `query.repository_id`.
    """
    for entry in manifest.entries:
        if entry.repository_id == query.repository_id:
            return entry.split
    raise KeyError(
        f"query_id={query.query_id!r} references repository_id={query.repository_id!r}, "
        f"which does not appear in the manifest."
    )
