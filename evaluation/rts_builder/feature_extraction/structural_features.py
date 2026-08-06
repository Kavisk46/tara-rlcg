"""Computes `StructuralFeatures` from a `RepositoryModel`.

`comment_coverage_ratio` is the one feature in this whole subsystem
that reads outside `RepositoryModel`'s own data: Python's `ast` module
(which `evaluation.rts_builder.parser` is built on) discards comments
entirely, so no comment information exists anywhere in `RepositoryModel`
to read. Computing it at all requires re-reading each source file from
disk via `RepositoryModel.root_path` -- see `README.md`'s "Design
Decisions" and `REVIEW_RESPONSE.md` for why this is an accepted,
explicitly-flagged exception to "receives RepositoryModel + Developer
Query" rather than a silent one, and how it degrades gracefully
(returns 0.0, never raises) if the source is no longer accessible.
"""
from __future__ import annotations

import io
import tokenize as std_tokenize
from pathlib import Path

from evaluation.rts_builder.feature_extraction.config import FeatureExtractionSettings
from evaluation.rts_builder.feature_extraction.models import StructuralFeatures
from evaluation.rts_builder.parser.models import RepositoryModel
from tara.core.logging import get_logger

logger = get_logger(__name__)


def compute_structural_features(model: RepositoryModel, settings: FeatureExtractionSettings) -> StructuralFeatures:
    """Compute every code-organization/documentation-density feature.

    Args:
        model: The parsed repository to summarize.
        settings: Controls whether `comment_coverage_ratio` is computed
            at all (`enable_comment_coverage`).

    Returns:
        The populated `StructuralFeatures`.
    """
    file_count = len(model.files)
    function_count = len(model.functions)
    class_count = len(model.classes)

    avg_functions_per_file = function_count / max(file_count, 1)
    avg_classes_per_file = class_count / max(file_count, 1)

    documentable = [*model.functions, *model.classes]
    docstring_coverage_ratio = (
        sum(1 for symbol in documentable if symbol.docstring) / len(documentable) if documentable else 0.0
    )

    comment_coverage_ratio = _compute_comment_coverage(model) if settings.enable_comment_coverage else 0.0

    return StructuralFeatures(
        avg_functions_per_file=avg_functions_per_file,
        avg_classes_per_file=avg_classes_per_file,
        docstring_coverage_ratio=docstring_coverage_ratio,
        comment_coverage_ratio=comment_coverage_ratio,
    )


def _compute_comment_coverage(model: RepositoryModel) -> float:
    """Return the mean, per-file fraction of source lines that are comment lines.

    A file that cannot be re-read or re-tokenized is skipped (logged,
    not raised) and excluded from the mean, rather than counted as 0%
    commented -- a stale/missing file should not silently drag down the
    ratio for files that are still perfectly readable.
    """
    root = Path(model.root_path)
    if not root.is_dir():
        logger.warning(
            "RepositoryModel.root_path %s no longer exists; comment_coverage_ratio defaulting to 0.0.", root
        )
        return 0.0

    ratios: list[float] = []
    for normalized_file in model.files:
        ratio = _comment_ratio_for_file(root / normalized_file.path)
        if ratio is not None:
            ratios.append(ratio)

    return sum(ratios) / len(ratios) if ratios else 0.0


def _comment_ratio_for_file(file_path: Path) -> float | None:
    """Return one file's comment-line fraction, or None if it can't be read/tokenized."""
    try:
        source = file_path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Could not read %s for comment_coverage_ratio: %s", file_path, exc)
        return None

    total_lines = len(source.splitlines())
    if total_lines == 0:
        return 0.0

    comment_lines = 0
    try:
        for token in std_tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == std_tokenize.COMMENT:
                comment_lines += 1
    except (std_tokenize.TokenError, SyntaxError, IndentationError) as exc:
        logger.warning("Could not tokenize %s for comment_coverage_ratio: %s", file_path, exc)
        return None

    return comment_lines / total_lines
