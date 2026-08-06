"""Unit tests for `evaluation.rts_builder.repository_loader.RepositoryLoader`.

Covers both the original Milestone 1 behavior and the reviewer-mandated
revisions in `REVIEW_RESPONSE.md`: mandatory full-SHA commit pinning,
verified reuse (fetch + forced checkout when a reused clone is on the
wrong commit), the per-repository file lock, input validation
(repository_id / source_url), byte-based dominant-language detection,
submodule handling, and manifest persistence.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from filelock import FileLock
from git import Repo as GitRepo

from evaluation.rts_builder.config import RepositoryLoaderSettings
from evaluation.rts_builder.exceptions import (
    CommitNotFoundError,
    CommitNotSpecifiedError,
    InvalidRepositoryInputError,
    RepositoryLockError,
    RepositoryValidationError,
)
from evaluation.rts_builder.models import Repository
from evaluation.rts_builder.repository_loader import RepositoryLoader
from tara.core.types import Language

# ---------------------------------------------------------------------------
# Baseline: clone, characterize, reuse
# ---------------------------------------------------------------------------


def test_load_repository_returns_a_fully_populated_repository(
    loader: RepositoryLoader, source_repository: tuple[Path, str, str]
) -> None:
    source_path, commit_sha, _ = source_repository

    repository = loader.load_repository("repo-basic", str(source_path), commit_sha)

    assert isinstance(repository, Repository)
    assert repository.repository_id == "repo-basic"
    assert repository.source_url == str(source_path)
    assert repository.commit_sha == commit_sha
    assert Path(repository.local_path).exists()
    assert repository.size_bytes > 0


def test_load_repository_counts_files_excluding_ignored_directories(
    loader: RepositoryLoader, source_repository: tuple[Path, str, str]
) -> None:
    source_path, commit_sha, _ = source_repository

    repository = loader.load_repository("repo-file-count", str(source_path), commit_sha)

    # app.py, utils.js, nested/module.py, README.md -- node_modules/dependency.js is ignored.
    assert repository.file_count == 4


def test_load_repository_counts_directories_excluding_ignored_directories(
    loader: RepositoryLoader, source_repository: tuple[Path, str, str]
) -> None:
    source_path, commit_sha, _ = source_repository

    repository = loader.load_repository("repo-dir-count", str(source_path), commit_sha)

    # Only 'nested' -- 'node_modules' and '.git' are both ignored.
    assert repository.directory_count == 1


def test_load_repository_reads_commit_metadata(
    loader: RepositoryLoader, source_repository: tuple[Path, str, str]
) -> None:
    source_path, commit_sha, _ = source_repository

    repository = loader.load_repository("repo-metadata", str(source_path), commit_sha)

    assert repository.commit_author == "TARA Test Suite"
    assert repository.commit_message == "Initial commit"
    assert repository.commit_date is not None


def test_load_repository_reads_default_branch(
    loader: RepositoryLoader, source_repository: tuple[Path, str, str]
) -> None:
    source_path, commit_sha, _ = source_repository

    repository = loader.load_repository("repo-branch", str(source_path), commit_sha)

    assert repository.default_branch is not None


def test_load_repository_is_idempotent_and_reuses_existing_clone(
    loader: RepositoryLoader, source_repository: tuple[Path, str, str]
) -> None:
    source_path, commit_sha, _ = source_repository

    first = loader.load_repository("repo-reuse", str(source_path), commit_sha)
    second = loader.load_repository("repo-reuse", str(source_path), commit_sha)

    assert first.local_path == second.local_path
    assert first.commit_sha == second.commit_sha == commit_sha
    # The manifest file itself must never perturb a subsequent scan's counts.
    assert first.file_count == second.file_count


def test_load_repository_raises_commit_not_found_error_for_unknown_commit(
    loader: RepositoryLoader, source_repository: tuple[Path, str, str]
) -> None:
    source_path, _, _ = source_repository

    with pytest.raises(CommitNotFoundError):
        loader.load_repository("repo-bad-commit", str(source_path), "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")


def test_load_repository_raises_validation_error_for_non_git_existing_path(
    loader: RepositoryLoader, loader_settings: RepositoryLoaderSettings, source_repository: tuple[Path, str, str]
) -> None:
    source_path, commit_sha, _ = source_repository
    conflicting_path = Path(loader_settings.clone_root) / "repo-conflict"
    conflicting_path.mkdir(parents=True)
    (conflicting_path / "not_a_repo.txt").write_text("nope", encoding="utf-8")

    with pytest.raises(RepositoryValidationError):
        loader.load_repository("repo-conflict", str(source_path), commit_sha)


def test_load_repository_raises_validation_error_for_empty_repository(loader: RepositoryLoader, tmp_path: Path) -> None:
    empty_repo_path = tmp_path / "empty_source"
    empty_repo_path.mkdir()
    repo = GitRepo.init(empty_repo_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "TARA Test Suite")
        config.set_value("user", "email", "tara-tests@example.com")
    repo.git.commit("--allow-empty", "-m", "empty commit")
    empty_commit_sha = repo.head.commit.hexsha

    with pytest.raises(RepositoryValidationError):
        loader.load_repository("repo-empty", str(empty_repo_path), empty_commit_sha)


def test_custom_ignored_directories_extend_rather_than_replace_defaults(
    tmp_path: Path, source_repository: tuple[Path, str, str]
) -> None:
    source_path, commit_sha, _ = source_repository
    settings = RepositoryLoaderSettings(clone_root=str(tmp_path / "clones"), ignored_directories=["nested"])
    loader = RepositoryLoader(settings=settings)

    repository = loader.load_repository("repo-custom-ignore", str(source_path), commit_sha)

    # 'nested' is now excluded (custom) *in addition to* 'node_modules' (default):
    # only app.py, utils.js, README.md remain.
    assert repository.file_count == 3
    assert repository.directory_count == 0


def test_language_registry_is_injected_and_actually_used(
    loader_settings: RepositoryLoaderSettings, source_repository: tuple[Path, str, str]
) -> None:
    from tara.parsing.language_registry import LanguageRegistry

    registry = LanguageRegistry()
    loader = RepositoryLoader(settings=loader_settings, language_registry=registry)
    source_path, commit_sha, _ = source_repository

    repository = loader.load_repository("repo-injected-registry", str(source_path), commit_sha)

    assert repository.language_distribution.get(Language.PYTHON) == 2


def test_max_file_count_warning_threshold_logs_a_warning(
    tmp_path: Path, source_repository: tuple[Path, str, str], caplog: pytest.LogCaptureFixture
) -> None:
    source_path, commit_sha, _ = source_repository
    settings = RepositoryLoaderSettings(clone_root=str(tmp_path / "clones"), max_file_count_warning_threshold=1)
    loader = RepositoryLoader(settings=settings)

    with caplog.at_level(logging.WARNING, logger="evaluation.rts_builder.repository_loader"):
        loader.load_repository("repo-warning-threshold", str(source_path), commit_sha)

    assert any("exceeding the configured warning threshold" in record.message for record in caplog.records)


def test_repository_with_no_recognized_source_files_has_unknown_primary_language(
    loader: RepositoryLoader, tmp_path: Path
) -> None:
    repo_path = tmp_path / "docs_only_source"
    repo_path.mkdir()
    repo = GitRepo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "TARA Test Suite")
        config.set_value("user", "email", "tara-tests@example.com")
    (repo_path / "README.md").write_text("# Docs only\n", encoding="utf-8")
    (repo_path / "NOTES.txt").write_text("notes\n", encoding="utf-8")
    repo.index.add(["README.md", "NOTES.txt"])
    commit = repo.index.commit("docs only")

    repository = loader.load_repository("repo-docs-only", str(repo_path), commit.hexsha)

    assert repository.primary_language is Language.UNKNOWN
    assert repository.language_distribution == {}
    assert repository.file_count == 2


# ---------------------------------------------------------------------------
# Requirement 1: commit_sha is mandatory and must be a full SHA
# ---------------------------------------------------------------------------


def test_load_repository_raises_when_commit_sha_is_empty(
    loader: RepositoryLoader, source_repository: tuple[Path, str, str]
) -> None:
    source_path, _, _ = source_repository

    with pytest.raises(CommitNotSpecifiedError):
        loader.load_repository("repo-no-commit", str(source_path), "")


def test_load_repository_raises_when_commit_sha_is_abbreviated(
    loader: RepositoryLoader, source_repository: tuple[Path, str, str]
) -> None:
    source_path, commit_sha, _ = source_repository

    with pytest.raises(CommitNotSpecifiedError):
        loader.load_repository("repo-short-commit", str(source_path), commit_sha[:8])


# ---------------------------------------------------------------------------
# Requirement 2: reuse must verify and correct commit consistency
# ---------------------------------------------------------------------------


def test_reusing_a_clone_pinned_to_a_different_commit_fetches_and_force_checks_out(
    loader: RepositoryLoader, source_repository: tuple[Path, str, str]
) -> None:
    source_path, first_commit_sha, second_commit_sha = source_repository

    first = loader.load_repository("repo-commit-switch", str(source_path), first_commit_sha)
    assert first.commit_sha == first_commit_sha
    assert (Path(first.local_path) / "app.py").read_text(encoding="utf-8") == "print('hello')\n"

    second = loader.load_repository("repo-commit-switch", str(source_path), second_commit_sha)

    assert second.local_path == first.local_path
    assert second.commit_sha == second_commit_sha
    assert (Path(second.local_path) / "app.py").read_text(encoding="utf-8") == "print('hello, again')\n"


# ---------------------------------------------------------------------------
# Requirement 3: thread safety via a per-repository lock
# ---------------------------------------------------------------------------


def test_load_repository_raises_lock_error_when_lock_is_already_held(
    tmp_path: Path, source_repository: tuple[Path, str, str]
) -> None:
    source_path, commit_sha, _ = source_repository
    clone_root = tmp_path / "clones"
    clone_root.mkdir(parents=True)
    lock_path = clone_root / "repo-locked.lock"

    external_lock = FileLock(str(lock_path))
    external_lock.acquire()
    try:
        settings = RepositoryLoaderSettings(clone_root=str(clone_root), lock_timeout_seconds=1)
        loader = RepositoryLoader(settings=settings)

        with pytest.raises(RepositoryLockError):
            loader.load_repository("repo-locked", str(source_path), commit_sha)
    finally:
        external_lock.release()


def test_load_repository_succeeds_once_lock_is_released(
    tmp_path: Path, source_repository: tuple[Path, str, str]
) -> None:
    source_path, commit_sha, _ = source_repository
    clone_root = tmp_path / "clones"
    clone_root.mkdir(parents=True)
    lock_path = clone_root / "repo-unlocked.lock"

    external_lock = FileLock(str(lock_path))
    external_lock.acquire()
    external_lock.release()

    settings = RepositoryLoaderSettings(clone_root=str(clone_root), lock_timeout_seconds=5)
    loader = RepositoryLoader(settings=settings)

    repository = loader.load_repository("repo-unlocked", str(source_path), commit_sha)
    assert repository.commit_sha == commit_sha


# ---------------------------------------------------------------------------
# Requirement 4: secure subprocess execution / input validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_repository_id", ["../escape", "a/b", "..", "-leading-dash", ""])
def test_load_repository_rejects_unsafe_repository_ids(
    loader: RepositoryLoader, source_repository: tuple[Path, str, str], bad_repository_id: str
) -> None:
    source_path, commit_sha, _ = source_repository

    with pytest.raises(InvalidRepositoryInputError):
        loader.load_repository(bad_repository_id, str(source_path), commit_sha)


@pytest.mark.parametrize(
    "bad_source_url",
    ["", "-upload-pack=/bin/sh", "https://example.com/repo.git; rm -rf /", "https://example.com/`whoami`.git"],
)
def test_load_repository_rejects_unsafe_source_urls(
    loader: RepositoryLoader, source_repository: tuple[Path, str, str], bad_source_url: str
) -> None:
    _, commit_sha, _ = source_repository

    with pytest.raises(InvalidRepositoryInputError):
        loader.load_repository("repo-bad-url", bad_source_url, commit_sha)


# ---------------------------------------------------------------------------
# Requirement 5: dominant language determined by byte statistics, not file count
# ---------------------------------------------------------------------------


def test_primary_language_is_determined_by_bytes_not_file_count(
    loader: RepositoryLoader, byte_dominant_language_repository: tuple[Path, str]
) -> None:
    source_path, commit_sha = byte_dominant_language_repository

    repository = loader.load_repository("repo-byte-dominant", str(source_path), commit_sha)

    # Five tiny .js files outnumber one large .py file -- file-count-based
    # selection would say JavaScript; byte-based selection must say Python.
    assert repository.language_distribution[Language.JAVASCRIPT] == 5
    assert repository.language_distribution[Language.PYTHON] == 1
    assert repository.language_byte_distribution[Language.PYTHON] > repository.language_byte_distribution[Language.JAVASCRIPT]
    assert repository.primary_language is Language.PYTHON


# ---------------------------------------------------------------------------
# Requirement 6: explicit submodule handling
# ---------------------------------------------------------------------------


def test_uninitialized_submodule_is_recorded_but_excluded_from_counts(
    loader: RepositoryLoader, repository_with_submodule: tuple[Path, str, str]
) -> None:
    parent_path, commit_sha, _ = repository_with_submodule

    repository = loader.load_repository("repo-with-submodule", str(parent_path), commit_sha)

    assert repository.submodules == ["vendor/lib"]
    # app.py and .gitmodules only -- vendor/lib's placeholder directory and its
    # (uninitialized, empty) content must not be counted.
    assert repository.file_count == 2
    assert repository.directory_count == 1  # 'vendor' itself, not 'vendor/lib'


def test_initialize_submodules_setting_includes_submodule_content(
    tmp_path: Path, repository_with_submodule: tuple[Path, str, str]
) -> None:
    parent_path, commit_sha, _ = repository_with_submodule
    settings = RepositoryLoaderSettings(clone_root=str(tmp_path / "clones"), initialize_submodules=True)
    loader = RepositoryLoader(settings=settings)

    repository = loader.load_repository("repo-with-submodule-init", str(parent_path), commit_sha)

    assert repository.submodules == ["vendor/lib"]
    # app.py, .gitmodules, vendor/lib/lib.py, and vendor/lib/.git (an initialized
    # submodule checkout has its own real ".git" *file*, not a directory, pointing
    # at its actual git-dir elsewhere -- unlike a top-level ".git" directory, it
    # isn't excluded by the directory-name ignore list. Documented in README.md's
    # "Potential Failure Modes" as a known, minor over-count.
    assert repository.file_count == 4
    assert (Path(repository.local_path) / "vendor" / "lib" / "lib.py").exists()


# ---------------------------------------------------------------------------
# Requirement 7: repository_manifest.json is persisted after validation
# ---------------------------------------------------------------------------


def test_manifest_is_persisted_and_matches_the_returned_repository(
    loader: RepositoryLoader, source_repository: tuple[Path, str, str]
) -> None:
    source_path, commit_sha, _ = source_repository

    repository = loader.load_repository("repo-manifest", str(source_path), commit_sha)

    assert repository.manifest_path is not None
    manifest_file = Path(repository.manifest_path)
    assert manifest_file.exists()
    assert manifest_file.parent == Path(repository.local_path)

    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert payload["repository_id"] == "repo-manifest"
    assert payload["commit_sha"] == commit_sha
    assert payload["file_count"] == repository.file_count
    assert payload["manifest_version"] == 1
