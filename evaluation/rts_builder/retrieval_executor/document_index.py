"""Builds each file's synthetic "document text" from a `RepositoryModel`.

`RepositoryModel` does not retain raw source text (Parser V1's own
scope boundary -- it stores line numbers and docstrings, not source
bytes), so both Lexical Retrieval's BM25 corpus and Dense Retrieval's
embedding inputs are built from the same available structural
metadata: a file's path, its module docstring, and the qualified names
and docstrings of every function/class it defines. Centralized here so
both retrievers agree on exactly what "the document" is for a file,
rather than each assembling a slightly different text independently.
"""
from __future__ import annotations

from collections import defaultdict

from evaluation.rts_builder.parser.models import RepositoryModel


def build_file_documents(model: RepositoryModel) -> dict[str, str]:
    """Return `{file_path: document_text}` for every file in `model`.

    Args:
        model: The parsed repository to build documents from.

    Returns:
        One entry per `model.files` entry, in file order. A file that
        defines no functions/classes and has no module docstring still
        gets an entry (its bare path), never omitted.
    """
    symbol_text_by_file: dict[str, list[str]] = defaultdict(list)
    for function in model.functions:
        symbol_text_by_file[function.file_path].append(function.qualified_name)
        if function.docstring:
            symbol_text_by_file[function.file_path].append(function.docstring)
    for klass in model.classes:
        symbol_text_by_file[klass.file_path].append(klass.qualified_name)
        if klass.docstring:
            symbol_text_by_file[klass.file_path].append(klass.docstring)

    documents: dict[str, str] = {}
    for normalized_file in model.files:
        parts = [normalized_file.path]
        if normalized_file.module_docstring:
            parts.append(normalized_file.module_docstring)
        parts.extend(symbol_text_by_file.get(normalized_file.path, []))
        documents[normalized_file.path] = "\n".join(parts)
    return documents
