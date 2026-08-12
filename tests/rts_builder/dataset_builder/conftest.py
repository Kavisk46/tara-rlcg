"""Shared fixtures for the RTS Builder's Dataset Builder subsystem tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from git import Repo as GitRepo

from evaluation.rts_builder.config import RepositoryLoaderSettings
from evaluation.rts_builder.dataset_builder.config import DatasetBuilderSettings
from evaluation.rts_builder.dataset_builder.pipeline_orchestrator import PipelineOrchestrator
from evaluation.rts_builder.parser.config import ParserSettings
from evaluation.rts_builder.parser.pipeline import PythonParserPipeline
from evaluation.rts_builder.repository_loader import RepositoryLoader


def _init_repo(repo_path: Path) -> GitRepo:
    repo_path.mkdir(parents=True, exist_ok=True)
    repo = GitRepo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "TARA Test Suite")
        config.set_value("user", "email", "tara-tests@example.com")
    return repo


@pytest.fixture(scope="module")
def sample_repository_source(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    """A small, real repository, returned with its pinned commit sha."""
    repo_path = tmp_path_factory.mktemp("rts_dataset_source") / "source_repo"
    repo = _init_repo(repo_path)

    pkg = repo_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "base.py").write_text(
        '"""Base module."""\nclass Animal:\n    """An animal."""\n\n    def speak(self):\n        return "noise"\n',
        encoding="utf-8",
    )
    (repo_path / "app.py").write_text(
        '"""App module."""\n'
        "from pkg.base import Animal\n\n\n"
        "def helper():\n    return 1\n\n\n"
        "def main():\n    return helper()\n\n\n"
        'class Dog(Animal):\n    """A dog that barks."""\n\n'
        "    def bark(self):\n        return helper()\n",
        encoding="utf-8",
    )
    repo.index.add(["pkg/__init__.py", "pkg/base.py", "app.py"])
    commit = repo.index.commit("Initial commit")
    return repo_path, commit.hexsha


@pytest.fixture
def manifest_path(tmp_path: Path, sample_repository_source: tuple[Path, str]) -> Path:
    """A one-repository manifest.json pointing at `sample_repository_source`."""
    source_path, commit_sha = sample_repository_source
    manifest = [{"repository_id": "test-repo", "source_url": str(source_path), "commit_sha": commit_sha}]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


@pytest.fixture
def queries_path(tmp_path: Path) -> Path:
    """A two-query queries.jsonl for `test-repo`."""
    queries = [
        {"repository_id": "test-repo", "query_text": "How does Dog bark?", "relevance_grades": {"app.py": 2.0, "pkg/base.py": 1.0}},
        {"repository_id": "test-repo", "query_text": "fix the bug in helper", "relevance_grades": {"app.py": 1.0}},
    ]
    path = tmp_path / "queries.jsonl"
    path.write_text("\n".join(json.dumps(q) for q in queries), encoding="utf-8")
    return path


@pytest.fixture
def dataset_settings(tmp_path: Path) -> DatasetBuilderSettings:
    """Dataset builder settings pointing `output_dir` at a fresh, isolated temp directory per test.

    Also points Repository Loader's own clone_root and Parser's own
    cache_root at isolated temp locations (via environment-free direct
    construction in the tests that need them) -- callers that need
    non-default upstream settings construct their own
    `PipelineOrchestrator` explicitly; this fixture only covers
    Dataset Builder's own settings surface.
    """
    return DatasetBuilderSettings(output_dir=str(tmp_path / "dataset_out"))


@pytest.fixture
def isolated_orchestrator(tmp_path: Path) -> PipelineOrchestrator:
    """A `PipelineOrchestrator` whose Repository Loader / Parser caches are isolated to `tmp_path`.

    Without this, the default `RepositoryLoaderSettings`/`ParserSettings`
    would clone/cache into the *actual* project working directory's
    `.rts_cache/`, polluting it every time the Dataset Builder test
    suite runs.
    """
    return PipelineOrchestrator(
        repository_loader=RepositoryLoader(settings=RepositoryLoaderSettings(clone_root=str(tmp_path / "clones"))),
        parser_pipeline=PythonParserPipeline(settings=ParserSettings(cache_root=str(tmp_path / "parsed"))),
    )
