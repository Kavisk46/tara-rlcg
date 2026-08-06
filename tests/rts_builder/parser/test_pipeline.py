"""Unit tests for `evaluation.rts_builder.parser.pipeline.PythonParserPipeline`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from git import Repo as GitRepo

from evaluation.rts_builder.config import RepositoryLoaderSettings
from evaluation.rts_builder.models import Repository
from evaluation.rts_builder.parser.config import ParserSettings
from evaluation.rts_builder.parser.exceptions import RepositoryStateError
from evaluation.rts_builder.parser.export import export_repository_model
from evaluation.rts_builder.parser.models import RepositoryModel
from evaluation.rts_builder.parser.pipeline import PythonParserPipeline
from evaluation.rts_builder.repository_loader import RepositoryLoader
from tara.core.types import Language

# ---------------------------------------------------------------------------
# Baseline extraction
# ---------------------------------------------------------------------------


def test_parse_repository_returns_normalized_model(pipeline: PythonParserPipeline, basic_repository: Repository) -> None:
    model = pipeline.parse_repository(basic_repository)

    assert isinstance(model, RepositoryModel)
    assert model.repository_id == basic_repository.repository_id
    assert model.commit_sha == basic_repository.commit_sha
    assert model.root_path == basic_repository.local_path
    assert model.parse_errors == []


def test_parse_repository_extracts_files_with_module_docstrings(
    pipeline: PythonParserPipeline, basic_repository: Repository
) -> None:
    model = pipeline.parse_repository(basic_repository)

    paths = {f.path for f in model.files}
    assert paths == {"app.py", "pkg/base.py", "pkg/__init__.py"}

    app_file = next(f for f in model.files if f.path == "app.py")
    assert app_file.module_docstring == "App module."
    assert app_file.size_bytes > 0
    assert app_file.content_hash


def test_parse_repository_extracts_functions_with_decorators_and_docstrings(
    pipeline: PythonParserPipeline, basic_repository: Repository
) -> None:
    model = pipeline.parse_repository(basic_repository)

    main = next(f for f in model.functions if f.name == "main")
    assert main.decorators == ["functools.wraps(helper)"]
    assert main.is_method is False

    bark = next(f for f in model.functions if f.name == "bark")
    assert bark.decorators == ["staticmethod"]
    assert bark.is_method is True
    assert bark.parent_class == "Dog"
    assert bark.qualified_name == "Dog.bark"

    base_speak = next(f for f in model.functions if f.qualified_name == "Animal.speak")
    assert base_speak.file_path == "pkg/base.py"


def test_parse_repository_distinguishes_top_level_functions_and_methods(
    pipeline: PythonParserPipeline, basic_repository: Repository
) -> None:
    model = pipeline.parse_repository(basic_repository)

    assert {f.name for f in model.top_level_functions} == {"helper", "main"}
    assert {f.qualified_name for f in model.methods} == {"Dog.bark", "Dog.speak", "Animal.speak"}


def test_parse_repository_extracts_classes_with_bases_and_docstrings(
    pipeline: PythonParserPipeline, basic_repository: Repository
) -> None:
    model = pipeline.parse_repository(basic_repository)

    dog = next(c for c in model.classes if c.name == "Dog")
    assert dog.base_names == ["Animal"]
    assert dog.docstring == "A dog."

    animal = next(c for c in model.classes if c.name == "Animal")
    assert animal.base_names == []
    assert animal.docstring == "An animal."


def test_parse_repository_extracts_async_functions(pipeline: PythonParserPipeline, tmp_path: Path) -> None:
    repo_path = tmp_path / "async_source"
    repo_path.mkdir()
    repo = GitRepo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "TARA Test Suite")
        config.set_value("user", "email", "tara-tests@example.com")
    (repo_path / "app.py").write_text("async def fetch():\n    return 1\n", encoding="utf-8")
    repo.index.add(["app.py"])
    commit = repo.index.commit("Async function")

    loader = RepositoryLoader(settings=RepositoryLoaderSettings(clone_root=str(tmp_path / "clones")))
    repository = loader.load_repository("async-repo", str(repo_path), commit.hexsha)

    model = pipeline.parse_repository(repository)

    fetch = next(f for f in model.functions if f.name == "fetch")
    assert fetch.is_async is True


def test_parse_repository_extracts_imports(pipeline: PythonParserPipeline, basic_repository: Repository) -> None:
    model = pipeline.parse_repository(basic_repository)

    app_imports = [i for i in model.imports if i.source_file == "app.py"]
    assert any(i.module == "pkg.base" and i.imported_names == ["Animal"] for i in app_imports)
    assert any(i.module == "functools" for i in app_imports)


# ---------------------------------------------------------------------------
# Import graph
# ---------------------------------------------------------------------------


def test_parse_repository_builds_import_graph_for_absolute_import(
    pipeline: PythonParserPipeline, basic_repository: Repository
) -> None:
    model = pipeline.parse_repository(basic_repository)

    assert any(e.source_file == "app.py" and e.target_file == "pkg/base.py" for e in model.import_graph)


def test_parse_repository_resolves_relative_imports(
    pipeline: PythonParserPipeline, relative_import_repository: Repository
) -> None:
    model = pipeline.parse_repository(relative_import_repository)

    targets = {e.target_file for e in model.import_graph if e.source_file == "pkg/b.py"}
    # 'from . import a' resolves to the package's own __init__.py (no direct match here,
    # since 'a' as an imported name should resolve as 'pkg.a' -- a submodule);
    # 'from .a import value' resolves the same way. Both point at pkg/a.py.
    assert "pkg/a.py" in targets


# ---------------------------------------------------------------------------
# Call graph
# ---------------------------------------------------------------------------


def test_parse_repository_resolves_calls_same_file_and_method_to_method(
    pipeline: PythonParserPipeline, basic_repository: Repository
) -> None:
    model = pipeline.parse_repository(basic_repository)

    by_name = {
        (_symbol_name(model, edge.caller_symbol_id), _symbol_name(model, edge.callee_symbol_id))
        for edge in model.call_graph
    }
    assert ("main", "helper") in by_name
    assert ("bark", "helper") in by_name
    assert ("speak", "bark") in by_name


def test_parse_repository_skips_ambiguous_calls(
    pipeline: PythonParserPipeline, ambiguous_call_repository: Repository
) -> None:
    model = pipeline.parse_repository(ambiguous_call_repository)
    assert model.call_graph == []


def test_parse_repository_skips_unresolved_builtin_calls(
    pipeline: PythonParserPipeline, unresolved_call_repository: Repository
) -> None:
    model = pipeline.parse_repository(unresolved_call_repository)
    assert model.call_graph == []


def test_enable_call_graph_false_produces_no_call_edges(tmp_path: Path, basic_repository: Repository) -> None:
    settings = ParserSettings(cache_root=str(tmp_path / "parsed"), enable_call_graph=False)
    pipeline = PythonParserPipeline(settings=settings)

    model = pipeline.parse_repository(basic_repository)

    assert model.call_graph == []


def _symbol_name(model: RepositoryModel, symbol_id: str) -> str:
    for function in model.functions:
        if function.symbol_id == symbol_id:
            return function.name
    for klass in model.classes:
        if klass.symbol_id == symbol_id:
            return klass.name
    raise AssertionError(f"No symbol with id {symbol_id!r}")


# ---------------------------------------------------------------------------
# Inheritance graph
# ---------------------------------------------------------------------------


def test_parse_repository_resolves_inheritance_across_files(
    pipeline: PythonParserPipeline, basic_repository: Repository
) -> None:
    model = pipeline.parse_repository(basic_repository)

    assert len(model.inheritance_graph) == 1
    edge = model.inheritance_graph[0]
    assert _symbol_name(model, edge.subclass_symbol_id) == "Dog"
    assert _symbol_name(model, edge.superclass_symbol_id) == "Animal"


def test_parse_repository_resolves_multiple_inheritance(
    pipeline: PythonParserPipeline, multiple_inheritance_repository: Repository
) -> None:
    model = pipeline.parse_repository(multiple_inheritance_repository)

    superclass_names = {_symbol_name(model, e.superclass_symbol_id) for e in model.inheritance_graph}
    assert superclass_names == {"Flyer", "Swimmer"}


def test_parse_repository_skips_ambiguous_inheritance(
    pipeline: PythonParserPipeline, ambiguous_inheritance_repository: Repository
) -> None:
    model = pipeline.parse_repository(ambiguous_inheritance_repository)
    assert model.inheritance_graph == []


def test_parse_repository_does_not_add_an_edge_for_explicit_object_base(
    pipeline: PythonParserPipeline, object_inheritance_repository: Repository
) -> None:
    model = pipeline.parse_repository(object_inheritance_repository)
    assert model.inheritance_graph == []
    assert model.classes[0].base_names == ["object"]


def test_enable_inheritance_graph_false_produces_no_edges(tmp_path: Path, basic_repository: Repository) -> None:
    settings = ParserSettings(cache_root=str(tmp_path / "parsed"), enable_inheritance_graph=False)
    pipeline = PythonParserPipeline(settings=settings)

    model = pipeline.parse_repository(basic_repository)

    assert model.inheritance_graph == []


# ---------------------------------------------------------------------------
# Walk: ignored directories, non-Python files, syntax errors
# ---------------------------------------------------------------------------


def test_ignored_directories_and_non_python_files_are_excluded(
    pipeline: PythonParserPipeline, ignored_and_non_python_repository: Repository
) -> None:
    model = pipeline.parse_repository(ignored_and_non_python_repository)

    paths = {f.path for f in model.files}
    assert paths == {"app.py"}


def test_syntax_error_in_one_file_does_not_abort_the_rest(
    pipeline: PythonParserPipeline, syntax_error_repository: Repository
) -> None:
    model = pipeline.parse_repository(syntax_error_repository)

    assert model.parse_errors == ["bad.py"]
    assert {f.path for f in model.files} == {"good.py"}


# ---------------------------------------------------------------------------
# Incremental parsing / cache
# ---------------------------------------------------------------------------


def test_parse_repository_uses_cache_on_second_call(pipeline: PythonParserPipeline, basic_repository: Repository) -> None:
    first = pipeline.parse_repository(basic_repository)
    assert first.from_cache is False

    second = pipeline.parse_repository(basic_repository)
    assert second.from_cache is True
    assert second.functions == first.functions
    assert second.call_graph == first.call_graph


def test_force_reparse_bypasses_cache(tmp_path: Path, basic_repository: Repository) -> None:
    cache_root = tmp_path / "parsed"
    first_pipeline = PythonParserPipeline(settings=ParserSettings(cache_root=str(cache_root)))
    first = first_pipeline.parse_repository(basic_repository)
    assert first.from_cache is False

    force_pipeline = PythonParserPipeline(settings=ParserSettings(cache_root=str(cache_root), force_reparse=True))
    second = force_pipeline.parse_repository(basic_repository)
    assert second.from_cache is False


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------


def test_manifest_file_is_persisted_and_matches_the_returned_model(
    pipeline: PythonParserPipeline, basic_repository: Repository
) -> None:
    model = pipeline.parse_repository(basic_repository)

    assert model.manifest_path is not None
    manifest_file = Path(model.manifest_path)
    assert manifest_file.exists()

    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert payload["repository_id"] == basic_repository.repository_id
    assert payload["commit_sha"] == basic_repository.commit_sha
    assert len(payload["functions"]) == len(model.functions)
    assert len(payload["call_graph"]) == len(model.call_graph)


def test_export_repository_model_writes_a_valid_json_round_trip(
    pipeline: PythonParserPipeline, basic_repository: Repository, tmp_path: Path
) -> None:
    model = pipeline.parse_repository(basic_repository)
    export_path = tmp_path / "explicit_export" / "repository_model.json"

    returned_path = export_repository_model(model, export_path)

    assert returned_path == export_path
    assert export_path.exists()
    reloaded = RepositoryModel.model_validate_json(export_path.read_text(encoding="utf-8"))
    assert reloaded.repository_id == model.repository_id
    assert reloaded.functions == model.functions
    assert reloaded.classes == model.classes
    assert reloaded.import_graph == model.import_graph
    assert reloaded.call_graph == model.call_graph
    assert reloaded.inheritance_graph == model.inheritance_graph


# ---------------------------------------------------------------------------
# Repository state errors
# ---------------------------------------------------------------------------


def test_parse_repository_raises_when_local_path_does_not_exist(pipeline: PythonParserPipeline, tmp_path: Path) -> None:
    ghost = Repository(
        repository_id="ghost",
        source_url="https://example.com/ghost.git",
        commit_sha="a" * 40,
        local_path=str(tmp_path / "does_not_exist"),
        primary_language=Language.PYTHON,
        file_count=0,
        directory_count=0,
        size_bytes=0,
    )

    with pytest.raises(RepositoryStateError):
        pipeline.parse_repository(ghost)


def test_parse_repository_raises_on_commit_mismatch(tmp_path: Path, two_commit_repository: tuple[Path, str, str]) -> None:
    source_path, first_sha, second_sha = two_commit_repository
    loader_settings = RepositoryLoaderSettings(clone_root=str(tmp_path / "clones"))
    loader = RepositoryLoader(settings=loader_settings)
    repository = loader.load_repository("mutate-repo", str(source_path), first_sha)

    GitRepo(repository.local_path).git.checkout("--force", second_sha)

    parser_settings = ParserSettings(cache_root=str(tmp_path / "parsed"))
    pipeline = PythonParserPipeline(settings=parser_settings)

    with pytest.raises(RepositoryStateError):
        pipeline.parse_repository(repository)
