"""Exception hierarchy for the RTS Builder's Retrieval Executor subsystem.

Rooted in ``tara.core.exceptions.TaraError``, matching the convention
already established by every prior RTS Builder milestone's own
exceptions module.
"""
from __future__ import annotations

from tara.core.exceptions import TaraError


class RetrievalExecutorError(TaraError):
    """Base class for all exceptions raised by the Retrieval Executor subsystem."""


class InvalidQueryError(RetrievalExecutorError):
    """Raised when the developer query passed to `RetrievalExecutor.execute_all` is not a string.

    An empty string (`""`) is valid input (every strategy degrades to a
    well-defined, empty or arbitrary-but-deterministic result -- see
    `README.md`'s Failure Modes); this is reserved for `None` or a
    non-`str` value.
    """


class MismatchedInputsError(RetrievalExecutorError):
    """Raised when `feature_vector` was not computed from `repository_model`.

    Compares `repository_id` and `commit_sha` on both inputs. A mismatch
    indicates a caller bug (passing a `FeatureVector` for a different
    repository or an earlier/later commit of the same one) -- exactly
    the kind of cross-milestone consistency bug `ParserPipeline`'s own
    commit-verification check exists to catch one stage earlier.
    """
