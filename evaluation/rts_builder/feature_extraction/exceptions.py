"""Exception hierarchy for the RTS Builder's Feature Extraction subsystem.

Rooted in ``tara.core.exceptions.TaraError``, matching the convention
already established by ``evaluation.rts_builder.exceptions`` and
``evaluation.rts_builder.parser.exceptions``.
"""
from __future__ import annotations

from tara.core.exceptions import TaraError


class FeatureExtractionError(TaraError):
    """Base class for all exceptions raised by the Feature Extraction subsystem."""


class InvalidQueryError(FeatureExtractionError):
    """Raised when the developer query passed to `FeatureExtractor.extract` is not a string.

    An empty string (`""`) is valid input (it yields all-zero/False
    query features, not an error) -- this is reserved for `None` or a
    non-`str` value, which indicate a caller bug, not a legitimately
    empty query.
    """
