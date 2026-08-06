"""Shared fixtures for the RTS Builder's Retrieval Executor subsystem tests.

Uses the real Repository Loader, Parser, and Feature Extraction
pipelines (Milestones 1, 2, 4 -- all accepted and frozen) to produce a
real `(RepositoryModel, FeatureVector)` pair for integration-style
tests, plus directly-constructed, minimal `RepositoryModel`/`FeatureVector`
instances for edge-case tests that don't need a real repository on disk.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo as GitRepo

from evaluation.rts_builder.config import RepositoryLoaderSettings
from evaluation.rts_builder.feature_extraction.config import FeatureExtractionSettings
from evaluation.rts_builder.feature_extraction.extractor import FeatureExtractor
from evaluation.rts_builder.feature_extraction.models import FeatureVector
from evaluation.rts_builder.parser.config import ParserSettings
from evaluation.rts_builder.parser.models import RepositoryModel
from evaluation.rts_builder.parser.pipeline import PythonParserPipeline
from evaluation.rts_builder.repository_loader import RepositoryLoader
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings


def _init_repo(repo_path: Path) -> GitRepo:
    repo_path.mkdir(parents=True, exist_ok=True)
    repo = GitRepo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "TARA Test Suite")
        config.set_value("user", "email", "tara-tests@example.com")
    return repo


@pytest.fixture
def retrieval_settings() -> RetrievalExecutorSettings:
    """Default retrieval-executor settings."""
    return RetrievalExecutorSettings()


@pytest.fixture(scope="module")
def sample_source(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small, real repository exercising lexical, dense, and graph signals at once.

    `pkg/base.py` defines `Animal` (docstring + `speak` method).
    `app.py` imports `Animal`, defines `helper` and `main` (which calls
    `helper`), and `Dog(Animal)` with a `bark` method (also calling
    `helper`) -- import, call, and inheritance edges all present, and
    `Dog`/`Animal`/`bark`/`speak`/`helper` are all identifier-matchable
    query targets.
    """
    repo_path = tmp_path_factory.mktemp("rts_retrieval_source") / "source_repo"
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
    repo.index.commit("Initial commit")
    return repo_path


@pytest.fixture
def sample_repository_model(tmp_path: Path, sample_source: Path) -> RepositoryModel:
    """`sample_source` loaded and parsed via the real Repository Loader + Parser pipeline."""
    commit_sha = GitRepo(sample_source).head.commit.hexsha
    loader = RepositoryLoader(settings=RepositoryLoaderSettings(clone_root=str(tmp_path / "clones")))
    repository = loader.load_repository("retrieval-repo", str(sample_source), commit_sha)

    pipeline = PythonParserPipeline(settings=ParserSettings(cache_root=str(tmp_path / "parsed")))
    return pipeline.parse_repository(repository)


@pytest.fixture
def sample_feature_vector(sample_repository_model: RepositoryModel) -> FeatureVector:
    """The real `FeatureVector` for `sample_repository_model`, via Feature Extraction."""
    extractor = FeatureExtractor(settings=FeatureExtractionSettings())
    return extractor.extract(sample_repository_model, "How does Dog bark?")


@pytest.fixture
def empty_repository_model(tmp_path: Path) -> RepositoryModel:
    """A directly constructed `RepositoryModel` with zero files, for edge-case tests."""
    return RepositoryModel(
        repository_id="empty-repo",
        commit_sha="a" * 40,
        root_path=str(tmp_path / "does_not_matter"),
        files=[], functions=[], classes=[], imports=[],
        import_graph=[], call_graph=[], inheritance_graph=[], parse_errors=[],
    )


@pytest.fixture
def empty_feature_vector(empty_repository_model: RepositoryModel) -> FeatureVector:
    """The real `FeatureVector` for `empty_repository_model`."""
    extractor = FeatureExtractor(settings=FeatureExtractionSettings())
    return extractor.extract(empty_repository_model, "any query")
