"""Projects a `RepositoryParseResult` + `RepositoryGraphs` into a `RepositoryModel`.

A pure function: it reads two already-built structures and produces a
new, flat, JSON-serializable one. It performs no parsing and no graph
resolution itself.
"""
from __future__ import annotations

from evaluation.rts_builder.parser.file_parser import ParsedPythonFile
from evaluation.rts_builder.parser.graph_builder import RepositoryGraphs
from evaluation.rts_builder.parser.models import (
    NormalizedClass,
    NormalizedFile,
    NormalizedFunction,
    NormalizedImport,
    RepositoryModel,
)
from evaluation.rts_builder.parser.repository_parser import RepositoryParseResult
from evaluation.rts_builder.parser.symbol_ids import build_symbol_id


def normalize(
    repository_id: str,
    commit_sha: str,
    root_path: str,
    parse_result: RepositoryParseResult,
    graphs: RepositoryGraphs,
) -> RepositoryModel:
    """Build the normalized `RepositoryModel` for one repository parse.

    Args:
        repository_id: The RTS pipeline's stable identifier for this repository.
        commit_sha: The pinned commit this parse was produced from (from `Repository`, not re-derived).
        root_path: Absolute filesystem path to the repository root at parse time.
        parse_result: Every successfully parsed file, plus per-file parse failures.
        graphs: The resolved import, call, and inheritance graphs.

    Returns:
        A `RepositoryModel` with `from_cache=False` and `manifest_path=None`;
        the caller (`PythonParserPipeline`) fills in the manifest path
        once the model has been written to disk.
    """
    files = [_normalize_file(parsed_file) for parsed_file in parse_result.files]
    return RepositoryModel(
        repository_id=repository_id,
        commit_sha=commit_sha,
        root_path=root_path,
        files=files,
        functions=_normalize_functions(parse_result.files),
        classes=_normalize_classes(parse_result.files),
        imports=_normalize_imports(parse_result.files),
        import_graph=graphs.import_graph,
        call_graph=graphs.call_graph,
        inheritance_graph=graphs.inheritance_graph,
        parse_errors=[error.file_path for error in parse_result.errors],
    )


def _normalize_file(parsed_file: ParsedPythonFile) -> NormalizedFile:
    return NormalizedFile(
        path=parsed_file.path,
        size_bytes=parsed_file.size_bytes,
        content_hash=parsed_file.content_hash,
        module_docstring=parsed_file.module_docstring,
        function_count=len(parsed_file.functions),
        class_count=len(parsed_file.classes),
        import_count=len(parsed_file.imports),
    )


def _normalize_functions(files: list[ParsedPythonFile]) -> list[NormalizedFunction]:
    normalized: list[NormalizedFunction] = []
    for parsed_file in files:
        for function in parsed_file.functions:
            normalized.append(
                NormalizedFunction(
                    symbol_id=build_symbol_id(parsed_file.path, function.qualified_name, function.start_line),
                    name=function.name,
                    qualified_name=function.qualified_name,
                    file_path=parsed_file.path,
                    is_method=function.is_method,
                    parent_class=function.parent_class,
                    is_async=function.is_async,
                    decorators=function.decorators,
                    docstring=function.docstring,
                    start_line=function.start_line,
                    end_line=function.end_line,
                )
            )
    return normalized


def _normalize_classes(files: list[ParsedPythonFile]) -> list[NormalizedClass]:
    normalized: list[NormalizedClass] = []
    for parsed_file in files:
        for klass in parsed_file.classes:
            normalized.append(
                NormalizedClass(
                    symbol_id=build_symbol_id(parsed_file.path, klass.qualified_name, klass.start_line),
                    name=klass.name,
                    qualified_name=klass.qualified_name,
                    file_path=parsed_file.path,
                    parent_class=klass.parent_class,
                    base_names=klass.base_names,
                    decorators=klass.decorators,
                    docstring=klass.docstring,
                    start_line=klass.start_line,
                    end_line=klass.end_line,
                )
            )
    return normalized


def _normalize_imports(files: list[ParsedPythonFile]) -> list[NormalizedImport]:
    normalized: list[NormalizedImport] = []
    for parsed_file in files:
        for raw_import in parsed_file.imports:
            normalized.append(
                NormalizedImport(
                    source_file=parsed_file.path,
                    module=raw_import.module,
                    imported_names=raw_import.imported_names,
                    is_relative=raw_import.is_relative,
                    level=raw_import.level,
                    line=raw_import.line,
                )
            )
    return normalized
