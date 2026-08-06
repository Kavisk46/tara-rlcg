"""Repository file walk: finds candidate Python source files, applying ignore/size filters.

Self-contained rather than reusing ``tara.parsing``'s walk (see
``README.md``'s "Design Decisions"): this milestone is Python-only, so
its file selection is a simple suffix check, not a multi-language
``LanguageRegistry`` lookup.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from tara.core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_IGNORED_DIRECTORIES: frozenset[str] = frozenset(
    {
        ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
        ".ruff_cache", "node_modules", "dist", "build", ".venv", "venv",
        ".tox", ".idea", ".vscode", "site-packages", "egg-info", ".rts_cache",
    }
)

_PYTHON_SUFFIXES: frozenset[str] = frozenset({".py", ".pyi"})


def iter_python_files(
    root_path: Path,
    extra_ignored_directories: frozenset[str] = frozenset(),
    max_file_size_bytes: int = 2_000_000,
) -> Iterator[Path]:
    """Yield every Python source file under ``root_path``, applying ignore/size filters.

    Uses an explicit stack rather than recursion, consistent with the
    rest of the RTS Builder's directory walks (``RepositoryLoader``'s
    ``_scan_tree``), to avoid Python's recursion limit on a deeply
    nested tree.

    Args:
        root_path: Repository root to walk.
        extra_ignored_directories: Additional directory names to
            exclude, on top of ``_DEFAULT_IGNORED_DIRECTORIES``.
        max_file_size_bytes: Files larger than this are skipped.

    Yields:
        Absolute paths to files with a ``.py`` or ``.pyi`` suffix, not
        under an ignored directory, at or below the size limit.
    """
    ignored_directories = _DEFAULT_IGNORED_DIRECTORIES | extra_ignored_directories

    stack = [root_path]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError as exc:
            logger.warning("Cannot list directory %s: %s", current, exc)
            continue

        for entry in entries:
            if entry.is_dir():
                if entry.name not in ignored_directories:
                    stack.append(entry)
                continue

            if entry.suffix not in _PYTHON_SUFFIXES:
                continue

            try:
                if entry.stat().st_size > max_file_size_bytes:
                    logger.debug("Skipping oversized file %s", entry)
                    continue
            except OSError as exc:
                logger.warning("Cannot stat file %s: %s", entry, exc)
                continue

            yield entry
