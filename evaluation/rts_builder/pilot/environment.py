"""Collects the execution-environment facts the Reproducibility section asks to be recorded.

Package versions are read via `importlib.metadata` (the installed
distribution's actual version, not whatever a `requirements.txt`/
`pyproject.toml` pin says) -- what mattered for a specific pilot run is
what was actually installed when it ran, which can legitimately drift
from the pin (a looser `>=` constraint, a local override) without
either being wrong.
"""
from __future__ import annotations

import platform
import sys
from importlib.metadata import PackageNotFoundError, version

from evaluation.rts_builder.pilot.models import EnvironmentInfo

# Packages whose version could materially change pilot output: pydantic (model
# validation/serialization), pyarrow (Parquet), matplotlib (figures), gitpython (git_commit
# resolution). numpy/pandas are deliberately absent -- neither is a direct dependency of this
# subsystem (see figures.py's Pearson correlation, computed without numpy).
_TRACKED_PACKAGES = ("pydantic", "pyarrow", "matplotlib", "gitpython")


def collect_environment_info() -> EnvironmentInfo:
    """Return the current interpreter/OS/package-version snapshot."""
    package_versions: dict[str, str] = {}
    for package_name in _TRACKED_PACKAGES:
        try:
            package_versions[package_name] = version(package_name)
        except PackageNotFoundError:
            package_versions[package_name] = "not installed"

    return EnvironmentInfo(
        python_version=sys.version,
        platform=platform.platform(),
        package_versions=package_versions,
    )
