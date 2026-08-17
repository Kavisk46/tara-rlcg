"""Unit tests for `evaluation.metrics.generation`.

Every test asserts against a hand-computed value.
"""
from __future__ import annotations

import pytest

from evaluation.metrics.generation import (
    edit_similarity,
    exact_match,
    pass_at_k,
    syntactic_validity,
)
from tara.core.exceptions import UnsupportedLanguageError
from tara.core.types import Language

# ============================================================================
# exact_match
# ============================================================================


def test_exact_match_identical_strings() -> None:
    assert exact_match("def f(): return 1", "def f(): return 1") is True


def test_exact_match_normalizes_whitespace() -> None:
    assert exact_match("def f():\n    return 1", "def f(): return 1") is True


def test_exact_match_normalizes_leading_trailing_whitespace() -> None:
    assert exact_match("  hello  ", "hello") is True


def test_exact_match_rejects_different_content() -> None:
    assert exact_match("return 1", "return 2") is False


def test_exact_match_empty_strings_match() -> None:
    assert exact_match("", "   ") is True


# ============================================================================
# edit_similarity
# ============================================================================


def test_edit_similarity_identical_is_one() -> None:
    assert edit_similarity("a b c", "a b c") == 1.0


def test_edit_similarity_single_substitution_hand_computed() -> None:
    # tokens: [the, quick, brown, fox] vs [the, quick, brown, dog]
    # edit distance = 1 (substitute fox -> dog), longest = 4 -> similarity = 1 - 1/4 = 0.75
    assert edit_similarity("the quick brown fox", "the quick brown dog") == pytest.approx(0.75)


def test_edit_similarity_single_insertion_hand_computed() -> None:
    # tokens: [a, b, c] vs [a, b, c, d]; edit distance = 1 (insert d), longest = 4 -> 1 - 1/4 = 0.75
    assert edit_similarity("a b c", "a b c d") == pytest.approx(0.75)


def test_edit_similarity_completely_different_hand_computed() -> None:
    # tokens: [a, b] vs [x, y]; edit distance = 2 (substitute both), longest = 2 -> 1 - 2/2 = 0.0
    assert edit_similarity("a b", "x y") == pytest.approx(0.0)


def test_edit_similarity_both_empty_is_one() -> None:
    assert edit_similarity("", "") == 1.0


def test_edit_similarity_one_empty_is_zero() -> None:
    # tokens: [] vs [a, b, c]; edit distance = 3, longest = 3 -> 1 - 3/3 = 0.0
    assert edit_similarity("", "a b c") == pytest.approx(0.0)


def test_edit_similarity_rejects_unsupported_tokenizer() -> None:
    with pytest.raises(ValueError, match="whitespace"):
        edit_similarity("a", "b", tokenizer="bpe")


# ============================================================================
# syntactic_validity
# ============================================================================


def test_syntactic_validity_valid_python() -> None:
    assert syntactic_validity("def f():\n    return 1\n", Language.PYTHON) is True


def test_syntactic_validity_invalid_python() -> None:
    assert syntactic_validity("def f(:\n    pass\n", Language.PYTHON) is False


def test_syntactic_validity_empty_string_is_false() -> None:
    assert syntactic_validity("", Language.PYTHON) is False


def test_syntactic_validity_whitespace_only_is_false() -> None:
    assert syntactic_validity("   \n  ", Language.PYTHON) is False


def test_syntactic_validity_unsupported_language_raises() -> None:
    with pytest.raises(UnsupportedLanguageError):
        syntactic_validity("anything", Language.UNKNOWN)


# ============================================================================
# pass_at_k
# ============================================================================


def test_pass_at_1_equals_c_over_n_hand_computed() -> None:
    # pass@1 = 1 - C(4,1)/C(5,1) = 1 - 4/5 = 0.2, which must equal c/n = 1/5.
    assert pass_at_k(n=5, c=1, k=1) == pytest.approx(0.2)
    assert pass_at_k(n=5, c=1, k=1) == pytest.approx(1 / 5)


def test_pass_at_k_all_samples_pass_is_one() -> None:
    assert pass_at_k(n=10, c=10, k=5) == 1.0


def test_pass_at_k_no_samples_pass_is_zero() -> None:
    assert pass_at_k(n=10, c=0, k=5) == pytest.approx(0.0)


def test_pass_at_k_mid_case_hand_computed() -> None:
    # pass@3 = 1 - C(3,3)/C(5,3) = 1 - 1/10 = 0.9
    assert pass_at_k(n=5, c=2, k=3) == pytest.approx(0.9)


def test_pass_at_k_fewer_failures_than_k_is_one() -> None:
    # n=5, c=4 -> only 1 failing sample; any k=2 sample is guaranteed to include a pass.
    assert pass_at_k(n=5, c=4, k=2) == 1.0


def test_pass_at_k_rejects_n_below_one() -> None:
    with pytest.raises(ValueError, match="n must be"):
        pass_at_k(n=0, c=0, k=1)


def test_pass_at_k_rejects_c_greater_than_n() -> None:
    with pytest.raises(ValueError, match="c must"):
        pass_at_k(n=5, c=6, k=1)


def test_pass_at_k_rejects_negative_c() -> None:
    with pytest.raises(ValueError, match="c must"):
        pass_at_k(n=5, c=-1, k=1)


def test_pass_at_k_rejects_k_greater_than_n() -> None:
    with pytest.raises(ValueError, match="k must"):
        pass_at_k(n=5, c=2, k=6)


def test_pass_at_k_rejects_k_below_one() -> None:
    with pytest.raises(ValueError, match="k must"):
        pass_at_k(n=5, c=2, k=0)
