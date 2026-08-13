"""Token budgeting: truncates a ranked candidate list to fit a configurable token budget.

Per PROJECT_SPEC.md §20.3: chunks are ranked and truncated to fit a
configurable maximum context-token budget (value TBD), and
`FusedContext.truncated` records whether truncation occurred. No
tokenizer library is a project dependency -- matching this project's
established "no dependency for something a simple, documented
approximation can do" pattern (see `DenseRetriever`'s FAISS-avoidance
rationale); `approximate_token_count` is a simple, deterministic,
injectable stand-in, explicitly not claimed to match any specific
model's real tokenizer.
"""
from __future__ import annotations

from collections.abc import Callable

from tara.fusion.models import FusedChunk

_CHARACTERS_PER_TOKEN_ESTIMATE = 4


def approximate_token_count(text: str) -> int:
    """A simple, deterministic, dependency-free token-count estimate.

    Args:
        text: The text to estimate a token count for.

    Returns:
        `ceil(len(text) / 4)` -- a commonly-cited rough approximation
        for English/code text against GPT-style byte-pair-encoding
        tokenizers, not calibrated against any specific model.
        PROJECT_SPEC.md §20.3 itself marks the real budget value TBD
        pending a chosen generation model; this estimate is provisional
        in the same sense. A caller with a real tokenizer for their
        chosen model should inject one via `TokenBudgeter(tokenizer=...)`
        rather than relying on this default. Empty text counts as 0.
    """
    if not text:
        return 0
    return -(-len(text) // _CHARACTERS_PER_TOKEN_ESTIMATE)  # ceiling division, no float rounding


class TokenBudgeter:
    """Counts and enforces a token budget over a ranked `FusedChunk` list.

    The token-counting function is injected (defaulting to
    `approximate_token_count`), matching every other substitutable
    collaborator in this project (`Embedder`, `RankingEngine`, ...) --
    a caller with a real tokenizer for a specific generation model can
    substitute one without changing this component's truncation logic.
    The same tokenizer is used both to size individual chunks (via
    `count_tokens`, called while building each `FusedChunk`) and to
    enforce the running total (via `apply`), so the two can never
    diverge.
    """

    def __init__(self, tokenizer: Callable[[str], int] | None = None) -> None:
        """Construct the budgeter.

        Args:
            tokenizer: `text -> token count`. Defaults to
                `approximate_token_count` when omitted.
        """
        self._count_tokens = tokenizer or approximate_token_count

    def count_tokens(self, text: str) -> int:
        """Estimate `text`'s token count using this budgeter's configured tokenizer."""
        return self._count_tokens(text)

    def apply(self, chunks: list[FusedChunk], budget: int) -> tuple[list[FusedChunk], bool]:
        """Include as many leading `chunks` as fit within `budget` total tokens.

        Args:
            chunks: Already-ranked candidates, in the order they should
                be considered for inclusion (highest-priority first).
                Each chunk's own `token_count` is trusted as-is (already
                computed, via this same tokenizer, when the chunk was
                built) rather than recomputed here.
            budget: Maximum total tokens to include, e.g.
                `TaraSettings().fusion_token_budget`. Must be positive
                (enforced by that field's own `gt=0` constraint
                upstream; not re-validated here).

        Returns:
            `(included_chunks, truncated)`: `included_chunks` is the
            longest leading prefix of `chunks` whose `token_count`s sum
            to at most `budget`. This is prefix truncation, not
            bin-packing: a chunk that would push the running total over
            budget is excluded, but chunks after it are never
            considered as replacements -- preserving rank order matters
            more than maximizing token utilization. `truncated` is True
            iff at least one chunk was excluded this way.
        """
        included: list[FusedChunk] = []
        running_total = 0
        for chunk in chunks:
            if running_total + chunk.token_count > budget:
                return included, True
            included.append(chunk)
            running_total += chunk.token_count
        return included, False
