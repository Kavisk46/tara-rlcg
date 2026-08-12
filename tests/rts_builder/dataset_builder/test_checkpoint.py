"""Unit tests for `evaluation.rts_builder.dataset_builder.checkpoint.CheckpointStore`."""
from __future__ import annotations

import json
from pathlib import Path

from evaluation.rts_builder.dataset_builder.checkpoint import CheckpointStore

_PIPELINE_DIGEST = "pipeline-digest-a"
_INPUT_DIGEST = "input-digest-a"


def _store(path: Path, pipeline_digest: str = _PIPELINE_DIGEST, input_digest: str = _INPUT_DIGEST) -> CheckpointStore:
    return CheckpointStore(path, pipeline_digest=pipeline_digest, input_digest=input_digest)


def test_new_checkpoint_has_nothing_complete(tmp_path: Path) -> None:
    store = _store(tmp_path / "checkpoint.jsonl")
    assert store.is_complete("repo", "sha", "query") is False
    assert len(store) == 0
    assert store.stale_entry_count == 0
    store.close()


def test_mark_complete_is_immediately_visible(tmp_path: Path) -> None:
    store = _store(tmp_path / "checkpoint.jsonl")
    store.mark_complete("repo", "sha", "query")
    assert store.is_complete("repo", "sha", "query") is True
    assert len(store) == 1
    store.close()


def test_completion_is_keyed_on_the_full_triple(tmp_path: Path) -> None:
    store = _store(tmp_path / "checkpoint.jsonl")
    store.mark_complete("repo", "sha1", "query")
    assert store.is_complete("repo", "sha2", "query") is False  # different commit_sha
    assert store.is_complete("repo", "sha1", "different query") is False
    store.close()


def test_persists_across_instances_with_matching_digests(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.jsonl"
    first = _store(path)
    first.mark_complete("repo", "sha", "q1")
    first.close()

    second = _store(path)
    assert second.is_complete("repo", "sha", "q1") is True
    second.mark_complete("repo", "sha", "q2")
    second.close()

    third = _store(path)
    assert third.is_complete("repo", "sha", "q1") is True
    assert third.is_complete("repo", "sha", "q2") is True
    assert len(third) == 2
    assert third.stale_entry_count == 0
    third.close()


def test_malformed_trailing_line_is_skipped_not_fatal(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.jsonl"
    path.write_text(
        f'{{"repository_id": "repo", "commit_sha": "sha", "query_text": "q1", '
        f'"pipeline_digest": "{_PIPELINE_DIGEST}", "input_digest": "{_INPUT_DIGEST}"}}\n{{"truncated',
        encoding="utf-8",
    )

    store = _store(path)

    assert store.is_complete("repo", "sha", "q1") is True
    assert len(store) == 1
    store.close()


def test_blank_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.jsonl"
    path.write_text(
        f'{{"repository_id": "repo", "commit_sha": "sha", "query_text": "q1", '
        f'"pipeline_digest": "{_PIPELINE_DIGEST}", "input_digest": "{_INPUT_DIGEST}"}}\n\n',
        encoding="utf-8",
    )

    store = _store(path)

    assert len(store) == 1
    store.close()


# ---------------------------------------------------------------------------
# Reviewer Minor Revision: pipeline_digest / input_digest invalidation
# ---------------------------------------------------------------------------


def test_entry_from_a_different_pipeline_digest_is_not_complete(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.jsonl"
    first = _store(path, pipeline_digest="pipeline-a")
    first.mark_complete("repo", "sha", "q1")
    first.close()

    second = _store(path, pipeline_digest="pipeline-b")  # e.g. configuration or code changed
    assert second.is_complete("repo", "sha", "q1") is False
    assert second.stale_entry_count == 1
    second.close()


def test_entry_from_a_different_input_digest_is_not_complete(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.jsonl"
    first = _store(path, input_digest="input-a")
    first.mark_complete("repo", "sha", "q1")
    first.close()

    second = _store(path, input_digest="input-b")  # e.g. manifest or queries file changed
    assert second.is_complete("repo", "sha", "q1") is False
    assert second.stale_entry_count == 1
    second.close()


def test_stale_and_fresh_entries_are_counted_independently(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.jsonl"
    first = _store(path, pipeline_digest="pipeline-a")
    first.mark_complete("repo", "sha", "q1")
    first.close()

    # Same digest as `first` -- q1 is still valid -- plus a newly completed q2.
    second = _store(path, pipeline_digest="pipeline-a")
    assert second.is_complete("repo", "sha", "q1") is True
    second.mark_complete("repo", "sha", "q2")
    second.close()

    # A third session under a *different* pipeline_digest invalidates both prior entries.
    third = _store(path, pipeline_digest="pipeline-b")
    assert third.is_complete("repo", "sha", "q1") is False
    assert third.is_complete("repo", "sha", "q2") is False
    assert third.stale_entry_count == 2
    third.close()


def test_a_pre_revision_checkpoint_entry_with_no_digest_fields_is_treated_as_stale(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.jsonl"
    path.write_text('{"repository_id": "repo", "commit_sha": "sha", "query_text": "q1"}\n', encoding="utf-8")

    store = _store(path)

    assert store.is_complete("repo", "sha", "q1") is False
    assert store.stale_entry_count == 1
    store.close()


def test_mark_complete_records_the_current_digests_on_disk(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.jsonl"
    store = _store(path, pipeline_digest="pipeline-x", input_digest="input-y")
    store.mark_complete("repo", "sha", "q1")
    store.close()

    record = json.loads(path.read_text(encoding="utf-8").strip())
    assert record["pipeline_digest"] == "pipeline-x"
    assert record["input_digest"] == "input-y"
