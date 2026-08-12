"""Shared utilities for the LTR experiment framework: seeding, logging, and JSONL I/O.

Every script in this package (`dataset_inspection`, `feature_pipeline`,
`train`, `evaluate`, `importance`, `error_analysis`) imports from here
rather than reimplementing seeding or logging setup, so behavior (e.g.
which RNGs a "seed everything" call touches) is identical everywhere
it matters for reproducibility.
"""
from __future__ import annotations

import json
import logging
import os
import random
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np

# Resolved once, relative to this file, so every script works regardless
# of the caller's current working directory.
LTR_DIR: Path = Path(__file__).resolve().parent
REPO_ROOT: Path = LTR_DIR.parents[2]
MERGED_DATASET_DIR: Path = REPO_ROOT / "evaluation" / "rts_builder" / "pilot" / "merged_dataset"
OUTPUTS_DIR: Path = LTR_DIR / "outputs"
MODELS_DIR: Path = OUTPUTS_DIR / "models"
FIGURES_DIR: Path = OUTPUTS_DIR / "figures"
REPORTS_DIR: Path = OUTPUTS_DIR / "reports"

TO_BE_ASSIGNED = "TO_BE_ASSIGNED"
"""The literal placeholder grade used throughout the RTS Dataset v1.0 for
every relevance judgment that has not yet been through human review.
See `evaluation/rts_builder/pilot/merged_dataset/dataset_card.md`
("Quality control"). A row with this grade carries no usable label and
must never be silently coerced to a numeric value -- see
`feature_pipeline.validate_labels_are_numeric`.
"""

RELEVANCE_GRADES = (0, 1, 2, 3)
"""The valid, finalized relevance-grade scale once human annotation is
complete, per `RELEVANCE_ANNOTATION_HANDBOOK.md`: 1-3 for a graded
relevant file (increasing relevance), with grade 0 reserved for "not
relevant" (recorded by the *absence* of a row for that file, per the
handbook, but accepted here as an explicit value too, for a labeling
tool that emits it explicitly rather than by omission).
"""


def set_global_seed(seed: int) -> None:
    """Seed every RNG this package's code paths can touch.

    Covers Python's `random`, NumPy, and (if installed and already
    imported) LightGBM's own RNG usage is controlled per-call via its
    `seed`/`random_state` parameters, not globally -- callers must also
    pass `seed` explicitly to `model.LambdaRankModel`. This function
    only handles the *global* RNGs that libraries fall back to when no
    explicit seed is given.

    Args:
        seed: The seed to apply everywhere.
    """
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def get_logger(name: str, *, level: int = logging.INFO, log_file: Path | None = None) -> logging.Logger:
    """Return a configured `Logger` that writes to stderr and, optionally, a file.

    Idempotent: calling this twice for the same `name` does not
    duplicate handlers (important since scripts may be imported by
    tests, which also call this).

    Args:
        name: Logger name, conventionally `__name__` of the caller.
        level: Minimum level to emit.
        log_file: If given, also append formatted records to this file
            (parent directories created if needed).

    Returns:
        A `logging.Logger` ready to use.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if logger.handlers:
        return logger  # already configured (e.g. re-imported in tests)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
    )

    stream_handler = logging.StreamHandler(stream=sys.stderr)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a `.jsonl` file into a list of dicts, preserving row order.

    Args:
        path: Path to a UTF-8 `.jsonl` file, one JSON object per line.
            Blank lines are skipped.

    Returns:
        One dict per non-blank line, in file order.

    Raises:
        FileNotFoundError: If `path` does not exist.
        json.JSONDecodeError: If a non-blank line is not valid JSON
            (re-raised with the offending line number prepended to the
            message, since the stdlib error alone does not report it
            for JSONL -- each line is parsed independently).
    """
    if not path.is_file():
        raise FileNotFoundError(f"JSONL file not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise json.JSONDecodeError(
                    f"{path}:{line_no}: {exc.msg}", exc.doc, exc.pos
                ) from exc
    return rows


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Lazily iterate a `.jsonl` file's rows, one dict at a time.

    Prefer this over `read_jsonl` when a caller only needs to stream
    through rows once (e.g. `dataset_inspection`'s distribution scans)
    and the file could plausibly be large.

    Args:
        path: Path to a UTF-8 `.jsonl` file.

    Yields:
        One dict per non-blank line, in file order.
    """
    if not path.is_file():
        raise FileNotFoundError(f"JSONL file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise json.JSONDecodeError(
                    f"{path}:{line_no}: {exc.msg}", exc.doc, exc.pos
                ) from exc


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write `rows` to `path` as UTF-8 JSONL, one compact JSON object per line.

    Args:
        path: Destination file (parent directories created if needed).
        rows: Rows to write, in the order given.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def ensure_output_dirs() -> None:
    """Create `outputs/{models,figures,reports}` if they do not already exist."""
    for d in (MODELS_DIR, FIGURES_DIR, REPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
