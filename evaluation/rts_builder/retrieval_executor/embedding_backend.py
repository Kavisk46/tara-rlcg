"""The default, deterministic embedding backend for Dense Retrieval.

Implements `tara.context.embedder.Embedder` -- reused directly rather
than redefined, since it is already exactly the right shape (`embed`,
`embed_batch`) and already has a real, production implementation
(`SentenceTransformerEmbedder`) available as a genuine, drop-in
alternative backend. That satisfies "pluggable embedding backend"
concretely: this module's `HashingEmbedder` and the existing
`SentenceTransformerEmbedder` are two interchangeable implementations
of one interface, not a new abstraction invented to sit beside an
unused old one.

`SentenceTransformerEmbedder` is not used as this subsystem's *default*
because it requires downloading a real model and a `torch`/`sentence
-transformers` runtime -- incompatible with fast, offline, deterministic
test execution. `HashingEmbedder` uses the well-known "feature hashing"
/ "hashing trick" technique (Weinberger et al., 2009; the same
technique behind scikit-learn's `HashingVectorizer` and Vowpal Wabbit)
to produce a real, dense embedding with no external model, no network
access, and byte-for-byte reproducible output.
"""
from __future__ import annotations

import hashlib
import math

from tara.context.embedder import Embedder
from tara.retrieval.utils import tokenize_for_search


class HashingEmbedder(Embedder):
    """Deterministic, dependency-free `Embedder` via the hashing trick.

    Each token is hashed (SHA-256, not Python's built-in `hash()` --
    which is randomly salted per process by default and therefore not
    reproducible across runs) into one of `dimensions` buckets, with a
    hash-derived sign, and accumulated; the result is L2-normalized.
    Same text in, same vector out, on any machine, in any process,
    forever -- exactly what "Deterministic execution" requires and what
    a real trained embedding model's version drift cannot itself
    guarantee.
    """

    def __init__(self, dimensions: int = 128) -> None:
        """Construct the embedder.

        Args:
            dimensions: The fixed output vector length. Must be > 0.
        """
        if dimensions <= 0:
            raise ValueError(f"dimensions must be > 0, got {dimensions!r}.")
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        """The fixed output vector length this embedder produces."""
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        """See `Embedder.embed`. Never raises; an empty/token-less text yields an all-zero vector."""
        vector = [0.0] * self._dimensions
        for token in tokenize_for_search(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], byteorder="big") % self._dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(component * component for component in vector))
        if norm == 0.0:
            return vector
        return [component / norm for component in vector]
