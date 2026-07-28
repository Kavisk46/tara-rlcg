"""Shared pytest fixtures for the TARA test suite."""
from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo


@pytest.fixture
def sample_repository(tmp_path: Path) -> Path:
    """Create a small, real Git repository with Python source files for parser tests."""
    repo_path = tmp_path / "sample_repo"
    repo_path.mkdir()
    repo = Repo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "TARA Test Suite")
        config.set_value("user", "email", "tara-tests@example.com")

    (repo_path / "app.py").write_text(
        '''"""Application entry point."""
import os
from collections import OrderedDict


class Greeter:
    """Greets users by name."""

    def greet(self, name: str) -> str:
        """Return a greeting for `name`."""
        return f"Hello, {name}!"


def main() -> None:
    """Run the application."""
    greeter = Greeter()
    print(greeter.greet("World"))
''',
        encoding="utf-8",
    )

    (repo_path / "utils.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )

    (repo_path / "README.md").write_text("# Sample\n", encoding="utf-8")

    repo.index.add(["app.py", "utils.py", "README.md"])
    repo.index.commit("Initial commit")

    return repo_path
