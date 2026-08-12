"""Exception hierarchy for the RTS Builder's Pilot subsystem.

Rooted in ``tara.core.exceptions.TaraError``, matching the convention
already established by every prior RTS Builder milestone's own
exceptions module.
"""
from __future__ import annotations

from tara.core.exceptions import TaraError


class PilotError(TaraError):
    """Base class for all exceptions raised by the Pilot subsystem."""


class PilotAssemblyError(PilotError):
    """Raised when the frozen Dataset Builder's own output cannot be read or reassembled.

    Distinct from `PilotValidationError`: this means the pilot could
    not even build a dataset to validate (e.g. Dataset Builder's
    grouped-format export was disabled, or its output is missing/
    corrupt) -- an infrastructure failure, not a data-quality finding.
    """


class PilotValidationError(PilotError):
    """Raised when the assembled dataset fails one of the Success Criteria's blocking checks.

    Carries the full `ValidationReport` (see `models.py`) so a caller
    can inspect exactly which check(s) failed rather than only a
    message. Only raised when `PilotSettings.fail_on_validation_error`
    is `True` (the default) -- see `runner.py`.
    """

    def __init__(self, message: str, report: object) -> None:
        super().__init__(message)
        self.report = report
