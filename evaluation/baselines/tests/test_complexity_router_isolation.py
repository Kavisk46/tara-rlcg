"""The literal "router spy" proof for COMPLEXITY_ROUTER, mirroring
`test_router_isolation.py`'s proof for B0-B4 exactly.

For the COMPLEXITY_ROUTER baseline, run the full
`BaselineRunner.run_complexity_baseline()` pipeline (plan -> retrieve ->
fuse -> generate) with `AdaptiveRouter.route` and
`HeuristicTaskClassifier.classify` replaced by spies, and assert each
spy's call count is exactly 0 -- structural proof that this baseline
never touches TARA's real adaptive router or task classifier, on top of
the behavioral proof in `test_complexity_router.py`
(`test_plan_is_identical_across_wildly_different_classifications`).

Also covers: the combined B0-B4 + COMPLEXITY_ROUTER sweep still isolates
the router; `evaluation.ablations.validation.validate_controlled_variables`
treats a TARA-adaptive-vs-COMPLEXITY_ROUTER comparison as a legitimate,
router-only variant difference (i.e. not a controlled-variable mismatch).
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from evaluation.ablations.validation import validate_controlled_variables
from evaluation.baselines.complexity_router import BASELINE_ID as COMPLEXITY_BASELINE_ID
from evaluation.baselines.definitions import BASELINE_DEFINITIONS
from evaluation.baselines.runner import BaselineRunner
from evaluation.baselines.tests.conftest import make_orchestrator
from evaluation.harness.models import ExperimentConfig
from tara.classification.classifier import HeuristicTaskClassifier
from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.core.types import RetrieverKind
from tara.generation.fake_provider import FakeCodeGenerator
from tara.routing.router import AdaptiveRouter

_ALL_KINDS = (RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH)
_MULTI_CLAUSE_QUERY = (
    "explain the parser and trace the call graph and check the symbol index"
)


# ============================================================================
# Structural isolation: AdaptiveRouter / HeuristicTaskClassifier are never called
# ============================================================================


def test_complexity_baseline_run_never_calls_adaptive_router_route(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    runner = BaselineRunner(orchestrator, FakeCodeGenerator())

    with patch.object(AdaptiveRouter, "route", autospec=True) as router_spy:
        runner.run_complexity_baseline(_MULTI_CLAUSE_QUERY, search_classification, rich_context)

    assert router_spy.call_count == 0


def test_complexity_baseline_run_never_calls_the_task_classifier(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    """`classification` is always supplied by the caller, exactly like every B0-B4 baseline --
    COMPLEXITY_ROUTER must never classify the query itself, and does not need to: it does not
    read `classification` to select a strategy at all (see `test_complexity_router.py`)."""
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    runner = BaselineRunner(orchestrator, FakeCodeGenerator())

    with patch.object(HeuristicTaskClassifier, "classify", autospec=True) as classifier_spy:
        runner.run_complexity_baseline(_MULTI_CLAUSE_QUERY, search_classification, rich_context)

    assert classifier_spy.call_count == 0


def test_adaptive_router_route_is_never_called_across_b0_through_b4_plus_complexity_router(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    """A single spy shared across the full B0-B4 sweep plus COMPLEXITY_ROUTER, extending
    `test_router_isolation.test_adaptive_router_route_is_never_called_across_the_entire_baseline_suite`
    to cover this new baseline in the same combined guarantee."""
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    runner = BaselineRunner(orchestrator, FakeCodeGenerator())

    with patch.object(AdaptiveRouter, "route", autospec=True) as router_spy:
        for baseline in BASELINE_DEFINITIONS:
            runner.run(baseline, "q", search_classification, rich_context)
        runner.run_complexity_baseline("q", search_classification, rich_context)

    assert router_spy.call_count == 0


# ============================================================================
# End-to-end: the baseline actually produces a plan, retrieves, fuses, and generates
# ============================================================================


def test_complexity_baseline_run_produces_a_plan_and_generated_code(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, fakes = make_orchestrator(*_ALL_KINDS)
    runner = BaselineRunner(orchestrator, FakeCodeGenerator())

    result = runner.run_complexity_baseline(
        _MULTI_CLAUSE_QUERY, search_classification, rich_context
    )

    assert result.baseline_id == COMPLEXITY_BASELINE_ID
    assert result.plan is not None
    assert result.generated_code is not None
    # _MULTI_CLAUSE_QUERY selects FULL_PIPELINE; confirm the real, registered retrievers for
    # every retriever kind the plan named were actually invoked (proving the plan was executed
    # by the real RetrievalOrchestrator, not merely built and discarded).
    for kind in result.plan.retrievers:
        assert fakes[kind].call_count == 1


def test_repeated_runs_of_the_same_query_are_deterministic(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    runner = BaselineRunner(orchestrator, FakeCodeGenerator())

    result_a = runner.run_complexity_baseline(
        _MULTI_CLAUSE_QUERY, search_classification, rich_context
    )
    result_b = runner.run_complexity_baseline(
        _MULTI_CLAUSE_QUERY, search_classification, rich_context
    )

    assert result_a.plan.strategy == result_b.plan.strategy
    assert result_a.plan.retrievers == result_b.plan.retrievers


# ============================================================================
# Controlled-variable validation: COMPLEXITY_ROUTER is a router-only variant
# ============================================================================


def _make_config(**overrides: object) -> ExperimentConfig:
    defaults: dict[str, object] = dict(
        experiment_id="exp-1",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        variant_ids=["TARA"],
        generation_model="fake-model",
        token_budget=4000,
        embedding_model_name="BAAI/bge-small-en-v1.5",
        prompt_template="baseline",
        k_values=[5, 10],
        repository_manifest_path="manifest.json",
        queries_path="queries.jsonl",
    )
    defaults.update(overrides)
    return ExperimentConfig(**defaults)  # type: ignore[arg-type]


def test_complexity_router_vs_tara_adaptive_passes_controlled_variable_validation() -> None:
    """A comparison between TARA-proper and COMPLEXITY_ROUTER, identical in every controlled
    field (repository, queries, generation model, token budget, embedding model) and differing
    only in `variant_ids`, must be accepted by `validate_controlled_variables` -- proving this
    baseline is treated as a router-only variant, exactly like an ablation or another baseline,
    never as a change to a controlled experimental variable."""
    tara_config = _make_config(experiment_id="exp-tara", variant_ids=["TARA"])
    complexity_config = _make_config(
        experiment_id="exp-complexity", variant_ids=[COMPLEXITY_BASELINE_ID]
    )

    validate_controlled_variables([tara_config, complexity_config])  # must not raise


def test_complexity_router_with_a_genuinely_different_repository_still_fails_validation() -> None:
    """Sanity check on the test above: the validator is not simply permissive by construction --
    it still correctly rejects a COMPLEXITY_ROUTER comparison that *does* vary a controlled
    field, exactly as it would for any other variant."""
    from evaluation.ablations.validation import ControlledVariableMismatchError

    tara_config = _make_config(
        experiment_id="exp-tara", variant_ids=["TARA"], repository_manifest_path="manifest-a.json"
    )
    complexity_config = _make_config(
        experiment_id="exp-complexity",
        variant_ids=[COMPLEXITY_BASELINE_ID],
        repository_manifest_path="manifest-b.json",
    )

    try:
        validate_controlled_variables([tara_config, complexity_config])
    except ControlledVariableMismatchError:
        pass
    else:
        raise AssertionError("expected ControlledVariableMismatchError for a repository mismatch")
