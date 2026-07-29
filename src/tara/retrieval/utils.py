"""Low-level, stateless helpers shared across the Lexical Retrieval module.

Two concerns live here, both deliberately generic and domain-independent
so they are trivially unit-testable in isolation:

1. Tokenization for BM25 indexing and querying (`tokenize_for_search`),
   which reuses `tara.classification.heuristics.tokenize` -- the exact
   tokenizer that produces `TaskClassification.extracted_keywords` --
   so a query and the corpus it searches always tokenize identically.
   Nothing about parsing, symbols, or `RepositoryContext` is duplicated
   or reimplemented here.
2. Byte-level source reading (`read_file_bytes`, `decode_byte_span`),
   mirroring the read/slice/decode convention already established in
   `tara.context.embedder` (whole file read once, per-symbol source
   sliced from it by byte offset), so the two modules that need to turn
   a `CodeSymbol`'s byte span into text agree on exactly how.

Neither concern needs a `RepositoryContext`, a `SymbolRecord`, or any
other TARA domain model as input -- that wiring belongs in
`lexical_retriever.py`, which calls these functions once per file/query
rather than each function managing its own caching or state.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from tara.classification.heuristics import is_stop_word, tokenize
from tara.core.exceptions import RetrievalError
from tara.core.logging import get_logger

logger = get_logger(__name__)


def tokenize_for_search(text: str) -> list[str]:
    """Tokenize `text` for BM25 indexing and querying.

    Reuses `tara.classification.heuristics.tokenize` as the base
    tokenizer, lowercases every token for case-insensitive matching, and
    drops common English stop words -- the same three steps
    `FeatureExtractor._extract_keywords` applies when building
    `TaskClassification.extracted_keywords`, so a query's tokens and the
    corpus's tokens are produced by the identical process. Term
    repetition is preserved (this is not deduplicated): `BM25Index`
    relies on repeated tokens to compute term frequency correctly.

    Known limitation, accepted rather than solved here: the base
    tokenizer preserves `.`/`/`/`\\`-joined sequences as a single token
    (so `"utils.py"` and `"self.foo"` each tokenize as one token, not
    two). This is deliberate for file-path recognition, but means a
    query for the bare token `"foo"` will not match source text
    containing only the compound token `"self.foo"`. Splitting compound
    tokens into sub-identifiers as well would improve recall for that
    case; it is not implemented in this milestone, and is left as a
    documented, not silent, gap for `lexical_retriever.py`'s eventual
    ranking-quality evaluation to surface if it matters in practice.

    Args:
        text: The raw text to tokenize -- a query string, a symbol's
            name/docstring, or a slice of source code.

    Returns:
        Lowercased, stop-word-filtered tokens, in their original order,
        with repeats preserved. Empty if `text` contains no indexable
        tokens (e.g. an empty string or one made only of punctuation).
    """
    return [token.lower() for token in tokenize(text) if not is_stop_word(token)]


def normalize_scores(raw_scores: Mapping[str, float]) -> dict[str, float]:
    """Min-max normalize a mapping of raw scores into a fixed `[0.0, 1.0]` range.

    Args:
        raw_scores: `document_id -> raw_score`, e.g. the direct output
            of `BM25Index.score`. Values may be on any scale, including
            negative (BM25 scores are not guaranteed positive for every
            possible `k1`/`b` combination even though this project's
            smoothed IDF keeps them non-negative in practice).

    Returns:
        `document_id -> normalized_score`, each in `[0.0, 1.0]`. Empty
        if `raw_scores` is empty. If every value is identical (including
        the single-document case), every document is mapped to `1.0`
        rather than dividing by a zero range -- a tie among the only
        candidates present is not evidence of low relevance.
    """
    if not raw_scores:
        return {}

    minimum = min(raw_scores.values())
    maximum = max(raw_scores.values())
    if maximum == minimum:
        return dict.fromkeys(raw_scores, 1.0)

    span = maximum - minimum
    return {document_id: (score - minimum) / span for document_id, score in raw_scores.items()}


def read_file_bytes(path: Path) -> bytes | None:
    """Read the complete contents of `path` as raw bytes.

    Returns `None` rather than raising when the file cannot be read, so
    a single missing, moved, or permission-denied file degrades that
    one file's indexing instead of aborting the whole corpus build --
    the same failure-isolation convention already used by
    `tara.context.embedder._read_file_bytes`.

    Args:
        path: Absolute filesystem path to read.

    Returns:
        The file's raw bytes, or `None` if it could not be read.
    """
    try:
        return path.read_bytes()
    except OSError as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None


def decode_byte_span(raw_bytes: bytes, start_byte: int, end_byte: int) -> str:
    """Decode `raw_bytes[start_byte:end_byte]` as UTF-8, replacing undecodable bytes.

    Args:
        raw_bytes: The full file content a byte span is being sliced from.
        start_byte: Inclusive start offset, as recorded on a `CodeSymbol`.
        end_byte: Exclusive end offset, as recorded on a `CodeSymbol`.

    Returns:
        The decoded text for `raw_bytes[start_byte:end_byte]`. Any byte
        sequence that is not valid UTF-8 is replaced with the standard
        Unicode replacement character rather than raising, matching the
        decode convention already used throughout `tara.parsing` and
        `tara.context`.

    Raises:
        RetrievalError: If `start_byte` is negative or `end_byte` is
            less than `start_byte` -- a malformed span indicates a bug
            further upstream (e.g. in symbol extraction), not a
            condition this function should silently paper over by
            returning an empty or truncated string.
    """
    if start_byte < 0:
        raise RetrievalError(f"decode_byte_span received a negative start_byte: {start_byte!r}.")
    if end_byte < start_byte:
        raise RetrievalError(
            f"decode_byte_span received end_byte ({end_byte!r}) < start_byte ({start_byte!r})."
        )
    return raw_bytes[start_byte:end_byte].decode("utf-8", errors="replace")
