"""Unit tests for `tara.retrieval.bm25_index.BM25Index`, `tara.retrieval.ranking.RankingEngine`,
and `tara.retrieval.utils.normalize_scores`.

These three are grouped in one file rather than split across
`test_ranking.py` / `test_utils.py`: the given test-file layout for this
milestone lists only `test_bm25.py`, `test_lexical.py`, and
`test_symbol_search.py`, and BM25 scoring, ranking, and score
normalization are a single tightly-coupled "scoring engine" concern --
`RankingEngine.rank` and `normalize_scores` exist specifically to turn
`BM25Index.score`'s raw output into a usable ranking, so testing them
together against the same fixtures is more natural than an artificial
split would be.

All fixtures here are synthetic `(document_id, tokens)` pairs -- no
`RepositoryContext`, no real repository, no file I/O -- since
`BM25Index` and `RankingEngine` are both domain-agnostic by design.
"""
from __future__ import annotations

import math

import pytest

from tara.core.config import TaraSettings
from tara.core.exceptions import ConfigurationError, RetrievalError
from tara.retrieval.bm25_index import BM25Index
from tara.retrieval.ranking import RankingEngine
from tara.retrieval.utils import normalize_scores

# ============================================================================
# BM25Index -- construction and parameter validation
# ============================================================================


def test_default_construction_uses_settings_defaults() -> None:
    index = BM25Index()
    assert index.k1 == pytest.approx(1.5)
    assert index.b == pytest.approx(0.75)


def test_explicit_k1_and_b_override_settings() -> None:
    index = BM25Index(k1=2.0, b=0.5)
    assert index.k1 == pytest.approx(2.0)
    assert index.b == pytest.approx(0.5)


def test_settings_object_supplies_defaults_when_not_explicitly_overridden() -> None:
    settings = TaraSettings(bm25_k1=1.2, bm25_b=0.3)
    index = BM25Index(settings=settings)
    assert index.k1 == pytest.approx(1.2)
    assert index.b == pytest.approx(0.3)


def test_explicit_k1_wins_over_settings() -> None:
    settings = TaraSettings(bm25_k1=1.2)
    index = BM25Index(k1=9.9, settings=settings)
    assert index.k1 == pytest.approx(9.9)


@pytest.mark.parametrize("bad_k1", [0.0, -1.0, -0.001, math.nan, math.inf, -math.inf])
def test_non_positive_or_non_finite_k1_raises_configuration_error(bad_k1: float) -> None:
    with pytest.raises(ConfigurationError):
        BM25Index(k1=bad_k1)


@pytest.mark.parametrize("bad_b", [-0.001, 1.001, 2.0, -1.0, math.nan, math.inf])
def test_out_of_range_or_non_finite_b_raises_configuration_error(bad_b: float) -> None:
    with pytest.raises(ConfigurationError):
        BM25Index(b=bad_b)


@pytest.mark.parametrize("b", [0.0, 1.0])
def test_b_boundary_values_are_valid(b: float) -> None:
    index = BM25Index(b=b)
    assert index.b == pytest.approx(b)


# ============================================================================
# BM25Index -- build()
# ============================================================================


def test_build_on_empty_iterable_creates_empty_index() -> None:
    """The 'empty repository' case: no documents at all."""
    index = BM25Index()
    index.build([])
    assert len(index) == 0
    assert index.score(["anything"]) == {}


def test_build_accepts_a_generator_not_only_a_list() -> None:
    def documents():
        yield ("doc-1", ["hello", "world"])
        yield ("doc-2", ["goodbye", "world"])

    index = BM25Index()
    index.build(documents())
    assert len(index) == 2


def test_build_replaces_a_previous_index() -> None:
    index = BM25Index()
    index.build([("doc-1", ["alpha"])])
    assert len(index) == 1

    index.build([("doc-2", ["beta"]), ("doc-3", ["gamma"])])
    assert len(index) == 2
    assert "doc-1" not in index
    assert "doc-2" in index and "doc-3" in index


def test_build_rejects_duplicate_document_id() -> None:
    index = BM25Index()
    with pytest.raises(RetrievalError, match="duplicate"):
        index.build([("dup", ["a"]), ("dup", ["b"])])


def test_build_rejects_empty_document_id() -> None:
    index = BM25Index()
    with pytest.raises(RetrievalError, match="empty"):
        index.build([("", ["a"])])


def test_document_with_empty_token_list_is_indexed_but_never_matches() -> None:
    index = BM25Index()
    index.build([("doc-empty", []), ("doc-full", ["hello"])])

    assert len(index) == 2
    assert "doc-empty" in index
    assert index.document_length("doc-empty") == 0

    scores = index.score(["hello"])
    assert set(scores) == {"doc-full"}


def test_document_length_accessor() -> None:
    index = BM25Index()
    index.build([("doc-1", ["a", "b", "c"])])
    assert index.document_length("doc-1") == 3


def test_document_length_raises_for_unknown_id() -> None:
    index = BM25Index()
    index.build([("doc-1", ["a"])])
    with pytest.raises(RetrievalError):
        index.document_length("does-not-exist")


def test_len_and_contains() -> None:
    index = BM25Index()
    index.build([("doc-1", ["a"]), ("doc-2", ["b"])])
    assert len(index) == 2
    assert "doc-1" in index
    assert "doc-missing" not in index


# ============================================================================
# BM25Index -- score() correctness
# ============================================================================


def test_score_empty_query_returns_empty_dict() -> None:
    index = BM25Index()
    index.build([("doc-1", ["hello", "world"])])
    assert index.score([]) == {}


def test_score_on_empty_index_returns_empty_dict() -> None:
    index = BM25Index()
    index.build([])
    assert index.score(["hello"]) == {}


def test_score_unknown_term_returns_empty_dict() -> None:
    """The 'unknown query' case: query terms absent from every document."""
    index = BM25Index()
    index.build([("doc-1", ["hello", "world"])])
    assert index.score(["zzz_never_indexed"]) == {}


def test_score_only_returns_documents_sharing_a_term_with_the_query() -> None:
    """Sparse-scoring convention: non-matching documents are omitted, not scored 0.0."""
    index = BM25Index()
    index.build(
        [
            ("doc-match", ["parse", "repository"]),
            ("doc-nomatch", ["completely", "unrelated", "content"]),
        ]
    )
    scores = index.score(["parse"])
    assert set(scores) == {"doc-match"}


def test_score_exact_single_term_match() -> None:
    index = BM25Index()
    index.build([("doc-1", ["parse", "repository"])])
    scores = index.score(["parse"])
    assert scores["doc-1"] > 0.0


def test_score_multiple_keywords_combines_contributions_from_each() -> None:
    """The 'multiple keyword query' case."""
    index = BM25Index()
    index.build(
        [
            ("doc-both", ["parse", "repository", "tree"]),
            ("doc-one", ["parse", "unrelated", "unrelated"]),
        ]
    )
    scores = index.score(["parse", "repository"])
    assert scores["doc-both"] > scores["doc-one"]


def test_repeated_query_term_increases_the_score_over_a_single_occurrence() -> None:
    index = BM25Index()
    index.build([("doc-1", ["repository", "graph", "builder"])])
    single = index.score(["repository"])["doc-1"]
    doubled = index.score(["repository", "repository"])["doc-1"]
    assert doubled > single


def test_higher_term_frequency_in_a_document_increases_its_score() -> None:
    index = BM25Index()
    index.build(
        [
            ("doc-frequent", ["target"] * 5 + ["filler"] * 5),
            ("doc-rare", ["target"] * 1 + ["filler"] * 5),
        ]
    )
    scores = index.score(["target"])
    assert scores["doc-frequent"] > scores["doc-rare"]


def test_longer_document_is_penalized_relative_to_shorter_for_equal_term_frequency() -> None:
    """Length normalization (the `b` parameter's documented effect)."""
    index = BM25Index(b=0.75)
    index.build(
        [
            ("doc-short", ["target", "short", "short"]),
            ("doc-long", ["target"] + ["filler"] * 20),
        ]
    )
    scores = index.score(["target"])
    assert scores["doc-short"] > scores["doc-long"]


def test_b_zero_disables_length_normalization() -> None:
    index = BM25Index(b=0.0)
    index.build(
        [
            ("doc-short", ["target", "short", "short"]),
            ("doc-long", ["target"] + ["filler"] * 20),
        ]
    )
    scores = index.score(["target"])
    assert scores["doc-short"] == pytest.approx(scores["doc-long"])


def test_rare_term_contributes_more_than_a_common_term() -> None:
    """Inverse document frequency: a term appearing in fewer documents scores higher."""
    documents = [("doc-common-only", ["common"])]
    documents += [(f"filler-{i}", ["common"]) for i in range(8)]
    documents.append(("doc-both", ["common", "rare"]))

    index = BM25Index()
    index.build(documents)

    common_only_score = index.score(["common"])["doc-both"]
    rare_only_score = index.score(["rare"])["doc-both"]
    assert rare_only_score > common_only_score


def test_idf_never_negative_even_for_a_term_in_every_document() -> None:
    """The smoothed-IDF design choice documented on `BM25Index._idf`."""
    index = BM25Index()
    index.build([("doc-1", ["shared"]), ("doc-2", ["shared"]), ("doc-3", ["shared"])])
    scores = index.score(["shared"])
    assert all(score >= 0.0 for score in scores.values())


def test_large_corpus_builds_and_scores_correctly() -> None:
    """A stand-in for the 'large repository' scenario: thousands of documents.

    Verifies the inverted index correctly narrows to the single matching
    document even when the corpus is large, i.e. `score` does not
    degrade to scanning every document.
    """
    filler_documents = [(f"filler-{i}", ["common", "term", "words"]) for i in range(5_000)]
    unique_document = ("needle", ["common", "unique_marker_xyz"])
    index = BM25Index()
    index.build([*filler_documents, unique_document])

    assert len(index) == 5_001
    scores = index.score(["unique_marker_xyz"])
    assert set(scores) == {"needle"}
    assert scores["needle"] > 0.0


# ============================================================================
# normalize_scores
# ============================================================================


def test_normalize_scores_empty_mapping() -> None:
    assert normalize_scores({}) == {}


def test_normalize_scores_min_max_range() -> None:
    normalized = normalize_scores({"a": 0.0, "b": 5.0, "c": 10.0})
    assert normalized == pytest.approx({"a": 0.0, "b": 0.5, "c": 1.0})


def test_normalize_scores_single_value_maps_to_one() -> None:
    assert normalize_scores({"a": 42.0}) == {"a": 1.0}


def test_normalize_scores_all_equal_values_map_to_one() -> None:
    assert normalize_scores({"a": 3.0, "b": 3.0, "c": 3.0}) == {"a": 1.0, "b": 1.0, "c": 1.0}


def test_normalize_scores_handles_negative_values() -> None:
    normalized = normalize_scores({"a": -10.0, "b": 0.0, "c": 10.0})
    assert normalized == pytest.approx({"a": 0.0, "b": 0.5, "c": 1.0})


# ============================================================================
# RankingEngine -- top-k behavior and ranking correctness
# ============================================================================


@pytest.fixture
def ranking_engine() -> RankingEngine:
    return RankingEngine()


def test_rank_on_empty_scores_returns_empty_list(ranking_engine: RankingEngine) -> None:
    assert ranking_engine.rank({}, top_k=5) == []


@pytest.mark.parametrize("bad_top_k", [0, -1, -100])
def test_rank_rejects_non_positive_top_k(ranking_engine: RankingEngine, bad_top_k: int) -> None:
    with pytest.raises(RetrievalError):
        ranking_engine.rank({"a": 1.0}, top_k=bad_top_k)


def test_rank_orders_by_descending_raw_score(ranking_engine: RankingEngine) -> None:
    raw = {"low": 1.0, "high": 10.0, "mid": 5.0}
    ranked = ranking_engine.rank(raw, top_k=3)
    assert [document_id for document_id, _ in ranked] == ["high", "mid", "low"]


def test_rank_truncates_to_top_k(ranking_engine: RankingEngine) -> None:
    raw = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0}
    ranked = ranking_engine.rank(raw, top_k=2)
    assert len(ranked) == 2
    assert [document_id for document_id, _ in ranked] == ["d", "c"]


def test_rank_top_k_larger_than_pool_returns_every_candidate(ranking_engine: RankingEngine) -> None:
    raw = {"a": 1.0, "b": 2.0}
    ranked = ranking_engine.rank(raw, top_k=1000)
    assert len(ranked) == 2


def test_rank_breaks_ties_deterministically_by_document_id(ranking_engine: RankingEngine) -> None:
    raw = {"zebra": 2.0, "apple": 2.0, "mango": 2.0}
    ranked = ranking_engine.rank(raw, top_k=3)
    assert [document_id for document_id, _ in ranked] == ["apple", "mango", "zebra"]


def test_rank_normalizes_over_the_full_pool_not_only_the_top_k_survivors(ranking_engine: RankingEngine) -> None:
    raw = {"a": 1.0, "b": 5.0, "c": 3.0, "d": 10.0}
    ranked = ranking_engine.rank(raw, top_k=2)
    scores_by_id = dict(ranked)

    assert scores_by_id["d"].normalized_score == pytest.approx(1.0)
    assert scores_by_id["b"].normalized_score == pytest.approx((5.0 - 1.0) / (10.0 - 1.0))


def test_rank_preserves_exact_raw_scores(ranking_engine: RankingEngine) -> None:
    raw = {"a": 3.14159}
    ranked = ranking_engine.rank(raw, top_k=1)
    assert ranked[0][1].raw_score == pytest.approx(3.14159)


def test_rank_end_to_end_with_a_real_bm25_index(ranking_engine: RankingEngine) -> None:
    """Ranking correctness against a real `BM25Index`, not only synthetic score dicts."""
    index = BM25Index()
    index.build(
        [
            ("doc-best", ["parse", "repository", "parse", "repository"]),
            ("doc-partial", ["parse", "unrelated", "unrelated"]),
            ("doc-none", ["completely", "unrelated"]),
        ]
    )
    raw_scores = index.score(["parse", "repository"])
    ranked = ranking_engine.rank(raw_scores, top_k=10)

    ordered_ids = [document_id for document_id, _ in ranked]
    assert ordered_ids == ["doc-best", "doc-partial"]
    assert "doc-none" not in ordered_ids
