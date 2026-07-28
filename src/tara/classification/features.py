"""Feature extraction for task classification.

`QueryFeatures` is the structured bundle every `Rule` and the
classifier itself reasons about; `FeatureExtractor.extract` is the only
place a raw query string is parsed. All patterns and keyword sets used
here are defined once, at import time, in `tara.classification.heuristics`
-- this module only combines their results, so repeated `classify()`
calls never pay for pattern recompilation.
"""
from __future__ import annotations

from dataclasses import dataclass

from tara.classification.heuristics import (
    detect_language,
    extract_extension,
    extract_quoted,
    is_stop_word,
    looks_like_file_path,
    looks_like_identifier,
    tokenize,
)
from tara.core.types import Language


@dataclass(frozen=True)
class QueryFeatures:
    """The structured signal set extracted from a single query string.

    Immutable: built once per `classify()` call and shared read-only by
    every rule, so rules can never see a partially-updated feature set
    or accidentally mutate one another's view of the query.
    """

    raw_query: str
    tokens: tuple[str, ...]
    token_set: frozenset[str]
    quoted_identifiers: tuple[str, ...]
    detected_symbols: tuple[str, ...]
    detected_file_paths: tuple[str, ...]
    extracted_keywords: tuple[str, ...]
    language_hint: Language | None


class FeatureExtractor:
    """Turns a raw query string into a `QueryFeatures` bundle.

    Stateless and safe to share across threads/queries; kept as a class
    (rather than a bare function) so it can be swapped or subclassed --
    e.g. for a domain with its own naming conventions -- and injected
    into `HeuristicTaskClassifier` like every other collaborator.
    """

    def extract(self, query: str) -> QueryFeatures:
        """Build the `QueryFeatures` for `query`.

        Args:
            query: The raw developer query. May be empty, whitespace-only,
                or made entirely of punctuation; that degrades to an
                all-empty feature bundle rather than raising.

        Returns:
            The extracted `QueryFeatures`.
        """
        tokens = tuple(tokenize(query))
        token_set = frozenset(token.lower() for token in tokens)
        quoted = tuple(extract_quoted(query))

        return QueryFeatures(
            raw_query=query,
            tokens=tokens,
            token_set=token_set,
            quoted_identifiers=quoted,
            detected_symbols=self._detect_symbols(tokens, quoted),
            detected_file_paths=self._detect_file_paths(tokens),
            extracted_keywords=self._extract_keywords(tokens),
            language_hint=detect_language(tokens),
        )

    @staticmethod
    def _detect_symbols(tokens: tuple[str, ...], quoted: tuple[str, ...]) -> tuple[str, ...]:
        """Identify tokens that read like code symbols, plus every quoted phrase verbatim.

        A quoted phrase is included unconditionally, regardless of
        naming convention: a user who explicitly quotes something is
        signaling "treat this as a literal term" even if it doesn't look
        like an identifier (e.g. a quoted multi-word API description).
        """
        seen: dict[str, None] = {}
        for token in tokens:
            if looks_like_file_path(token):
                continue
            if looks_like_identifier(token):
                seen.setdefault(token, None)
        for phrase in quoted:
            seen.setdefault(phrase, None)
        return tuple(seen)

    @staticmethod
    def _detect_file_paths(tokens: tuple[str, ...]) -> tuple[str, ...]:
        """Identify tokens that read like a file path or a bare `name.ext` filename."""
        seen: dict[str, None] = {}
        for token in tokens:
            if looks_like_file_path(token) or extract_extension(token) is not None:
                seen.setdefault(token, None)
        return tuple(seen)

    @staticmethod
    def _extract_keywords(tokens: tuple[str, ...]) -> tuple[str, ...]:
        """Return search-worthy terms: original-case tokens, minus stop words and duplicates."""
        seen: dict[str, None] = {}
        for token in tokens:
            if is_stop_word(token):
                continue
            seen.setdefault(token, None)
        return tuple(seen)
