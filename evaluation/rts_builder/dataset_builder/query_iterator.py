"""Reads a queries file (JSONL, one `QuerySpec` per line, keyed by `repository_id`).

JSONL, not a JSON array, because the query population is expected to be
large (`docs/DATASET_BUILDER_SPEC.md` §4's proposed 2,000-5,000 query
target) -- line-oriented parsing never requires holding the whole file
in memory as one parsed structure, consistent with this milestone's
"Streaming writes" requirement applied symmetrically to reading.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError

from evaluation.rts_builder.dataset_builder.exceptions import ManifestError
from evaluation.rts_builder.dataset_builder.models import QuerySpec


class QueryIterator:
    """Indexes a queries JSONL file by `repository_id`, preserving each repository's query order."""

    def __init__(self, queries_path: Path) -> None:
        """Load and validate every query record.

        Args:
            queries_path: Path to a JSONL file, one `QuerySpec` object
                per line (see `DatasetSchema.md`).

        Raises:
            ManifestError: If the file doesn't exist, or any non-blank
                line fails to parse as JSON or fails `QuerySpec`
                validation. Unlike a checkpoint file (where a
                corrupted trailing line is treated as evidence of an
                interrupted write and skipped), a queries file is
                curated input data -- a malformed line here is a data
                -authoring error that should stop the run, not be
                silently dropped.
        """
        self._queries_path = queries_path
        self._queries_by_repository: dict[str, list[QuerySpec]] = {}
        self._all_queries: list[QuerySpec] = []
        self._load(queries_path)

    @property
    def queries_path(self) -> Path:
        """The queries file this iterator was constructed from -- used by `digest.compute_input_digest`."""
        return self._queries_path

    def _load(self, queries_path: Path) -> None:
        if not queries_path.is_file():
            raise ManifestError(f"Queries file not found: {queries_path}")

        with queries_path.open(encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ManifestError(f"{queries_path}:{line_number} is not valid JSON: {exc}") from exc
                try:
                    spec = QuerySpec.model_validate(payload)
                except ValidationError as exc:
                    raise ManifestError(f"{queries_path}:{line_number} is not a valid QuerySpec: {exc}") from exc

                self._queries_by_repository.setdefault(spec.repository_id, []).append(spec)
                self._all_queries.append(spec)

    def queries_for(self, repository_id: str) -> list[QuerySpec]:
        """Return every query for `repository_id`, in file order. Empty list if none exist."""
        return list(self._queries_by_repository.get(repository_id, []))

    def __iter__(self) -> Iterator[QuerySpec]:
        """Iterate every query across every repository, in file order."""
        return iter(self._all_queries)

    def __len__(self) -> int:
        return len(self._all_queries)
