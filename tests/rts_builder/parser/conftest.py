"""Shared fixtures for the RTS Builder's (Python-only) Parser subsystem tests.

Uses the real `RepositoryLoader` (Milestone 1, accepted and frozen) to
produce `Repository` objects to feed into `PythonParserPipeline`, rather
than constructing them by hand: this exercises the two milestones
together exactly as the RTS pipeline will actually compose them.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo as GitRepo

from evaluation.rts_builder.config import RepositoryLoaderSettings
from evaluation.rts_builder.models import Repository
from evaluation.rts_builder.parser.config import ParserSettings
from evaluation.rts_builder.parser.pipeline import PythonParserPipeline
from evaluation.rts_builder.repository_loader import RepositoryLoader


def _init_repo(repo_path: Path) -> GitRepo:
    """Create an empty git repository at `repo_path` with a test-suite identity configured."""
    repo_path.mkdir(parents=True, exist_ok=True)
    repo = GitRepo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "TARA Test Suite")
        config.set_value("user", "email", "tara-tests@example.com")
    return repo


def _load(tmp_path: Path, source_path: Path, commit_sha: str, repository_id: str) -> Repository:
    """Load `source_path`@`commit_sha` via a real `RepositoryLoader` into an isolated clone_root."""
    settings = RepositoryLoaderSettings(clone_root=str(tmp_path / "clones"))
    loader = RepositoryLoader(settings=settings)
    return loader.load_repository(repository_id, str(source_path), commit_sha)


@pytest.fixture
def parser_settings(tmp_path: Path) -> ParserSettings:
    """Parser settings pointing `cache_root` at a fresh, isolated temp directory per test."""
    return ParserSettings(cache_root=str(tmp_path / "parsed"))


@pytest.fixture
def pipeline(parser_settings: ParserSettings) -> PythonParserPipeline:
    """A `PythonParserPipeline` using `parser_settings` and default (real) collaborators."""
    return PythonParserPipeline(settings=parser_settings)


@pytest.fixture(scope="module")
def basic_source(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small, real repository exercising nearly every extraction target at once.

    `pkg/base.py` defines `Animal` (a class with a docstring and a
    `speak` method). `app.py` absolute-imports `Animal`, defines a
    top-level function `helper`, a decorated top-level function `main`
    that calls `helper`, and `Dog(Animal)` -- a subclass with a
    `@staticmethod` method `bark` (which calls `helper`) and an
    overridden `speak` method (which calls `self.bark()`, a same-class
    method-to-method call).
    """
    repo_path = tmp_path_factory.mktemp("rts_parser_basic") / "source_repo"
    repo = _init_repo(repo_path)

    pkg = repo_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "base.py").write_text(
        '"""Base module."""\n\n\nclass Animal:\n    """An animal."""\n\n    def speak(self):\n        return \'noise\'\n',
        encoding="utf-8",
    )
    (repo_path / "app.py").write_text(
        '"""App module."""\n'
        "from pkg.base import Animal\n"
        "import functools\n\n\n"
        "def helper():\n    return 1\n\n\n"
        "@functools.wraps(helper)\n"
        "def main():\n    return helper()\n\n\n"
        "class Dog(Animal):\n"
        '    """A dog."""\n\n'
        "    @staticmethod\n"
        "    def bark():\n        return helper()\n\n"
        "    def speak(self):\n        return self.bark()\n",
        encoding="utf-8",
    )

    repo.index.add(["pkg/__init__.py", "pkg/base.py", "app.py"])
    repo.index.commit("Initial commit")
    return repo_path


@pytest.fixture
def basic_repository(tmp_path: Path, basic_source: Path) -> Repository:
    """`basic_source` loaded (via a real `RepositoryLoader`) into an isolated clone."""
    commit_sha = GitRepo(basic_source).head.commit.hexsha
    return _load(tmp_path, basic_source, commit_sha, repository_id="basic-repo")


@pytest.fixture
def relative_import_repository(tmp_path: Path) -> Repository:
    """A repository exercising relative-import resolution (`from . import a`, `from .a import value`)."""
    repo_path = tmp_path / "relative_source"
    repo = _init_repo(repo_path)
    pkg = repo_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    (pkg / "b.py").write_text("from . import a\nfrom .a import value\n", encoding="utf-8")
    repo.index.add(["pkg/__init__.py", "pkg/a.py", "pkg/b.py"])
    commit = repo.index.commit("Relative imports")
    return _load(tmp_path, repo_path, commit.hexsha, repository_id="relative-repo")


@pytest.fixture
def ambiguous_call_repository(tmp_path: Path) -> Repository:
    """A repository where a call's target name matches two different functions -> zero call edges."""
    repo_path = tmp_path / "ambiguous_call_source"
    repo = _init_repo(repo_path)
    (repo_path / "a.py").write_text("def process():\n    return 'a'\n", encoding="utf-8")
    (repo_path / "b.py").write_text("def process():\n    return 'b'\n", encoding="utf-8")
    (repo_path / "caller.py").write_text("def caller():\n    return process()\n", encoding="utf-8")
    repo.index.add(["a.py", "b.py", "caller.py"])
    commit = repo.index.commit("Ambiguous process()")
    return _load(tmp_path, repo_path, commit.hexsha, repository_id="ambiguous-call-repo")


@pytest.fixture
def unresolved_call_repository(tmp_path: Path) -> Repository:
    """A repository whose only call site targets a builtin, never defined in the repository."""
    repo_path = tmp_path / "unresolved_call_source"
    repo = _init_repo(repo_path)
    (repo_path / "app.py").write_text("def caller():\n    return len([1, 2, 3])\n", encoding="utf-8")
    repo.index.add(["app.py"])
    commit = repo.index.commit("Unresolved builtin call")
    return _load(tmp_path, repo_path, commit.hexsha, repository_id="unresolved-call-repo")


@pytest.fixture
def multiple_inheritance_repository(tmp_path: Path) -> Repository:
    """A repository with a class inheriting from two locally defined base classes."""
    repo_path = tmp_path / "multi_inherit_source"
    repo = _init_repo(repo_path)
    (repo_path / "bases.py").write_text(
        "class Flyer:\n    pass\n\n\nclass Swimmer:\n    pass\n", encoding="utf-8"
    )
    (repo_path / "app.py").write_text(
        "from bases import Flyer, Swimmer\n\n\nclass Duck(Flyer, Swimmer):\n    pass\n", encoding="utf-8"
    )
    repo.index.add(["bases.py", "app.py"])
    commit = repo.index.commit("Multiple inheritance")
    return _load(tmp_path, repo_path, commit.hexsha, repository_id="multi-inherit-repo")


@pytest.fixture
def ambiguous_inheritance_repository(tmp_path: Path) -> Repository:
    """A repository where a base class name matches two different classes -> zero inheritance edges."""
    repo_path = tmp_path / "ambiguous_inherit_source"
    repo = _init_repo(repo_path)
    (repo_path / "a.py").write_text("class Base:\n    pass\n", encoding="utf-8")
    (repo_path / "b.py").write_text("class Base:\n    pass\n", encoding="utf-8")
    (repo_path / "app.py").write_text("class Child(Base):\n    pass\n", encoding="utf-8")
    repo.index.add(["a.py", "b.py", "app.py"])
    commit = repo.index.commit("Ambiguous Base")
    return _load(tmp_path, repo_path, commit.hexsha, repository_id="ambiguous-inherit-repo")


@pytest.fixture
def object_inheritance_repository(tmp_path: Path) -> Repository:
    """A repository with a class explicitly inheriting from `object` -> should not produce an edge."""
    repo_path = tmp_path / "object_inherit_source"
    repo = _init_repo(repo_path)
    (repo_path / "app.py").write_text("class Foo(object):\n    pass\n", encoding="utf-8")
    repo.index.add(["app.py"])
    commit = repo.index.commit("Explicit object base")
    return _load(tmp_path, repo_path, commit.hexsha, repository_id="object-inherit-repo")


@pytest.fixture
def syntax_error_repository(tmp_path: Path) -> Repository:
    """A repository with one syntactically invalid file alongside one valid file."""
    repo_path = tmp_path / "syntax_error_source"
    repo = _init_repo(repo_path)
    (repo_path / "good.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    (repo_path / "bad.py").write_text("def broken(:\n    return 1\n", encoding="utf-8")
    repo.index.add(["good.py", "bad.py"])
    commit = repo.index.commit("One broken file")
    return _load(tmp_path, repo_path, commit.hexsha, repository_id="syntax-error-repo")


@pytest.fixture
def ignored_and_non_python_repository(tmp_path: Path) -> Repository:
    """A repository with an ignored directory and a non-Python file, both of which must be skipped."""
    repo_path = tmp_path / "ignored_source"
    repo = _init_repo(repo_path)
    (repo_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    (repo_path / "notes.txt").write_text("not python\n", encoding="utf-8")
    venv_dir = repo_path / ".venv"
    venv_dir.mkdir()
    (venv_dir / "vendored.py").write_text("def should_not_be_seen():\n    return 1\n", encoding="utf-8")
    repo.index.add(["app.py", "notes.txt", ".venv/vendored.py"])
    commit = repo.index.commit("Ignored dir and non-python file")
    return _load(tmp_path, repo_path, commit.hexsha, repository_id="ignored-repo")


@pytest.fixture
def two_commit_repository(tmp_path: Path) -> tuple[Path, str, str]:
    """A source repository with two commits, for simulating a mid-pipeline mutation.

    Returns `(source_path, first_commit_sha, second_commit_sha)`.
    """
    repo_path = tmp_path / "two_commit_source"
    repo = _init_repo(repo_path)
    (repo_path / "app.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    repo.index.add(["app.py"])
    first = repo.index.commit("First commit")

    (repo_path / "app.py").write_text("def a():\n    return 2\n", encoding="utf-8")
    repo.index.add(["app.py"])
    second = repo.index.commit("Second commit")

    return repo_path, first.hexsha, second.hexsha
