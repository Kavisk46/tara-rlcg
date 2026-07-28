"""Language detection and Tree-sitter parser registry for TARA.

Maps file extensions to supported languages and lazily constructs
`tree_sitter.Parser` instances via the precompiled grammar bundle in
`tree_sitter_languages`, caching one parser per language for the
lifetime of the registry.
"""
from __future__ import annotations

from typing import Final

from tree_sitter import Parser
from tree_sitter_languages import get_parser

from tara.core.exceptions import UnsupportedLanguageError
from tara.core.types import Language

_EXTENSION_TO_LANGUAGE: Final[dict[str, Language]] = {
    ".py": Language.PYTHON,
    ".pyi": Language.PYTHON,
    ".js": Language.JAVASCRIPT,
    ".jsx": Language.JAVASCRIPT,
    ".mjs": Language.JAVASCRIPT,
    ".cjs": Language.JAVASCRIPT,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".java": Language.JAVA,
    ".go": Language.GO,
    ".rs": Language.RUST,
    ".c": Language.C,
    ".h": Language.C,
    ".cpp": Language.CPP,
    ".cc": Language.CPP,
    ".cxx": Language.CPP,
    ".hpp": Language.CPP,
    ".hxx": Language.CPP,
}

_LANGUAGE_TO_GRAMMAR: Final[dict[Language, str]] = {
    Language.PYTHON: "python",
    Language.JAVASCRIPT: "javascript",
    Language.TYPESCRIPT: "typescript",
    Language.JAVA: "java",
    Language.GO: "go",
    Language.RUST: "rust",
    Language.C: "c",
    Language.CPP: "cpp",
}


class LanguageRegistry:
    """Detects source languages and provides cached Tree-sitter parsers.

    A single registry instance amortizes the cost of constructing
    `Parser` objects, which is measurable when parsing repositories with
    thousands of files. Instances are safe to share across threads for
    reads once warmed, since `tree_sitter.Parser.parse` does not mutate
    the parser's own state.
    """

    def __init__(self) -> None:
        """Construct an empty registry; parsers are built lazily on first use."""
        self._parser_cache: dict[Language, Parser] = {}

    def detect_language(self, file_extension: str) -> Language:
        """Resolve a file extension (e.g. ".py") to a `Language`.

        Args:
            file_extension: The extension including the leading dot, as
                returned by `pathlib.Path.suffix`.

        Returns:
            The detected `Language`, or `Language.UNKNOWN` if the
            extension is not recognized.
        """
        return _EXTENSION_TO_LANGUAGE.get(file_extension.lower(), Language.UNKNOWN)

    def is_supported(self, language: Language) -> bool:
        """Return whether `language` has a registered Tree-sitter grammar."""
        return language in _LANGUAGE_TO_GRAMMAR

    def get_parser(self, language: Language) -> Parser:
        """Return a cached Tree-sitter parser for the given language.

        Args:
            language: The language to obtain a parser for.

        Returns:
            A ready-to-use `tree_sitter.Parser` instance.

        Raises:
            UnsupportedLanguageError: If no Tree-sitter grammar is
                registered for `language`.
        """
        cached = self._parser_cache.get(language)
        if cached is not None:
            return cached

        grammar_name = _LANGUAGE_TO_GRAMMAR.get(language)
        if grammar_name is None:
            raise UnsupportedLanguageError(
                f"No Tree-sitter grammar is registered for language: {language!r}"
            )

        parser = get_parser(grammar_name)
        self._parser_cache[language] = parser
        return parser
