"""`PilotRunner`: drives the frozen `DatasetGenerator`, then splits, validates, exports, and documents the result.

This is the Pilot subsystem's outer loop, structurally mirroring how
`DatasetGenerator` itself wraps `PipelineOrchestrator` -- one stage
(here, the entire frozen Dataset Builder) runs first and unmodified,
and everything new happens strictly on its output:

    DatasetGenerator.generate()          (frozen, unmodified)
            |
            v
    assembler.load_current_rows()        (digest-filter + flatten + enrich)
            |
            v
    QuerySplitter.assign() per query     (deterministic train/val/test)
            |
            v
    PilotValidator.validate()            (Success Criteria + descriptive stats)
            |
            v
    exporter.* / figures.* / reporting.* (splits, figures, docs)

See `Architecture.md` for the full diagram and `README.md` for usage.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa

from evaluation.rts_builder.dataset_builder.config import DatasetBuilderSettings
from evaluation.rts_builder.dataset_builder.dataset_generator import DatasetGenerator
from evaluation.rts_builder.dataset_builder.models import DatasetGenerationSummary
from evaluation.rts_builder.dataset_builder.query_iterator import QueryIterator
from evaluation.rts_builder.dataset_builder.repository_iterator import RepositoryIterator
from evaluation.rts_builder.pilot import exporter, figures, reporting
from evaluation.rts_builder.pilot.assembler import load_current_rows
from evaluation.rts_builder.pilot.config import PilotSettings
from evaluation.rts_builder.pilot.environment import collect_environment_info
from evaluation.rts_builder.pilot.exceptions import PilotValidationError
from evaluation.rts_builder.pilot.models import (
    PilotSummary,
    ReproducibilityRecord,
    SplitCounts,
    SplitName,
    ValidationReport,
)
from evaluation.rts_builder.pilot.splitter import QuerySplitter
from evaluation.rts_builder.pilot.validator import PilotValidator
from tara.core.logging import get_logger

logger = get_logger(__name__)


class PilotRunner:
    """Produces the pilot RTS: runs Dataset Builder, then splits/validates/exports/documents its output."""

    def __init__(
        self,
        settings: PilotSettings | None = None,
        dataset_generator: DatasetGenerator | None = None,
        dataset_settings: DatasetBuilderSettings | None = None,
    ) -> None:
        """Construct the runner.

        Args:
            settings: Pilot-specific configuration (splits, output
                locations, validation toggles). Defaults to `PilotSettings()`.
            dataset_generator: The frozen Dataset Builder driver to run
                first. Defaults to `DatasetGenerator(settings=dataset_settings)`.
                If given explicitly, `dataset_settings` is ignored (the
                generator already owns its own settings).
            dataset_settings: Only used to build a default
                `dataset_generator` when one isn't given. Grouped export
                is forced on (`enable_grouped_export=True`) regardless
                of what's passed, since the pilot's assembler requires it.
        """
        self._settings = settings or PilotSettings()
        if dataset_generator is not None:
            self._dataset_generator = dataset_generator
            self._dataset_settings = dataset_settings or DatasetBuilderSettings()
        else:
            base_settings = dataset_settings or DatasetBuilderSettings()
            effective_settings = base_settings.model_copy(update={"enable_grouped_export": True})
            self._dataset_generator = DatasetGenerator(settings=effective_settings)
            self._dataset_settings = effective_settings

    def run(self, repository_iterator: RepositoryIterator, query_iterator: QueryIterator) -> PilotSummary:
        """Run the full pilot: generate, assemble, split, validate, export, document.

        Raises:
            PilotAssemblyError: If Dataset Builder's grouped output is
                missing or unreadable.
            PilotValidationError: If `PilotSettings.fail_on_validation_error`
                is True (the default) and any blocking Success
                Criterion fails -- split files/figures/docs are not
                written over a dataset known to have failed validation.
        """
        started_at = datetime.now(timezone.utc)
        data_dir = Path(self._settings.data_dir).resolve()

        generation_summary = self._dataset_generator.generate(repository_iterator, query_iterator)
        rows = self._assemble_rows(repository_iterator, generation_summary)

        splitter = QuerySplitter(self._settings)
        query_splits = self._assign_splits(rows, splitter)
        for row in rows:
            key = (str(row["repository_id"]), str(row["commit_sha"]), str(row["query_text"]))
            row["split"] = query_splits[key].value

        report = PilotValidator(self._settings).validate(rows)
        if not report.passed and self._settings.fail_on_validation_error:
            failing = [check.name for check in report.checks if check.blocking and not check.passed]
            raise PilotValidationError(
                f"Pilot dataset failed blocking validation check(s): {', '.join(failing)}. "
                "See the ValidationReport on this exception for full detail.",
                report,
            )

        output_paths, figure_paths, split_counts = self._export(rows, report, generation_summary, data_dir)

        reproducibility = ReproducibilityRecord(
            pipeline_digest=generation_summary.pipeline_digest,
            input_digest=generation_summary.input_digest,
            environment=collect_environment_info(),
        )

        summary = PilotSummary(
            dataset_generation_summary=generation_summary,
            split_counts=split_counts,
            validation_report=report,
            reproducibility=reproducibility,
            output_paths=output_paths,
            figure_paths=figure_paths,
            started_at=started_at,
        )

        self._write_documentation(summary, data_dir)

        logger.info(
            "Pilot run complete: %d repositories, %d queries, %d rows (train=%d val=%d test=%d queries), validation %s",
            len(report.repository_distribution), report.query_count, report.row_count,
            split_counts.train_queries, split_counts.validation_queries, split_counts.test_queries,
            "PASSED" if report.passed else "FAILED",
        )
        return summary

    def _assemble_rows(
        self, repository_iterator: RepositoryIterator, generation_summary: DatasetGenerationSummary
    ) -> list[dict[str, object]]:
        metadata_by_repository_id = {spec.repository_id: spec.metadata for spec in repository_iterator}
        grouped_jsonl_path = Path(self._dataset_settings.output_dir).resolve() / self._dataset_settings.grouped_jsonl_filename
        return load_current_rows(
            grouped_jsonl_path,
            generation_summary.pipeline_digest.digest_hash,
            generation_summary.input_digest.digest_hash,
            metadata_by_repository_id,
        )

    def _assign_splits(
        self, rows: list[dict[str, object]], splitter: QuerySplitter
    ) -> dict[tuple[str, str, str], SplitName]:
        query_splits: dict[tuple[str, str, str], SplitName] = {}
        for row in rows:
            key = (str(row["repository_id"]), str(row["commit_sha"]), str(row["query_text"]))
            if key not in query_splits:
                query_splits[key] = splitter.assign(*key)
        return query_splits

    def _export(
        self,
        rows: list[dict[str, object]],
        report: ValidationReport,
        generation_summary: DatasetGenerationSummary,
        data_dir: Path,
    ) -> tuple[dict[str, str], dict[str, str], SplitCounts]:
        rows_by_split: dict[SplitName, list[dict[str, object]]] = {name: [] for name in SplitName}
        for row in rows:
            rows_by_split[SplitName(row["split"])].append(row)

        schema = pa.Table.from_pylist(rows).schema if rows else pa.schema([])

        split_files = {
            SplitName.TRAIN: (self._settings.train_parquet_filename, self._settings.train_jsonl_filename),
            SplitName.VALIDATION: (self._settings.validation_parquet_filename, self._settings.validation_jsonl_filename),
            SplitName.TEST: (self._settings.test_parquet_filename, self._settings.test_jsonl_filename),
        }
        output_paths: dict[str, str] = {}
        for split_name, (parquet_filename, jsonl_filename) in split_files.items():
            split_rows = rows_by_split[split_name]
            parquet_path = data_dir / parquet_filename
            jsonl_path = data_dir / jsonl_filename
            exporter.write_split_parquet(split_rows, parquet_path, schema)
            exporter.write_split_jsonl(split_rows, jsonl_path)
            output_paths[f"{split_name.value}_parquet"] = str(parquet_path)
            output_paths[f"{split_name.value}_jsonl"] = str(jsonl_path)

        statistics_path = data_dir / self._settings.dataset_statistics_filename
        statistics_path.parent.mkdir(parents=True, exist_ok=True)
        statistics_path.write_text(generation_summary.statistics.model_dump_json(indent=2), encoding="utf-8")
        output_paths["dataset_statistics"] = str(statistics_path)

        feature_statistics_path = data_dir / self._settings.feature_statistics_filename
        exporter.write_feature_statistics_csv(report.feature_distributions, feature_statistics_path)
        output_paths["feature_statistics"] = str(feature_statistics_path)

        figures_dir = data_dir / self._settings.figures_dirname
        figure_paths = figures.generate_all(rows, list(report.feature_distributions.keys()), figures_dir, self._settings.figure_dpi)

        split_counts = SplitCounts(
            train_queries=len({(r["repository_id"], r["commit_sha"], r["query_text"]) for r in rows_by_split[SplitName.TRAIN]}),
            validation_queries=len({(r["repository_id"], r["commit_sha"], r["query_text"]) for r in rows_by_split[SplitName.VALIDATION]}),
            test_queries=len({(r["repository_id"], r["commit_sha"], r["query_text"]) for r in rows_by_split[SplitName.TEST]}),
            train_rows=len(rows_by_split[SplitName.TRAIN]),
            validation_rows=len(rows_by_split[SplitName.VALIDATION]),
            test_rows=len(rows_by_split[SplitName.TEST]),
        )
        return output_paths, figure_paths, split_counts

    def _write_documentation(self, summary: PilotSummary, data_dir: Path) -> None:
        validation_report_path = data_dir / self._settings.validation_report_filename
        validation_report_path.write_text(reporting.render_validation_report_markdown(summary.validation_report), encoding="utf-8")

        readme_path = data_dir / self._settings.dataset_readme_filename
        readme_path.write_text(reporting.render_data_readme_markdown(summary, self._settings), encoding="utf-8")

        card_path = data_dir / self._settings.dataset_card_filename
        card_path.write_text(reporting.render_dataset_card_markdown(summary, self._settings), encoding="utf-8")

        summary.output_paths["validation_report"] = str(validation_report_path)
        summary.output_paths["data_readme"] = str(readme_path)
        summary.output_paths["dataset_card"] = str(card_path)
