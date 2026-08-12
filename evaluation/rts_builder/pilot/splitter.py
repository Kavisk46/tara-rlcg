"""Deterministic train/validation/test split assignment, one decision per query.

A Learning-to-Rank dataset must never leak the same query into two
splits -- all four of a query's strategy rows have to land in the same
split together. `QuerySplitter.assign` is a pure function of
`(split_seed, repository_id, commit_sha, query_text)`: hashing (instead
of, say, shuffling an in-memory list with a seeded PRNG) means a
query's split assignment is stable regardless of processing order, and
-- as a deliberate side benefit not required by this milestone but
worth stating -- stable even if the query population later grows,
since each query's own bucket never depends on any other query's
presence or absence.
"""
from __future__ import annotations

import hashlib

from evaluation.rts_builder.pilot.config import PilotSettings
from evaluation.rts_builder.pilot.models import SplitName

_HASH_SPACE = 1 << 256
_FIELD_SEPARATOR = "\x1f"


class QuerySplitter:
    """Assigns each query to train/validation/test using `PilotSettings`' ratios and seed."""

    def __init__(self, settings: PilotSettings) -> None:
        self._settings = settings

    def assign(self, repository_id: str, commit_sha: str, query_text: str) -> SplitName:
        """Return the split this `(repository, commit, query)` triple deterministically belongs to."""
        payload = _FIELD_SEPARATOR.join(
            (self._settings.split_seed, repository_id, commit_sha, query_text)
        ).encode("utf-8")
        fraction = int(hashlib.sha256(payload).hexdigest(), 16) / _HASH_SPACE

        if fraction < self._settings.train_ratio:
            return SplitName.TRAIN
        if fraction < self._settings.train_ratio + self._settings.validation_ratio:
            return SplitName.VALIDATION
        return SplitName.TEST
