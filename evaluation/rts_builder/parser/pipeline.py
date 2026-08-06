"""`PythonParserPipeline`: the Parser subsystem's single public entry point.

Turns a `Repository` (Repository Loader's output -- accepted, frozen,
not touched by this module) into a `RepositoryModel`. Orchestrates,
without reimplementing, this milestone's own components: the file walk
(`file_walker`), per-file AST extraction (`file_parser`,
`repository_parser`), graph resolution (`graph_builder`), normalization
(`normalizer`), and the incremental-parsing cache (`cache`).
"""
from __future__ import annotations

from pathlib import Path

from git import InvalidGitRepositoryError, Repo

from evaluation.rts_builder.models import Repository
from evaluation.rts_builder.parser.cache import RepositoryModelCache
from evaluation.rts_builder.parser.config import ParserSettings
from evaluation.rts_builder.parser.exceptions import RepositoryStateError
from evaluation.rts_builder.parser.graph_builder import GraphBuilder
from evaluation.rts_builder.parser.models import RepositoryModel
from evaluation.rts_builder.parser.normalizer import normalize
from evaluation.rts_builder.parser.repository_parser import PythonRepositoryParser
from tara.core.logging import get_logger

logger = get_logger(__name__)


class PythonParserPipeline:
    """Converts a pinned `Repository` into a normalized `RepositoryModel`.

    Every collaborator is injected, following the same
    constructor-injection convention as `RepositoryLoader`.
    """

    def __init__(
        self,
        settings: ParserSettings | None = None,
        repository_parser: PythonRepositoryParser | None = None,
        graph_builder: GraphBuilder | None = None,
        cache: RepositoryModelCache | None = None,
    ) -> None:
        """Construct the pipeline.

        Args:
            settings: Configuration for the walk, caching, and graph
                behavior. Defaults to `ParserSettings()` (environment
                defaults).
            repository_parser: Defaults to `PythonRepositoryParser(settings)`.
            graph_builder: Defaults to `GraphBuilder(settings)`.
            cache: Defaults to a `RepositoryModelCache` constructed from `settings`.
        """
        self._settings = settings or ParserSettings()
        self._repository_parser = repository_parser or PythonRepositoryParser(self._settings)
        self._graph_builder = graph_builder or GraphBuilder(self._settings)
        self._cache = cache or RepositoryModelCache(self._settings)

    def parse_repository(self, repository: Repository) -> RepositoryModel:
        """Parse `repository` (as loaded by Repository Loader) into a `RepositoryModel`.

        Args:
            repository: A `Repository` returned by
                `RepositoryLoader.load_repository`. Its `local_path`
                must still exist and must still be checked out to
                `repository.commit_sha`.

        Returns:
            The normalized parse. `from_cache` indicates whether this
            was served from `repository_model.json`
            (`settings.force_reparse=False` and a matching cache entry
            existed) or freshly computed.

        Raises:
            RepositoryStateError: If `repository.local_path` doesn't
                exist, isn't a git repository, or its checked-out commit
                no longer matches `repository.commit_sha` (e.g. it was
                mutated by a concurrent `load_repository()` call for a
                different commit between the two milestones).
        """
        if not self._settings.force_reparse:
            cached = self._cache.load(repository.repository_id, repository.commit_sha)
            if cached is not None:
                logger.info(
                    "Using cached repository model for %s@%s", repository.repository_id, repository.commit_sha[:8]
                )
                return cached

        local_path = Path(repository.local_path)
        if not local_path.is_dir():
            raise RepositoryStateError(
                f"{local_path} does not exist. Was repository {repository.repository_id!r} loaded via "
                "RepositoryLoader.load_repository(), and has its clone not been removed since?"
            )
        self._verify_commit_unchanged(repository, local_path)

        parse_result = self._repository_parser.parse(local_path)
        graphs = self._graph_builder.build(parse_result.files)
        model = normalize(
            repository_id=repository.repository_id,
            commit_sha=repository.commit_sha,
            root_path=str(local_path),
            parse_result=parse_result,
            graphs=graphs,
        )

        manifest_path = self._cache.save(model)
        model = model.model_copy(update={"manifest_path": str(manifest_path)})

        logger.info(
            "Parsed repository %s@%s: %d files, %d functions, %d classes, %d imports, "
            "%d import edges, %d call edges, %d inheritance edges",
            repository.repository_id, repository.commit_sha[:8], len(model.files), len(model.functions),
            len(model.classes), len(model.imports), len(model.import_graph), len(model.call_graph),
            len(model.inheritance_graph),
        )
        return model

    @staticmethod
    def _verify_commit_unchanged(repository: Repository, local_path: Path) -> None:
        """Guard against the repository having been mutated between Loader and Parser stages.

        `RepositoryLoader` guarantees `local_path`'s HEAD is exactly
        `repository.commit_sha` at the moment `load_repository()`
        returns, but its lock is released once that call returns. A
        narrow race is possible: a concurrent `load_repository()` call
        for the *same* `repository_id` but a *different* commit could
        re-checkout `local_path` before this pipeline reads it. Silently
        parsing the wrong commit would be a correctness bug invisible
        until much later; this check turns it into an immediate, clear
        failure instead.

        Raises:
            RepositoryStateError: If `local_path` isn't a git
                repository, or its HEAD doesn't match `repository.commit_sha`.
        """
        try:
            current_sha = Repo(local_path).head.commit.hexsha
        except (InvalidGitRepositoryError, ValueError) as exc:
            raise RepositoryStateError(f"{local_path} is not a valid git repository: {exc}") from exc

        if current_sha != repository.commit_sha:
            raise RepositoryStateError(
                f"Repository {repository.repository_id!r} at {local_path} is now at commit "
                f"{current_sha!r}, but was loaded and pinned at {repository.commit_sha!r}. It was likely "
                "mutated by a concurrent load_repository() call for a different commit between the "
                "Repository Loader and Parser stages."
            )
