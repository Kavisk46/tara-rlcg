"""Exception hierarchy for the RTS Builder's Repository Loader.

Rooted in `tara.core.exceptions.TaraError` rather than a wholly separate
hierarchy, so a caller working across both the TARA retrieval pipeline
and the RTS Builder can catch `TaraError` for "anything either can
throw," while still being able to catch a Repository Loader failure
specifically and distinguish it from, say, a routing failure.
"""
from __future__ import annotations

from tara.core.exceptions import TaraError


class RepositoryLoaderError(TaraError):
    """Base class for all exceptions raised by the Repository Loader."""


class RepositoryCloneError(RepositoryLoaderError):
    """Raised when cloning a repository fails (invalid URL, network failure, timeout)."""


class CommitNotFoundError(RepositoryLoaderError):
    """Raised when the requested commit SHA cannot be checked out in a cloned repository."""


class RepositoryValidationError(RepositoryLoaderError):
    """Raised when a cloned repository fails structural validation (empty, corrupted, or commit mismatch)."""


class CommitNotSpecifiedError(RepositoryLoaderError):
    """Raised when `commit_sha` is missing or empty.

    The loader never defaults to `HEAD`: a caller must always pin an
    exact commit, since RTS pipeline runs must be exactly reproducible.
    """


class RepositoryLockError(RepositoryLoaderError):
    """Raised when the per-repository lock cannot be acquired within the configured timeout.

    Indicates contention: another process (typically a concurrent RTS
    dataset worker) is currently holding the lock for this
    `repository_id`.
    """


class InvalidRepositoryInputError(RepositoryLoaderError):
    """Raised when `repository_id` or `source_url` fails input validation.

    Distinct from `RepositoryValidationError`, which is about the state
    of a repository *after* it has been cloned. This is a pre-clone
    guard against malformed identifiers (directory traversal) and
    malformed URLs (argument injection into the underlying `git`
    subprocess).
    """
