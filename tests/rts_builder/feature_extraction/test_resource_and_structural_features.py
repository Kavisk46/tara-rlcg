"""Unit tests for resource-feature size buckets and structural-feature graceful degradation."""
from __future__ import annotations

import shutil
from pathlib import Path

from evaluation.rts_builder.feature_extraction.config import FeatureExtractionSettings
from evaluation.rts_builder.feature_extraction.models import RepositorySizeCategory
from evaluation.rts_builder.feature_extraction.resource_features import compute_resource_features
from evaluation.rts_builder.feature_extraction.structural_features import compute_structural_features
from evaluation.rts_builder.parser.models import NormalizedFile, RepositoryModel


def _fabricate_model(file_count: int, root_path: str = "/does-not-matter") -> RepositoryModel:
    files = [
        NormalizedFile(
            path=f"module_{i}.py", size_bytes=100, content_hash=f"hash{i}",
            module_docstring=None, function_count=0, class_count=0, import_count=0,
        )
        for i in range(file_count)
    ]
    return RepositoryModel(
        repository_id="fabricated", commit_sha="a" * 40, root_path=root_path,
        files=files, functions=[], classes=[], imports=[], import_graph=[],
        call_graph=[], inheritance_graph=[], parse_errors=[],
    )


def test_repository_size_category_small_at_threshold() -> None:
    settings = FeatureExtractionSettings(small_repository_file_count_threshold=50, large_repository_file_count_threshold=500)
    features = compute_resource_features(_fabricate_model(50), settings)
    assert features.repository_size_category is RepositorySizeCategory.SMALL


def test_repository_size_category_medium_just_above_small_threshold() -> None:
    settings = FeatureExtractionSettings(small_repository_file_count_threshold=50, large_repository_file_count_threshold=500)
    features = compute_resource_features(_fabricate_model(51), settings)
    assert features.repository_size_category is RepositorySizeCategory.MEDIUM


def test_repository_size_category_medium_at_large_threshold() -> None:
    settings = FeatureExtractionSettings(small_repository_file_count_threshold=50, large_repository_file_count_threshold=500)
    features = compute_resource_features(_fabricate_model(500), settings)
    assert features.repository_size_category is RepositorySizeCategory.MEDIUM


def test_repository_size_category_large_above_large_threshold() -> None:
    settings = FeatureExtractionSettings(small_repository_file_count_threshold=50, large_repository_file_count_threshold=500)
    features = compute_resource_features(_fabricate_model(501), settings)
    assert features.repository_size_category is RepositorySizeCategory.LARGE


def test_estimated_tokens_uses_configured_chars_per_token_ratio() -> None:
    settings = FeatureExtractionSettings(chars_per_token_estimate=2.0)
    model = _fabricate_model(1)  # 100 bytes total
    features = compute_resource_features(model, settings)
    assert features.estimated_repository_tokens == 50


def test_comment_coverage_gracefully_degrades_when_root_path_removed_after_parsing(tmp_path: Path) -> None:
    root = tmp_path / "vanished_repo"
    root.mkdir()
    (root / "module_0.py").write_text("x = 1\n", encoding="utf-8")
    model = _fabricate_model(1, root_path=str(root))

    shutil.rmtree(root)

    settings = FeatureExtractionSettings()
    features = compute_structural_features(model, settings)

    assert features.comment_coverage_ratio == 0.0


def test_comment_coverage_skips_unreadable_files_but_still_averages_the_rest(tmp_path: Path) -> None:
    root = tmp_path / "partial_repo"
    root.mkdir()
    (root / "module_0.py").write_text("# a comment\nx = 1\n", encoding="utf-8")
    model = RepositoryModel(
        repository_id="partial", commit_sha="a" * 40, root_path=str(root),
        files=[
            NormalizedFile(path="module_0.py", size_bytes=10, content_hash="h0", module_docstring=None, function_count=0, class_count=0, import_count=0),
            NormalizedFile(path="missing.py", size_bytes=10, content_hash="h1", module_docstring=None, function_count=0, class_count=0, import_count=0),
        ],
        functions=[], classes=[], imports=[], import_graph=[], call_graph=[], inheritance_graph=[], parse_errors=[],
    )

    features = compute_structural_features(model, FeatureExtractionSettings())

    # module_0.py: 1 comment line / 2 total lines = 0.5; missing.py is skipped, not averaged in as 0.
    assert features.comment_coverage_ratio == 0.5
