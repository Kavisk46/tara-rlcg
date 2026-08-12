"""Checkpoint/resume support, keyed on `(repository_id, commit_sha, query_text, pipeline_digest, input_digest)`.

An append-only JSONL log, not a rewritten-each-time snapshot: appending
one small line per completed query is O(1) regardless of how large the
dataset has grown, versus rewriting the whole checkpoint file on every
completion, which would be O(n) per query and O(n^2) overall -- exactly
the cost "Streaming writes" is meant to avoid.

Reviewer Minor Revision (Revisions 3-4): invalidation is **whole-file**,
not per-entry, deliberately -- see `CheckpointStore`'s docstring for
why. "The checkpoint becomes invalid" (Revision 1) and "invalidate
checkpoint" (Revision 4) are both singular, whole-checkpoint framings,
and a whole-file policy is also what keeps `DatasetGenerator`'s
cumulative `dataset_statistics.json` reseeding correct: see
`README.md`'s "Reproducibility Guarantees" for the double-counting bug
a *partial* (per-entry) invalidation policy would otherwise cause.
"""
from __future__ import annotations

import json
from pathlib import Path

from evaluation.rts_builder.dataset_builder.exceptions import CheckpointError
from tara.core.logging import get_logger

logger = get_logger(__name__)

_CompletionKey = tuple[str, str, str]


class CheckpointStore:
    """Records and queries which `(repository_id, commit_sha, query_text)` triples are complete.

    A query is marked complete only *after* every enabled export writer
    has successfully written its rows for that query (see
    `dataset_generator.py`) -- so a checkpoint entry is always a
    trustworthy claim that output already exists on disk for that
    query, under the pipeline/input configuration recorded alongside
    it, never a claim about work merely attempted.

    Invalidation is whole-file: if *any* loaded entry was recorded
    under a `pipeline_digest`/`input_digest` different from this run's,
    every entry -- including ones that happen to still match -- is
    treated as incomplete for this run's `is_complete` checks. This is
    deliberately simpler than per-entry invalidation, and not just for
    simplicity's sake: `pipeline_digest`/`input_digest` each describe
    the *entire* run's configuration/inputs, not any one query's, so a
    change to either means every query in the dataset needs
    recomputing under the new digest, not a mix of "trust this one,
    recompute that one" -- and per-entry invalidation would silently
    double-count a recomputed query's contribution in
    `DatasetGenerator`'s cumulative statistics (its old contribution is
    already baked into the previously-written `dataset_statistics.json`
    that a fresh accumulator would otherwise reseed from). Nothing is
    physically deleted or rewritten -- old entries remain on disk,
    informational, and a future run under their original digests would
    recognize them as valid again.
    """

    def __init__(self, checkpoint_path: Path, pipeline_digest: str, input_digest: str) -> None:
        """Open (or create) the checkpoint file, loading any already-completed entries.

        Args:
            checkpoint_path: Path to the checkpoint JSONL file. Its
                parent directory is created if missing.
            pipeline_digest: This run's `PipelineDigest.digest_hash`
                (`digest.compute_pipeline_digest`). Baked in at
                construction rather than passed to every `is_complete`
                /`mark_complete` call, since it is constant for the
                whole duration of one `generate()` run.
            input_digest: This run's `InputDigest.digest_hash`
                (`digest.compute_input_digest`).

        Raises:
            CheckpointError: If the file exists but cannot be opened
                for reading, or cannot be opened for appending.
        """
        self._path = checkpoint_path
        self._pipeline_digest = pipeline_digest
        self._input_digest = input_digest
        self._stale_entry_count = 0
        self._completed: set[_CompletionKey] = self._load_existing()

        try:
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = checkpoint_path.open("a", encoding="utf-8")
        except OSError as exc:
            raise CheckpointError(f"Could not open checkpoint file for appending at {checkpoint_path}: {exc}") from exc

    def _load_existing(self) -> set[_CompletionKey]:
        if not self._path.exists():
            return set()

        completed: set[_CompletionKey] = set()
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise CheckpointError(f"Could not read existing checkpoint file at {self._path}: {exc}") from exc

        for line_number, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                key = (record["repository_id"], record["commit_sha"], record["query_text"])
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                # A malformed trailing line is expected evidence of a process that crashed
                # mid-write on a previous run -- skip it (that query simply reruns), don't
                # abort resuming the whole dataset over one truncated line.
                logger.warning("Skipping malformed checkpoint line %d in %s: %s", line_number, self._path, exc)
                continue

            # .get() (not direct indexing): a pre-Revision entry (or one from a stale digest)
            # simply won't match today's digests below -- it never KeyErrors.
            if record.get("pipeline_digest") != self._pipeline_digest or record.get("input_digest") != self._input_digest:
                self._stale_entry_count += 1
            completed.add(key)

        if self._stale_entry_count:
            logger.warning(
                "%d of %d checkpoint entries in %s were recorded under a different pipeline_digest/input_digest "
                "(pipeline code/configuration or input files changed since they were recorded) -- the entire "
                "checkpoint is treated as invalid this run; every query will be recomputed.",
                self._stale_entry_count, len(completed), self._path,
            )
            return set()  # whole-file invalidation -- see class docstring

        logger.info("Loaded %d completed entries from checkpoint %s, all valid under the current digests", len(completed), self._path)
        return completed

    @property
    def stale_entry_count(self) -> int:
        """Number of loaded entries recorded under a different pipeline_digest/input_digest than this run's.

        A nonzero value means the *entire* checkpoint was invalidated
        (see class docstring) -- this count describes how many entries
        triggered that, not how many entries remain usable (zero,
        whenever this is nonzero).
        """
        return self._stale_entry_count

    def is_complete(self, repository_id: str, commit_sha: str, query_text: str) -> bool:
        """Return whether this triple was already marked complete, under this run's current digests."""
        return (repository_id, commit_sha, query_text) in self._completed

    def mark_complete(self, repository_id: str, commit_sha: str, query_text: str) -> None:
        """Durably record that `(repository_id, commit_sha, query_text)` has been fully written under the current digests.

        Raises:
            CheckpointError: If the write fails.
        """
        key = (repository_id, commit_sha, query_text)
        record = {
            "repository_id": repository_id,
            "commit_sha": commit_sha,
            "query_text": query_text,
            "pipeline_digest": self._pipeline_digest,
            "input_digest": self._input_digest,
        }
        try:
            self._handle.write(json.dumps(record, sort_keys=True) + "\n")
            self._handle.flush()
        except OSError as exc:
            raise CheckpointError(f"Could not write checkpoint entry to {self._path}: {exc}") from exc
        self._completed.add(key)

    def __len__(self) -> int:
        return len(self._completed)

    def close(self) -> None:
        """Close the underlying file handle."""
        self._handle.close()
