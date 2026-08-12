"""`DatasetGenerator`: the bulk driver over every repository and query, with checkpointing and streaming export.

Where `PipelineOrchestrator` runs the six pipeline stages for *one*
repository/query, `DatasetGenerator` is the outer loop: it drives the
orchestrator across an entire `RepositoryIterator` x `QueryIterator`
population, skips whatever the `CheckpointStore` already reports done,
fans each freshly-computed query out to every enabled export writer,
folds it into the running `StatisticsAccumulator`, and only then marks
it checkpointed. See `Pipeline.md` for the full data-flow diagram.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from evaluation.rts_builder.dataset_builder.checkpoint import CheckpointStore
from evaluation.rts_builder.dataset_builder.config import DatasetBuilderSettings
from evaluation.rts_builder.dataset_builder.digest import compute_input_digest, compute_pipeline_digest
from evaluation.rts_builder.dataset_builder.models import (
    DatasetGenerationSummary,
    DatasetRow,
    DatasetStatistics,
    GroupedDatasetRecord,
    InputDigest,
    PipelineDigest,
    PipelineSettingsSnapshot,
)
from evaluation.rts_builder.dataset_builder.pipeline_orchestrator import PipelineOrchestrator
from evaluation.rts_builder.dataset_builder.query_iterator import QueryIterator
from evaluation.rts_builder.dataset_builder.repository_iterator import RepositoryIterator
from evaluation.rts_builder.dataset_builder.statistics import StatisticsAccumulator
from evaluation.rts_builder.dataset_builder.writers import (
    CsvRowWriter,
    GroupedJsonlWriter,
    JsonlRowWriter,
    ParquetRowWriter,
    RowWriter,
)
from tara.core.logging import get_logger

logger = get_logger(__name__)


class DatasetGenerator:
    """Drives `PipelineOrchestrator` across an entire repository/query population, producing the RTS dataset."""

    def __init__(
        self,
        settings: DatasetBuilderSettings | None = None,
        orchestrator: PipelineOrchestrator | None = None,
        checkpoint_store: CheckpointStore | None = None,
        pipeline_settings: PipelineSettingsSnapshot | None = None,
    ) -> None:
        """Construct the generator.

        Args:
            settings: Output locations, enabled export formats, and
                batching. Defaults to `DatasetBuilderSettings()`.
            orchestrator: Defaults to `PipelineOrchestrator()` (which
                itself defaults every one of the five wrapped stages).
            checkpoint_store: If given, used as-is (its digests are
                assumed already correct) and `generate()` will not
                construct its own. If omitted (the common case),
                `generate()` builds one itself once it can compute this
                run's digests -- see `PipelineDigest`/`InputDigest`.
            pipeline_settings: The settings bundle `configuration_hash`
                is derived from. **Must match** whatever settings
                `orchestrator`'s five collaborators were actually
                constructed with, if not left at all-defaults -- see
                `PipelineSettingsSnapshot`'s docstring. Defaults to
                `PipelineSettingsSnapshot()` (every wrapped stage at
                its own default settings), which is only correct if
                `orchestrator` was also left at its defaults.
        """
        self._settings = settings or DatasetBuilderSettings()
        self._orchestrator = orchestrator or PipelineOrchestrator()
        self._output_dir = Path(self._settings.output_dir).resolve()
        self._pipeline_settings = pipeline_settings or PipelineSettingsSnapshot()
        self._explicit_checkpoint_store = checkpoint_store

    def generate(self, repository_iterator: RepositoryIterator, query_iterator: QueryIterator) -> DatasetGenerationSummary:
        """Run the full dataset build: every repository, every pending query, every enabled export format.

        Args:
            repository_iterator: The repositories to process, in order.
            query_iterator: The query population, keyed by `repository_id`.

        Returns:
            A summary of what ran, what was skipped (already
            checkpointed), what failed (logged, not fatal), what was
            invalidated by a digest change, and where output was
            written -- including `pipeline_digest`/`input_digest`
            themselves, for reproducibility auditing.
        """
        started_at = datetime.now(timezone.utc)

        pipeline_digest = compute_pipeline_digest(self._pipeline_settings)
        input_digest = compute_input_digest(repository_iterator.manifest_path, query_iterator.queries_path)
        self._write_digest(pipeline_digest, input_digest)

        checkpoint_store = self._explicit_checkpoint_store or CheckpointStore(
            self._output_dir / self._settings.checkpoint_filename,
            pipeline_digest=pipeline_digest.digest_hash,
            input_digest=input_digest.digest_hash,
        )
        self._checkpoint_store = checkpoint_store  # used by the loop below and by close-on-exit in `finally`

        row_writers = self._build_row_writers()
        grouped_writer = self._build_grouped_writer()
        statistics_path = self._output_dir / self._settings.statistics_filename

        # Do not reseed from a prior dataset_statistics.json if the checkpoint was invalidated:
        # every query is about to be recomputed this run (whole-file invalidation, see
        # CheckpointStore's docstring), so reseeding from the old aggregate would double-count
        # each recomputed query's contribution (once from the now-stale seed, once fresh). This
        # run's freshly-accumulated statistics alone are the complete, correct picture.
        seed = None if checkpoint_store.stale_entry_count else StatisticsAccumulator.from_existing(statistics_path)
        accumulator = StatisticsAccumulator(seed=seed)

        repositories_processed = repositories_skipped = repositories_failed = 0
        queries_processed = queries_skipped = queries_failed = 0

        try:
            for repository_spec in repository_iterator:
                queries = query_iterator.queries_for(repository_spec.repository_id)
                pending = [
                    query_spec
                    for query_spec in queries
                    if not self._checkpoint_store.is_complete(
                        repository_spec.repository_id, repository_spec.commit_sha, query_spec.query_text
                    )
                ]
                queries_skipped += len(queries) - len(pending)

                if not pending:
                    repositories_skipped += 1
                    logger.info(
                        "Skipping repository %s: all %d queries already checkpointed",
                        repository_spec.repository_id, len(queries),
                    )
                    continue

                try:
                    _repository, model = self._orchestrator.run_repository_stages(repository_spec)
                except Exception as exc:  # noqa: BLE001 - one bad repository's data must not abort the whole run
                    repositories_failed += 1
                    logger.warning(
                        "Repository %s failed to load/parse, skipping (will retry on resume): %s",
                        repository_spec.repository_id, exc,
                    )
                    continue

                repositories_processed += 1

                for query_spec in pending:
                    # Computation (Feature Extraction / Retrieval Executor / Oracle Utility) can
                    # legitimately fail on unusual per-query data -- caught and skipped, retried on
                    # a future resume, without aborting the rest of the run.
                    try:
                        feature_vector, oracle_result = self._orchestrator.run_query_stages(model, query_spec)
                    except Exception as exc:  # noqa: BLE001 - one bad query's data must not abort the whole run
                        queries_failed += 1
                        logger.warning(
                            "Query %r for repository %s failed, skipping (will retry on resume): %s",
                            query_spec.query_text, repository_spec.repository_id, exc,
                        )
                        continue

                    # Writing and checkpointing are infrastructure operations, not per-query data
                    # concerns: deliberately *not* caught here. A failure (e.g. disk full) is loud
                    # and aborts the run -- silently marking every subsequent query "failed" while
                    # the real cause was a full disk would be worse than an immediate, clear failure.
                    for row in oracle_result.rows:
                        flat_row = DatasetRow(
                            feature_vector=feature_vector, oracle_row=row,
                            pipeline_digest=pipeline_digest.digest_hash, input_digest=input_digest.digest_hash,
                        ).to_flat_dict()
                        for writer in row_writers:
                            writer.write_row(flat_row)
                    if grouped_writer is not None:
                        grouped_writer.write_record(
                            GroupedDatasetRecord(
                                feature_vector=feature_vector, oracle_result=oracle_result,
                                pipeline_digest=pipeline_digest.digest_hash, input_digest=input_digest.digest_hash,
                            )
                        )
                    accumulator.update(feature_vector, oracle_result)
                    self._checkpoint_store.mark_complete(
                        repository_spec.repository_id, repository_spec.commit_sha, query_spec.query_text
                    )
                    queries_processed += 1
        finally:
            for writer in row_writers:
                writer.close()
            if grouped_writer is not None:
                grouped_writer.close()
            self._checkpoint_store.close()

        statistics = accumulator.build_statistics()
        output_paths = self._write_statistics(statistics, statistics_path)

        summary = DatasetGenerationSummary(
            repositories_processed=repositories_processed,
            repositories_skipped=repositories_skipped,
            repositories_failed=repositories_failed,
            queries_processed=queries_processed,
            queries_skipped=queries_skipped,
            queries_failed=queries_failed,
            queries_invalidated_by_digest_change=checkpoint_store.stale_entry_count,
            pipeline_digest=pipeline_digest,
            input_digest=input_digest,
            statistics=statistics,
            output_paths=output_paths,
            started_at=started_at,
        )
        logger.info(
            "Dataset generation complete: %d repositories processed (%d skipped, %d failed), "
            "%d queries processed (%d skipped, %d failed), %d rows written",
            repositories_processed, repositories_skipped, repositories_failed,
            queries_processed, queries_skipped, queries_failed, statistics.row_count,
        )
        return summary

    def _write_digest(self, pipeline_digest: PipelineDigest, input_digest: InputDigest) -> None:
        """Persist this run's digests to `<output_dir>/<digest_filename>`, for reproducibility auditing.

        Written *before* the checkpoint is consulted, so `digest.json`
        always reflects the digests this specific `generate()` call is
        about to use -- including on a run that ends up skipping every
        repository because everything was already checkpointed.
        """
        digest_path = self._output_dir / self._settings.digest_filename
        digest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"pipeline_digest": pipeline_digest.model_dump(mode="json"), "input_digest": input_digest.model_dump(mode="json")}
        digest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _build_row_writers(self) -> list[RowWriter]:
        writers: list[RowWriter] = []
        if self._settings.enable_jsonl_export:
            writers.append(JsonlRowWriter(self._output_dir / self._settings.long_format_jsonl_filename))
        if self._settings.enable_csv_export:
            writers.append(CsvRowWriter(self._output_dir / self._settings.long_format_csv_filename))
        if self._settings.enable_parquet_export:
            writers.append(
                ParquetRowWriter(
                    self._output_dir / self._settings.long_format_parquet_dirname, self._settings.parquet_batch_size
                )
            )
        return writers

    def _build_grouped_writer(self) -> GroupedJsonlWriter | None:
        if not self._settings.enable_grouped_export:
            return None
        return GroupedJsonlWriter(self._output_dir / self._settings.grouped_jsonl_filename)

    def _write_statistics(self, statistics: DatasetStatistics, statistics_path: Path) -> dict[str, str]:
        statistics_path.parent.mkdir(parents=True, exist_ok=True)
        statistics_path.write_text(statistics.model_dump_json(indent=2), encoding="utf-8")

        output_paths = {"statistics": str(statistics_path)}
        if self._settings.enable_jsonl_export:
            output_paths["long_format_jsonl"] = str(self._output_dir / self._settings.long_format_jsonl_filename)
        if self._settings.enable_csv_export:
            output_paths["long_format_csv"] = str(self._output_dir / self._settings.long_format_csv_filename)
        if self._settings.enable_parquet_export:
            output_paths["long_format_parquet"] = str(self._output_dir / self._settings.long_format_parquet_dirname)
        if self._settings.enable_grouped_export:
            output_paths["grouped_jsonl"] = str(self._output_dir / self._settings.grouped_jsonl_filename)
        output_paths["checkpoint"] = str(self._output_dir / self._settings.checkpoint_filename)
        output_paths["digest"] = str(self._output_dir / self._settings.digest_filename)
        return output_paths
