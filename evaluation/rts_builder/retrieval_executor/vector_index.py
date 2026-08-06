"""The vector index abstraction for Dense Retrieval, and its default implementation.

`VectorIndex` is a `Protocol` (structural typing), not an ABC: a future
FAISS- or other vector-database-backed implementation only needs to
match this shape, not inherit from anything in this module -- see
`README.md`'s Future Extension Points. `InMemoryVectorIndex` is a
brute-force, pure-Python cosine-similarity search: correct and
plenty fast at the scale this subsystem actually operates at (one
repository's file count, typically low thousands at most), and it adds
no new dependency (no `faiss-cpu`, already a project dependency but
unused here -- see `README.md` for why) for a workload that does not
need an approximate-nearest-neighbor index to be fast.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Protocol


class VectorIndex(Protocol):
    """Structural contract for a searchable collection of id -> vector entries."""

    def build(self, vectors: Mapping[str, list[float]]) -> None:
        """Replace this index's contents with `vectors`."""
        ...

    def search(self, query_vector: list[float], top_k: int) -> list[tuple[str, float]]:
        """Return the `top_k` ids most similar to `query_vector`, highest similarity first."""
        ...


class InMemoryVectorIndex:
    """Brute-force cosine-similarity search over an in-memory `{id: vector}` mapping."""

    def __init__(self) -> None:
        """Construct an empty index; populate it via `build`."""
        self._vectors: dict[str, list[float]] = {}

    def build(self, vectors: Mapping[str, list[float]]) -> None:
        """See `VectorIndex.build`."""
        self._vectors = dict(vectors)

    def search(self, query_vector: list[float], top_k: int) -> list[tuple[str, float]]:
        """See `VectorIndex.search`.

        Ties are broken by id ascending, for the same determinism
        reason `common.rank_scores` breaks ties that way. Returns fewer
        than `top_k` entries if the index has fewer than `top_k` items;
        empty if the index is empty.
        """
        scored = [
            (document_id, _cosine_similarity(query_vector, vector)) for document_id, vector in self._vectors.items()
        ]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return scored[:top_k]

    def __len__(self) -> int:
        return len(self._vectors)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return the cosine similarity of `a` and `b`, or `0.0` if either is a zero vector.

    Raises:
        ValueError: If `a` and `b` have different lengths -- silently
            truncating via a non-strict zip would compute a similarity
            over the wrong subset of dimensions rather than surface a
            real embedder-configuration bug.
    """
    dot_product = sum(x * y for x, y in zip(a, b, strict=True))
    magnitude_a = math.sqrt(sum(x * x for x in a))
    magnitude_b = math.sqrt(sum(y * y for y in b))
    if magnitude_a == 0.0 or magnitude_b == 0.0:
        return 0.0
    return dot_product / (magnitude_a * magnitude_b)
