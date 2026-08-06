"""The normalized `FeatureVector`: this milestone's entire output contract.

Grouped into five sub-models, one per requirement group (Query,
Repository, Graph, Structural, Resource) -- not one flat model -- so the
schema stays traceable to the specification it implements, and each
group can be computed, tested, and documented independently
(`FEATURE_CATALOG.md`). `FeatureVector.to_flat_dict` is what makes the
composed object "suitable for machine learning" per the requirement:
a single flat mapping, one key per leaf feature, ready to become a
`pandas` row or a training-table column set.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from tara.core.types import Language


class RepositorySizeCategory(str, Enum):
    """A coarse repository-size bucket, thresholds configured via `FeatureExtractionSettings`."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class QueryFeatures(BaseModel):
    """Features describing the developer query's own text, independent of any repository."""

    length: int = Field(..., ge=0, description="Character length of the raw query text.")
    identifier_count: int = Field(
        ..., ge=0, description="Count of tokens shaped like a single code identifier "
        "(snake_case, camelCase, PascalCase, CONSTANT_CASE, or an acronym), e.g. 'fooBar', 'max_size'."
    )
    api_token_count: int = Field(
        ..., ge=0, description="Count of dotted compound tokens, e.g. 'os.path', 'requests.get' -- "
        "distinct from identifier_count, which only matches single-segment tokens."
    )
    has_question_keyword: bool = Field(..., description="Query contains a question-style word (how/why/what/where/explain/does).")
    has_bug_keyword: bool = Field(..., description="Query contains a bug/failure-related word (bug/fix/error/exception/crash/fail/broken).")
    has_test_keyword: bool = Field(..., description="Query contains a testing-related word (test/tests/testing/pytest/unittest).")
    has_refactor_keyword: bool = Field(..., description="Query contains a refactor-related word (refactor/rename/cleanup/simplify/restructure).")
    complexity: float = Field(
        ..., ge=0.0, le=1.0, description="A simple, explainable [0,1] heuristic combining normalized word "
        "count, identifier density, and clause count -- not a learned or validated score. See README.md."
    )


class RepositoryFeatures(BaseModel):
    """Features describing the repository's overall size and shape."""

    file_count: int = Field(..., ge=0, description="Number of successfully parsed files.")
    function_count: int = Field(..., ge=0, description="Number of functions and methods (RepositoryModel.functions).")
    class_count: int = Field(..., ge=0, description="Number of classes.")
    module_count: int = Field(
        ..., ge=0, description="Number of distinct top-level packages/modules (first path segment); "
        "coarser than file_count -- see README.md for why these two are not the same number."
    )
    avg_file_size_bytes: float = Field(..., ge=0.0, description="Mean file size in bytes across all files; 0.0 if there are none.")
    dominant_language: Language = Field(
        ..., description="Always Language.PYTHON if the repository has at least one file, else "
        "Language.UNKNOWN -- Parser V1 only ever parses Python files. See README.md."
    )


class GraphFeatures(BaseModel):
    """Features describing the structural graphs `RepositoryModel` carries."""

    import_density: float = Field(..., ge=0.0, description="Import graph density: len(import_graph) / max(file_count, 1).")
    call_density: float = Field(..., ge=0.0, description="Call graph density: len(call_graph) / max(function_count, 1).")
    inheritance_density: float = Field(..., ge=0.0, description="Inheritance graph density: len(inheritance_graph) / max(class_count, 1).")
    connected_components: int = Field(
        ..., ge=0, description="Connected components of the undirected, file-level projection of all "
        "three graphs combined (import edges directly; call/inheritance edges projected to the files "
        "their endpoints are defined in). 0 for a repository with no files."
    )
    avg_degree: float = Field(
        ..., ge=0.0, description="Average node degree (2 * edges / nodes) of that same combined, "
        "file-level graph. 0.0 for a repository with no files."
    )


class StructuralFeatures(BaseModel):
    """Features describing code organization and documentation density."""

    avg_functions_per_file: float = Field(..., ge=0.0, description="function_count / max(file_count, 1).")
    avg_classes_per_file: float = Field(..., ge=0.0, description="class_count / max(file_count, 1).")
    docstring_coverage_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of functions+classes with a non-empty docstring."
    )
    comment_coverage_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of source lines that are '#' comment lines, averaged "
        "across files, re-read from disk via RepositoryModel.root_path. 0.0 if disabled "
        "(FeatureExtractionSettings.enable_comment_coverage=False) or if the source is no longer "
        "accessible -- see README.md's Failure Modes."
    )


class ResourceFeatures(BaseModel):
    """Features estimating the cost of consuming this repository downstream."""

    estimated_repository_tokens: int = Field(
        ..., ge=0, description="Total file size in bytes divided by chars_per_token_estimate -- a rough, "
        "tokenizer-independent approximation, not an exact count from any specific LLM's tokenizer."
    )
    repository_size_category: RepositorySizeCategory = Field(
        ..., description="SMALL/MEDIUM/LARGE bucket by file_count, thresholds configured via "
        "FeatureExtractionSettings."
    )


class FeatureVector(BaseModel):
    """The complete, normalized feature representation of one (repository, query) pair.

    This is the Feature Extraction subsystem's entire output contract.
    Deterministic in every feature value for a fixed
    `(RepositoryModel, query_text, FeatureExtractionSettings)` triple;
    `computed_at` is provenance metadata, not a feature, and is
    explicitly excluded from `to_flat_dict`'s ML-facing output for
    exactly that reason.
    """

    repository_id: str = Field(..., description="The repository_id this feature vector was computed for.")
    commit_sha: str = Field(..., description="The pinned commit this feature vector was computed for.")
    query_text: str = Field(..., description="The raw developer query text these query_* features were computed from.")

    query: QueryFeatures
    repository: RepositoryFeatures
    graph: GraphFeatures
    structural: StructuralFeatures
    resource: ResourceFeatures

    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="When this FeatureVector was computed. Provenance, not a feature."
    )

    def to_flat_dict(self) -> dict[str, int | float | bool | str]:
        """Flatten every leaf feature into a single, group-prefixed mapping.

        This is the "suitable for machine learning" view: one row,
        scalar-valued columns, ready to become a `pandas.Series` or a
        line in a training table. Provenance fields (`repository_id`,
        `commit_sha`, `query_text`, `computed_at`) are intentionally
        excluded -- callers that want them for joining/auditing should
        read them directly off the `FeatureVector`, not from the
        feature row itself, so a training matrix never accidentally
        includes an identifier column as if it were a numeric feature.
        Enum-valued features (`dominant_language`, `repository_size_category`)
        are flattened to their string `.value`; encoding them (e.g.
        one-hot) is a modeling decision for the consumer, not this
        subsystem's job.

        Returns:
            A flat `{group_feature_name: value}` mapping, e.g.
            `{"query_length": 42, "repo_file_count": 12, ...}`. Every
            leaf field name is prefixed with its group name uniformly
            (field names were chosen to avoid any "graph_import_graph_density"
            -style stutter -- see `GraphFeatures.import_density` etc.).
        """
        flat: dict[str, int | float | bool | str] = {}
        for group_name, group in (
            ("query", self.query),
            ("repo", self.repository),
            ("graph", self.graph),
            ("structural", self.structural),
            ("resource", self.resource),
        ):
            for field_name, value in group.model_dump().items():
                flat[f"{group_name}_{field_name}"] = value.value if isinstance(value, Enum) else value
        return flat
