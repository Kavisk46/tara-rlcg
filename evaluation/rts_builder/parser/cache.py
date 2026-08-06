"""Commit-level cache for `RepositoryModel`, enabling incremental parsing.

Granularity is per-`(repository_id, commit_sha)`, not per-file: if a
`repository_model.json` already exists for the exact commit being
requested, the entire cached `RepositoryModel` is returned and no
walking, parsing, or graph resolution happens at all. This mirrors
`RepositoryLoader`'s own idempotent-reuse design: repositories are
pinned to one commit and re-parsed across pipeline runs and development
iterations, not edited file-by-file between parses.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from evaluation.rts_builder.parser.config import ParserSettings
from evaluation.rts_builder.parser.exceptions import ParserCacheError
from evaluation.rts_builder.parser.export import export_repository_model
from evaluation.rts_builder.parser.models import RepositoryModel
from tara.core.logging import get_logger

logger = get_logger(__name__)

_MANIFEST_FILENAME = "repository_model.json"


class RepositoryModelCache:
    """Reads and atomically writes `repository_model.json` cache entries."""

    def __init__(self, settings: ParserSettings) -> None:
        """Construct the cache.

        Args:
            settings: Provides `cache_root`, under which each
                repository gets its own subdirectory.
        """
        self._settings = settings

    def manifest_path(self, repository_id: str) -> Path:
        """Return the deterministic cache path for `repository_id`."""
        return Path(self._settings.cache_root).resolve() / repository_id / _MANIFEST_FILENAME

    def load(self, repository_id: str, commit_sha: str) -> RepositoryModel | None:
        """Return a cached `RepositoryModel` for `(repository_id, commit_sha)`, or None on any miss.

        A miss includes: no cache file exists, the cache file is
        unreadable or corrupt, or the cached commit doesn't match
        `commit_sha`. Every miss case is logged and treated identically
        (return None) -- a damaged cache entry must never block the
        pipeline, only cost it a re-parse.
        """
        path = self.manifest_path(repository_id)
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Cache entry at %s is unreadable, treating as a miss: %s", path, exc)
            return None

        if payload.get("commit_sha") != commit_sha:
            logger.debug(
                "Cache entry at %s is for a different commit (%s), treating as a miss.",
                path, payload.get("commit_sha"),
            )
            return None

        try:
            cached = RepositoryModel.model_validate(payload)
        except ValidationError as exc:
            logger.warning("Cache entry at %s failed schema validation, treating as a miss: %s", path, exc)
            return None

        return cached.model_copy(update={"from_cache": True})

    def save(self, model: RepositoryModel) -> Path:
        """Atomically persist `model` and return the manifest path it was written to.

        Raises:
            ParserCacheError: If the manifest cannot be written.
        """
        path = self.manifest_path(model.repository_id)
        try:
            return export_repository_model(model, path)
        except OSError as exc:
            raise ParserCacheError(f"Failed to write parser cache entry at {path}: {exc}") from exc
