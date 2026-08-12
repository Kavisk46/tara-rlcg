"""Unit tests for `evaluation.rts_builder.pilot.environment.collect_environment_info`."""
from __future__ import annotations

from evaluation.rts_builder.pilot.environment import collect_environment_info


def test_collects_python_version_and_platform() -> None:
    info = collect_environment_info()
    assert info.python_version
    assert info.platform


def test_collects_versions_for_every_tracked_package() -> None:
    info = collect_environment_info()
    for package_name in ("pydantic", "pyarrow", "matplotlib", "gitpython"):
        assert package_name in info.package_versions
        assert info.package_versions[package_name] != ""
