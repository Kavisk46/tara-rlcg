"""Unit tests for `error_analysis.py`'s query/repository/confidence failure analysis.

Synthetic feature-matrix-shaped inputs throughout -- constructed to
have an analytically obvious right answer (e.g. "this specific query
must be wrong because its predicted top-1 file was deliberately given
the lowest true grade"), never real model output.
"""
from __future__ import annotations

import numpy as np

from evaluation.experiments.ltr.error_analysis import (
    analyze_queries, find_confidence_failures, summarize_by_category, summarize_by_repository,
)


def _fixture():
    """Two query groups: one where the model is correct, one where it is confidently wrong."""
    query_ids = ["q1", "q2"]
    # Row order: q1's 2 candidates, then q2's 2 candidates.
    repository_ids = ["repoA", "repoA", "repoB", "repoB"]
    categories = ["bug_fix", "testing"]
    difficulties = ["easy", "hard"]
    file_paths = ["a/best.py", "a/worst.py", "b/best.py", "b/worst.py"]
    y_true = np.array([3, 0, 3, 0])  # in both groups, first file is the true best
    # q1: model correctly scores the true-best file highest (small margin).
    # q2: model confidently (large margin) scores the WRONG file highest.
    y_score = np.array([2.0, 1.0, 1.0, 10.0])
    group_sizes = np.array([2, 2])
    return query_ids, repository_ids, categories, difficulties, file_paths, y_true, y_score, group_sizes


class TestAnalyzeQueries:
    def test_produces_one_row_per_group(self) -> None:
        rows = analyze_queries(*_fixture())
        assert len(rows) == 2
        assert [r.query_id for r in rows] == ["q1", "q2"]

    def test_correct_and_incorrect_groups_identified(self) -> None:
        rows = analyze_queries(*_fixture())
        q1, q2 = rows
        assert q1.is_top1_correct is True
        assert q2.is_top1_correct is False

    def test_predicted_and_true_best_files_are_correct(self) -> None:
        rows = analyze_queries(*_fixture())
        q1, q2 = rows
        assert q1.predicted_top_file == "a/best.py"
        assert q1.true_best_file == "a/best.py"
        assert q2.predicted_top_file == "b/worst.py"  # the model's (wrong) top pick
        assert q2.true_best_file == "b/best.py"

    def test_score_margin_computed_correctly(self) -> None:
        rows = analyze_queries(*_fixture())
        q1, q2 = rows
        assert q1.score_margin == 1.0  # 2.0 - 1.0
        assert q2.score_margin == 9.0  # 10.0 - 1.0


class TestSummaries:
    def test_summarize_by_repository(self) -> None:
        rows = analyze_queries(*_fixture())
        by_repo = summarize_by_repository(rows)
        assert by_repo["repoA"]["top1_accuracy"] == 1.0
        assert by_repo["repoB"]["top1_accuracy"] == 0.0
        assert by_repo["repoA"]["n_queries"] == 1

    def test_summarize_by_category(self) -> None:
        rows = analyze_queries(*_fixture())
        by_cat = summarize_by_category(rows)
        assert by_cat["bug_fix"]["top1_accuracy"] == 1.0
        assert by_cat["testing"]["top1_accuracy"] == 0.0


class TestConfidenceFailures:
    def test_only_wrong_and_confident_predictions_included(self) -> None:
        rows = analyze_queries(*_fixture())
        failures = find_confidence_failures(rows, margin_threshold=5.0)
        assert len(failures) == 1
        assert failures[0].query_id == "q2"

    def test_threshold_excludes_low_margin_wrong_predictions(self) -> None:
        rows = analyze_queries(*_fixture())
        # q2's margin is 9.0; a threshold above that should exclude it even though it's wrong.
        failures = find_confidence_failures(rows, margin_threshold=100.0)
        assert failures == []

    def test_correct_predictions_never_counted_as_confidence_failures(self) -> None:
        rows = analyze_queries(*_fixture())
        # Even a threshold of 0 (everything "confident") must not flag q1, which was correct.
        failures = find_confidence_failures(rows, margin_threshold=0.0)
        assert all(f.query_id != "q1" for f in failures)
