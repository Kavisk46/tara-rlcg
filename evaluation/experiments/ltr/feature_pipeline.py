"""Phase 2 -- turn raw RTS Dataset v1.0 rows into a numeric LTR feature matrix.

Consumes the per-query records already produced by the (frozen) TARA
RTS dataset-assembly pipeline (`query_id`, `repository_id`, `category`,
`difficulty`, `query_text`, `notes`, `candidates: [{file, grade,
reason}]`) and turns each `(query, candidate file)` pair into one row
of a numeric feature matrix suitable for a LightGBM `LGBMRanker`.

Two feature families:

1. **Retrieval-derived** (`lexical_*`, `dense_*`, `graph_*`, `hybrid_*`
   plus the query/repository/graph/structural/resource groups from
   `evaluation.rts_builder.feature_extraction`): computed by genuinely
   invoking the frozen Repository Loader -> Parser -> Feature
   Extraction -> Retrieval Executor chain against each repository's
   pinned-commit local clone. This is the primary, intended signal for
   the LEXICAL / DENSE / GRAPH / HYBRID ranking objective. When this
   pipeline is run with retrieval features disabled (`--no-retrieval`,
   for fast unit testing), every such column is `NaN` with a paired
   `*_available = 0` flag -- never a fabricated score.
2. **Structural/text** (query length, candidate file-path shape,
   annotation `reason` length): computed directly and cheaply from the
   dataset rows themselves, always available.

Categorical encoding, missing-value handling, and column order are all
deterministic and are the same regardless of which split is being
processed -- see `FEATURE_COLUMNS` (the single source of truth for
output column order) and `CategoryEncoder` (fit once on the training
split, then reused, never refit per-split -- see `train.py`).

This module never coerces the dataset's placeholder relevance grade
(`"TO_BE_ASSIGNED"`) into a numeric label. `validate_labels_are_numeric`
raises `UnlabeledDatasetError` instead -- see that function's docstring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

if __package__ in (None, ""):  # pragma: no cover - direct-execution convenience
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from evaluation.experiments.ltr.utils import (
    MERGED_DATASET_DIR, REPO_ROOT, RELEVANCE_GRADES, TO_BE_ASSIGNED, get_logger, read_jsonl,
)

logger = get_logger(__name__)


class FeaturePipelineError(Exception):
    """Base class for this module's own errors."""


class UnlabeledDatasetError(FeaturePipelineError):
    """Raised when a split has no usable (real, numeric) relevance grade.

    Deliberately distinct from silently mapping the placeholder grade
    `"TO_BE_ASSIGNED"` to `0` or any other number, which would
    fabricate a training signal that does not exist. Per RTS Dataset
    v1.0's own `dataset_card.md` ("Quality control"), every relevance
    grade in the shipped dataset is this exact placeholder pending
    human review.
    """


class SchemaError(FeaturePipelineError):
    """Raised when an input row does not match the expected RTS Dataset v1.0 schema."""


# ---------------------------------------------------------------------------
# Repository source URLs -- needed only to construct a RepositoryLoader call
# for a repository that is not already present under RepositoryLoaderSettings
# .clone_root. When `clone_root` is pointed at the repo checkout root (the
# default in this module), every one of these repositories is already
# cloned and pinned there, so `load_repository` reuses the existing clone
# and this URL is used only for RepositoryLoader's own input validation and
# manifest bookkeeping -- never to trigger a real network clone in the
# expected (already-cloned) case.
# ---------------------------------------------------------------------------
REPOSITORY_SOURCE_URLS: dict[str, str] = {
    "fastapi": "https://github.com/tiangolo/fastapi",
    "flask": "https://github.com/pallets/flask",
    "requests": "https://github.com/psf/requests",
    "click": "https://github.com/pallets/click",
    "celery": "https://github.com/celery/celery",
    "sqlalchemy": "https://github.com/sqlalchemy/sqlalchemy",
    "pandas": "https://github.com/pandas-dev/pandas",
    "scikit-learn": "https://github.com/scikit-learn/scikit-learn",
}

REPOSITORY_COMMIT_SHAS: dict[str, str] = {
    "fastapi": "a375f6b948b99fa4260129856bbf11d037f363ef",
    "flask": "6a2f545bfd8ed31e19066a299296917e034aca58",
    "requests": "1f6589ec3a1ee910f9a65cc3ceac60b26677bc0e",
    "click": "00e592cea702e0b2caa0dee42489fdb1c22cd845",
    "celery": "f109abf852525b69a1b6eee0457c6cd5561e0529",
    "sqlalchemy": "dc6a8b18a5bcda653e34aab2a70c7469dcd4300d",
    "pandas": "d0d07d18f9fe855529997e3fe16cf1d0c8ce5eb8",
    "scikit-learn": "9b9be3abddd88675c5dc2e3623e652cb7545a26c",
}
"""Pinned exactly as recorded in `evaluation/rts_builder/pilot/merged_dataset/reproducibility.md`.
Duplicated here (rather than parsed back out of the dataset files) so
this module has no runtime dependency on Markdown parsing; consistency
is enforced by `tests/test_feature_pipeline.py::test_pinned_commits_match_reproducibility_md`.
"""

DIFFICULTY_ORDER: dict[str, int] = {"easy": 0, "medium": 1, "hard": 2}

STRATEGIES = ("lexical", "dense", "graph", "hybrid")

# The single source of truth for output column order. Every function that
# emits a feature row MUST emit exactly these keys, in this order -- see
# `FeatureMatrix.feature_names` and `_row_to_vector`.
STRUCTURAL_FEATURE_COLUMNS: tuple[str, ...] = (
    "query_word_count",
    "query_char_count",
    "candidate_path_depth",
    "candidate_path_length",
    "candidate_is_test_file",
    "candidate_is_doc_file",
    "candidate_reason_word_count",
    "difficulty_ordinal",
)

RETRIEVAL_FEATURE_COLUMNS: tuple[str, ...] = tuple(
    f"{strategy}_{suffix}"
    for strategy in STRATEGIES
    for suffix in ("score", "rank", "retrieved", "available")
)

CATEGORICAL_STRUCTURAL_COLUMNS: tuple[str, ...] = ("category_code", "repository_id_code", "file_extension_code")

# Populated lazily the first time retrieval-derived FeatureVector.to_flat_dict()
# columns are observed (their exact set is defined by the frozen
# feature_extraction subsystem, not duplicated here by hand -- duplicating it
# would risk silent drift if that frozen module's catalog ever changes).
_QUERY_REPO_FEATURE_COLUMNS_CACHE: list[str] | None = None


@dataclass(frozen=True)
class FeatureMatrix:
    """The complete, ready-to-train (or ready-to-predict) output of this pipeline.

    Attributes:
        X: `(n_rows, n_features)` float64 matrix, column order == `feature_names`.
        y: `(n_rows,)` int array of relevance grades (only meaningful
            when the source rows had real numeric grades -- see
            `validate_labels_are_numeric`).
        group_sizes: `(n_groups,)` int array, LightGBM's "group"/"query
            boundary" format: `X[0:group_sizes[0]]` is the first
            query's candidates, `X[group_sizes[0]:group_sizes[0]+group_sizes[1]]`
            the second, and so on, in the same order as `query_ids`.
        feature_names: Column names, in `X`'s column order.
        categorical_feature_names: Subset of `feature_names` that are
            categorical (integer-coded), for `LGBMRanker(categorical_feature=...)`.
        query_ids: One entry per group, in `group_sizes` order.
        file_paths: One entry per row of `X`, in `X`'s row order.
        repository_ids: One entry per row of `X`, in `X`'s row order (for error analysis).
    """

    X: np.ndarray
    y: np.ndarray
    group_sizes: np.ndarray
    feature_names: list[str]
    categorical_feature_names: list[str]
    query_ids: list[str]
    file_paths: list[str]
    repository_ids: list[str]

    def __post_init__(self) -> None:
        if self.X.shape[0] != self.y.shape[0]:
            raise FeaturePipelineError(f"X has {self.X.shape[0]} rows but y has {self.y.shape[0]}")
        if self.X.shape[0] != len(self.file_paths):
            raise FeaturePipelineError(f"X has {self.X.shape[0]} rows but file_paths has {len(self.file_paths)}")
        if int(self.group_sizes.sum()) != self.X.shape[0]:
            raise FeaturePipelineError(
                f"group_sizes sums to {int(self.group_sizes.sum())} but X has {self.X.shape[0]} rows"
            )
        if len(self.group_sizes) != len(self.query_ids):
            raise FeaturePipelineError(
                f"{len(self.group_sizes)} groups but {len(self.query_ids)} query_ids"
            )


class CategoryEncoder:
    """A deterministic, fit-once label encoder for a single categorical column.

    Unlike `sklearn.preprocessing.LabelEncoder`, the vocabulary is
    always sorted before assigning codes, so the same set of categories
    always yields the same code assignment regardless of the order
    values were first observed in -- required for a model trained in
    one process to produce identical codes when re-loaded in another.
    An unseen category at transform time is mapped to a dedicated
    "unknown" code (`len(vocabulary)`), not to an existing category and
    not treated as an error, so a model trained on `train.jsonl` can
    still score a `validation.jsonl`/`test.jsonl` row whose category
    value never appeared in training (this cannot currently happen for
    `category`/`difficulty`/`repository_id`, whose vocabularies are
    fixed dataset-wide per `dataset_card.md`, but is guaranteed to be
    possible for `file_extension`, which is unbounded).
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._vocabulary: list[str] = []
        self._code_by_value: dict[str, int] = {}
        self._fitted = False

    def fit(self, values: list[str]) -> "CategoryEncoder":
        self._vocabulary = sorted(set(values))
        self._code_by_value = {v: i for i, v in enumerate(self._vocabulary)}
        self._fitted = True
        return self

    @property
    def unknown_code(self) -> int:
        return len(self._vocabulary)

    def transform_one(self, value: str) -> int:
        if not self._fitted:
            raise FeaturePipelineError(f"CategoryEncoder({self.name!r}) used before fit()")
        return self._code_by_value.get(value, self.unknown_code)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "vocabulary": self._vocabulary}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CategoryEncoder":
        enc = cls(d["name"])
        enc._vocabulary = list(d["vocabulary"])
        enc._code_by_value = {v: i for i, v in enumerate(enc._vocabulary)}
        enc._fitted = True
        return enc


@dataclass
class Encoders:
    """The three categorical encoders this pipeline fits, bundled for save/load."""

    category: CategoryEncoder
    repository_id: CategoryEncoder
    file_extension: CategoryEncoder

    @classmethod
    def fit(cls, rows: list[dict[str, Any]]) -> "Encoders":
        """Fit all three encoders on `rows` (conventionally, the training split only).

        Args:
            rows: Query records (each with a `candidates` list), as
                loaded from a split `.jsonl` file.
        """
        categories = [r["category"] for r in rows]
        repository_ids = [r["repository_id"] for r in rows]
        extensions = [_file_extension(c["file"]) for r in rows for c in r.get("candidates", [])]
        return cls(
            category=CategoryEncoder("category").fit(categories),
            repository_id=CategoryEncoder("repository_id").fit(repository_ids),
            file_extension=CategoryEncoder("file_extension").fit(extensions),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "category": self.category.to_dict(),
            "repository_id": self.repository_id.to_dict(),
            "file_extension": self.file_extension.to_dict(),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Encoders":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            category=CategoryEncoder.from_dict(payload["category"]),
            repository_id=CategoryEncoder.from_dict(payload["repository_id"]),
            file_extension=CategoryEncoder.from_dict(payload["file_extension"]),
        )


def _file_extension(file_path: str) -> str:
    """Return a file's extension (including the dot), or `"<none>"` for an extensionless path."""
    suffix = Path(file_path).suffix
    return suffix if suffix else "<none>"


def _is_test_file(file_path: str) -> bool:
    lowered = file_path.lower()
    return "test" in lowered


def _is_doc_file(file_path: str) -> bool:
    lowered = file_path.lower()
    return lowered.endswith((".rst", ".md", ".txt")) or "/doc" in lowered or lowered.startswith("doc")


def validate_labels_are_numeric(rows: list[dict[str, Any]], *, split_name: str) -> None:
    """Raise `UnlabeledDatasetError` unless at least one candidate has a real numeric grade.

    This is a hard gate, deliberately placed ahead of feature-matrix
    construction for any *training* or *evaluation* use (see `train.py`
    and `evaluate.py`, both of which call this before doing anything
    else) so that an unlabeled dataset fails immediately and legibly,
    rather than training "successfully" against a fabricated or
    accidentally-coerced label.

    Args:
        rows: Query records from one split.
        split_name: Used only for the error message.

    Raises:
        UnlabeledDatasetError: If every candidate's `grade` is the
            placeholder `"TO_BE_ASSIGNED"` (or there are no candidates
            at all).
    """
    total = 0
    placeholder = 0
    for row in rows:
        for c in row.get("candidates", []):
            total += 1
            if c.get("grade") == TO_BE_ASSIGNED:
                placeholder += 1
    if total == 0:
        raise UnlabeledDatasetError(f"{split_name}: contains 0 candidate rows -- nothing to label.")
    if placeholder == total:
        raise UnlabeledDatasetError(
            f"{split_name}: all {total} candidate rows have the placeholder grade "
            f"'{TO_BE_ASSIGNED}'. RTS Dataset v1.0 ships without human-assigned relevance "
            "grades (see merged_dataset/dataset_card.md, 'Quality control'). Training or "
            "evaluating against this split requires completing human annotation first "
            "(see merged_dataset/human_annotation_checklist.md-equivalent guidance per "
            "repository) and replacing every 'TO_BE_ASSIGNED' with an integer in "
            f"{RELEVANCE_GRADES}. Refusing to proceed rather than fabricate labels."
        )
    if placeholder > 0:
        logger.warning(
            "%s: %d/%d candidate rows (%.1f%%) still carry the placeholder grade '%s' and will "
            "be excluded from training/evaluation by build_feature_matrix's caller -- see "
            "train.py's row-filtering step.",
            split_name, placeholder, total, 100.0 * placeholder / total, TO_BE_ASSIGNED,
        )


class RetrievalFeatureProvider:
    """Genuinely invokes the frozen Repository Loader -> Parser -> Feature
    Extraction -> Retrieval Executor chain to compute, for a given
    `(repository_id, query_text)` pair, the Lexical/Dense/Graph/Hybrid
    retrieval results and the query/repository/graph/structural/resource
    `FeatureVector`.

    Not a redesign of any of those subsystems: this class only
    constructs and calls their existing public entry points
    (`RepositoryLoader.load_repository`,
    `PythonParserPipeline.parse_repository`, `FeatureExtractor.extract`,
    `RetrievalExecutor.execute_all`) and adds its own on-disk result
    cache (`cache_dir`) so repeated feature-pipeline runs against the
    same `(repository, query)` pairs -- e.g. across `train`/`validation`/
    `test`, or across repeated development iterations -- do not
    recompute retrieval or re-parse a repository already parsed in this
    process. The Parser subsystem also has its own independent
    persistent cache (`repository_model.json`); this class's cache is
    additive, not a replacement.

    Args:
        clone_root: Passed to `RepositoryLoaderSettings.clone_root`.
            Defaults to the parent of every repository checkout used
            throughout this project (`REPO_ROOT`), so that
            `RepositoryLoader` finds and reuses the already-pinned
            local clones (`REPO_ROOT/<repository_id>`) instead of
            attempting a fresh network clone.
        cache_dir: Where to persist retrieval results between runs.
    """

    def __init__(self, clone_root: Path = REPO_ROOT, cache_dir: Path | None = None) -> None:
        from evaluation.rts_builder.config import RepositoryLoaderSettings
        from evaluation.rts_builder.feature_extraction.config import FeatureExtractionSettings
        from evaluation.rts_builder.feature_extraction.extractor import FeatureExtractor
        from evaluation.rts_builder.parser.config import ParserSettings
        from evaluation.rts_builder.parser.pipeline import PythonParserPipeline
        from evaluation.rts_builder.repository_loader import RepositoryLoader
        from evaluation.rts_builder.retrieval_executor.executor import RetrievalExecutor

        self._loader = RepositoryLoader(RepositoryLoaderSettings(clone_root=str(clone_root)))
        self._parser_pipeline = PythonParserPipeline(ParserSettings())
        self._feature_extractor = FeatureExtractor(FeatureExtractionSettings())
        self._retrieval_executor = RetrievalExecutor()

        self._cache_dir = cache_dir or (Path(__file__).resolve().parent / "outputs" / "retrieval_cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._repository_model_by_id: dict[str, Any] = {}
        self._feature_vector_by_repo: dict[str, Any] = {}

    def _cache_path(self, repository_id: str, query_text: str) -> Path:
        digest = hashlib.sha256(query_text.encode("utf-8")).hexdigest()[:16]
        return self._cache_dir / repository_id / f"{digest}.json"

    def get_repository_model(self, repository_id: str) -> Any:
        """Load + parse `repository_id` once per process, reusing the Parser's own on-disk cache."""
        if repository_id in self._repository_model_by_id:
            return self._repository_model_by_id[repository_id]
        if repository_id not in REPOSITORY_SOURCE_URLS:
            raise FeaturePipelineError(f"Unknown repository_id {repository_id!r}; not in REPOSITORY_SOURCE_URLS.")
        commit_sha = REPOSITORY_COMMIT_SHAS[repository_id]
        logger.info("Loading repository %s @ %s", repository_id, commit_sha[:8])
        repository = self._loader.load_repository(
            repository_id=repository_id, source_url=REPOSITORY_SOURCE_URLS[repository_id], commit_sha=commit_sha
        )
        logger.info("Parsing repository %s (this may take a while on first run)", repository_id)
        model = self._parser_pipeline.parse_repository(repository)
        logger.info(
            "Parsed %s: %d files, %d functions, %d classes (from_cache=%s)",
            repository_id, len(model.files), len(model.functions), len(model.classes), model.from_cache,
        )
        self._repository_model_by_id[repository_id] = model
        return model

    def get_query_feature_vector(self, repository_id: str, query_text: str) -> Any:
        """Compute (or reuse, within this process) the `FeatureVector` for one `(repo, query)` pair."""
        key = (repository_id, query_text)
        cached = self._feature_vector_by_repo.get(key)
        if cached is not None:
            return cached
        model = self.get_repository_model(repository_id)
        vector = self._feature_extractor.extract(model, query_text)
        self._feature_vector_by_repo[key] = vector
        return vector

    def get_retrieval_result(self, repository_id: str, query_text: str) -> Any:
        """Compute (or load from the on-disk cache) the four-strategy `RetrievalExecutionResult`."""
        from evaluation.rts_builder.retrieval_executor.models import RetrievalExecutionResult

        cache_path = self._cache_path(repository_id, query_text)
        if cache_path.is_file():
            logger.debug("Retrieval cache hit: %s", cache_path)
            return RetrievalExecutionResult.model_validate_json(cache_path.read_text(encoding="utf-8"))

        model = self.get_repository_model(repository_id)
        feature_vector = self.get_query_feature_vector(repository_id, query_text)
        logger.info("Executing lexical/dense/graph/hybrid retrieval for %s: %r", repository_id, query_text[:60])
        result = self._retrieval_executor.execute_all(model, feature_vector, query_text)

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(result.model_dump_json(), encoding="utf-8")
        return result


def _strategy_lookup(result_files: list[Any]) -> dict[str, tuple[float, int]]:
    """`{file_path: (score, 1-indexed rank)}` for one strategy's `retrieved_files`."""
    return {f.file_path: (f.score, i + 1) for i, f in enumerate(result_files)}


def _retrieval_columns_for_candidate(
    file_path: str, retrieval_result: Any | None
) -> dict[str, float]:
    """Build the 16 `{strategy}_{score,rank,retrieved,available}` columns for one candidate.

    Args:
        file_path: The candidate's repository-relative path.
        retrieval_result: A `RetrievalExecutionResult`, or `None` if
            retrieval features are disabled for this run (all columns
            become unavailable, not zero).

    Returns:
        Exactly the 16 keys named in `RETRIEVAL_FEATURE_COLUMNS`.
    """
    out: dict[str, float] = {}
    for strategy in STRATEGIES:
        if retrieval_result is None:
            out[f"{strategy}_score"] = np.nan
            out[f"{strategy}_rank"] = np.nan
            out[f"{strategy}_retrieved"] = 0.0
            out[f"{strategy}_available"] = 0.0
            continue
        strategy_result = getattr(retrieval_result, strategy)
        lookup = _strategy_lookup(strategy_result.retrieved_files)
        if file_path in lookup:
            score, rank = lookup[file_path]
            out[f"{strategy}_score"] = float(score)
            out[f"{strategy}_rank"] = float(rank)
            out[f"{strategy}_retrieved"] = 1.0
        else:
            # Retrieval ran but did not surface this candidate in its top_k:
            # a real, informative "not retrieved" signal, not a missing value.
            out[f"{strategy}_score"] = 0.0
            out[f"{strategy}_rank"] = float(len(strategy_result.retrieved_files) + 1)
            out[f"{strategy}_retrieved"] = 0.0
        out[f"{strategy}_available"] = 1.0
    return out


ENUM_COLUMN_VOCABULARIES: dict[str, tuple[str, ...]] = {
    # Fixed, sorted vocabularies sourced directly from the frozen types they
    # come from -- not fit at runtime -- so their integer codes are stable
    # across every process/run without needing a saved encoder for them:
    #   - "repo_dominant_language" flattens FeatureVector.repository.dominant_language,
    #     a `tara.core.types.Language` (str) Enum.
    #   - "resource_repository_size_category" flattens
    #     FeatureVector.resource.repository_size_category, a
    #     `evaluation.rts_builder.feature_extraction.models.RepositorySizeCategory` (str) Enum.
    # Both enums are part of the frozen subsystems' own data contracts (see
    # their docstrings), so hardcoding their value sets here does not risk
    # silent drift the way re-deriving them from observed data would.
    "repo_dominant_language": ("c", "cpp", "go", "java", "javascript", "python", "rust", "typescript", "unknown"),
    "resource_repository_size_category": ("large", "medium", "small"),
}


def _encode_enum_value(column: str, value: str) -> float:
    """Look up `value`'s fixed ordinal code within `ENUM_COLUMN_VOCABULARIES[column]`.

    Args:
        column: The flat-dict key this value came from.
        value: The Enum's `.value` string, as produced by `FeatureVector.to_flat_dict()`.

    Returns:
        The value's index in the fixed vocabulary, or
        `len(vocabulary)` (an explicit "unknown value" code) if
        `column` has no registered vocabulary or `value` is not in it
        -- never silently 0, which would be indistinguishable from a
        real first-position value.
    """
    vocabulary = ENUM_COLUMN_VOCABULARIES.get(column)
    if vocabulary is None:
        logger.warning("No fixed vocabulary registered for enum-valued column %r; encoding as 'unknown'.", column)
        return 0.0
    try:
        return float(vocabulary.index(value.lower()))
    except ValueError:
        logger.warning("Value %r for column %r is not in its registered vocabulary %r.", value, column, vocabulary)
        return float(len(vocabulary))


def _query_repo_feature_columns(feature_vector: Any | None, template_keys: list[str]) -> dict[str, float]:
    """Flatten a `FeatureVector` (or produce all-`NaN` placeholders) into numeric columns.

    Args:
        feature_vector: The frozen Feature Extraction subsystem's
            output for this `(repository, query)` pair, or `None` if
            retrieval/feature-extraction is disabled for this run.
        template_keys: The full set of flat-dict keys to emit (from a
            previously-seen `FeatureVector`), used to keep column
            identity stable across rows even when `feature_vector` is
            `None` for this particular row.
    """
    if feature_vector is None:
        return {k: np.nan for k in template_keys}
    flat = feature_vector.to_flat_dict()
    out: dict[str, float] = {}
    for k, v in flat.items():
        if isinstance(v, bool):
            out[k] = float(v)
        elif isinstance(v, (int, float)):
            out[k] = float(v)
        else:
            # Enum-valued (e.g. resource_repository_size_category, repo_dominant_language):
            # encode via this column's fixed, hardcoded vocabulary -- see
            # ENUM_COLUMN_VOCABULARIES's docstring for why this is safe to hardcode.
            out[k] = _encode_enum_value(k, str(v))
    return out


def build_feature_matrix(
    rows: list[dict[str, Any]],
    *,
    encoders: Encoders,
    retrieval_provider: RetrievalFeatureProvider | None,
    require_numeric_labels: bool,
) -> FeatureMatrix:
    """Turn a list of query records into a `FeatureMatrix`.

    Args:
        rows: Query records (as loaded from a split `.jsonl` file).
        encoders: Fitted `Encoders` (fit on the *training* split only
            -- see `train.py`; passing encoders fit on validation/test
            would leak information and is a caller error, not checked
            here).
        retrieval_provider: If given, used to compute real
            lexical/dense/graph/hybrid + query/repo/graph/structural/
            resource features by invoking the frozen subsystems. If
            `None`, every such column is emitted as `NaN`/unavailable
            (see `_retrieval_columns_for_candidate`) -- fast, for unit
            tests and schema/shape checks that do not need real
            retrieval signal.
        require_numeric_labels: If `True`, rows whose candidate `grade`
            is the placeholder are dropped from the output (with a
            logged count) rather than included with a fabricated label;
            if a query's *entire* candidate list is placeholder-only,
            that query is dropped from the group structure entirely.
            If `False`, every row is included and `y` is `0` for any
            placeholder grade (only appropriate for *inference*, where
            no label is used downstream at all -- `train.py` and
            `evaluate.py` both pass `True`).

    Returns:
        A `FeatureMatrix` with deterministic column order
        (`STRUCTURAL_FEATURE_COLUMNS + RETRIEVAL_FEATURE_COLUMNS +`
        query/repo flat-dict columns, discovered from the first row
        that has them `+ CATEGORICAL_STRUCTURAL_COLUMNS`, always last).
    """
    global _QUERY_REPO_FEATURE_COLUMNS_CACHE

    feature_rows: list[dict[str, float]] = []
    labels: list[int] = []
    group_sizes: list[int] = []
    query_ids: list[str] = []
    file_paths: list[str] = []
    repository_ids: list[str] = []

    n_dropped_rows = 0
    n_dropped_queries = 0

    for row in rows:
        query_text = row["query_text"]
        repository_id = row["repository_id"]
        candidates = row.get("candidates", [])

        retrieval_result = None
        feature_vector = None
        if retrieval_provider is not None:
            retrieval_result = retrieval_provider.get_retrieval_result(repository_id, query_text)
            feature_vector = retrieval_provider.get_query_feature_vector(repository_id, query_text)
            if _QUERY_REPO_FEATURE_COLUMNS_CACHE is None:
                _QUERY_REPO_FEATURE_COLUMNS_CACHE = sorted(feature_vector.to_flat_dict().keys())

        template_keys = _QUERY_REPO_FEATURE_COLUMNS_CACHE or []

        this_query_rows: list[dict[str, float]] = []
        this_query_labels: list[int] = []
        this_query_files: list[str] = []

        for c in candidates:
            grade_raw = c.get("grade")
            if grade_raw == TO_BE_ASSIGNED or grade_raw is None:
                if require_numeric_labels:
                    n_dropped_rows += 1
                    continue
                label = 0
            else:
                try:
                    label = int(grade_raw)
                except (TypeError, ValueError) as exc:
                    raise SchemaError(
                        f"{row['query_id']}: candidate grade {grade_raw!r} is neither the placeholder "
                        f"{TO_BE_ASSIGNED!r} nor an int."
                    ) from exc
                if label not in RELEVANCE_GRADES:
                    raise SchemaError(
                        f"{row['query_id']}: candidate grade {label} is out of the valid range {RELEVANCE_GRADES}."
                    )

            file_path = c["file"]
            structural = {
                "query_word_count": float(len(query_text.split())),
                "query_char_count": float(len(query_text)),
                "candidate_path_depth": float(file_path.count("/")),
                "candidate_path_length": float(len(file_path)),
                "candidate_is_test_file": float(_is_test_file(file_path)),
                "candidate_is_doc_file": float(_is_doc_file(file_path)),
                "candidate_reason_word_count": float(len(str(c.get("reason", "")).split())),
                "difficulty_ordinal": float(DIFFICULTY_ORDER.get(row["difficulty"], -1)),
            }
            retrieval_cols = _retrieval_columns_for_candidate(file_path, retrieval_result)
            query_repo_cols = _query_repo_feature_columns(feature_vector, template_keys)
            categorical = {
                "category_code": float(encoders.category.transform_one(row["category"])),
                "repository_id_code": float(encoders.repository_id.transform_one(repository_id)),
                "file_extension_code": float(encoders.file_extension.transform_one(_file_extension(file_path))),
            }

            full_row = {**structural, **retrieval_cols, **query_repo_cols, **categorical}
            this_query_rows.append(full_row)
            this_query_labels.append(label)
            this_query_files.append(file_path)

        if not this_query_rows:
            n_dropped_queries += 1
            continue

        feature_rows.extend(this_query_rows)
        labels.extend(this_query_labels)
        file_paths.extend(this_query_files)
        repository_ids.extend([repository_id] * len(this_query_rows))
        group_sizes.append(len(this_query_rows))
        query_ids.append(row["query_id"])

    if n_dropped_rows or n_dropped_queries:
        logger.warning(
            "Dropped %d placeholder-labeled candidate row(s) and %d fully-unlabeled quer(y/ies) "
            "while building the feature matrix (require_numeric_labels=%s).",
            n_dropped_rows, n_dropped_queries, require_numeric_labels,
        )

    feature_names = list(STRUCTURAL_FEATURE_COLUMNS) + list(RETRIEVAL_FEATURE_COLUMNS)
    feature_names += _QUERY_REPO_FEATURE_COLUMNS_CACHE or []
    feature_names += list(CATEGORICAL_STRUCTURAL_COLUMNS)

    if feature_rows:
        X = np.array([[r.get(name, np.nan) for name in feature_names] for r in feature_rows], dtype=np.float64)
    else:
        X = np.zeros((0, len(feature_names)), dtype=np.float64)

    return FeatureMatrix(
        X=X,
        y=np.array(labels, dtype=np.int64),
        group_sizes=np.array(group_sizes, dtype=np.int64),
        feature_names=feature_names,
        categorical_feature_names=list(CATEGORICAL_STRUCTURAL_COLUMNS),
        query_ids=query_ids,
        file_paths=file_paths,
        repository_ids=repository_ids,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI: build and save a `FeatureMatrix` (as `.npz` + a JSON sidecar) for one split.

    Example:
        python -m evaluation.experiments.ltr.feature_pipeline --split train --no-retrieval
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["train", "validation", "test"], required=True)
    parser.add_argument("--merged-dataset-dir", type=Path, default=MERGED_DATASET_DIR)
    parser.add_argument("--encoders-path", type=Path, default=None, help="Fit encoders here if training split; else load from here.")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "outputs")
    parser.add_argument("--no-retrieval", action="store_true", help="Skip real retrieval-feature computation (fast; for testing).")
    parser.add_argument("--repositories", nargs="*", default=None, help="If given, only process these repository_id values.")
    parser.add_argument("--max-queries", type=int, default=None, help="If given, process at most this many queries (for smoke tests).")
    parser.add_argument("--allow-unlabeled", action="store_true", help="Build a matrix even if a split is fully placeholder-labeled (labels will be 0; NOT for training).")
    args = parser.parse_args(argv)

    rows = read_jsonl(args.merged_dataset_dir / f"{args.split}.jsonl")
    if args.repositories:
        rows = [r for r in rows if r["repository_id"] in args.repositories]
    if args.max_queries:
        rows = rows[: args.max_queries]

    if not args.allow_unlabeled:
        validate_labels_are_numeric(rows, split_name=args.split)

    encoders_path = args.encoders_path or (args.output_dir / "encoders.json")
    if args.split == "train":
        encoders = Encoders.fit(read_jsonl(args.merged_dataset_dir / "train.jsonl"))
        encoders.save(encoders_path)
        logger.info("Fitted encoders on train split, saved to %s", encoders_path)
    else:
        if not encoders_path.is_file():
            raise FeaturePipelineError(
                f"No fitted encoders found at {encoders_path}. Run with --split train first."
            )
        encoders = Encoders.load(encoders_path)

    provider = None if args.no_retrieval else RetrievalFeatureProvider()
    matrix = build_feature_matrix(
        rows, encoders=encoders, retrieval_provider=provider, require_numeric_labels=not args.allow_unlabeled
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    npz_path = args.output_dir / f"features_{args.split}.npz"
    np.savez_compressed(npz_path, X=matrix.X, y=matrix.y, group_sizes=matrix.group_sizes)
    meta_path = args.output_dir / f"features_{args.split}.meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "feature_names": matrix.feature_names,
                "categorical_feature_names": matrix.categorical_feature_names,
                "query_ids": matrix.query_ids,
                "file_paths": matrix.file_paths,
                "repository_ids": matrix.repository_ids,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info(
        "Wrote %s (%d rows x %d features across %d groups) and %s",
        npz_path, matrix.X.shape[0], matrix.X.shape[1], len(matrix.group_sizes), meta_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
