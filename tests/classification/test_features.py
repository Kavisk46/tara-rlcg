"""Unit tests for `tara.classification.features.FeatureExtractor`."""
from __future__ import annotations

from tara.classification.features import FeatureExtractor
from tara.core.types import Language


def test_extract_on_empty_query_returns_all_empty_features() -> None:
    features = FeatureExtractor().extract("")

    assert features.tokens == ()
    assert features.token_set == frozenset()
    assert features.quoted_identifiers == ()
    assert features.detected_symbols == ()
    assert features.detected_file_paths == ()
    assert features.extracted_keywords == ()
    assert features.language_hint is None


def test_extract_on_whitespace_only_query() -> None:
    features = FeatureExtractor().extract("   \t\n  ")
    assert features.tokens == ()


def test_extract_on_punctuation_only_query() -> None:
    features = FeatureExtractor().extract("??? !!! ...")
    assert features.tokens == ()
    assert features.detected_symbols == ()


def test_detected_symbols_covers_every_naming_convention() -> None:
    query = (
        "Compare RepositoryParser, TreeSitterRepositoryParser, GraphBuilder, "
        "SentenceTransformerEmbedder and parse_repository"
    )
    features = FeatureExtractor().extract(query)

    assert set(features.detected_symbols) == {
        "RepositoryParser",
        "TreeSitterRepositoryParser",
        "GraphBuilder",
        "SentenceTransformerEmbedder",
        "parse_repository",
    }


def test_detected_symbols_excludes_ordinary_capitalized_words() -> None:
    features = FeatureExtractor().extract("Show me the documentation")
    assert features.detected_symbols == ()


def test_detected_symbols_includes_acronyms() -> None:
    features = FeatureExtractor().extract("Where is JWT implemented?")
    assert "JWT" in features.detected_symbols


def test_detected_symbols_includes_quoted_phrases_verbatim() -> None:
    features = FeatureExtractor().extract('What is "get user by id" used for?')
    assert "get user by id" in features.detected_symbols
    assert "get user by id" in features.quoted_identifiers


def test_detected_symbols_excludes_file_paths() -> None:
    features = FeatureExtractor().extract("Find the bug in utils.py")
    assert "utils.py" not in features.detected_symbols
    assert "utils.py" in features.detected_file_paths


def test_detected_file_paths_recognizes_full_paths_and_bare_filenames() -> None:
    query = "Look at src/tara/parsing/repository_parser.py and README.md"
    features = FeatureExtractor().extract(query)

    assert "src/tara/parsing/repository_parser.py" in features.detected_file_paths
    assert "README.md" in features.detected_file_paths


def test_extracted_keywords_excludes_stop_words() -> None:
    features = FeatureExtractor().extract("Find the parse_repository function in utils.py")

    lowered = {kw.lower() for kw in features.extracted_keywords}
    assert "the" not in lowered
    assert "in" not in lowered
    assert "parse_repository" in features.extracted_keywords
    assert "utils.py" in features.extracted_keywords


def test_extracted_keywords_deduplicates_preserving_first_occurrence_order() -> None:
    features = FeatureExtractor().extract("parser parser parser GraphBuilder")
    assert features.extracted_keywords == ("parser", "GraphBuilder")


def test_language_hint_detected() -> None:
    features = FeatureExtractor().extract("How do I write this in TypeScript?")
    assert features.language_hint == Language.TYPESCRIPT


def test_language_hint_none_when_no_language_mentioned() -> None:
    features = FeatureExtractor().extract("Find parse_repository")
    assert features.language_hint is None


def test_token_set_is_lowercased_view_of_tokens() -> None:
    features = FeatureExtractor().extract("Find RepositoryParser")
    assert features.token_set == frozenset({"find", "repositoryparser"})
    assert features.tokens == ("Find", "RepositoryParser")
