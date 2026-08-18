"""Unit tests for `evaluation.ablations.definitions`: catalog completeness and consistency."""
from __future__ import annotations

from evaluation.ablations.definitions import ABLATION_DEFINITIONS, AblationId, AblationStatus


def test_covers_a1_through_a9_in_order() -> None:
    assert [a.ablation_id for a in ABLATION_DEFINITIONS] == list(AblationId)


def test_no_duplicate_ablation_ids() -> None:
    ids = [a.ablation_id for a in ABLATION_DEFINITIONS]
    assert len(ids) == len(set(ids))


def test_every_supported_ablation_has_at_least_one_variant() -> None:
    for ablation in ABLATION_DEFINITIONS:
        if ablation.status is AblationStatus.SUPPORTED:
            assert len(ablation.variants) >= 1, (
                f"{ablation.ablation_id} is SUPPORTED but has no variants"
            )


def test_every_unsupported_ablation_has_prerequisite_notes() -> None:
    for ablation in ABLATION_DEFINITIONS:
        if ablation.status is AblationStatus.UNSUPPORTED_TBD:
            assert ablation.prerequisite_notes, (
                f"{ablation.ablation_id} is UNSUPPORTED_TBD but has no prerequisite_notes"
            )


def test_unsupported_ablation_has_no_variants() -> None:
    for ablation in ABLATION_DEFINITIONS:
        if ablation.status is AblationStatus.UNSUPPORTED_TBD:
            assert ablation.variants == []


def test_a6_is_the_only_fully_unsupported_ablation() -> None:
    unsupported = [
        a.ablation_id for a in ABLATION_DEFINITIONS if a.status is AblationStatus.UNSUPPORTED_TBD
    ]
    assert unsupported == [AblationId.A6]


def test_every_variant_has_a_non_empty_mechanism_string() -> None:
    for ablation in ABLATION_DEFINITIONS:
        for variant in ablation.variants:
            assert variant.mechanism.strip() != ""


def test_a7_has_exactly_five_swept_threshold_variants() -> None:
    a7 = next(a for a in ABLATION_DEFINITIONS if a.ablation_id == AblationId.A7)
    thresholds = sorted(v.parameters["confidence_threshold"] for v in a7.variants)
    assert thresholds == [0.3, 0.4, 0.5, 0.6, 0.7]


def test_a9_has_baseline_and_with_classification_variants() -> None:
    a9 = next(a for a in ABLATION_DEFINITIONS if a.ablation_id == AblationId.A9)
    mechanisms = {v.mechanism for v in a9.variants}
    assert mechanisms == {
        "tara.generation.prompt.PromptTemplate.BASELINE",
        "tara.generation.prompt.PromptTemplate.WITH_TASK_CLASSIFICATION",
    }


def test_a8_declares_embedding_model_name_as_a_controlled_variable_exception() -> None:
    a8 = next(a for a in ABLATION_DEFINITIONS if a.ablation_id == AblationId.A8)
    assert a8.controlled_variable_exceptions == ["embedding_model_name"]


def test_only_a8_declares_any_controlled_variable_exception() -> None:
    # A2-A7 change a Router/context/policy, never a repository, query set, LLM, token budget,
    # or embedding model -- so none of them should need a controlled-variable exception.
    for ablation in ABLATION_DEFINITIONS:
        if ablation.ablation_id is AblationId.A8:
            continue
        assert ablation.controlled_variable_exceptions == []


def test_a8_variant_ids_are_distinct_and_do_not_include_the_tbd_third_model() -> None:
    a8 = next(a for a in ABLATION_DEFINITIONS if a.ablation_id == AblationId.A8)
    variant_ids = [v.variant_id for v in a8.variants]
    assert len(variant_ids) == len(set(variant_ids))
    assert len(a8.variants) == 2
    assert a8.prerequisite_notes is not None
    assert "jina" in a8.prerequisite_notes.lower()
