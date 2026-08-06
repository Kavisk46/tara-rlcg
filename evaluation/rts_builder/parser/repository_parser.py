"""Walks a repository and parses every Python file in it, tolerating individual failures.

Composes ``file_walker.iter_python_files`` and ``PythonFileParser``:
requirement steps 1-4 (walk, ignore, parse AST, extract) of the Parser
subsystem's scope, stopping short of repository-wide graph construction
(``graph_builder.py``) and normalization (``normalizer.py``), which need
every file's parse available at once and so belong to the caller
(``pipeline.py``), not to a per-file-resilient walk.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from evaluation.rts_builder.parser.config import ParserSettings
from evaluation.rts_builder.parser.exceptions import PythonFileParseError
from evaluation.rts_builder.parser.file_parser import ParsedPythonFile, PythonFileParser
from evaluation.rts_builder.parser.file_walker import iter_python_files
from tara.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ParseFailure:
    """Records a recoverable failure while parsing a single file."""

    file_path: str
    message: str


@dataclass(frozen=True)
class RepositoryParseResult:
    """Every file that parsed successfully, plus every file that didn't."""

    files: list[ParsedPythonFile] = field(default_factory=list)
    errors: list[ParseFailure] = field(default_factory=list)


class PythonRepositoryParser:
    """Parses every Python file in a repository, one file's failure never aborting the rest."""

    def __init__(self, settings: ParserSettings | None = None, file_parser: PythonFileParser | None = None) -> None:
        """Construct the parser.

        Args:
            settings: Controls the walk's ignore list and size limit.
                Defaults to ``ParserSettings()`` (environment defaults).
            file_parser: Defaults to a fresh ``PythonFileParser()``.
        """
        self._settings = settings or ParserSettings()
        self._file_parser = file_parser or PythonFileParser()

    def parse(self, repository_root: Path) -> RepositoryParseResult:
        """Walk and parse every Python file under ``repository_root``.

        Args:
            repository_root: Absolute path to the repository root.

        Returns:
            Every successfully parsed file, plus a ``ParseFailure`` for
            every file that failed (bad encoding or a syntax error).
        """
        files: list[ParsedPythonFile] = []
        errors: list[ParseFailure] = []

        for file_path in iter_python_files(
            repository_root,
            extra_ignored_directories=frozenset(self._settings.ignored_directories),
            max_file_size_bytes=self._settings.max_file_size_bytes,
        ):
            relative = file_path.relative_to(repository_root).as_posix()
            try:
                files.append(self._file_parser.parse(repository_root, file_path))
            except PythonFileParseError as exc:
                logger.warning("Failed to parse %s: %s", relative, exc)
                errors.append(ParseFailure(file_path=relative, message=str(exc)))

        logger.info("Parsed repository %s: %d files parsed, %d errors", repository_root, len(files), len(errors))
        return RepositoryParseResult(files=files, errors=errors)
