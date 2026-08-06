"""Verifies `config.yaml`'s frozen protocols stay in sync with their code-level source of truth.

Prevents the exact failure mode a "freeze this protocol" review comment
is meant to guard against: documentation describing a contract the code
doesn't (or no longer does) honor.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from evaluation.rts_builder.retrieval_executor import latency_protocol
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings

_CONFIG_YAML_PATH = Path(__file__).parents[3] / "evaluation" / "rts_builder" / "retrieval_executor" / "config.yaml"


def _load_config_yaml() -> dict:
    return yaml.safe_load(_CONFIG_YAML_PATH.read_text(encoding="utf-8"))


def test_config_yaml_exists_and_parses() -> None:
    assert _CONFIG_YAML_PATH.exists()
    payload = _load_config_yaml()
    assert "hybrid_score_normalization" in payload
    assert "latency_protocol" in payload


def test_config_yaml_latency_include_list_matches_latency_protocol_py() -> None:
    payload = _load_config_yaml()
    assert tuple(payload["latency_protocol"]["include"]) == latency_protocol.LATENCY_INCLUDED_OPERATIONS


def test_config_yaml_latency_exclude_list_matches_latency_protocol_py() -> None:
    payload = _load_config_yaml()
    assert tuple(payload["latency_protocol"]["exclude"]) == latency_protocol.LATENCY_EXCLUDED_OPERATIONS


def test_config_yaml_latency_boundaries_match_latency_protocol_py() -> None:
    payload = _load_config_yaml()
    assert payload["latency_protocol"]["starts"] == latency_protocol.LATENCY_STARTS
    assert payload["latency_protocol"]["ends"] == latency_protocol.LATENCY_ENDS


def test_config_yaml_hybrid_default_weights_match_settings_defaults() -> None:
    payload = _load_config_yaml()
    defaults = RetrievalExecutorSettings()
    weights = payload["hybrid_score_normalization"]["default_weights"]

    assert weights["alpha_lexical"] == defaults.hybrid_lexical_weight
    assert weights["beta_dense"] == defaults.hybrid_dense_weight
    assert weights["gamma_graph"] == defaults.hybrid_graph_weight


def test_config_yaml_hybrid_weights_sum_to_one() -> None:
    payload = _load_config_yaml()
    weights = payload["hybrid_score_normalization"]["default_weights"]
    total = weights["alpha_lexical"] + weights["beta_dense"] + weights["gamma_graph"]
    assert abs(total - 1.0) < 1e-9
