"""Deterministic `pipeline_digest` / `input_digest` computation (Reviewer Minor Revision).

Every function here is a pure function of its inputs (settings, file
bytes, or the TARA codebase's own git state) -- no randomness, no
wall-clock dependence -- so the same pipeline code, configuration, and
input files always produce the same digests, which is the entire
property `CheckpointStore`'s widened key (Revision 3) depends on to
detect a *meaningful* change versus a spurious one. See
`README.md`'s "Reproducibility Guarantees" and `DatasetSchema.md` for
the exact formula behind each field.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from git import InvalidGitRepositoryError, Repo

from evaluation.rts_builder.dataset_builder.exceptions import DatasetBuilderError
from evaluation.rts_builder.dataset_builder.models import InputDigest, PipelineDigest, PipelineSettingsSnapshot
from evaluation.rts_builder.feature_extraction.models import FeatureVector
from evaluation.rts_builder.oracle_utility.models import StrategyOracleRow
from tara.core.logging import get_logger

logger = get_logger(__name__)

PIPELINE_VERSION = "1.0.0"
"""Dataset Builder's own orchestration-code version. Bumped by a maintainer when this
package's stage-composition/data-flow semantics change in a way that should force
checkpoint invalidation even without an accompanying commit (e.g. while iterating on
an uncommitted local change -- though see `resolve_git_commit`'s '-dirty' suffix,
which already catches the common case of that specific scenario).
"""


class DigestComputationError(DatasetBuilderError):
    """Raised when a digest cannot be computed (e.g. an input file vanished after iterator construction)."""


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_of_json(payload: object) -> str:
    """Hash a JSON-serializable payload deterministically (key order never affects the result)."""
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return _sha256_hex(canonical.encode("utf-8"))


def resolve_git_commit(start_path: Path | None = None) -> str:
    """Best-effort resolution of the TARA codebase's own git commit SHA.

    Args:
        start_path: Where to start searching for an enclosing git
            repository. Defaults to this file's own location, so the
            result reflects the TARA checkout this code is actually
            running from, regardless of the caller's working directory.

    Returns:
        The current commit's full hex SHA, suffixed `-dirty` if the
        working tree has uncommitted changes (staged or unstaged) --
        the same convention `git describe --dirty` uses, since an
        uncommitted local modification to any RTS Builder module is
        otherwise invisible to a digest based on commit SHA alone.
        Returns `"unknown"` if `start_path` is not inside a git
        repository at all (e.g. an installed package with no `.git`
        directory) -- never raises.
    """
    try:
        repo = Repo(start_path or Path(__file__).resolve(), search_parent_directories=True)
        commit_sha = repo.head.commit.hexsha
    except (InvalidGitRepositoryError, ValueError):
        return "unknown"

    try:
        is_dirty = repo.is_dirty(untracked_files=False)
    except OSError:
        is_dirty = False
    return f"{commit_sha}-dirty" if is_dirty else commit_sha


def compute_feature_schema_version() -> str:
    """Return a content hash of `FeatureVector`'s current JSON schema.

    A hash of the actual schema, not a manually-maintained version
    string: a hand-bumped constant can be forgotten when a field
    changes, silently defeating the whole point of this revision
    (detecting a schema change); a schema hash cannot drift from the
    code, by construction.
    """
    return _sha256_of_json(FeatureVector.model_json_schema())[:16]


def compute_oracle_schema_version() -> str:
    """Return a content hash of `StrategyOracleRow`'s current JSON schema. See `compute_feature_schema_version`."""
    return _sha256_of_json(StrategyOracleRow.model_json_schema())[:16]


def compute_configuration_hash(settings: PipelineSettingsSnapshot) -> str:
    """Return a content hash of every wrapped stage's effective settings.

    Args:
        settings: The settings bundle a caller asserts matches what
            `PipelineOrchestrator`'s collaborators were actually
            constructed with -- see `PipelineSettingsSnapshot`'s
            docstring for why this cannot be verified automatically.
    """
    payload = {
        "repository_loader": settings.repository_loader_settings.model_dump(mode="json"),
        "parser": settings.parser_settings.model_dump(mode="json"),
        "feature_extraction": settings.feature_extraction_settings.model_dump(mode="json"),
        "retrieval_executor": settings.retrieval_executor_settings.model_dump(mode="json"),
        "oracle_utility": settings.oracle_utility_settings.model_dump(mode="json"),
        "dataset_builder": settings.dataset_builder_settings.model_dump(mode="json"),
    }
    return _sha256_of_json(payload)


def compute_pipeline_digest(settings: PipelineSettingsSnapshot, git_commit: str | None = None) -> PipelineDigest:
    """Compute the full `PipelineDigest` for a run.

    Args:
        settings: See `compute_configuration_hash`.
        git_commit: Overrides `resolve_git_commit()`'s result -- mainly
            for tests, which should not depend on this actual
            repository's real git state to be deterministic themselves.

    Returns:
        A `PipelineDigest` with every field populated, including the
        combined `digest_hash`.
    """
    resolved_git_commit = git_commit if git_commit is not None else resolve_git_commit()
    digest = PipelineDigest(
        pipeline_version=PIPELINE_VERSION,
        git_commit=resolved_git_commit,
        feature_schema_version=compute_feature_schema_version(),
        oracle_schema_version=compute_oracle_schema_version(),
        configuration_hash=compute_configuration_hash(settings),
        digest_hash="",
    )
    combined_hash = _sha256_of_json(digest.model_dump(mode="json", exclude={"digest_hash"}))
    return digest.model_copy(update={"digest_hash": combined_hash})


def compute_input_digest(repository_manifest_path: Path, queries_path: Path) -> InputDigest:
    """Compute the full `InputDigest` for a run's input files.

    Args:
        repository_manifest_path: The manifest `RepositoryIterator` was
            actually constructed from (its `.manifest_path`).
        queries_path: The queries file `QueryIterator` was actually
            constructed from (its `.queries_path`); already includes
            each query's `relevance_grades` inline -- see `InputDigest`'s
            docstring for why no third, separate hash is computed.

    Returns:
        An `InputDigest` with both file hashes and the combined `digest_hash`.

    Raises:
        DigestComputationError: If either file cannot be read (e.g. it
            was deleted after the corresponding iterator was
            constructed but before `generate()` started).
    """
    try:
        manifest_hash = _sha256_hex(repository_manifest_path.read_bytes())
        queries_hash = _sha256_hex(queries_path.read_bytes())
    except OSError as exc:
        raise DigestComputationError(f"Could not read an input file while computing input_digest: {exc}") from exc

    digest = InputDigest(repository_manifest_hash=manifest_hash, queries_hash=queries_hash, digest_hash="")
    combined_hash = _sha256_of_json(digest.model_dump(mode="json", exclude={"digest_hash"}))
    return digest.model_copy(update={"digest_hash": combined_hash})
