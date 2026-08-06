"""Atomic JSON export for a `RepositoryModel` (requirement 7).

The single JSON-writing code path in this package: both a direct,
one-off ``export_repository_model`` call and the incremental-parsing
cache (`cache.py`, on every fresh parse) go through this function, so
there is exactly one place that knows how to serialize a `RepositoryModel`
to disk.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from evaluation.rts_builder.parser.models import RepositoryModel


def export_repository_model(model: RepositoryModel, path: Path) -> Path:
    """Atomically write `model` as JSON to `path`.

    Written via write-to-temp-file-then-atomic-rename (`Path.replace`,
    atomic on both POSIX and Windows, matching the technique already
    used by `RepositoryLoader`'s `repository_manifest.json` and the
    previous milestone's `parser_manifest.json`), so a crash mid-write
    can never leave a corrupt or truncated JSON file at `path`.

    Args:
        model: The repository model to export.
        path: Destination file path. Its parent directory is created if
            it doesn't already exist.

    Returns:
        `path`, for convenient chaining.

    Raises:
        OSError: If the file cannot be written (disk full, permissions).
            Callers that need a typed RTS-specific exception (e.g. the
            cache) are expected to catch this and re-raise as
            `ParserCacheError` themselves; this function stays a
            general-purpose export utility, not cache-specific.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = model.model_dump_json(indent=2)

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".repository_model_", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with open(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        tmp_path.replace(path)
    except OSError:
        tmp_path.unlink(missing_ok=True)
        raise
    return path
