"""Deterministic, content-addressed identifiers computed at the Pilot layer.

Neither `RepositorySpec`/`QuerySpec` (frozen Dataset Builder input
models) nor `StrategyOracleRow`/`FeatureVector`/`GroupedDatasetRecord`
(frozen Oracle Utility/Feature Extraction/Dataset Builder output
models) carry a stable per-query identifier -- a query is identified by
its raw text throughout the entire frozen pipeline. The pilot's own
required output schema asks for a "Query ID" column, so one is computed
here, purely as a consumer of frozen output, without adding a field to
or otherwise touching any frozen model.
"""
from __future__ import annotations

import hashlib

_QUERY_ID_HEX_LENGTH = 16
_FIELD_SEPARATOR = "\x1f"


def compute_query_id(repository_id: str, commit_sha: str, query_text: str) -> str:
    """A stable id for one `(repository_id, commit_sha, query_text)` triple.

    Deterministic and collision-resistant (16 hex chars = 64 bits of a
    SHA-256 digest): the same triple always produces the same id,
    across runs, processes, and machines, with no counter or registry
    to keep in sync -- the same content-addressing principle
    `digest.py` already applies to pipeline/input digests.
    """
    payload = _FIELD_SEPARATOR.join((repository_id, commit_sha, query_text)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:_QUERY_ID_HEX_LENGTH]
