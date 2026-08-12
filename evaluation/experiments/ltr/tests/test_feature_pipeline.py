"""Unit tests for `feature_pipeline.py`: encoders, label validation, and structural features.

None of these tests invoke the frozen Repository Loader / Parser /
Feature Extraction / Retrieval Executor subsystems (`retrieval_provider=None`
throughout) -- that integration is exercised separately as a live smoke
test (see `README.md`'s "What was actually run" section), not as part
of this fast, hermetic unit-test suite.
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from evaluation.experiments.ltr.feature_pipeline import (
    CATEGORICAL_STRUCTURAL_COLUMNS, STRUCTURAL_FEATURE_COLUMNS, CategoryEncoder, Encoders,
    RETRIEVAL_FEATURE_COLUMNS, SchemaError, UnlabeledDatasetError, build_feature_matrix,
    validate_labels_are_numeric,
)
from evaluation.experiments.ltr.utils import TO_BE_ASSIGNED


def _make_row(query_id: str, repository_id: str, category: str, difficulty: str, query_text: str, candidates: list[dict]) -> dict:
    return {
        "query_id": query_id,
        "repository_id": repository_id,
        "category": category,
        "difficulty": difficulty,
        "query_text": query_text,
        "notes": "synthetic test fixture",
        "candidates": candidates,
    }


UNLABELED_ROWS = [
    _make_row(
        "repo-001", "repo", "bug_fix", "medium", "a query with enough words to pass validation checks",
        [
            {"file": "a/b.py", "grade": TO_BE_ASSIGNED, "reason": "x"},
            {"file": "a/c.py", "grade": TO_BE_ASSIGNED, "reason": "y"},
        ],
    ),
]

LABELED_ROWS = [
    _make_row(
        "repo-001", "repo", "bug_fix", "medium", "a query with enough words to pass validation checks",
        [
            {"file": "a/b.py", "grade": 3, "reason": "the real fix location"},
            {"file": "a/test_b.py", "grade": 1, "reason": "regression test"},
            {"file": "docs/b.rst", "grade": 0, "reason": "unrelated doc"},
        ],
    ),
    _make_row(
        "repo-002", "repo", "feature_implementation", "easy", "a second query also with enough words in it",
        [
            {"file": "a/d.py", "grade": 2, "reason": "the feature site"},
        ],
    ),
]


class TestValidateLabelsAreNumeric:
    def test_raises_when_fully_placeholder(self) -> None:
        with pytest.raises(UnlabeledDatasetError):
            validate_labels_are_numeric(UNLABELED_ROWS, split_name="unit_test")

    def test_passes_when_at_least_one_real_grade(self) -> None:
        validate_labels_are_numeric(LABELED_ROWS, split_name="unit_test")  # should not raise

    def test_raises_on_zero_candidates(self) -> None:
        rows = [_make_row("r-001", "repo", "bug_fix", "easy", "a query with enough words for validation", [])]
        with pytest.raises(UnlabeledDatasetError):
            validate_labels_are_numeric(rows, split_name="unit_test")


class TestCategoryEncoder:
    def test_fit_assigns_sorted_codes_deterministically(self) -> None:
        enc = CategoryEncoder("x").fit(["banana", "apple", "cherry"])
        # Sorted vocabulary: apple=0, banana=1, cherry=2 -- regardless of input order.
        assert enc.transform_one("apple") == 0
        assert enc.transform_one("banana") == 1
        assert enc.transform_one("cherry") == 2

    def test_fit_order_does_not_affect_codes(self) -> None:
        enc1 = CategoryEncoder("x").fit(["a", "b", "c"])
        enc2 = CategoryEncoder("x").fit(["c", "b", "a"])
        for v in ("a", "b", "c"):
            assert enc1.transform_one(v) == enc2.transform_one(v)

    def test_unseen_value_gets_unknown_code(self) -> None:
        enc = CategoryEncoder("x").fit(["a", "b"])
        assert enc.transform_one("never_seen") == enc.unknown_code
        assert enc.unknown_code == 2

    def test_roundtrip_through_dict(self) -> None:
        enc = CategoryEncoder("x").fit(["z", "a", "m"])
        restored = CategoryEncoder.from_dict(json.loads(json.dumps(enc.to_dict())))
        assert restored.transform_one("a") == enc.transform_one("a")
        assert restored.transform_one("z") == enc.transform_one("z")

    def test_used_before_fit_raises(self) -> None:
        enc = CategoryEncoder("x")
        with pytest.raises(Exception):
            enc.transform_one("a")


class TestEncoders:
    def test_fit_covers_all_three_columns(self) -> None:
        encoders = Encoders.fit(LABELED_ROWS)
        assert encoders.category.transform_one("bug_fix") != encoders.category.unknown_code
        assert encoders.repository_id.transform_one("repo") != encoders.repository_id.unknown_code
        assert encoders.file_extension.transform_one(".py") != encoders.file_extension.unknown_code

    def test_save_and_load_roundtrip(self, tmp_path) -> None:
        encoders = Encoders.fit(LABELED_ROWS)
        path = tmp_path / "encoders.json"
        encoders.save(path)
        restored = Encoders.load(path)
        assert restored.category.transform_one("bug_fix") == encoders.category.transform_one("bug_fix")
        assert restored.repository_id.transform_one("repo") == encoders.repository_id.transform_one("repo")


class TestBuildFeatureMatrix:
    def test_shape_and_deterministic_column_order(self) -> None:
        encoders = Encoders.fit(LABELED_ROWS)
        matrix = build_feature_matrix(LABELED_ROWS, encoders=encoders, retrieval_provider=None, require_numeric_labels=True)

        n_candidates = sum(len(r["candidates"]) for r in LABELED_ROWS)
        assert matrix.X.shape[0] == n_candidates
        assert matrix.y.shape[0] == n_candidates
        assert list(matrix.group_sizes) == [3, 1]
        assert matrix.query_ids == ["repo-001", "repo-002"]

        expected_columns = (
            list(STRUCTURAL_FEATURE_COLUMNS) + list(RETRIEVAL_FEATURE_COLUMNS) + list(CATEGORICAL_STRUCTURAL_COLUMNS)
        )
        assert matrix.feature_names == expected_columns

    def test_labels_match_input_grades_in_row_order(self) -> None:
        encoders = Encoders.fit(LABELED_ROWS)
        matrix = build_feature_matrix(LABELED_ROWS, encoders=encoders, retrieval_provider=None, require_numeric_labels=True)
        assert list(matrix.y) == [3, 1, 0, 2]

    def test_retrieval_columns_are_nan_and_unavailable_without_provider(self) -> None:
        encoders = Encoders.fit(LABELED_ROWS)
        matrix = build_feature_matrix(LABELED_ROWS, encoders=encoders, retrieval_provider=None, require_numeric_labels=True)
        lexical_score_idx = matrix.feature_names.index("lexical_score")
        lexical_available_idx = matrix.feature_names.index("lexical_available")
        assert np.all(np.isnan(matrix.X[:, lexical_score_idx]))
        assert np.all(matrix.X[:, lexical_available_idx] == 0.0)

    def test_placeholder_rows_are_dropped_when_labels_required(self) -> None:
        mixed_rows = LABELED_ROWS + UNLABELED_ROWS
        encoders = Encoders.fit(mixed_rows)
        matrix = build_feature_matrix(mixed_rows, encoders=encoders, retrieval_provider=None, require_numeric_labels=True)
        # UNLABELED_ROWS's query ("repo-001" -- note: same id as LABELED_ROWS's first entry in
        # this fixture combination is intentionally avoided by using distinct ids in a real
        # dataset; here we assert only that no row with grade TO_BE_ASSIGNED made it into y.
        assert TO_BE_ASSIGNED not in [str(v) for v in matrix.y]
        assert matrix.X.shape[0] == 4  # only LABELED_ROWS's 4 candidates remain

    def test_invalid_grade_value_raises_schema_error(self) -> None:
        bad_rows = [
            _make_row(
                "repo-099", "repo", "bug_fix", "easy", "a query with enough words for schema validation",
                [{"file": "a.py", "grade": 99, "reason": "x"}],
            )
        ]
        encoders = Encoders.fit(bad_rows)
        with pytest.raises(SchemaError):
            build_feature_matrix(bad_rows, encoders=encoders, retrieval_provider=None, require_numeric_labels=True)

    def test_candidate_path_features_are_computed_correctly(self) -> None:
        rows = [
            _make_row(
                "repo-050", "repo", "testing", "easy", "a query with enough words for a feature check",
                [{"file": "pkg/sub/test_thing.py", "grade": 1, "reason": "x"}],
            )
        ]
        encoders = Encoders.fit(rows)
        matrix = build_feature_matrix(rows, encoders=encoders, retrieval_provider=None, require_numeric_labels=True)
        depth_idx = matrix.feature_names.index("candidate_path_depth")
        is_test_idx = matrix.feature_names.index("candidate_is_test_file")
        assert matrix.X[0, depth_idx] == 2.0  # "pkg/sub/test_thing.py" has 2 "/" characters
        assert matrix.X[0, is_test_idx] == 1.0
