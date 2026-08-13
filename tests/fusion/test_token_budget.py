"""Unit tests for `tara.fusion.token_budget`.

Covers `approximate_token_count` (the dependency-free char/4 estimate)
and `TokenBudgeter` (counting + prefix-truncation enforcement).
"""
from __future__ import annotations

from tara.fusion.token_budget import TokenBudgeter, approximate_token_count
from tests.fusion.conftest import make_fused_chunk

# ============================================================================
# approximate_token_count
# ============================================================================


def test_approximate_token_count_empty_string_is_zero() -> None:
    assert approximate_token_count("") == 0


def test_approximate_token_count_uses_ceiling_division() -> None:
    assert approximate_token_count("abcd") == 1  # exactly 4 chars -> 1 token
    assert approximate_token_count("abcde") == 2  # 5 chars -> rounds up to 2
    assert approximate_token_count("a") == 1


def test_approximate_token_count_is_deterministic() -> None:
    text = "def greet(name: str) -> str: ..."
    assert approximate_token_count(text) == approximate_token_count(text)


# ============================================================================
# TokenBudgeter.count_tokens
# ============================================================================


def test_count_tokens_defaults_to_approximate_token_count() -> None:
    budgeter = TokenBudgeter()
    assert budgeter.count_tokens("abcdefgh") == approximate_token_count("abcdefgh")


def test_count_tokens_uses_injected_tokenizer() -> None:
    budgeter = TokenBudgeter(tokenizer=lambda text: len(text.split()))
    assert budgeter.count_tokens("four little words here") == 4


# ============================================================================
# TokenBudgeter.apply
# ============================================================================


def test_apply_empty_chunks_returns_empty_not_truncated() -> None:
    included, truncated = TokenBudgeter().apply([], budget=100)
    assert included == []
    assert truncated is False


def test_apply_all_chunks_fit_within_budget() -> None:
    chunks = [
        make_fused_chunk(chunk_id="a", token_count=10),
        make_fused_chunk(chunk_id="b", token_count=10),
    ]
    included, truncated = TokenBudgeter().apply(chunks, budget=50)
    assert [c.chunk_id for c in included] == ["a", "b"]
    assert truncated is False


def test_apply_excludes_chunk_that_would_exceed_budget() -> None:
    chunks = [
        make_fused_chunk(chunk_id="a", token_count=10),
        make_fused_chunk(chunk_id="b", token_count=10),
    ]
    included, truncated = TokenBudgeter().apply(chunks, budget=15)
    assert [c.chunk_id for c in included] == ["a"]
    assert truncated is True


def test_apply_first_chunk_alone_exceeding_budget_yields_empty_and_truncated() -> None:
    chunks = [make_fused_chunk(chunk_id="a", token_count=100)]
    included, truncated = TokenBudgeter().apply(chunks, budget=10)
    assert included == []
    assert truncated is True


def test_apply_is_prefix_truncation_not_bin_packing() -> None:
    # A later, smaller chunk that WOULD fit is still excluded once an earlier,
    # larger chunk has already exceeded the remaining budget -- rank order is
    # preserved over maximizing token utilization.
    chunks = [
        make_fused_chunk(chunk_id="big", token_count=15),
        make_fused_chunk(chunk_id="small", token_count=1),
    ]
    included, truncated = TokenBudgeter().apply(chunks, budget=10)
    assert [c.chunk_id for c in included] == []
    assert truncated is True


def test_apply_exact_budget_boundary_is_included() -> None:
    chunks = [make_fused_chunk(chunk_id="a", token_count=10)]
    included, truncated = TokenBudgeter().apply(chunks, budget=10)
    assert [c.chunk_id for c in included] == ["a"]
    assert truncated is False


def test_apply_zero_token_chunks_all_included() -> None:
    chunks = [
        make_fused_chunk(chunk_id="a", token_count=0),
        make_fused_chunk(chunk_id="b", token_count=0),
    ]
    included, truncated = TokenBudgeter().apply(chunks, budget=1)
    assert [c.chunk_id for c in included] == ["a", "b"]
    assert truncated is False


def test_apply_does_not_mutate_input_list() -> None:
    chunks = [
        make_fused_chunk(chunk_id="a", token_count=10),
        make_fused_chunk(chunk_id="b", token_count=10),
    ]
    original = list(chunks)
    TokenBudgeter().apply(chunks, budget=15)
    assert chunks == original


def test_apply_is_deterministic_across_repeated_calls() -> None:
    chunks = [
        make_fused_chunk(chunk_id="a", token_count=10),
        make_fused_chunk(chunk_id="b", token_count=10),
    ]
    first = TokenBudgeter().apply(chunks, budget=15)
    second = TokenBudgeter().apply(chunks, budget=15)
    assert [c.chunk_id for c in first[0]] == [c.chunk_id for c in second[0]]
    assert first[1] == second[1]
