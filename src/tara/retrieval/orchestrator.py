"""Retrieval Orchestrator: executes an already-decided `RetrievalPlan`.

`RetrievalOrchestrator` is deliberately dumb about *strategy*: the
Task-Guided Adaptive Router already decided which retriever kinds to
run, in what order, and whether to run them concurrently
(`RetrievalPlan.retrievers` / `.execution_order` / `.parallel`). This
class's only job is mechanical execution of that already-made decision
-- it never adds, drops, or reorders a retriever kind the plan didn't
already specify, and it never inspects `context` to second-guess the
plan (that capability-checking already happened once, in
`RetrievalPlanner._apply_context_constraints`, before this class ever
sees the plan).

Two categories of "can't run a requested retriever" are handled
differently, on purpose:

- **A retriever kind the plan wants but this orchestrator instance has
  no implementation registered for** ("unavailable") is a deployment/
  wiring gap, not a data-integrity problem -- the same category of
  situation `RetrievalPlanner` itself already degrades gracefully for
  (dropping DENSE when no embeddings exist, falling back to LEXICAL).
  Handled the same way: log a clear warning identifying exactly which
  `RetrieverKind` was unavailable, skip it, and continue with the rest
  of the plan. This is "clean" (no crash) without being silent (the
  warning is specific, and the returned list is observably shorter than
  `len(plan.retrievers)` for any caller that checks).
- **`plan.execution_order` and `plan.retrievers` disagreeing on the
  retriever set** is a plan-construction defect with no sensible
  degraded execution -- blindly trusting either field would mean
  running something the plan didn't actually select. Raises
  `OrchestrationError` immediately, before executing anything.

A single retriever raising `RetrievalError` *during* its own
`.retrieve()` call is treated the same as "unavailable": logged and
skipped, not propagated, so one retriever's failure never prevents the
others in the same plan from still producing results.
"""
from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor

from tara.context.models import RepositoryContext
from tara.core.exceptions import OrchestrationError, RetrievalError
from tara.core.logging import get_logger
from tara.core.types import RetrieverKind
from tara.interfaces.retriever import Retriever
from tara.retrieval.models import RetrievedContext
from tara.routing.models import RetrievalPlan

logger = get_logger(__name__)


class RetrievalOrchestrator:
    """Executes a `RetrievalPlan` against a fixed set of registered `Retriever`s.

    `retrievers` is injected at construction (Dependency Inversion,
    matching every other TARA component with a substitutable
    collaborator) rather than constructed internally -- the composition
    root decides which concrete `LexicalRetriever`/`DenseRetriever`/
    `GraphRetriever` instances exist, this class only decides how to
    drive them through one plan.
    """

    def __init__(self, retrievers: Mapping[RetrieverKind, Retriever]) -> None:
        """Construct the orchestrator.

        Args:
            retrievers: Every `Retriever` implementation this
                orchestrator instance can run, keyed by the
                `RetrieverKind` it implements. Not required to cover
                every member of `RetrieverKind` -- a plan requesting a
                kind absent here is handled per this module's docstring
                (logged and skipped), not rejected at construction time,
                since which kinds a given deployment has wired up can
                reasonably vary.
        """
        self._retrievers = dict(retrievers)

    def execute(
        self, query: str, plan: RetrievalPlan, context: RepositoryContext
    ) -> list[RetrievedContext]:
        """Run every retriever `plan` specifies, per its own ordering/concurrency choice.

        Args:
            query: The raw developer query, passed through unchanged to
                every retriever `plan` names.
            plan: The already-decided execution plan. Never mutated,
                never second-guessed beyond the consistency check
                documented on the module.
            context: The repository's semantic context, passed through
                unchanged to every retriever.

        Returns:
            One `RetrievedContext` per retriever that actually ran,
            ordered by `plan.execution_order` regardless of whether
            `plan.parallel` is true or false -- real concurrent dispatch
            when parallel, but the *output* order is always the plan's
            declared order, never real-world completion order. Empty if
            `plan.execution_order` is empty, or if every requested
            retriever was unavailable or failed.

        Raises:
            OrchestrationError: If `plan.execution_order` and
                `plan.retrievers` name different retriever sets.
        """
        self._validate_plan(plan)

        if not plan.execution_order:
            return []

        if plan.parallel:
            return self._execute_parallel(query, plan, context)
        return self._execute_sequential(query, plan, context)

    @staticmethod
    def _validate_plan(plan: RetrievalPlan) -> None:
        """Reject a `plan` whose `execution_order` and `retrievers` disagree.

        Raises:
            OrchestrationError: As documented on `execute`.
        """
        if set(plan.execution_order) != set(plan.retrievers):
            raise OrchestrationError(
                f"RetrievalPlan is internally inconsistent: "
                f"execution_order={plan.execution_order!r} "
                f"names a different retriever set than retrievers={plan.retrievers!r}."
            )

    def _execute_sequential(
        self, query: str, plan: RetrievalPlan, context: RepositoryContext
    ) -> list[RetrievedContext]:
        """Run every retriever in `plan.execution_order`, one at a time, in that order."""
        results: list[RetrievedContext] = []
        for kind in plan.execution_order:
            result = self._run_one(kind, query, plan, context)
            if result is not None:
                results.append(result)
        return results

    def _execute_parallel(
        self, query: str, plan: RetrievalPlan, context: RepositoryContext
    ) -> list[RetrievedContext]:
        """Dispatch every retriever in `plan.execution_order` concurrently via a thread pool.

        Genuine concurrent dispatch (each retriever's `.retrieve()` call
        is submitted to the pool before any of them are waited on), but
        the returned list is still assembled by iterating
        `plan.execution_order` -- never by "whichever future finished
        first" -- so output order never depends on real-world thread
        scheduling.
        """
        runnable_kinds: list[RetrieverKind] = []
        for kind in plan.execution_order:
            if kind in self._retrievers:
                runnable_kinds.append(kind)
            else:
                self._log_unavailable(kind)

        if not runnable_kinds:
            return []

        results: list[RetrievedContext] = []
        with ThreadPoolExecutor(max_workers=len(runnable_kinds)) as executor:
            futures = {
                kind: executor.submit(self._retrievers[kind].retrieve, query, plan, context)
                for kind in runnable_kinds
            }
            for kind in plan.execution_order:
                future = futures.get(kind)
                if future is None:
                    continue
                try:
                    results.append(future.result())
                except RetrievalError as exc:
                    self._log_failure(kind, exc)
        return results

    def _run_one(
        self, kind: RetrieverKind, query: str, plan: RetrievalPlan, context: RepositoryContext
    ) -> RetrievedContext | None:
        """Run a single registered retriever, or return `None` if unavailable/failed."""
        retriever = self._retrievers.get(kind)
        if retriever is None:
            self._log_unavailable(kind)
            return None
        try:
            return retriever.retrieve(query, plan, context)
        except RetrievalError as exc:
            self._log_failure(kind, exc)
            return None

    @staticmethod
    def _log_unavailable(kind: RetrieverKind) -> None:
        logger.warning(
            "RetrievalOrchestrator: plan requested %s but no Retriever is registered "
            "for it; skipping.",
            kind.value,
        )

    @staticmethod
    def _log_failure(kind: RetrieverKind, exc: Exception) -> None:
        logger.warning(
            "RetrievalOrchestrator: %s raised %s; skipping its results.", kind.value, exc
        )
