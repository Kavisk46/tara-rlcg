"""Unit tests for `evaluation.ablations.matrix`."""
from __future__ import annotations

from pathlib import Path

from evaluation.ablations.definitions import ABLATION_DEFINITIONS
from evaluation.ablations.matrix import (
    DEFAULT_MATRIX_PATH,
    build_ablation_matrix,
    read_ablation_matrix_json,
    write_ablation_matrix_json,
)


def test_build_ablation_matrix_wraps_all_definitions() -> None:
    matrix = build_ablation_matrix()
    assert matrix.ablations == list(ABLATION_DEFINITIONS)


def test_round_trip_through_json(tmp_path: Path) -> None:
    matrix = build_ablation_matrix()
    path = tmp_path / "matrix.json"

    write_ablation_matrix_json(matrix, path)
    loaded = read_ablation_matrix_json(path)

    assert loaded == matrix


def test_committed_matrix_file_is_up_to_date() -> None:
    # The generated deliverable file must reflect the current ABLATION_DEFINITIONS -- if this
    # fails, someone changed definitions.py without regenerating ablation_matrix.json
    # (`python -m evaluation.ablations.matrix`).
    assert DEFAULT_MATRIX_PATH.exists(), (
        "ablation_matrix.json does not exist -- run `python -m evaluation.ablations.matrix`."
    )
    on_disk = read_ablation_matrix_json(DEFAULT_MATRIX_PATH)
    current = build_ablation_matrix()
    assert on_disk == current, (
        "ablation_matrix.json is stale -- re-run `python -m evaluation.ablations.matrix`."
    )
