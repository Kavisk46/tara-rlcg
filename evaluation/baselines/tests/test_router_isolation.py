"""The literal "router spy" proof this milestone's instructions require.

For every baseline B0-B4, run the full `BaselineRunner.run()` pipeline
(plan -> retrieve -> fuse -> generate) with `AdaptiveRouter.route` and
`HeuristicTaskClassifier.classify` replaced by spies, and assert each
spy's call count is exactly 0. This is a stronger, more literal check
than `test_definitions.test_baselines_ignore_classification_unlike_default_policies`
(which proves isolation *behaviorally*, by observing a fixed plan never
varies with classification): this test proves isolation *structurally*,
by observing the adaptive router and the classifier are never even
invoked, regardless of what they would have decided.

No baseline architecture change was needed to make this seam available:
`evaluation.baselines.plan_builder.build_fixed_plan` never imports
`AdaptiveRouter`/`HeuristicTaskClassifier` in the first place, so
`unittest.mock.patch.object` on the real classes is sufficient -- there
is no dependency-injection point to add, because there is no dependency
to inject a fake in place of.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from evaluation.baselines.definitions import BASELINE_DEFINITIONS, BaselineDefinition, BaselineId
from evaluation.baselines.runner import BaselineRunner
from evaluation.baselines.tests.conftest import make_orchestrator
from tara.classification.classifier import HeuristicTaskClassifier
from tara.classification.models import TaskClassification
from tara.context.models import RepositoryContext
from tara.core.types import RetrieverKind
from tara.generation.fake_provider import FakeCodeGenerator
from tara.routing.router import AdaptiveRouter

_ALL_KINDS = (RetrieverKind.LEXICAL, RetrieverKind.DENSE, RetrieverKind.GRAPH)


def _definition(baseline_id: BaselineId) -> BaselineDefinition:
    return next(b for b in BASELINE_DEFINITIONS if b.baseline_id is baseline_id)


@pytest.mark.parametrize(
    "baseline_id", [BaselineId.B0, BaselineId.B1, BaselineId.B2, BaselineId.B3, BaselineId.B4]
)
def test_baseline_run_never_calls_adaptive_router_route(
    baseline_id: BaselineId,
    rich_context: RepositoryContext,
    search_classification: TaskClassification,
) -> None:
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    runner = BaselineRunner(orchestrator, FakeCodeGenerator())

    with patch.object(AdaptiveRouter, "route", autospec=True) as router_spy:
        runner.run(
            _definition(baseline_id), "how does greet work?", search_classification, rich_context
        )

    assert router_spy.call_count == 0


@pytest.mark.parametrize(
    "baseline_id", [BaselineId.B0, BaselineId.B1, BaselineId.B2, BaselineId.B3, BaselineId.B4]
)
def test_baseline_run_never_calls_the_task_classifier(
    baseline_id: BaselineId,
    rich_context: RepositoryContext,
    search_classification: TaskClassification,
) -> None:
    """`classification` is always supplied by the caller (computed once per query, per
    `BaselineRunner.run`'s own contract) -- a baseline must never classify the query itself."""
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    runner = BaselineRunner(orchestrator, FakeCodeGenerator())

    with patch.object(HeuristicTaskClassifier, "classify", autospec=True) as classifier_spy:
        runner.run(
            _definition(baseline_id), "how does greet work?", search_classification, rich_context
        )

    assert classifier_spy.call_count == 0


def test_adaptive_router_route_is_never_called_across_the_entire_baseline_suite(
    rich_context: RepositoryContext, search_classification: TaskClassification
) -> None:
    """A single spy shared across every baseline in one run, for an even stronger guarantee
    than one baseline at a time: nothing in a full B0-B4 sweep ever touches the router."""
    orchestrator, _fakes = make_orchestrator(*_ALL_KINDS)
    runner = BaselineRunner(orchestrator, FakeCodeGenerator())

    with patch.object(AdaptiveRouter, "route", autospec=True) as router_spy:
        for baseline in BASELINE_DEFINITIONS:
            runner.run(baseline, "q", search_classification, rich_context)

    assert router_spy.call_count == 0
