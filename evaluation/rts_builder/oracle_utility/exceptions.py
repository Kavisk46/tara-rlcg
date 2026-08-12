"""Exception hierarchy for the RTS Builder's Oracle Utility subsystem.

Rooted in ``tara.core.exceptions.TaraError``, matching the convention
already established by every prior RTS Builder milestone's own
exceptions module.
"""
from __future__ import annotations

from tara.core.exceptions import TaraError


class OracleUtilityError(TaraError):
    """Base class for all exceptions raised by the Oracle Utility subsystem."""


class MismatchedInputsError(OracleUtilityError):
    """Raised when a `RelevanceJudgment` was not authored for the same query as a `RetrievalExecutionResult`.

    Compares `repository_id`, `commit_sha`, and `query_text` on both
    inputs. A mismatch indicates a caller bug (pairing ground-truth
    relevance judgments with the wrong query's retrieval results) --
    the same class of cross-milestone consistency bug
    `RetrievalExecutor.execute_all`'s own `MismatchedInputsError` and
    `ParserPipeline`'s commit-verification check exist to catch one
    stage earlier.
    """
