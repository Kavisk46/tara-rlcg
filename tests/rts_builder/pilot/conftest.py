"""Shared fixtures for the RTS Builder's Pilot subsystem tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from git import Repo as GitRepo

from evaluation.rts_builder.config import RepositoryLoaderSettings
from evaluation.rts_builder.dataset_builder.config import DatasetBuilderSettings
from evaluation.rts_builder.dataset_builder.dataset_generator import DatasetGenerator
from evaluation.rts_builder.dataset_builder.pipeline_orchestrator import PipelineOrchestrator
from evaluation.rts_builder.dataset_builder.query_iterator import QueryIterator
from evaluation.rts_builder.dataset_builder.repository_iterator import RepositoryIterator
from evaluation.rts_builder.parser.config import ParserSettings
from evaluation.rts_builder.parser.pipeline import PythonParserPipeline
from evaluation.rts_builder.pilot.assembler import load_current_rows
from evaluation.rts_builder.pilot.config import PilotSettings
from evaluation.rts_builder.repository_loader import RepositoryLoader


def _init_repo(repo_path: Path) -> GitRepo:
    repo_path.mkdir(parents=True, exist_ok=True)
    repo = GitRepo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "TARA Test Suite")
        config.set_value("user", "email", "tara-tests@example.com")
    return repo


@pytest.fixture(scope="module")
def two_repository_sources(tmp_path_factory: pytest.TempPathFactory) -> list[tuple[str, Path, str]]:
    """Two small, real repositories, for exercising repository_distribution across more than one repo."""
    sources: list[tuple[str, Path, str]] = []
    for index in range(2):
        repo_path = tmp_path_factory.mktemp(f"rts_pilot_source_{index}") / "source_repo"
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
        sources.append((f"pilot-repo-{index}", repo_path, commit.hexsha))
    return sources


@pytest.fixture
def manifest_path(tmp_path: Path, two_repository_sources: list[tuple[str, Path, str]]) -> Path:
    """A two-repository manifest.json, each with distinct passthrough metadata."""
    manifest = [
        {
            "repository_id": repository_id, "source_url": str(source_path), "commit_sha": commit_sha,
            "metadata": {"license": f"license-{repository_id}"},
        }
        for repository_id, source_path, commit_sha in two_repository_sources
    ]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


@pytest.fixture
def queries_path(tmp_path: Path, two_repository_sources: list[tuple[str, Path, str]]) -> Path:
    """Three queries per repository (six total), with non-trivial relevance grades."""
    queries = []
    for repository_id, _source_path, _commit_sha in two_repository_sources:
        queries.extend(
            [
                {"repository_id": repository_id, "query_text": f"How does Dog bark in {repository_id}?", "relevance_grades": {"app.py": 2.0, "pkg/base.py": 1.0}},
                {"repository_id": repository_id, "query_text": f"fix the bug in helper for {repository_id}", "relevance_grades": {"app.py": 1.0}},
                {"repository_id": repository_id, "query_text": f"explain the Animal class in {repository_id}", "relevance_grades": {"pkg/base.py": 2.0}},
            ]
        )
    path = tmp_path / "queries.jsonl"
    path.write_text("\n".join(json.dumps(query) for query in queries), encoding="utf-8")
    return path


@pytest.fixture
def dataset_settings(tmp_path: Path) -> DatasetBuilderSettings:
    """Dataset builder settings pointing output_dir at an isolated temp directory, grouped export forced on."""
    return DatasetBuilderSettings(output_dir=str(tmp_path / "dataset_out"), enable_grouped_export=True)


@pytest.fixture
def isolated_orchestrator(tmp_path: Path) -> PipelineOrchestrator:
    """A `PipelineOrchestrator` whose Repository Loader / Parser caches are isolated to `tmp_path`."""
    return PipelineOrchestrator(
        repository_loader=RepositoryLoader(settings=RepositoryLoaderSettings(clone_root=str(tmp_path / "clones"))),
        parser_pipeline=PythonParserPipeline(settings=ParserSettings(cache_root=str(tmp_path / "parsed"))),
    )


@pytest.fixture
def pilot_settings(tmp_path: Path) -> PilotSettings:
    """Pilot settings pointing data_dir at an isolated temp directory, with a fixed, deterministic split seed."""
    return PilotSettings(data_dir=str(tmp_path / "data"), split_seed="pilot-test-seed")


@pytest.fixture
def sample_rows(
    dataset_settings: DatasetBuilderSettings, isolated_orchestrator: PipelineOrchestrator,
    manifest_path: Path, queries_path: Path,
) -> list[dict[str, object]]:
    """Real, frozen-pipeline-produced flat rows (2 repos x 3 queries x 4 strategies = 24 rows), assembled and enriched.

    Built by actually running `DatasetGenerator` + `assembler.load_current_rows`, not hand
    -typed -- so these rows always match the real, current flat-row schema (every feature/
    label/provenance column) even as the frozen upstream models evolve. Each row's `split` is
    set to `"train"` as a placeholder; tests exercising split assignment itself compute their
    own via `QuerySplitter`.
    """
    generator = DatasetGenerator(settings=dataset_settings, orchestrator=isolated_orchestrator)
    summary = generator.generate(RepositoryIterator(manifest_path), QueryIterator(queries_path))

    metadata_by_repository_id = {spec.repository_id: spec.metadata for spec in RepositoryIterator(manifest_path)}
    grouped_path = Path(dataset_settings.output_dir) / dataset_settings.grouped_jsonl_filename
    rows = load_current_rows(
        grouped_path, summary.pipeline_digest.digest_hash, summary.input_digest.digest_hash, metadata_by_repository_id
    )
    for row in rows:
        row["split"] = "train"
    return rows
