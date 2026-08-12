"""Integration tests for `evaluation.rts_builder.dataset_builder.pipeline_orchestrator.PipelineOrchestrator`."""
from __future__ import annotations

from evaluation.rts_builder.dataset_builder.models import QuerySpec, RepositorySpec
from evaluation.rts_builder.dataset_builder.pipeline_orchestrator import PipelineOrchestrator
from evaluation.rts_builder.feature_extraction.models import FeatureVector
from evaluation.rts_builder.oracle_utility.models import OracleUtilityResult
from evaluation.rts_builder.parser.models import RepositoryModel


def test_run_repository_stages_returns_repository_and_parsed_model(
    isolated_orchestrator: PipelineOrchestrator, sample_repository_source: tuple, manifest_path
) -> None:
    source_path, commit_sha = sample_repository_source
    spec = RepositorySpec(repository_id="test-repo", source_url=str(source_path), commit_sha=commit_sha)

    repository, model = isolated_orchestrator.run_repository_stages(spec)

    assert repository.repository_id == "test-repo"
    assert repository.commit_sha == commit_sha
    assert isinstance(model, RepositoryModel)
    assert model.repository_id == "test-repo"
    assert len(model.files) == 3


def test_run_query_stages_returns_features_and_oracle_result(
    isolated_orchestrator: PipelineOrchestrator, sample_repository_source: tuple
) -> None:
    source_path, commit_sha = sample_repository_source
    spec = RepositorySpec(repository_id="test-repo", source_url=str(source_path), commit_sha=commit_sha)
    _repository, model = isolated_orchestrator.run_repository_stages(spec)

    query_spec = QuerySpec(repository_id="test-repo", query_text="How does Dog bark?", relevance_grades={"app.py": 1.0})
    feature_vector, oracle_result = isolated_orchestrator.run_query_stages(model, query_spec)

    assert isinstance(feature_vector, FeatureVector)
    assert feature_vector.query_text == "How does Dog bark?"
    assert isinstance(oracle_result, OracleUtilityResult)
    assert len(oracle_result.rows) == 4
    assert oracle_result.query_text == "How does Dog bark?"


def test_run_query_stages_reflects_the_relevance_judgment(
    isolated_orchestrator: PipelineOrchestrator, sample_repository_source: tuple
) -> None:
    source_path, commit_sha = sample_repository_source
    spec = RepositorySpec(repository_id="test-repo", source_url=str(source_path), commit_sha=commit_sha)
    _repository, model = isolated_orchestrator.run_repository_stages(spec)

    query_spec = QuerySpec(repository_id="test-repo", query_text="anything", relevance_grades={})
    _feature_vector, oracle_result = isolated_orchestrator.run_query_stages(model, query_spec)

    # No ground truth at all -- every strategy's quality_score must degrade to 0.0 (see Oracle Utility's
    # own documented behavior for an empty RelevanceJudgment).
    assert all(row.quality.quality_score == 0.0 for row in oracle_result.rows)
