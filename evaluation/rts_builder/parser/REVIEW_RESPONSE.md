# Anticipated Review: Parser Subsystem (RTS Builder, Python-only V1)

This design has not yet been externally reviewed. Following the same
discipline established for Repository Loader's actual review and the
previous Parser implementation's anticipated review, this document
self-applies that scrutiny first: each item is a comment we expect,
paired with how the design already addresses it or why it's an
accepted, documented limitation.

---

## Item 1: This replaces a previously implemented multi-language Parser — was anything lost?

**Anticipated comment.** *"An earlier milestone already implemented a
Parser subsystem supporting 8 languages via Tree-sitter, with its own
call graph and file-dependency graph. This version supports only Python
and was built from scratch. What, specifically, was given up?"*

**Response.** JavaScript/TypeScript/Java/Go/Rust/C/C++ support, and the
file-dependency-graph view distinct from the import graph (the previous
design kept both; this one has only `import_graph`, since without a
separate multi-granularity requirement there was no reason to maintain
two overlapping edge lists — see `README.md`). Reuse of
`tara.parsing`/`tara.context` was also given up, deliberately (see
Design Decisions) — this version cannot benefit from, or inherit bugs
from, changes to those modules. Gained: decorator extraction (absent
from the previous design's `CodeSymbol` model entirely), a class
inheritance graph (not present before), module-level docstring
extraction, and materially more accurate import resolution (real
Python module-path semantics vs. cross-language filename-stem
matching). This was an explicit, user-directed replacement, not a
silent regression — confirmed before implementation began.

---

## Item 2: Call and inheritance resolution are still name-based, not type-aware

**Anticipated comment.** *"Same concern as before: `w.method()` is
resolved by looking up the bare name `method` across the whole
repository. Two unrelated classes each defining a same-named method
make every call to either unresolvable. Same for inheritance: two
classes both named `Base` make every subclass of either unresolvable.
Is that acceptable?"*

**Response.** Yes, for the same reason given previously: true
type-aware resolution needs a real type checker (e.g. running mypy or a
language-server backend), which is out of scope for a standard-library
`ast`-based structural parse. The alternative — guessing, e.g. "pick the
match in the same file if one exists" — produces silently wrong edges,
which is worse for anything built on top of this graph later than a
missing edge. Being Python-only did let us improve precision
*elsewhere* (import resolution, via real module-path semantics — see
Item 3) without being able to close this particular gap, since the
gap is fundamentally about needing type information `ast` alone
doesn't carry.

---

## Item 3: How much better is the new import resolution, really, and where does it still fail?

**Anticipated comment.** *"README.md claims real Python module-path
semantics are 'meaningfully more accurate.' What's actually verified,
and what's still unhandled?"*

**Response.** Verified by test: absolute imports (`from pkg.base import
Animal`), and relative imports at `level=1` both as a bare `from .
import a` (submodule-name resolution) and as `from .a import value`
(direct dotted-module resolution) — see
`test_parse_repository_resolves_relative_imports`. **Not** verified:
`level >= 2` (`from .. import x`, `from ...pkg import y`) walking
multiple package levels up — the algorithm handles it (see
`_resolve_import_targets`'s `levels_up` computation) but has no
dedicated test exercising `level=2` or higher. Also unhandled by
design, not by oversight: `sys.path` manipulation, namespace packages
without `__init__.py`, and any import whose real target lives outside
the parsed repository subtree (e.g. an editable install of a sibling
package) — all correctly fall through to "unresolved," which is the
intended, safe behavior (no edge, not a wrong edge), but worth stating
plainly rather than implying full Python import-system fidelity.

---

## Item 4: No per-repository lock, again

**Anticipated comment.** *(Same structural question as the previous
milestone's review.)* *"Repository Loader locks every git operation.
This pipeline doesn't lock anything. Consistent?"*

**Response.** Same answer as before, restated because the reasoning
still holds under this redesign: this pipeline only reads
`repository.local_path` (the walk is filesystem-only; the one git
operation, reading HEAD for the commit-consistency check, is also a
read) and its only write (the cache entry) is already atomic. Two
workers racing to parse the same `(repository_id, commit_sha)` waste
CPU, never corrupt anything. Not re-litigated further here; see the
previous milestone's `REVIEW_RESPONSE.md` Item 3 for the full argument,
which applies unchanged to this redesign.

---

## Item 5: Decorators are stored as source text — is that actually useful, or just a checkbox?

**Anticipated comment.** *"`decorators: list[str]` stores unparsed
source expressions like `'functools.wraps(helper)'`. Nothing resolves
what a decorator actually *does* (e.g. that `@staticmethod` changes
`is_method`'s practical meaning, or that a decorator might wrap the
function into something with a different call signature entirely). Is
storing the text alone meaningful?"*

**Response.** Meaningful as *structure*, not as *behavior* — consistent
with this milestone's stated scope (structural extraction, explicitly
not feature extraction, which is a later, excluded milestone). A
downstream consumer can pattern-match on decorator text for coarse
signals (e.g. "is this route decorated with `@app.route`," "is this
test decorated with `@pytest.fixture`") without this milestone claiming
to understand what any decorator semantically does — that would require
executing or type-checking the code, well beyond an AST walk. This is
explicitly the same boundary requirement 4's "Extract... Decorators"
implies: capture them, don't interpret them.

---

## Item 6: `RepositoryModel.imports` and `import_graph` overlap — same question as before

**Anticipated comment.** *"Isn't `import_graph` just `imports` with
unresolved entries filtered out?"*

**Response.** Similar answer to the previous milestone's equivalent
question, adapted: `imports` is one entry per statement, exactly as
written, always (including external/unresolvable ones, with full
detail: `module`, `imported_names`, `level`). `import_graph` is a
distinct, coarser view: one edge per *resolved* file pair, produced by
`graph_builder`'s module-path resolution — not by filtering `imports`
after the fact. Unlike the previous milestone, there is no third,
separate "file dependency graph" this time (that distinction was
dropped — see Item 1); `import_graph` is now the only resolved,
file-level view, and it is deliberately still not the same object as
`imports`, for the same reason as before: different granularity, and
`imports` records information (unresolved/external targets, `level`)
that a pure edge list cannot.

---

## Summary

| # | Concern | Status |
|---|---|---|
| 1 | Multi-language support and the file-dependency-graph view were dropped | Confirmed, user-directed replacement — gains (decorators, inheritance, better import resolution) stated explicitly |
| 2 | Call/inheritance resolution is name-based, ambiguity silently skipped | Accepted, documented tradeoff (unchanged rationale from the previous milestone) |
| 3 | Import resolution's real coverage (verified vs. assumed) | `level=1` relative and absolute imports tested; `level>=2` and `sys.path`-dependent imports untested/unhandled by design |
| 4 | No per-repository lock | Same reasoning as the previous milestone's review, still applicable |
| 5 | Decorators stored as text only, no semantic interpretation | By design — structural extraction, not feature extraction |
| 6 | `imports` vs. `import_graph` overlap | Different granularity/claims, not redundant |

No code outside `evaluation/rts_builder/parser/` was modified.
Repository Loader (`evaluation/rts_builder/repository_loader.py`,
`config.py`, `exceptions.py`, `models.py`) was not touched.
`tests/rts_builder/parser/` has 26 tests, all passing alongside the
full existing project suite.
