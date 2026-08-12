"""Unit tests for `dataset_inspection.py`, using small synthetic split files (never the real dataset).

Real-dataset inspection is exercised separately by actually running
`python -m evaluation.experiments.ltr.dataset_inspection` (see
`README.md` and `outputs/reports/phase1_dataset_inspection.md`, a
genuine, already-generated report against the real split files) --
these tests instead check the *inspection logic itself* against
deliberately-broken small fixtures, which the real dataset (having
already passed this exact inspection cleanly) cannot exercise.
"""
from __future__ import annotations

import json

import pytest

from evaluation.experiments.ltr.dataset_inspection import format_report, inspect_split
from evaluation.experiments.ltr.utils import TO_BE_ASSIGNED, write_jsonl


def _valid_row(qid: str, repo: str = "repo", n_candidates: int = 2) -> dict:
    return {
        "query_id": qid,
        "repository_id": repo,
        "category": "bug_fix",
        "difficulty": "medium",
        "query_text": "a synthetic query with enough words to look realistic",
        "notes": "synthetic fixture",
        "candidates": [
            {"file": f"a/file_{i}.py", "grade": TO_BE_ASSIGNED, "reason": "synthetic"} for i in range(n_candidates)
        ],
    }


class TestInspectSplit:
    def test_clean_file_has_no_errors(self, tmp_path) -> None:
        path = tmp_path / "train.jsonl"
        write_jsonl(path, [_valid_row("repo-001"), _valid_row("repo-002")])
        result = inspect_split("train", path)
        assert result.n_rows == 2
        assert result.schema_errors == []
        assert result.missing_value_errors == []
        assert result.duplicate_query_ids == []
        assert result.zero_candidate_query_ids == []

    def test_missing_top_level_field_is_detected(self, tmp_path) -> None:
        row = _valid_row("repo-001")
        del row["notes"]
        path = tmp_path / "train.jsonl"
        write_jsonl(path, [row])
        result = inspect_split("train", path)
        assert any("notes" in e for e in result.schema_errors)

    def test_empty_query_text_is_a_missing_value_error(self, tmp_path) -> None:
        row = _valid_row("repo-001")
        row["query_text"] = "   "
        path = tmp_path / "train.jsonl"
        write_jsonl(path, [row])
        result = inspect_split("train", path)
        assert any("query_text" in e for e in result.missing_value_errors)

    def test_zero_candidates_detected(self, tmp_path) -> None:
        row = _valid_row("repo-001", n_candidates=0)
        path = tmp_path / "train.jsonl"
        write_jsonl(path, [row])
        result = inspect_split("train", path)
        assert result.zero_candidate_query_ids == ["repo-001"]

    def test_duplicate_query_id_detected(self, tmp_path) -> None:
        path = tmp_path / "train.jsonl"
        write_jsonl(path, [_valid_row("dupe-001"), _valid_row("dupe-001")])
        result = inspect_split("train", path)
        assert result.duplicate_query_ids == ["dupe-001"]

    def test_unexpected_category_flagged(self, tmp_path) -> None:
        row = _valid_row("repo-001")
        row["category"] = "not_a_real_category"
        path = tmp_path / "train.jsonl"
        write_jsonl(path, [row])
        result = inspect_split("train", path)
        assert any("category" in e for e in result.schema_errors)

    def test_duplicate_candidate_file_within_query_flagged(self, tmp_path) -> None:
        row = _valid_row("repo-001", n_candidates=1)
        row["candidates"].append(dict(row["candidates"][0]))  # exact duplicate file
        path = tmp_path / "train.jsonl"
        write_jsonl(path, [row])
        result = inspect_split("train", path)
        assert any("duplicate candidate file" in e for e in result.schema_errors)

    def test_all_placeholder_grades_reported_not_raised(self, tmp_path) -> None:
        path = tmp_path / "train.jsonl"
        write_jsonl(path, [_valid_row("repo-001")])
        result = inspect_split("train", path)  # must not raise -- Phase 1 reports, does not gate
        assert result.has_any_numeric_label is False
        assert result.grade_value_counts[TO_BE_ASSIGNED] == 2

    def test_real_numeric_grade_detected(self, tmp_path) -> None:
        row = _valid_row("repo-001", n_candidates=1)
        row["candidates"][0]["grade"] = 2
        path = tmp_path / "train.jsonl"
        write_jsonl(path, [row])
        result = inspect_split("train", path)
        assert result.has_any_numeric_label is True

    def test_missing_file_raises(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError):
            inspect_split("train", tmp_path / "does_not_exist.jsonl")


class TestFormatReport:
    def test_report_mentions_every_split(self, tmp_path) -> None:
        path = tmp_path / "train.jsonl"
        write_jsonl(path, [_valid_row("repo-001")])
        result = inspect_split("train", path)
        report = format_report([result])
        assert "train" in report
        assert "repo-001" not in report  # per-row IDs aren't expected verbatim, but the split name is
        assert "TO_BE_ASSIGNED" in report or "No real numeric relevance grade" in report
