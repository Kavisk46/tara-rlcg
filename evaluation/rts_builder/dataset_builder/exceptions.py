"""Exception hierarchy for the RTS Builder's Dataset Builder subsystem.

Rooted in ``tara.core.exceptions.TaraError``, matching the convention
already established by every prior RTS Builder milestone's own
exceptions module.
"""
from __future__ import annotations

from tara.core.exceptions import TaraError


class DatasetBuilderError(TaraError):
    """Base class for all exceptions raised by the Dataset Builder subsystem."""


class ManifestError(DatasetBuilderError):
    """Raised when a repository manifest or queries file is missing, malformed, or fails validation."""


class CheckpointError(DatasetBuilderError):
    """Raised when the checkpoint store cannot be read or written.

    A malformed *individual line* in an existing checkpoint file is not
    an error (see `checkpoint.py` -- skipped and logged, the same
    crash-resilience convention every prior milestone's own cache/
    checkpoint reader uses); this is reserved for failures opening or
    writing the checkpoint file itself.
    """


class DatasetWriteError(DatasetBuilderError):
    """Raised when a dataset export writer fails to write a row or close its output."""
