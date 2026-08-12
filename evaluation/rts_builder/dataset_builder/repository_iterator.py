"""Reads a repository manifest (JSON array) into an ordered, deterministic sequence of `RepositorySpec`.

Manifest order is preserved exactly (no sorting, no set/dict
deduplication that could reorder entries) -- required for "Deterministic
execution": two runs over the same manifest must process repositories
in the same order.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError

from evaluation.rts_builder.dataset_builder.exceptions import ManifestError
from evaluation.rts_builder.dataset_builder.models import RepositorySpec


class RepositoryIterator:
    """Iterates over a repository manifest file, one `RepositorySpec` per entry."""

    def __init__(self, manifest_path: Path) -> None:
        """Load and validate the manifest.

        Args:
            manifest_path: Path to a JSON file containing an array of
                repository manifest entries (see `DatasetSchema.md`).

        Raises:
            ManifestError: If the file doesn't exist, isn't valid JSON,
                isn't a JSON array, or any entry fails `RepositorySpec`
                validation. Duplicate `repository_id`s are also
                rejected -- silently processing the same id twice would
                make checkpoint/statistics accounting ambiguous.
        """
        self._manifest_path = manifest_path
        self._specs = self._load(manifest_path)

    @property
    def manifest_path(self) -> Path:
        """The manifest file this iterator was constructed from -- used by `digest.compute_input_digest`."""
        return self._manifest_path

    def _load(self, manifest_path: Path) -> list[RepositorySpec]:
        if not manifest_path.is_file():
            raise ManifestError(f"Repository manifest not found: {manifest_path}")

        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ManifestError(f"Repository manifest at {manifest_path} is not valid JSON: {exc}") from exc

        if not isinstance(payload, list):
            raise ManifestError(f"Repository manifest at {manifest_path} must be a JSON array, got {type(payload).__name__}.")

        specs: list[RepositorySpec] = []
        seen_ids: set[str] = set()
        for index, entry in enumerate(payload):
            try:
                spec = RepositorySpec.model_validate(entry)
            except ValidationError as exc:
                raise ManifestError(f"Repository manifest entry {index} at {manifest_path} is invalid: {exc}") from exc
            if spec.repository_id in seen_ids:
                raise ManifestError(f"Repository manifest at {manifest_path} has a duplicate repository_id: {spec.repository_id!r}.")
            seen_ids.add(spec.repository_id)
            specs.append(spec)

        return specs

    def __iter__(self) -> Iterator[RepositorySpec]:
        return iter(self._specs)

    def __len__(self) -> int:
        return len(self._specs)
