"""`PipelineOrchestrator`: runs the frozen six-stage pipeline for one repository and one query.

```
Repository -> Repository Loader -> Parser -> Feature Extraction -> Retrieval Executor -> Oracle Utility -> RTS row
```

Every stage is an already-accepted, frozen RTS Builder milestone,
constructor-injected here exactly as each of them injects its own
collaborators -- this module orchestrates, it does not reimplement or
modify any of the five wrapped subsystems. See `Pipeline.md` for the
full stage-by-stage data-flow diagram.
"""
from __future__ import annotations

from evaluation.rts_builder.dataset_builder.models import QuerySpec, RepositorySpec
from evaluation.rts_builder.feature_extraction.extractor import FeatureExtractor
from evaluation.rts_builder.feature_extraction.models import FeatureVector
from evaluation.rts_builder.models import Repository
from evaluation.rts_builder.oracle_utility.computer import OracleUtilityComputer
from evaluation.rts_builder.oracle_utility.models import OracleUtilityResult, RelevanceJudgment
from evaluation.rts_builder.parser.models import RepositoryModel
from evaluation.rts_builder.parser.pipeline import PythonParserPipeline
from evaluation.rts_builder.repository_loader import RepositoryLoader
from evaluation.rts_builder.retrieval_executor.executor import RetrievalExecutor
from tara.core.logging import get_logger

logger = get_logger(__name__)


class PipelineOrchestrator:
    """Runs the six frozen pipeline stages, split into a per-repository phase and a per-query phase.

    The split matters for correctness, not just organization: cloning
    and parsing a repository is expensive and query-independent, so it
    happens exactly once per repository (`run_repository_stages`), while
    feature extraction, retrieval, and oracle utility computation are
    genuinely query-dependent and run once per query
    (`run_query_stages`) against the same already-parsed
    `RepositoryModel`.
    """

    def __init__(
        self,
        repository_loader: RepositoryLoader | None = None,
        parser_pipeline: PythonParserPipeline | None = None,
        feature_extractor: FeatureExtractor | None = None,
        retrieval_executor: RetrievalExecutor | None = None,
        oracle_computer: OracleUtilityComputer | None = None,
    ) -> None:
        """Construct the orchestrator.

        Args:
            repository_loader: Defaults to `RepositoryLoader()`.
            parser_pipeline: Defaults to `PythonParserPipeline()`.
            feature_extractor: Defaults to `FeatureExtractor()`.
            retrieval_executor: Defaults to `RetrievalExecutor()`.
            oracle_computer: Defaults to `OracleUtilityComputer()`.
        """
        self._repository_loader = repository_loader or RepositoryLoader()
        self._parser_pipeline = parser_pipeline or PythonParserPipeline()
        self._feature_extractor = feature_extractor or FeatureExtractor()
        self._retrieval_executor = retrieval_executor or RetrievalExecutor()
        self._oracle_computer = oracle_computer or OracleUtilityComputer()

    def run_repository_stages(self, repository_spec: RepositorySpec) -> tuple[Repository, RepositoryModel]:
        """Stages 1-2: load and parse one repository.

        Args:
            repository_spec: Identifies which repository to load.

        Returns:
            `(Repository, RepositoryModel)` -- both are needed downstream:
            `Repository` for its `local_path`/`commit_sha` provenance,
            `RepositoryModel` for every later stage's actual input.

        Raises:
            evaluation.rts_builder.exceptions.RepositoryLoaderError: On any Repository Loader failure.
            evaluation.rts_builder.parser.exceptions.ParserSubsystemError: On any Parser failure.
        """
        logger.info("Loading repository %s", repository_spec.repository_id)
        repository = self._repository_loader.load_repository(
            repository_spec.repository_id, repository_spec.source_url, repository_spec.commit_sha
        )
        model = self._parser_pipeline.parse_repository(repository)
        return repository, model

    def run_query_stages(self, model: RepositoryModel, query_spec: QuerySpec) -> tuple[FeatureVector, OracleUtilityResult]:
        """Stages 3-6: feature extraction, retrieval, and oracle utility computation for one query.

        Args:
            model: The repository's already-parsed structural model
                (from `run_repository_stages`).
            query_spec: The query text and its ground-truth relevance
                judgment.

        Returns:
            `(FeatureVector, OracleUtilityResult)` -- the features (the
            Learning-to-Rank input side) and the oracle labels (the
            Learning-to-Rank supervision side) for this one query.

        Raises:
            evaluation.rts_builder.feature_extraction.exceptions.FeatureExtractionError: On any Feature Extraction failure.
            evaluation.rts_builder.retrieval_executor.exceptions.RetrievalExecutorError: On any Retrieval Executor failure.
            evaluation.rts_builder.oracle_utility.exceptions.OracleUtilityError: On any Oracle Utility failure.
        """
        feature_vector = self._feature_extractor.extract(model, query_spec.query_text)
        execution_result = self._retrieval_executor.execute_all(model, feature_vector, query_spec.query_text)

        judgment = RelevanceJudgment(
            repository_id=model.repository_id,
            commit_sha=model.commit_sha,
            query_text=query_spec.query_text,
            relevance_grades=query_spec.relevance_grades,
        )
        oracle_result = self._oracle_computer.compute(execution_result, judgment)
        return feature_vector, oracle_result
