"""Abstract interface for the Repository Parser pipeline stage.

`RepositoryParser` is the first stage of the TARA pipeline: it turns a
path to a repository on disk into a `ParsedRepository`, the structural
fact-base every later stage (context extraction, task classification,
retrieval) builds on. Defining it as an ABC lets TARA swap parsing
backends (e.g. a future incremental or cached parser) without touching
any downstream code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from tara.parsing.models import ParsedRepository


class RepositoryParser(ABC):
    """Contract for turning a repository on disk into structural facts."""

    @abstractmethod
    def parse(self, repository_path: Path) -> ParsedRepository:
        """Parse every supported source file in a repository.

        Args:
            repository_path: Filesystem path to the root of the
                repository to parse.

        Returns:
            A `ParsedRepository` containing one `ParsedFile` per
            successfully parsed source file, plus a `ParseError` for
            every file that failed to parse.

        Raises:
            RepositoryParsingError: If `repository_path` does not exist
                or is not a directory.
        """
        raise NotImplementedError
