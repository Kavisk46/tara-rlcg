"""Repository Loader: clones, validates, and characterizes a single repository.

Milestone 1 of the RTS Builder (`docs/DATASET_BUILDER_SPEC.md` §2, Stage 0
"Repository Collection" / Stage 1 "Repository Preprocessing" precondition).
Responsible for exactly seven things: cloning a repository from its source
URL (or reusing an existing local clone), checking out and verifying a
pinned commit, validating the result, reading commit-level metadata,
detecting the dominant programming language, and counting files and
directories.

Explicitly out of scope for this milestone, per the RTS Builder's staged
design: parsing (`tara.parsing`), retrieval, embeddings, oracle utility
computation, and feature extraction. A `Repository` object is a
precondition for those later stages, not a replacement for them.

Revision note: this module was revised in response to an ICSE-style
review of v1 (see `REVIEW_RESPONSE.md`). The public entry point is now
`load_repository()` (renamed from `load()`); every reviewer-mandated
change is called out inline where it lives and cross-referenced from
`REVIEW_RESPONSE.md`.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from filelock import FileLock
from filelock import Timeout as FileLockTimeout
from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Repo

from evaluation.rts_builder.config import RepositoryLoaderSettings
from evaluation.rts_builder.exceptions import (
    CommitNotFoundError,
    CommitNotSpecifiedError,
    InvalidRepositoryInputError,
    RepositoryCloneError,
    RepositoryLockError,
    RepositoryValidationError,
)
from evaluation.rts_builder.models import Repository
from tara.core.logging import get_logger
from tara.core.types import Language
from tara.parsing.language_registry import LanguageRegistry

logger = get_logger(__name__)

_DEFAULT_IGNORED_DIRECTORIES: frozenset[str] = frozenset(
    {
        ".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build",
        ".idea", ".vscode", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    }
)
"""A separate, deliberately small default set from `tara.parsing`'s own
ignore list: this loader's job (counting files/directories, detecting a
dominant language) is coarser-grained than symbol extraction, and does
not need to import `tara.parsing`'s private, unexported ignore-list
constant to do it correctly.
"""

_MANIFEST_FILENAME: Final[str] = "repository_manifest.json"
"""Written into a repository's own working tree; excluded from every
scan by name so its own presence never perturbs file_count / language
statistics, on this or any later `load_repository()` call.
"""

_REPOSITORY_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
"""`repository_id` becomes a filesystem directory name directly under
`clone_root`; this charset excludes path separators and forbids leading
'.', '-' , which is sufficient (in conjunction with the explicit '..'
rejection below) to make traversal outside `clone_root` structurally
impossible, not merely discouraged.
"""

_COMMIT_SHA_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-fA-F]{40}$")
"""Full 40-character SHAs only. `_ensure_commit_checked_out` verifies
post-checkout HEAD with strict equality against the requested
`commit_sha` (not a `startswith` prefix match), so an abbreviated SHA
would resolve correctly on checkout but then always fail that
equality check -- rejecting it here, with a clear message, is better
than that confusing downstream failure. It also matches the RTS
pipeline's existing reproducibility discipline of pinning exact, full
commit SHAs (`docs/DATASET_PLAN.md`), never abbreviations.
"""

_FORBIDDEN_URL_TOKENS: Final[tuple[str, ...]] = (";", "|", "`", "$(", "\n", "\r", "\x00")
"""Defense-in-depth only: GitPython/`subprocess` already invoke `git`
via an argument list, never a shell string, so none of these are
interpretable as shell metacharacters today. They are still rejected so
a future change to how the URL is passed to `git` (or to any other
subprocess) cannot silently reintroduce a shell-injection vector.
"""


def _validate_repository_id(repository_id: str) -> None:
    """Reject a `repository_id` that could escape `clone_root` or is otherwise malformed.

    Raises:
        InvalidRepositoryInputError: If `repository_id` is empty, contains
            a path separator or '..', or contains any character outside
            `_REPOSITORY_ID_PATTERN`.
    """
    if not repository_id or ".." in repository_id or not _REPOSITORY_ID_PATTERN.match(repository_id):
        raise InvalidRepositoryInputError(
            f"repository_id {repository_id!r} is invalid: must be non-empty, contain only letters, "
            "digits, '.', '_', '-', and must not contain '..' or a path separator."
        )


def _validate_source_url(source_url: str) -> None:
    """Reject a `source_url` that could be misread as a `git` command-line option or shell fragment.

    Raises:
        InvalidRepositoryInputError: If `source_url` is empty, starts
            with '-' (which `git` would interpret as a flag rather than
            a URL -- a real argument-injection vector), or contains any
            token in `_FORBIDDEN_URL_TOKENS`.
    """
    if not source_url or not source_url.strip():
        raise InvalidRepositoryInputError("source_url must not be empty.")
    if source_url.startswith("-"):
        raise InvalidRepositoryInputError(
            f"source_url {source_url!r} must not start with '-': this would let it be interpreted "
            "as a command-line option by the underlying git subprocess rather than a URL."
        )
    for token in _FORBIDDEN_URL_TOKENS:
        if token in source_url:
            raise InvalidRepositoryInputError(
                f"source_url {source_url!r} contains {token!r}, which is never valid in a git remote "
                "URL and is rejected as a defense-in-depth measure."
            )


def _validate_commit_sha(commit_sha: str) -> None:
    """Require a non-empty `commit_sha`; the loader never defaults to HEAD.

    Raises:
        CommitNotSpecifiedError: If `commit_sha` is empty, whitespace-only,
            or not a full 40-character hexadecimal SHA.
    """
    if not commit_sha or not commit_sha.strip():
        raise CommitNotSpecifiedError(
            "commit_sha is required and must not be empty. RepositoryLoader never defaults to HEAD: "
            "every load must pin an exact, reproducible commit."
        )
    if not _COMMIT_SHA_PATTERN.match(commit_sha):
        raise CommitNotSpecifiedError(
            f"commit_sha {commit_sha!r} must be a full 40-character hexadecimal SHA. Abbreviated "
            "SHAs are rejected: the RTS pipeline requires exact, unambiguous commit pins."
        )


class RepositoryLoader:
    """Clones, validates, and characterizes a single repository for the RTS pipeline.

    Both collaborators are injected: `settings` controls where
    repositories are cloned to, locking/warning/submodule behavior;
    `language_registry` is the same `tara.parsing.language_registry.LanguageRegistry`
    already used by `TreeSitterRepositoryParser`, reused here for
    per-file extension-to-language detection rather than re-implemented,
    so this loader's notion of "what language is this file" can never
    drift from the main parsing pipeline's.

    Every git operation for a given `repository_id` -- clone, fetch,
    checkout, submodule update, and the final manifest write -- is
    performed while holding an exclusive, cross-platform file lock
    scoped to that `repository_id`, so concurrent RTS dataset workers
    loading the *same* repository cannot interleave and corrupt its
    local clone. Different `repository_id`s never contend with each
    other: the lock is per-repository, not global, so a fleet of workers
    building an RTS across many repositories still runs in parallel.
    """

    def __init__(
        self,
        settings: RepositoryLoaderSettings | None = None,
        language_registry: LanguageRegistry | None = None,
    ) -> None:
        """Construct the loader.

        Args:
            settings: Configuration controlling clone location, timeout,
                locking, submodule handling, and ignored directories.
                Defaults to `RepositoryLoaderSettings()` (environment
                defaults) when omitted.
            language_registry: Used for per-file language detection.
                Defaults to a fresh `LanguageRegistry` when omitted;
                sharing one instance across loaders is safe and avoids
                rebuilding its internal parser cache.
        """
        self._settings = settings or RepositoryLoaderSettings()
        self._language_registry = language_registry or LanguageRegistry()
        self._ignored_directories = _DEFAULT_IGNORED_DIRECTORIES | set(self._settings.ignored_directories)

    def load_repository(self, repository_id: str, source_url: str, commit_sha: str) -> Repository:
        """Load a repository: clone (or reuse), pin, verify, validate, and characterize it.

        Args:
            repository_id: Stable identifier for this repository within
                the RTS pipeline. Used as the local clone's directory
                name; restricted to a safe charset (see
                `_validate_repository_id`).
            source_url: The repository's source URL (or local path) to
                clone from.
            commit_sha: The exact commit to check out and pin to.
                Mandatory -- never defaults to HEAD.

        Returns:
            A fully populated `Repository` object. Its
            `repository_manifest.json` has already been written to
            `local_path` by the time this returns.

        Raises:
            InvalidRepositoryInputError: If `repository_id` or
                `source_url` fails input validation.
            CommitNotSpecifiedError: If `commit_sha` is empty.
            RepositoryLockError: If the per-repository lock cannot be
                acquired within `settings.lock_timeout_seconds`.
            RepositoryCloneError: If cloning or fetching fails: invalid
                URL, network failure, or the clone exceeds
                `settings.clone_timeout_seconds`.
            CommitNotFoundError: If `commit_sha` cannot be checked out
                (even after a fetch) in the repository.
            RepositoryValidationError: If an existing local path is not
                a valid git repository, or the repository is empty after
                checkout, or the checked-out commit does not match
                `commit_sha`.
        """
        _validate_repository_id(repository_id)
        _validate_source_url(source_url)
        _validate_commit_sha(commit_sha)

        clone_root = Path(self._settings.clone_root).resolve()
        clone_root.mkdir(parents=True, exist_ok=True)
        local_path = clone_root / repository_id
        lock_path = clone_root / f"{repository_id}.lock"

        try:
            with FileLock(str(lock_path), timeout=self._settings.lock_timeout_seconds):
                return self._load_locked(repository_id, source_url, commit_sha, local_path)
        except FileLockTimeout as exc:
            raise RepositoryLockError(
                f"Could not acquire the lock for repository {repository_id!r} within "
                f"{self._settings.lock_timeout_seconds}s; another worker may be holding it."
            ) from exc

    def _load_locked(self, repository_id: str, source_url: str, commit_sha: str, local_path: Path) -> Repository:
        """The full load pipeline, run while `repository_id`'s lock is held."""
        repo = self._clone_or_reuse(source_url, local_path)
        default_branch = self._read_default_branch(repo)
        self._ensure_commit_checked_out(repo, commit_sha, source_url)
        self._validate_structure(local_path, repo, commit_sha)

        submodule_paths = self._detect_submodules(repo)
        if self._settings.initialize_submodules and submodule_paths:
            self._initialize_submodules(repo, source_url)

        file_count, directory_count, size_bytes, language_distribution, language_byte_distribution = (
            self._scan_tree(
                local_path,
                submodule_paths=frozenset(submodule_paths) if not self._settings.initialize_submodules else frozenset(),
            )
        )
        primary_language = self._determine_primary_language(language_byte_distribution)
        commit_author, commit_date, commit_message = self._read_commit_metadata(repo)

        repository = Repository(
            repository_id=repository_id,
            source_url=source_url,
            commit_sha=repo.head.commit.hexsha,
            local_path=str(local_path),
            default_branch=default_branch,
            primary_language=primary_language,
            language_distribution=language_distribution,
            language_byte_distribution=language_byte_distribution,
            file_count=file_count,
            directory_count=directory_count,
            size_bytes=size_bytes,
            commit_author=commit_author,
            commit_date=commit_date,
            commit_message=commit_message,
            submodules=submodule_paths,
        )

        manifest_path = local_path / _MANIFEST_FILENAME
        repository = repository.model_copy(update={"manifest_path": str(manifest_path)})
        self._write_manifest(manifest_path, repository)

        logger.info(
            "Loaded repository %s: %s@%s -> %d files, %d directories, %d bytes, primary_language=%s",
            repository_id, source_url, commit_sha[:8], file_count, directory_count, size_bytes,
            primary_language.value,
        )
        return repository

    def _clone_or_reuse(self, source_url: str, local_path: Path) -> Repo:
        """Clone `source_url` into `local_path`, or reuse an existing valid clone there.

        Raises:
            RepositoryValidationError: If `local_path` exists but is not
                a valid git repository.
            RepositoryCloneError: If cloning fails.
        """
        if local_path.exists():
            try:
                repo = Repo(local_path)
                logger.debug("Reusing existing clone of %s at %s", source_url, local_path)
                return repo
            except (InvalidGitRepositoryError, NoSuchPathError) as exc:
                raise RepositoryValidationError(
                    f"{local_path} exists but is not a valid git repository: {exc}"
                ) from exc

        local_path.parent.mkdir(parents=True, exist_ok=True)

        # `kill_after_timeout` is GitPython's native clone-timeout mechanism, but it is
        # explicitly unsupported on Windows (GitPython raises GitCommandError if passed
        # there at all) -- not a TARA limitation, a documented upstream one. Enforced on
        # every other platform; on Windows, the clone proceeds without a timeout, logged
        # loudly so the gap is visible rather than silently absent. See README.md's
        # "Potential Failure Modes" section.
        clone_kwargs: dict[str, Any] = {}
        if sys.platform != "win32":
            clone_kwargs["kill_after_timeout"] = self._settings.clone_timeout_seconds
            logger.info(
                "Cloning %s into %s (timeout=%ds)", source_url, local_path, self._settings.clone_timeout_seconds
            )
        else:
            logger.warning(
                "Clone timeout enforcement is unavailable on Windows (GitPython/Windows "
                "limitation). Cloning %s into %s with no enforced timeout.",
                source_url, local_path,
            )

        try:
            # Positional args passed as a Python argument list to a subprocess invocation
            # (never a shell string) by GitPython itself; `source_url` has already passed
            # `_validate_source_url`'s argument-injection guard before reaching here.
            return Repo.clone_from(source_url, local_path, **clone_kwargs)
        except GitCommandError as exc:
            raise RepositoryCloneError(f"Failed to clone {source_url} into {local_path}: {exc}") from exc

    def _ensure_commit_checked_out(self, repo: Repo, commit_sha: str, source_url: str) -> None:
        """Guarantee `repo`'s HEAD is exactly `commit_sha`, fetching and forcing checkout if not.

        Applies uniformly whether `repo` was just cloned or reused: a
        freshly cloned repository's HEAD sits at its default branch's
        tip, which is not generally `commit_sha` either, so the same
        "verify, and if different: fetch + force-checkout + re-verify"
        logic is the correct behavior in both cases, not just on reuse.

        Raises:
            RepositoryCloneError: If the fetch (needed when the
                requested commit isn't yet present locally) fails.
            CommitNotFoundError: If checkout fails, or if the
                post-checkout HEAD still doesn't match `commit_sha`.
        """
        current_sha = self._current_head_sha(repo)
        if current_sha == commit_sha:
            logger.debug("Repository already at requested commit %s.", commit_sha[:8])
            return

        logger.info(
            "HEAD (%s) does not match requested commit %s; fetching and forcing checkout.",
            current_sha[:8] if current_sha else "<unborn>", commit_sha[:8],
        )
        try:
            repo.remotes.origin.fetch()
        except GitCommandError as exc:
            raise RepositoryCloneError(f"Failed to fetch updates for {source_url}: {exc}") from exc

        try:
            repo.git.checkout("--force", commit_sha)
        except GitCommandError as exc:
            raise CommitNotFoundError(
                f"Commit {commit_sha!r} could not be checked out in {source_url}: {exc}"
            ) from exc

        verified_sha = self._current_head_sha(repo)
        if verified_sha != commit_sha:
            raise CommitNotFoundError(
                f"Checkout of {commit_sha!r} in {source_url} did not succeed: HEAD is now "
                f"{verified_sha!r}."
            )

    @staticmethod
    def _current_head_sha(repo: Repo) -> str | None:
        """Return `repo`'s current HEAD commit SHA, or None if HEAD is unborn (no commits yet)."""
        try:
            return repo.head.commit.hexsha
        except (ValueError, GitCommandError):
            return None

    def _validate_structure(self, local_path: Path, repo: Repo, requested_commit_sha: str) -> None:
        """Confirm the checked-out repository is non-empty and pinned to the requested commit.

        "Non-empty" means at least one *tracked working-tree entry*, not
        merely a non-empty directory listing: `local_path` always
        contains a `.git` entry regardless of whether the checked-out
        commit's tree has any files at all (e.g. a repository whose only
        commit was made with `--allow-empty`), so `.git` is excluded
        from this check specifically to avoid a false negative there.

        Raises:
            RepositoryValidationError: If either check fails.
        """
        checked_out_sha = repo.head.commit.hexsha
        if checked_out_sha != requested_commit_sha:
            raise RepositoryValidationError(
                f"Checked-out commit {checked_out_sha!r} does not match requested {requested_commit_sha!r}."
            )
        working_tree_entries = [entry for entry in local_path.iterdir() if entry.name != ".git"]
        if not working_tree_entries:
            raise RepositoryValidationError(f"{local_path} has no tracked files after checkout (empty working tree).")

    def _detect_submodules(self, repo: Repo) -> list[str]:
        """Return the POSIX-style relative paths of `repo`'s declared submodules, if any.

        Reading `.gitmodules` is best-effort: a malformed or unparsable
        file should not fail the whole load (the repository itself is
        still perfectly loadable), so any exception here is logged and
        treated as "no submodules detected" rather than propagated.
        """
        try:
            return sorted(submodule.path.replace("\\", "/") for submodule in repo.submodules)
        except Exception as exc:  # noqa: BLE001 - third-party .gitmodules parsing, no documented exception type
            logger.warning("Could not parse .gitmodules for %s: %s", repo.working_dir, exc)
            return []

    def _initialize_submodules(self, repo: Repo, source_url: str) -> None:
        """Recursively initialize and update `repo`'s submodules.

        Only called when `settings.initialize_submodules` is True.

        Raises:
            RepositoryCloneError: If the submodule update fails
                (network failure, unreachable submodule URL, etc.).
        """
        logger.info("Initializing submodules for %s.", source_url)
        try:
            repo.submodule_update(init=True, recursive=True)
        except GitCommandError as exc:
            raise RepositoryCloneError(f"Failed to initialize submodules for {source_url}: {exc}") from exc

    def _scan_tree(
        self, local_path: Path, submodule_paths: frozenset[str]
    ) -> tuple[int, int, int, dict[Language, int], dict[Language, int]]:
        """Walk `local_path`, counting files/directories and per-language file counts and bytes.

        Uses an explicit stack rather than recursion, consistent with
        `tara.parsing.repository_parser`'s own directory-walk, to avoid
        Python's recursion limit on a deeply nested tree.

        `submodule_paths` (relative to `local_path`) are skipped
        entirely -- neither descended into nor counted -- since an
        uninitialized submodule directory on disk holds no real content
        (see `RepositoryLoaderSettings.initialize_submodules`). Pass an
        empty set when submodules were initialized, so their now-real
        content is scanned like any other directory.
        """
        file_count = 0
        directory_count = 0
        size_bytes = 0
        language_file_counts: dict[Language, int] = {}
        language_byte_counts: dict[Language, int] = {}

        stack = [local_path]
        while stack:
            current = stack.pop()
            try:
                entries = list(current.iterdir())
            except OSError as exc:
                logger.warning("Cannot list directory %s: %s", current, exc)
                continue

            for entry in entries:
                relative_posix = entry.relative_to(local_path).as_posix()

                if entry.is_dir():
                    if entry.name in self._ignored_directories:
                        continue
                    if relative_posix in submodule_paths:
                        logger.debug("Skipping uninitialized submodule directory %s", relative_posix)
                        continue
                    directory_count += 1
                    stack.append(entry)
                    continue

                if entry.parent == local_path and entry.name == _MANIFEST_FILENAME:
                    continue

                file_count += 1
                entry_size = 0
                try:
                    entry_size = entry.stat().st_size
                    size_bytes += entry_size
                except OSError as exc:
                    logger.warning("Cannot stat file %s: %s", entry, exc)

                language = self._language_registry.detect_language(entry.suffix)
                if language is not Language.UNKNOWN:
                    language_file_counts[language] = language_file_counts.get(language, 0) + 1
                    language_byte_counts[language] = language_byte_counts.get(language, 0) + entry_size

        if file_count > self._settings.max_file_count_warning_threshold:
            logger.warning(
                "Repository at %s has %d files, exceeding the configured warning threshold of %d.",
                local_path, file_count, self._settings.max_file_count_warning_threshold,
            )

        return file_count, directory_count, size_bytes, language_file_counts, language_byte_counts

    @staticmethod
    def _determine_primary_language(language_byte_distribution: dict[Language, int]) -> Language:
        """Return the language with the most total bytes, or `Language.UNKNOWN` if none detected.

        Bytes, not file count: a repository with 200 tiny generated JSON
        fixtures and 5 large Python modules is a Python repository, and
        file-count-based selection would get that backwards. This
        mirrors the standard approach used by tools such as GitHub
        Linguist.
        """
        if not language_byte_distribution:
            return Language.UNKNOWN
        return max(language_byte_distribution, key=lambda language: language_byte_distribution[language])

    @staticmethod
    def _read_commit_metadata(repo: Repo) -> tuple[str | None, datetime | None, str | None]:
        """Return (author name, commit datetime, first line of commit message) for `repo`'s HEAD."""
        commit = repo.head.commit
        author = commit.author.name if commit.author is not None else None
        commit_date = commit.committed_datetime
        message = commit.message
        first_line = message.strip().splitlines()[0] if isinstance(message, str) and message.strip() else None
        return author, commit_date, first_line

    @staticmethod
    def _read_default_branch(repo: Repo) -> str | None:
        """Best-effort resolution of the repository's default branch name.

        Read immediately after cloning, before any commit checkout: a
        freshly cloned repository has an active branch, but checking out
        a specific commit puts it into detached-HEAD state, after which
        `repo.active_branch` raises. The fallback (the remote's symbolic
        HEAD reference) also covers the case of reusing an already
        -detached existing clone from a prior run.
        """
        try:
            return repo.active_branch.name
        except TypeError:
            pass
        try:
            return repo.remotes.origin.refs.HEAD.reference.remote_head
        except (AttributeError, IndexError, ValueError):
            return None

    @staticmethod
    def _write_manifest(manifest_path: Path, repository: Repository) -> None:
        """Atomically persist `repository` as `manifest_path`'s JSON content.

        Written via write-to-temp-file-then-rename in the same directory:
        `Path.replace` is an atomic rename on both POSIX (`rename(2)`)
        and Windows (`MoveFileEx` with `MOVEFILE_REPLACE_EXISTING`), so a
        process crash or concurrent read can never observe a partially
        -written manifest.
        """
        payload = repository.model_dump(mode="json")
        payload["manifest_version"] = 1

        fd, tmp_name = tempfile.mkstemp(dir=str(manifest_path.parent), prefix=".repository_manifest_", suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with open(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
            tmp_path.replace(manifest_path)
        except OSError:
            tmp_path.unlink(missing_ok=True)
            raise
