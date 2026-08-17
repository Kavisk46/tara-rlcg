"""Generation-quality metrics, per `EXPERIMENT_PLAN.md` §3.

**CodeBLEU is not implemented here** -- see this package's `__init__.py`
docstring for why. `exact_match` and `edit_similarity` need no
dependency beyond the standard library; `syntactic_validity` reuses
`tara.parsing`'s existing Tree-sitter infrastructure (no new
dependency, per `EXPERIMENT_PLAN.md` §3's own instruction to reuse it);
`pass_at_k` implements only the standard unbiased *estimator* formula --
computing its `n`/`c` inputs requires actually executing generated code,
which this project does not do (`PROJECT_SPEC.md` §8).
"""
from __future__ import annotations

import math

from tara.core.types import Language
from tara.parsing.language_registry import LanguageRegistry


def exact_match(candidate: str, reference: str) -> bool:
    """Whitespace-normalized exact match, per `EXPERIMENT_PLAN.md` §3.

    Args:
        candidate: The generated text.
        reference: The reference/acceptable-output text.

    Returns:
        True iff `candidate` and `reference` are identical after
        stripping leading/trailing whitespace and collapsing internal
        runs of whitespace to a single space -- "normalized
        whitespace/formatting," per §3, not a byte-for-byte comparison.
    """
    return _normalize_whitespace(candidate) == _normalize_whitespace(reference)


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def edit_similarity(candidate: str, reference: str, *, tokenizer: str = "whitespace") -> float:
    """`1 - (edit_distance / max(len(candidate_tokens), len(reference_tokens)))`.

    Per `EXPERIMENT_PLAN.md` §3: "normalized token-level edit distance...
    Exact tokenizer TBD, to be fixed during Phase 4 implementation and
    held constant across all variants and metrics for a given
    experimental run." This implementation fixes a simple, provisional
    tokenizer (`str.split()`, whitespace-delimited) as its own Phase-4
    decision, exposed as a keyword argument so a caller can override it
    consistently for their own experimental run rather than being
    locked into this default -- but whichever tokenizer is chosen must,
    per §3, be held constant across every variant/metric in that run.

    Args:
        candidate: The generated text.
        reference: The reference/acceptable-output text.
        tokenizer: Must currently be `"whitespace"` (the only
            implemented option) -- reserved as an explicit parameter so
            a future tokenizer choice doesn't require changing this
            function's signature.

    Returns:
        A value in `[0.0, 1.0]`; `1.0` for an exact token-sequence
        match, `0.0` when `candidate` and `reference` share no tokens
        in a way that makes them maximally distant. Returns `1.0` when
        both `candidate` and `reference` tokenize to zero tokens (two
        empty strings are identical, not maximally distant).

    Raises:
        ValueError: If `tokenizer` is not `"whitespace"`.
    """
    if tokenizer != "whitespace":
        raise ValueError(f"Unsupported tokenizer {tokenizer!r}; only 'whitespace' is implemented.")

    candidate_tokens = candidate.split()
    reference_tokens = reference.split()
    longest = max(len(candidate_tokens), len(reference_tokens))
    if longest == 0:
        return 1.0

    distance = _levenshtein_distance(candidate_tokens, reference_tokens)
    return 1.0 - (distance / longest)


def _levenshtein_distance(a: list[str], b: list[str]) -> int:
    """Standard O(len(a) * len(b)) dynamic-programming token-level edit distance."""
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous_row = list(range(len(b) + 1))
    for i, token_a in enumerate(a, start=1):
        current_row = [i] + [0] * len(b)
        for j, token_b in enumerate(b, start=1):
            insertion_cost = current_row[j - 1] + 1
            deletion_cost = previous_row[j] + 1
            substitution_cost = previous_row[j - 1] + (0 if token_a == token_b else 1)
            current_row[j] = min(insertion_cost, deletion_cost, substitution_cost)
        previous_row = current_row
    return previous_row[-1]


_SYNTACTIC_VALIDITY_REGISTRY = LanguageRegistry()


def syntactic_validity(code: str, language: Language) -> bool:
    """Whether `code` parses without a syntax error under Tree-sitter, per `EXPERIMENT_PLAN.md` §3.

    Reuses the exact `tara.parsing.language_registry.LanguageRegistry`
    already relied on by the Repository Parser -- "a deliberate reuse
    of existing, tested infrastructure rather than a new dependency,"
    per §3's own instruction.

    Args:
        code: The generated code text to check.
        language: Which Tree-sitter grammar to parse it with.

    Returns:
        True iff Tree-sitter's parse tree reports no syntax error
        (`tree.root_node.has_error` is False) and `code` is non-empty
        (an empty string is never syntactically valid code, even though
        Tree-sitter itself would parse it into an empty, error-free
        tree).

    Raises:
        UnsupportedLanguageError: If no Tree-sitter grammar is
            registered for `language` (e.g. `Language.UNKNOWN`).
    """
    if not code.strip():
        return False
    parser = _SYNTACTIC_VALIDITY_REGISTRY.get_parser(language)
    tree = parser.parse(code.encode("utf-8"))
    return not tree.root_node.has_error


def pass_at_k(n: int, c: int, k: int) -> float:
    """The standard unbiased pass@k estimator (Chen et al. 2021 / Codex-style).

    `pass@k = 1 - C(n-c, k) / C(n, k)`, per `EXPERIMENT_PLAN.md` §3.
    **This function estimates pass@k from already-known execution
    results; it does not execute anything itself.** Computing `c` (how
    many of `n` sampled generations actually pass) requires running
    each generation against a safe test-execution harness, which
    `PROJECT_SPEC.md` §8 places out of scope for this project -- a
    caller with their own execution results (e.g. from an external
    sandboxed test runner) may still use this estimator; this project's
    own harness does not compute `c` for any query, since it has no
    such harness (see `evaluation.harness`).

    Args:
        n: Total number of samples drawn for one query. Must be >= 1.
        c: Number of those `n` samples that passed. Must satisfy
            `0 <= c <= n`.
        k: The `k` in pass@k. Must satisfy `1 <= k <= n`.

    Returns:
        A value in `[0.0, 1.0]`.

    Raises:
        ValueError: If any argument violates its stated constraint.
    """
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n!r}.")
    if not (0 <= c <= n):
        raise ValueError(f"c must satisfy 0 <= c <= n (n={n!r}), got {c!r}.")
    if not (1 <= k <= n):
        raise ValueError(f"k must satisfy 1 <= k <= n (n={n!r}), got {k!r}.")

    if n - c < k:
        # C(n-c, k) is 0 whenever there are fewer than k failing samples to choose from --
        # i.e. every k-sized sample is guaranteed to contain at least one passing generation.
        return 1.0
    return 1.0 - (math.comb(n - c, k) / math.comb(n, k))
