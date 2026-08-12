"""Shared fixtures for the RTS Builder's Oracle Utility subsystem tests.

Most tests construct `RetrievalExecutionResult` directly (via
`make_execution_result`) rather than running the full Repository Loader
-> Parser -> Feature Extraction -> Retrieval Executor pipeline: this
subsystem's only real input dependency is the *shape* of
`RetrievalExecutionResult`, and fabricating it directly makes expected
quality/utility/ranking values easy to reason about precisely. One
end-to-end integration fixture (`real_execution_result`) exercises the
full, real pipeline once, to prove composition with the actual frozen
milestones still works.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo as GitRepo

from evaluation.rts_builder.config import RepositoryLoaderSettings
from evaluation.rts_builder.feature_extraction.config import FeatureExtractionSettings
from evaluation.rts_builder.feature_extraction.extractor import FeatureExtractor
from evaluation.rts_builder.oracle_utility.config import OracleUtilitySettings
from evaluation.rts_builder.parser.config import ParserSettings
from evaluation.rts_builder.parser.pipeline import PythonParserPipeline
from evaluation.rts_builder.repository_loader import RepositoryLoader
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings
from evaluation.rts_builder.retrieval_executor.executor import RetrievalExecutor
from evaluation.rts_builder.retrieval_executor.models import (
    RetrievalExecutionResult,
    RetrievalStrategyName,
    RetrievedFile,
    StrategyResult,
)

_REPOSITORY_ID = "oracle-test-repo"
_COMMIT_SHA = "a" * 40
_QUERY_TEXT = "how does Dog bark?"


def make_strategy_result(
    strategy_name: RetrievalStrategyName,
    file_scores: dict[str, float],
    latency_ms: float,
    context_token_count: int = 100,
) -> StrategyResult:
    """Build a `StrategyResult` directly, ranked by descending score."""
    ordered = sorted(file_scores.items(), key=lambda pair: (-pair[1], pair[0]))
    retrieved_files = [RetrievedFile(file_path=path, score=score) for path, score in ordered]
    return StrategyResult(
        strategy_name=strategy_name,
        repository_id=_REPOSITORY_ID,
        commit_sha=_COMMIT_SHA,
        query_text=_QUERY_TEXT,
        retrieved_files=retrieved_files,
        retrieval_score=max(file_scores.values(), default=0.0),
        retrieval_latency_ms=latency_ms,
        context_token_count=context_token_count,
    )


def make_execution_result(
    lexical_files: dict[str, float],
    dense_files: dict[str, float],
    graph_files: dict[str, float],
    hybrid_files: dict[str, float],
    latencies: dict[RetrievalStrategyName, float] | None = None,
) -> RetrievalExecutionResult:
    """Build a full `RetrievalExecutionResult` directly from per-strategy file->score mappings."""
    latencies = latencies or {
        RetrievalStrategyName.LEXICAL: 1.0,
        RetrievalStrategyName.DENSE: 2.0,
        RetrievalStrategyName.GRAPH: 0.5,
        RetrievalStrategyName.HYBRID: 0.1,
    }
    return RetrievalExecutionResult(
        repository_id=_REPOSITORY_ID,
        commit_sha=_COMMIT_SHA,
        query_text=_QUERY_TEXT,
        lexical=make_strategy_result(RetrievalStrategyName.LEXICAL, lexical_files, latencies[RetrievalStrategyName.LEXICAL]),
        dense=make_strategy_result(RetrievalStrategyName.DENSE, dense_files, latencies[RetrievalStrategyName.DENSE]),
        graph=make_strategy_result(RetrievalStrategyName.GRAPH, graph_files, latencies[RetrievalStrategyName.GRAPH]),
        hybrid=make_strategy_result(RetrievalStrategyName.HYBRID, hybrid_files, latencies[RetrievalStrategyName.HYBRID]),
    )


@pytest.fixture
def oracle_settings() -> OracleUtilitySettings:
    """Default Oracle Utility settings."""
    return OracleUtilitySettings()


@pytest.fixture
def basic_execution_result() -> RetrievalExecutionResult:
    """A simple, fabricated `RetrievalExecutionResult` with clearly-differentiated per-strategy results."""
    return make_execution_result(
        lexical_files={"app.py": 5.0},
        dense_files={"app.py": 0.9, "pkg/base.py": 0.4, "pkg/__init__.py": 0.1},
        graph_files={"app.py": 1.0, "pkg/base.py": 0.5},
        hybrid_files={"app.py": 0.9, "pkg/base.py": 0.5, "pkg/__init__.py": 0.1},
    )


def _init_repo(repo_path: Path) -> GitRepo:
    repo_path.mkdir(parents=True, exist_ok=True)
    repo = GitRepo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "TARA Test Suite")
        config.set_value("user", "email", "tara-tests@example.com")
    return repo


@pytest.fixture(scope="module")
def real_pipeline_source(tmp_path_factory: pytest.TempPathFactory) -> Path:
    repo_path = tmp_path_factory.mktemp("rts_oracle_source") / "source_repo"
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
def real_execution_result(tmp_path: Path, real_pipeline_source: Path) -> RetrievalExecutionResult:
    """A real `RetrievalExecutionResult`, computed by the actual, frozen upstream pipeline."""
    commit_sha = GitRepo(real_pipeline_source).head.commit.hexsha
    loader = RepositoryLoader(settings=RepositoryLoaderSettings(clone_root=str(tmp_path / "clones")))
    repository = loader.load_repository("real-oracle-repo", str(real_pipeline_source), commit_sha)

    parser_pipeline = PythonParserPipeline(settings=ParserSettings(cache_root=str(tmp_path / "parsed")))
    model = parser_pipeline.parse_repository(repository)

    feature_extractor = FeatureExtractor(settings=FeatureExtractionSettings())
    feature_vector = feature_extractor.extract(model, "How does Dog bark?")

    retrieval_executor = RetrievalExecutor(settings=RetrievalExecutorSettings())
    return retrieval_executor.execute_all(model, feature_vector, "How does Dog bark?")
