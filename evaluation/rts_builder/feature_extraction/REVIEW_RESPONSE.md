# Anticipated Review: Feature Extraction Subsystem (RTS Builder, Milestone 4)

Following the discipline established for Repository Loader's actual
review and both Parser milestones' anticipated reviews, this document
self-applies that scrutiny before an external one happens.

---

## Item 1: This diverges from `docs/DATASET_BUILDER_SPEC.md` §6 — was that checked, or just assumed?

**Anticipated comment.** *"The project already has a Feature Extraction
specification with named features (`repo_symbol_count`, `task_type`,
`graph_is_populated`, a per-strategy `Resource` group tied to
`RoutingStrategy`...). This implementation uses almost none of those
names or that Task/Resource structure. Was the existing spec
consulted, or overridden without reconciliation?"*

**Response.** Consulted directly (`docs/DATASET_BUILDER_SPEC.md` §6 was
read before implementation began) and explicitly not followed, for a
stated reason, not an oversight: that table assumes a `RepositoryContext`
input (from `tara.context`, multi-language, embedding-capable) and a
completed Task Annotation stage feeding a `Task` feature group — neither
holds in this project's actual, evolved pipeline (Repository Loader and
Parser were rebuilt self-contained and Python-only, producing
`RepositoryModel`; Task Classification/Annotation is unimplemented and
explicitly excluded from this milestone). This milestone implements the
concrete, narrower specification given directly for it. The divergence
is stated in `README.md`'s dedicated section rather than left for a
reader to discover by comparing documents themselves.

---

## Item 2: Is reusing `tara.classification.heuristics` actually not the Task Classifier?

**Anticipated comment.** *"`query_features.py` imports
`looks_like_identifier` and `tokenize` from
`tara.classification.heuristics` — the same module the (excluded) Task
Classifier is built on. Keyword-indicator sets like `_BUG_KEYWORDS` look
like the beginning of a rule-based classifier. Where exactly is the
line?"*

**Response.** The line is: no `TaskType` is ever assigned, no
confidence is scored, no rule priority/tie-break logic runs, and no
`TaskClassification` object is produced. `tokenize` and
`looks_like_identifier` are pure, stateless predicates over a single
token — `tara.retrieval.utils.tokenize_for_search` already reuses the
same two functions for a third, unrelated purpose (BM25 indexing), which
is the precedent this follows, not a new pattern invented to route
around the exclusion. The four keyword sets (`_QUESTION_KEYWORDS` etc.)
produce four independent booleans, not a `TaskType` enum member — there
is no decision, priority order, or classification output anywhere in
this module. If a future milestone needs actual task classification, it
would still need the real `HeuristicTaskClassifier`; nothing here
substitutes for it or could be mistaken for its output (`FeatureVector`
has no `task_type` field).

---

## Item 3: `comment_coverage_ratio` breaks the "receives RepositoryModel + Developer Query" contract

**Anticipated comment.** *"The spec says the Feature Extractor
*receives* `RepositoryModel` and a query. `comment_coverage_ratio`
re-reads files from disk via `RepositoryModel.root_path` — that's a
third, implicit input (the filesystem) the spec doesn't mention. Is
that acceptable?"*

**Response.** Flagged directly rather than left implicit: it is the
*one* feature in this subsystem with this property, and the reason is
structural, not a design shortcut — Python's `ast` module (which Parser
V1 is built on, frozen, and out of scope to modify) discards comments
entirely during parsing, so no comment token, count, or location exists
anywhere in `RepositoryModel`'s data for this or any feature to read.
There is no way to compute a genuine "comment coverage" signal from
`RepositoryModel` alone; the only choices were: don't implement this
feature at all (but it's an explicit, named requirement), fabricate a
placeholder value (worse — silently wrong data in a "deterministic
outputs" subsystem), or compute it honestly via the one remaining real
source of truth, the file on disk, accepting the dependency and
documenting it. The third option was chosen. It degrades to `0.0`
(logged, never raised) if the source is inaccessible or
`enable_comment_coverage=False`, so this dependency is opt-out and
fails soft rather than becoming a hard requirement on filesystem
availability for the rest of the vector.

---

## Item 4: Name-based, heuristic weights everywhere — is any of this validated?

**Anticipated comment.** *"`query_complexity`'s weights, the
`chars_per_token_estimate` ratio, and the size-category thresholds are
all hand-picked defaults. Has any of this been calibrated against real
queries or repositories?"*

**Response.** No — and `README.md` and this document both say so
explicitly rather than presenting these as validated. This mirrors
`docs/DATASET_BUILDER_SPEC.md`'s own established discipline of marking
an untested constant (its Utility formula's `lambda = 0.1`) as "a
proposed default requiring pilot calibration," not a settled value.
Every one of these constants is a `FeatureExtractionSettings` field,
specifically so a future pilot/calibration pass (the same kind
`DATASET_BUILDER_SPEC.md` already anticipates elsewhere in the
pipeline) can retune them without touching any compute module —
`query_features.py`, `resource_features.py`, etc. contain no hardcoded
literals for anything that plausibly needs recalibration.

---

## Item 5: `dominant_language` is a near-constant — why include a feature with almost no information content?

**Anticipated comment.** *"Given Parser V1 only ever produces Python
files, `dominant_language` is `PYTHON` for every non-empty repository
in the dataset. A feature with one effective value contributes nothing
to a learned model. Why keep it?"*

**Response.** Correct that it's currently near-zero-information, and
`README.md` says exactly that rather than implying otherwise. Kept for
two reasons: it's an explicitly named requirement item ("Dominant
language" under Repository Features), and it's forward-compatible —
when a future Parser version supports more languages again (the
milestone before this one already did, before being narrowed to
Python-only V1 per direction), this feature starts carrying real signal
without any schema change to `RepositoryFeatures` or `FeatureVector`,
and without needing every already-computed feature vector in an
existing dataset to be regenerated under a new schema.

---

## Item 6: Connected-components/avg-degree collapse three different edge semantics into one graph — is that principled or convenient?

**Anticipated comment.** *"Import edges, call edges, and inheritance
edges mean structurally different things (module dependency vs.
control flow vs. type hierarchy). Merging all three into one undirected
graph for `connected_components`/`avg_degree` treats them as
interchangeable. Is that defensible?"*

**Response.** Defensible as a specific, narrow claim — "how structurally
interconnected is this repository's file set, by any relationship
type" — not as a claim that the three relationships are semantically
equivalent. The three *typed* densities
(`import_density`/`call_density`/`inheritance_density`) are kept
separate specifically because their semantics differ; only the two
connectivity-shape metrics the specification asks for
(`connected_components`, `avg_degree`) are computed over the union,
because a repository's overall connectivity shape is exactly the kind
of signal that benefits from combining every available structural
relationship rather than picking one arbitrarily. If a future milestone
needs per-relationship-type connectivity instead, `graph_features.py`'s
`_build_combined_file_graph` would need three separate graphs instead
of one merged one — a small, well-contained change, not a redesign.

---

## Item 7: No test against a repository with `level >= 2` relative imports, deep nesting, or multiple languages once V2 exists

**Anticipated comment.** *(Consistent with prior milestones' honest
coverage gaps.)* *"Test coverage is against one representative
repository plus fabricated edge cases. Was anything about `RepositoryModel`
shape assumed but not verified?"*

**Response.** `module_count`'s top-level-grouping logic was verified
only against a two-level structure (`app.py` + `pkg/`); untested against
deeper nesting (`pkg/sub/subsub/mod.py`, still correctly grouped under
`"pkg"` by construction — the logic only ever looks at the first path
segment — but not exercised by a dedicated test). `graph_features.py`'s
combined-graph construction was verified with import, call, and
inheritance edges all present in the same small repository, but not
with a repository large enough to exercise multiple disconnected
components beyond the trivial "one isolated `__init__.py`" case already
covered. Neither is expected to be wrong given how the logic is
written, but "expected to be wrong given the logic" and "verified by a
test" are different claims, and only the fabricated-edge-case tests
(`test_resource_and_structural_features.py`) closed gaps of the second
kind for `resource`/`structural` features specifically.

---

## Summary

| # | Concern | Status |
|---|---|---|
| 1 | Diverges from `DATASET_BUILDER_SPEC.md` §6 | Confirmed, reconciled and explained in `README.md`, not silent |
| 2 | Reuses `tara.classification.heuristics` — is that the Task Classifier? | No: pure stateless predicates, same reuse pattern as `tokenize_for_search`; no classification output exists |
| 3 | `comment_coverage_ratio` reads the filesystem, not just `RepositoryModel` | Accepted, necessary (Parser discards comments by construction), degrades gracefully |
| 4 | Heuristic constants are uncalibrated | Accepted, explicitly marked as such, fully configuration-driven for future calibration |
| 5 | `dominant_language` is near-constant in V1 | Accepted, kept for forward compatibility with a future multi-language Parser |
| 6 | Combined graph merges three different edge semantics | Deliberate, narrow scope (connectivity shape only); typed densities stay separate |
| 7 | Some structural-logic paths (deep nesting, larger graphs) reasoned about but not directly tested | Acknowledged gap, not claimed as covered |

No code outside `evaluation/rts_builder/feature_extraction/` was
modified. Repository Loader and Parser were not touched.
`tests/rts_builder/feature_extraction/` has 33 tests, all passing
alongside the full existing project suite.
