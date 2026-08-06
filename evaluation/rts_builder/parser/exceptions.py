"""Exception hierarchy for the RTS Builder's Parser subsystem (Python-only V1).

Rooted in ``tara.core.exceptions.TaraError``, matching the convention
already established by ``evaluation.rts_builder.exceptions``, so a
caller working across the whole RTS Builder can catch ``TaraError`` for
"anything either milestone can throw," while still being able to catch
a Parser failure specifically.
"""
from __future__ import annotations

from tara.core.exceptions import TaraError


class ParserSubsystemError(TaraError):
    """Base class for all exceptions raised by the Parser subsystem."""


class RepositoryStateError(ParserSubsystemError):
    """Raised when the ``Repository`` handed to the Parser isn't in the state it claims.

    Covers two cases: ``local_path`` doesn't exist on disk (the
    repository was never loaded, or its clone was removed after
    loading), and ``local_path``'s checked-out commit no longer matches
    ``Repository.commit_sha`` (it was mutated, e.g. by a concurrent
    ``RepositoryLoader.load_repository()`` call for a different commit,
    between the Repository Loader and Parser stages).
    """


class PythonFileParseError(ParserSubsystemError):
    """Raised internally when a single Python file cannot be parsed.

    Caught by ``PythonRepositoryParser.parse`` and converted into a
    recorded ``ParseError`` entry rather than propagated: a single
    unparsable file (a syntax error, an unreadable encoding) must never
    abort parsing the rest of the repository. This type exists so that
    conversion has one well-typed signal to catch, instead of catching
    ``SyntaxError`` and ``UnicodeDecodeError`` as two unrelated cases at
    the call site.
    """


class GraphBuildError(ParserSubsystemError):
    """Raised when import/call/inheritance graph construction fails unexpectedly.

    Individual unresolved or ambiguous edges are not errors (see
    ``REVIEW_RESPONSE.md``); this is reserved for failures in the
    resolution process itself.
    """


class ParserCacheError(ParserSubsystemError):
    """Raised when a cached ``RepositoryModel`` cannot be read or written.

    A corrupt or unreadable cache entry is treated as a cache miss
    (logged, not raised) so a damaged cache file can never block the
    pipeline; this is reserved for failures writing a *new* cache entry,
    which should surface rather than be silently swallowed.
    """
