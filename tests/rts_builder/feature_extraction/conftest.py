"""Shared fixtures for the RTS Builder's Feature Extraction subsystem tests.

Uses the real `RepositoryLoader` and `PythonParserPipeline` (Milestones
1-2, accepted and frozen) to produce a real `RepositoryModel` for
integration-style tests, plus a directly constructed, empty
`RepositoryModel` for edge-case tests that don't need a real repository
on disk.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo as GitRepo

from evaluation.rts_builder.config import RepositoryLoaderSettings
from evaluation.rts_builder.feature_extraction.config import FeatureExtractionSettings
from evaluation.rts_builder.feature_extraction.extractor import FeatureExtractor
from evaluation.rts_builder.parser.config import ParserSettings
from evaluation.rts_builder.parser.models import RepositoryModel
from evaluation.rts_builder.parser.pipeline import PythonParserPipeline
from evaluation.rts_builder.repository_loader import RepositoryLoader


def _init_repo(repo_path: Path) -> GitRepo:
    repo_path.mkdir(parents=True, exist_ok=True)
    repo = GitRepo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "TARA Test Suite")
        config.set_value("user", "email", "tara-tests@example.com")
    return repo


@pytest.fixture
def feature_settings(tmp_path: Path) -> FeatureExtractionSettings:
    """Default feature-extraction settings."""
    return FeatureExtractionSettings()


@pytest.fixture
def extractor(feature_settings: FeatureExtractionSettings) -> FeatureExtractor:
    """A `FeatureExtractor` using `feature_settings`."""
    return FeatureExtractor(settings=feature_settings)


@pytest.fixture(scope="module")
def sample_source(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small, real repository exercising every feature group at once.

    `pkg/base.py` defines `Animal` (docstring + a `#`-commented method
    body). `app.py` imports `Animal`, defines `helper` and `main`
    (which calls `helper`), and `Dog(Animal)` with a `bark` method
    (which also calls `helper`) -- and includes source comments, for
    `comment_coverage_ratio`.
    """
    repo_path = tmp_path_factory.mktemp("rts_features_source") / "source_repo"
    repo = _init_repo(repo_path)

    pkg = repo_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "base.py").write_text(
        "# Base module comment\n"
        'class Animal:\n    """An animal."""\n\n'
        "    def speak(self):\n        # noise\n        return 'noise'\n",
        encoding="utf-8",
    )
    (repo_path / "app.py").write_text(
        '"""App module."""\n'
        "from pkg.base import Animal\n\n\n"
        "def helper():\n    # returns one\n    return 1\n\n\n"
        "def main():\n    return helper()\n\n\n"
        "class Dog(Animal):\n    def bark(self):\n        return helper()\n",
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
    repository = loader.load_repository("features-repo", str(sample_source), commit_sha)

    pipeline = PythonParserPipeline(settings=ParserSettings(cache_root=str(tmp_path / "parsed")))
    return pipeline.parse_repository(repository)


@pytest.fixture
def empty_repository_model(tmp_path: Path) -> RepositoryModel:
    """A directly constructed `RepositoryModel` with zero files, for edge-case tests."""
    return RepositoryModel(
        repository_id="empty-repo",
        commit_sha="a" * 40,
        root_path=str(tmp_path / "does_not_matter"),
        files=[],
        functions=[],
        classes=[],
        imports=[],
        import_graph=[],
        call_graph=[],
        inheritance_graph=[],
        parse_errors=[],
    )
