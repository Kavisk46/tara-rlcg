"""Data contracts for the RTS Builder's Repository Loader (Milestone 1)."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from tara.core.types import Language


class Repository(BaseModel):
    """A single repository, cloned, pinned, validated, and characterized.

    This is Milestone 1's entire output contract: a repository that has
    been cloned (or its existing local clone reused), checked out to an
    exact, verified commit, confirmed non-empty and structurally valid,
    and described by file/directory counts and a per-language file-count
    breakdown. No parsing, retrieval, or embedding has happened -- those
    are later RTS Builder milestones and this object carries nothing
    from them.
    """

    repository_id: str = Field(
        ..., min_length=1, description="Stable identifier for this repository within the RTS pipeline."
    )
    source_url: str = Field(..., min_length=1, description="The repository's public source URL.")
    commit_sha: str = Field(
        ..., min_length=1, description="The exact commit checked out; verified to match the requested pin."
    )
    local_path: str = Field(..., min_length=1, description="Absolute filesystem path to the cloned working tree.")
    default_branch: str | None = Field(
        default=None, description="The repository's default branch name, if determinable."
    )
    primary_language: Language = Field(
        ...,
        description="The dominant language by total bytes (not file count) across detected-language "
        "files -- e.g. GitHub Linguist's approach -- so a few large files outweigh many tiny ones.",
    )
    language_distribution: dict[Language, int] = Field(
        default_factory=dict, description="File count per detected language. Informational; not used "
        "to determine primary_language (see language_byte_distribution)."
    )
    language_byte_distribution: dict[Language, int] = Field(
        default_factory=dict,
        description="Total bytes per detected language. This is the statistic primary_language is "
        "derived from.",
    )
    file_count: int = Field(..., ge=0, description="Total files, excluding ignored directories and, "
        "when submodules are not initialized, uninitialized submodule content.")
    directory_count: int = Field(
        ..., ge=0, description="Total directories, excluding ignored directories and their contents."
    )
    size_bytes: int = Field(..., ge=0, description="Total on-disk size of counted files, in bytes.")
    commit_author: str | None = Field(default=None, description="Author name of the pinned commit, if available.")
    commit_date: datetime | None = Field(default=None, description="Commit timestamp of the pinned commit, if available.")
    commit_message: str | None = Field(
        default=None, description="First line of the pinned commit's message, if available."
    )
    submodules: list[str] = Field(
        default_factory=list,
        description="Relative paths (POSIX-style) of git submodules declared in .gitmodules, if any. "
        "Excluded from file/directory counts unless RepositoryLoaderSettings.initialize_submodules is True.",
    )
    manifest_path: str | None = Field(
        default=None,
        description="Absolute path to this repository's persisted repository_manifest.json, written "
        "immediately after this Repository object was successfully validated and characterized.",
    )
    loaded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="When this Repository object was constructed."
    )
