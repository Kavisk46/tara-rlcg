"""Shared fixtures for the `tara.context` test suite."""
from __future__ import annotations

from pathlib import Path

import pytest

from tara.parsing.models import ParsedRepository
from tara.parsing.repository_parser import TreeSitterRepositoryParser


@pytest.fixture
def parsed_sample_repository(sample_repository: Path) -> ParsedRepository:
    """Parse the shared `sample_repository` fixture with the real Repository Parser.

    Context-extraction tests exercise the real, already-tested
    `TreeSitterRepositoryParser` so graph/embedding logic is tested
    against realistic input; only the embedding *model* is ever mocked.
    """
    return TreeSitterRepositoryParser().parse(sample_repository)
