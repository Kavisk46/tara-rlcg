"""Computes `RepositoryFeatures` from a `RepositoryModel`."""
from __future__ import annotations

from evaluation.rts_builder.feature_extraction.models import RepositoryFeatures
from evaluation.rts_builder.parser.models import RepositoryModel
from tara.core.types import Language


def compute_repository_features(model: RepositoryModel) -> RepositoryFeatures:
    """Compute every repository-level size/shape feature.

    Args:
        model: The parsed repository to summarize.

    Returns:
        The populated `RepositoryFeatures`.
    """
    file_count = len(model.files)
    function_count = len(model.functions)
    class_count = len(model.classes)
    module_count = len({_top_level_module_name(normalized_file.path) for normalized_file in model.files})
    avg_file_size_bytes = (
        sum(normalized_file.size_bytes for normalized_file in model.files) / file_count if file_count else 0.0
    )
    dominant_language = Language.PYTHON if file_count else Language.UNKNOWN

    return RepositoryFeatures(
        file_count=file_count,
        function_count=function_count,
        class_count=class_count,
        module_count=module_count,
        avg_file_size_bytes=avg_file_size_bytes,
        dominant_language=dominant_language,
    )


def _top_level_module_name(file_path: str) -> str:
    """Return the top-level package/module a file belongs to.

    A nested file (`pkg/sub/mod.py`) belongs to top-level module
    `"pkg"`; a bare top-level file (`app.py`) is its own module,
    `"app"`. This is deliberately coarser than `file_count` -- see
    `RepositoryFeatures.module_count`'s docstring and `README.md`.
    """
    if "/" in file_path:
        return file_path.split("/", 1)[0]
    for suffix in (".py", ".pyi"):
        if file_path.endswith(suffix):
            return file_path[: -len(suffix)]
    return file_path
