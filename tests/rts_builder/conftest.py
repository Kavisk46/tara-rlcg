"""Shared fixtures for the RTS Builder's Repository Loader tests."""
from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo as GitRepo

from evaluation.rts_builder.config import RepositoryLoaderSettings
from evaluation.rts_builder.repository_loader import RepositoryLoader


def _init_repo(repo_path: Path) -> GitRepo:
    """Create an empty git repository at `repo_path` with a test-suite identity configured."""
    repo_path.mkdir(parents=True, exist_ok=True)
    repo = GitRepo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "TARA Test Suite")
        config.set_value("user", "email", "tara-tests@example.com")
    return repo


@pytest.fixture(scope="module")
def source_repository(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, str]:
    """A small, real git repository to clone from, with two known pinned commits.

    Module-scoped and read-only for every test that uses it: tests only
    clone *from* this path, never mutate it, so sharing one real repo
    across the whole module avoids repeating the (comparatively slow)
    git-init-and-commit setup per test. Content is chosen to exercise
    language detection (Python + JavaScript), ignored-directory exclusion
    (`node_modules`), and multi-line commit messages. A second commit is
    included specifically so tests can exercise the reviewer-mandated
    "reuse must verify commit consistency" behavior (fetch + forced
    checkout when a reused clone is pinned to the wrong commit).

    Returns:
        `(repo_path, first_commit_sha, second_commit_sha)`.
    """
    repo_path = tmp_path_factory.mktemp("rts_loader_source") / "source_repo"
    repo = _init_repo(repo_path)

    (repo_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (repo_path / "utils.js").write_text("console.log('hi');\n", encoding="utf-8")
    nested_dir = repo_path / "nested"
    nested_dir.mkdir()
    (nested_dir / "module.py").write_text("x = 1\n", encoding="utf-8")
    ignored_dir = repo_path / "node_modules"
    ignored_dir.mkdir()
    (ignored_dir / "dependency.js").write_text("// vendored\n", encoding="utf-8")
    (repo_path / "README.md").write_text("# Sample\n", encoding="utf-8")

    repo.index.add(["app.py", "utils.js", "nested/module.py", "node_modules/dependency.js", "README.md"])
    first_commit = repo.index.commit("Initial commit\n\nA longer description line.")

    (repo_path / "app.py").write_text("print('hello, again')\n", encoding="utf-8")
    repo.index.add(["app.py"])
    second_commit = repo.index.commit("Update app.py")

    return repo_path, first_commit.hexsha, second_commit.hexsha


@pytest.fixture
def loader_settings(tmp_path: Path) -> RepositoryLoaderSettings:
    """Loader settings pointing `clone_root` at a fresh, isolated temp directory per test."""
    return RepositoryLoaderSettings(clone_root=str(tmp_path / "clones"))


@pytest.fixture
def loader(loader_settings: RepositoryLoaderSettings) -> RepositoryLoader:
    """A `RepositoryLoader` using `loader_settings` and a fresh default `LanguageRegistry`."""
    return RepositoryLoader(settings=loader_settings)


@pytest.fixture(scope="module")
def repository_with_submodule(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, str]:
    """A git repository with one submodule declared at `vendor/lib`.

    `protocol.file.allow=always` is passed as a one-off `-c` override on
    the `git submodule add` invocation only: modern git refuses `file://`
    -style submodule sources by default (a real, unrelated-to-us
    hardening git shipped for exactly the kind of local-path submodule
    setup this fixture needs). Production submodule URLs are `https://`
    and are never affected by this; it only exists so this fixture can
    build a realistic submodule scenario without a network dependency.

    Returns:
        `(parent_repo_path, submodule_commit_sha_in_parent, parent_commit_sha)`.
    """
    submodule_source_path = tmp_path_factory.mktemp("rts_submodule_source") / "sub_source"
    submodule_repo = _init_repo(submodule_source_path)
    (submodule_source_path / "lib.py").write_text("value = 42\n", encoding="utf-8")
    submodule_repo.index.add(["lib.py"])
    submodule_repo.index.commit("Submodule initial commit")

    parent_path = tmp_path_factory.mktemp("rts_submodule_parent") / "parent_repo"
    parent_repo = _init_repo(parent_path)
    (parent_path / "app.py").write_text("print('parent')\n", encoding="utf-8")
    parent_repo.index.add(["app.py"])
    parent_repo.index.commit("Parent initial commit")

    parent_repo.git.execute(
        [
            "git", "-c", "protocol.file.allow=always",
            "submodule", "add", str(submodule_source_path), "vendor/lib",
        ]
    )
    # Only `.gitmodules` needs staging here: `git submodule add` already stages
    # `vendor/lib` itself as a gitlink (mode 160000). Re-adding "vendor/lib" via
    # `index.add` would instead walk its working-tree contents (including its own
    # internal `.git` file) and stage them as ordinary blobs, corrupting the
    # gitlink into a nested `vendor/lib/.git` path that Windows git refuses to
    # check out on a later clone.
    parent_repo.index.add([".gitmodules"])
    commit = parent_repo.index.commit("Add vendor/lib submodule")

    return parent_path, commit.hexsha, str(submodule_source_path)


@pytest.fixture(scope="module")
def byte_dominant_language_repository(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    """A repository where file *count* and file *byte size* disagree on the dominant language.

    Five tiny JavaScript files outnumber a single, much larger Python
    file -- exercising `_determine_primary_language`'s byte-based
    selection (`primary_language` should be Python) as distinct from a
    naive file-count-based selection (which would incorrectly say
    JavaScript).
    """
    repo_path = tmp_path_factory.mktemp("rts_byte_dominant") / "byte_repo"
    repo = _init_repo(repo_path)

    added_files = []
    for i in range(5):
        filename = f"tiny_{i}.js"
        (repo_path / filename).write_text("1;\n", encoding="utf-8")
        added_files.append(filename)

    large_content = "\n".join(f"def generated_function_{i}():\n    return {i}\n" for i in range(200))
    (repo_path / "large_module.py").write_text(large_content, encoding="utf-8")
    added_files.append("large_module.py")

    repo.index.add(added_files)
    commit = repo.index.commit("Mixed language, byte-count mismatch")

    return repo_path, commit.hexsha
