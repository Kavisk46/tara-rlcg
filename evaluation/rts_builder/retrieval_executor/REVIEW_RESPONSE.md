# Review Response: Retrieval Executor Subsystem (RTS Builder, Milestone 5)

## Part 1: Response to Reviewer #2 (Minor Revision)

Three requested revisions, addressed in order. Architecture is
unchanged: no class was added or removed, no public method signature
changed, and no strategy's retrieval behavior (which files are
retrieved, or their relative ranking) changed. All changes are scoped
to `evaluation/rts_builder/retrieval_executor/` and its own tests.

---

### Revision 1 — Hybrid Score Normalization

> *Document and implement the exact mathematical formulation. For every
> query: normalize Lexical/Dense/Graph scores independently using the
> chosen normalization method (state it explicitly). Then compute
> Hybrid = αL' + βD' + γG' where α+β+γ=1, default α=β=γ=1/3. Document
> this formula in README.md, STRATEGY_COMPARISON.md, REVIEW_RESPONSE.md.*

**Implemented Solution.** The normalization and combination were
already implemented exactly this way since this milestone's original
submission (`hybrid_retrieval.py:HybridRetriever.combine`, using
`tara.retrieval.utils.normalize_scores` — min-max normalization,
mapping an all-tied or single-score input to `1.0` rather than dividing
by zero — applied independently to each of Lexical's, Dense's, and
Graph's own `retrieved_files` scores, then combined via
`hybrid_lexical_weight`/`hybrid_dense_weight`/`hybrid_graph_weight`,
already validated at settings-construction time to sum to `1.0`, with
each defaulting to `1/3`). What this revision required was writing the
formulation down precisely, since a formula the code satisfies but
nowhere states is exactly what "document and implement" — with
"implement" evidently in question — is asking to close. Added a
piecewise-formula statement of the normalization (explicit about the
all-tied edge case), the combination formula, and the constraint on
`α, β, γ`, in all three requested locations, plus the same content as
structured data in the new `config.yaml`.

**Files Changed.**
- `README.md`: new "Hybrid Score Normalization" section (LaTeX-rendered formula).
- `STRATEGY_COMPARISON.md`: new "Hybrid Score Normalization" section (plain-text formula, cross-referencing `README.md`).
- `REVIEW_RESPONSE.md`: this section.
- `config.yaml` (new file): `hybrid_score_normalization` block — method, formula, constraint, default weights, and the `RetrievalExecutorSettings` field each symbol maps to.
- `tests/rts_builder/retrieval_executor/test_latency_protocol.py` (new file): also asserts `config.yaml`'s recorded default weights match `RetrievalExecutorSettings()`'s actual defaults and sum to `1.0`, so this documentation cannot silently drift from the code either.

**Remaining Limitations.** None identified for this revision specifically — see Part 2, Item 1 below for the pre-existing (not new) discussion of what a high Hybrid score does and doesn't mean given the default backend's characteristics.

---

### Revision 2 — Latency Protocol

> *Freeze the measurement protocol. Latency starts immediately before
> `retrieve()`; ends immediately after ranked results are returned.
> Include: embedding generation, vector search, graph traversal, score
> computation. Exclude: repository loading, index construction, model
> download. Add this protocol to config.yaml, README.md.*

**Implemented Solution.** This one *did* require a code change, not
only documentation — see "Remaining Limitations" for why that
distinction matters and was not skipped over. Before this revision,
each retriever measured latency as a single `time.perf_counter()` span
covering its entire `retrieve()` body, which necessarily included BM25
-index/vector-index/file-adjacency-map construction, since (in this
milestone's uncached architecture) that construction happens inside
`retrieve()` on every call. That measured number did not match the
frozen protocol's "exclude index construction," so bringing the code
into conformance was necessary for the documentation to describe the
code truthfully rather than aspirationally. Added
`common.LatencyAccumulator`, which lets a retriever open/close multiple
timed spans within one `retrieve()` call, leaving excluded
-per-protocol code (index construction) untimed in between:

- **Lexical**: BM25 index build happens before the timer starts; query tokenization through final ranking is one timed span.
- **Dense**: document-embedding generation is timed, then vector-index construction happens untimed, then query-embedding generation + vector search is a second timed span, summed with the first.
- **Graph**: seed-finding (query-dependent) is timed, then the file-adjacency map is built untimed, then BFS traversal + ranking is a second timed span, summed with the first.
- **Hybrid**: unchanged — it has no index-construction phase at all, so its single existing timed span already conformed.

The apparent tension between "starts immediately before `retrieve()`"
and "excludes index construction that happens inside `retrieve()`" is
resolved explicitly in `README.md`'s new "Design Rationale: Revision 2"
subsection: the boundary instruction fixes the outer measurement
window; the include/exclude list fixes which phases *within* that
window are actually accumulated.

**Files Changed.**
- `latency_protocol.py` (new file): the frozen protocol as importable constants — single source of truth.
- `config.yaml` (new file): `latency_protocol` block — prose statement of the same protocol, plus per-file notes on why exclusion requires discontiguous timing in the current architecture.
- `common.py`: added `LatencyAccumulator`.
- `lexical_retrieval.py`, `dense_retrieval.py`, `graph_retrieval.py`: `retrieve()` internals restructured to use `LatencyAccumulator` and exclude index construction; public signatures, return types, and control flow unchanged.
- `hybrid_retrieval.py`: no change (already conformed).
- `README.md`: new "Latency Measurement Protocol" section (per-strategy included/excluded table) and "Design Rationale: Revision 2" subsection.
- `STRATEGY_COMPARISON.md`: "Typical latency shape" row updated to state what's excluded per strategy; new cross-referencing "Latency Measurement Protocol" section.
- `tests/rts_builder/retrieval_executor/test_latency_protocol.py` (new file): asserts `config.yaml`'s `latency_protocol` include/exclude lists and start/end boundary strings stay textually identical to `latency_protocol.py`'s constants.
- Existing tests in `test_lexical_retrieval.py`, `test_dense_retrieval.py`, `test_graph_retrieval.py`, `test_executor.py` were re-run (not rewritten — they assert `retrieval_latency_ms >= 0.0`, which remains true) to confirm the internal timing restructuring introduced no behavioral regression.

**Remaining Limitations.** The underlying cost this protocol excludes
from the *reported number* — index construction happening on every
call, with no caching — still exists as a real architectural
characteristic; this revision changes what is *measured and reported*,
not what work the system actually performs per call. That distinction
is deliberate (a measurement fix, not a caching feature, and adding
caching now would be exactly the kind of architecture change this
revision's own instructions ("do not redesign the architecture")
preclude) but is worth restating plainly: `retrieval_latency_ms` is now
an accurate measure of per-query cost against an already-available
repository representation, not a measure of this call's actual total
wall-clock duration. See Part 2, Item 4 for the pre-existing discussion
of the caching gap itself.

---

### Revision 3 — SentenceTransformer Integration Test

> *Add an integration test using SentenceTransformerEmbedder. Use a
> cached tiny local model. No network access during CI. Verify:
> embedding generation, vector search, retrieved results, failure
> handling.*

**Implemented Solution.** Added
`tests/rts_builder/retrieval_executor/test_sentence_transformer_integration.py`,
using `sentence-transformers/all-MiniLM-L6-v2` (a small, ~80MB model
already present in this environment's local Hugging Face cache) via the
existing, unmodified `tara.context.embedder.SentenceTransformerEmbedder`.
Six tests:

1. **Embedding generation** — `embed()` produces a real, non-degenerate dense vector; the same text embeds identically on repeated calls.
2. **Vector search / retrieved results** — a real `DenseRetriever(embedder=SentenceTransformerEmbedder(...))` correctly ranks a "parsing"-themed file above a "database"-themed one for a parsing-themed query, and vice versa for a database-themed query — a genuine semantic-similarity assertion the default `HashingEmbedder` could not reliably satisfy (see Part 2, Item 1), now actually verified against a real model.
3. **Failure handling** (two tests) — requesting an uncached, unreachable model fails fast, locally, and is not silently swallowed by `DenseRetriever`.

**No network access during CI**, concretely enforced, not just
asserted: `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE` are set to `"1"` as
*module-level code, before* `sentence_transformers`/`huggingface_hub`
are imported anywhere in the process (including by the
`pytest.importorskip` call in the same module). This ordering was
verified empirically, the hard way, to matter: `huggingface_hub` reads
`HF_HUB_OFFLINE` into a module-level constant at import time, not on
every call, so an earlier draft of this test that set the env vars
inside a `pytest` fixture (which only runs at test-execution time, well
after collection-time imports have already completed) silently failed
to engage offline mode — the "uncached model" failure test made a real
HTTPS request to `huggingface.co` and got back a live `401` response,
which the test's own logs surfaced. Moving the env-var assignment
before the import fixed this, confirmed by re-running: the same test
then failed fast and locally with an offline-mode error, no network
request in the logs at all. If the model is not present in the local
cache (e.g. an unprovisioned CI runner), the module-scoped fixture that
loads it calls `pytest.skip`, so CI stays green rather than depending
on a specific machine's cache contents — the requirement is "no network
access," not "always run this test everywhere."

**A genuine gap found while writing the failure-handling test, not
fixed (out of scope):**
`tara.context.embedder.SentenceTransformerEmbedder._ensure_model` wraps
only the `import sentence_transformers` statement in a
try/except → `EmbeddingError`; the `SentenceTransformer(model_name,
device=device)` constructor call itself is unguarded. An uncached
/unreachable model therefore raises a raw `OSError` (from
`huggingface_hub`), not `tara.core.exceptions.EmbeddingError` — a
caller catching `EmbeddingError` specifically (as `README.md`'s own
Failure Modes documentation for `Embedder` implies one reasonably
would) would not catch this. This is a pre-existing defect in
`tara.context.embedder`, part of the core `tara` library, not this
subsystem — "Do NOT modify any other subsystem" places fixing it
out of scope for this revision. The test asserts the *actual* current
behavior (`OSError`) rather than the arguably-more-correct one, with an
explicit docstring explaining why, so the test documents this gap
honestly instead of either failing against reality or silently
asserting something false.

**Files Changed.**
- `tests/rts_builder/retrieval_executor/test_sentence_transformer_integration.py` (new file).
- `pyproject.toml`: no change needed — `torch`/`sentence-transformers` were already listed as main dependencies; they were declared but not installed in this development environment, now installed to actually exercise this test. `pyyaml` (needed only by `test_latency_protocol.py`) added to the `dev` optional-dependency group.

**Remaining Limitations.** This test suite depends on a specific model
being present in the local cache; it is not a substitute for a
dedicated CI step that provisions that cache deliberately (e.g. a
Docker image layer or CI cache action seeding
`~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2`)
— without that provisioning, this test module will *skip*, not run, in
a fresh CI environment, silently reducing coverage rather than failing
loudly. Ensuring CI actually provisions the cache (rather than relying
on it accidentally being present, as it happens to be in this
development environment) is a Future Extension Point, not addressed by
this revision. The `SentenceTransformerEmbedder._ensure_model` gap
noted above is also unresolved, by design (out of scope).

---

## Part 2: Anticipated Review (prior to Reviewer #2's Minor Revision)

Following the discipline established for Repository Loader's actual
review and every subsequent milestone's anticipated review, this
document self-applies that scrutiny before an external one happens.
Failure modes are cataloged in their own section at the end, per this
milestone's explicit deliverable list. Retained below as originally
written, with two items now cross-referenced from Part 1 where
Reviewer #2's revisions bear directly on them.

---

## Item 1: `HashingEmbedder` produces embeddings with no semantic understanding — is calling this "Dense Retrieval" honest?

**Anticipated comment.** *"Real dense retrieval relies on a trained
model's semantic understanding of text. `HashingEmbedder` is a
bag-of-tokens hash with no training, no semantics, and no notion that
'parse' and 'read' are related. Isn't labeling this 'Dense Retrieval'
overselling what it does?"*

**Response.** The label describes the retrieval *mechanism* (dense,
fixed-dimension vector similarity via cosine search over a vector
index), not a claim about semantic quality, and `STRATEGY_COMPARISON.md`
says exactly that explicitly: a dataset consumer should read a
`HashingEmbedder`-backed high score as "coarse hashing/token-presence
similarity," not semantic understanding. Feature hashing is itself a
real, established dense-embedding technique (not invented for this
milestone to avoid a dependency) — it genuinely produces dense vectors
usable with cosine similarity and a vector index, satisfying the
architectural requirement ("embedding-based retrieval," "pluggable
embedding backend," "vector index abstraction") precisely. The
*quality* ceiling of the default backend is a separate, clearly
-documented property, not a misrepresentation of what mechanism is
running. `Embedder` being reused from `tara.context.embedder` means a
real semantic backend (`SentenceTransformerEmbedder`) is one
constructor argument away, with zero changes to `DenseRetriever`,
`RetrievalExecutor`, or any output type.

---

## Item 2: `SentenceTransformerEmbedder` is available but never exercised by this milestone's own test suite

**Status: resolved by Reviewer #2's Revision 3 — see Part 1.** Original
anticipated comment and response retained below for the record.

**Anticipated comment.** *"If real semantic embeddings are 'one
constructor argument away,' why isn't there a test proving that
actually works end-to-end?"*

**Response (original, pre-Revision-3).** Not tested here, and that gap
is stated directly rather than implied away. `SentenceTransformerEmbedder`
already has its own test coverage where it was originally implemented
(`tara.context`); re-testing it here would mean this milestone's test
suite depends on downloading a real model over the network, which
conflicts directly with "Deterministic execution" and fast, offline
CI. What *is* verified here: `DenseRetriever` accepts any `Embedder`
via constructor injection and never inspects which concrete subclass it
received (`dense_retrieval.py` has zero `isinstance` branching on the
embedder), which is the actual claim "pluggable" makes — verified by
type/interface discipline, not by an integration test against a
specific alternative implementation. Wiring a real backend into an
actual dataset-construction run and confirming it does not crash
mid-batch would still be worth doing before that first real run —
listed as a Future Extension Point, not silently assumed to already be
covered.

**What changed:** `test_sentence_transformer_integration.py` (Part 1,
Revision 3) now does exactly this — a real, offline, locally-cached
model, exercised end-to-end through `DenseRetriever`, including a
genuine semantic-ranking assertion. The interface-discipline argument
above still holds as the reason `DenseRetriever` itself needed no
change to support this; what was missing was the test proving it, which
now exists.

---

## Item 3: Graph Retrieval's file-level projection duplicates Feature Extraction's — why not share the code?

**Anticipated comment.** *"`graph_retrieval.py`'s `_build_file_adjacency`
is structurally almost identical to Feature Extraction's
`graph_features._build_combined_file_graph`. Why maintain the same
~15 lines twice instead of extracting a shared helper?"*

**Response.** Considered and declined, for the same reason Feature
Extraction itself declined to import Parser's private
`_module_path_for_file` rather than write its own: `_build_combined_file_graph`
is a private (`_`-prefixed), undocumented-as-a-contract helper internal
to Feature Extraction's own module — reaching into it would couple this
milestone to an implementation detail neither milestone's own docs
promise to keep stable, and Feature Extraction is now frozen (accepted,
"do not modify"), so even a compatible refactor on this side could not
be paired with a corresponding change there if the two ever needed to
diverge (e.g. this module's version deliberately omits `networkx`,
returning a plain `dict[str, set[str]]` instead of a `networkx.Graph`,
since BFS over a plain adjacency dict is all `graph_retrieval.py`
needs). A genuinely shared utility would belong in a common location
neither of these two frozen/soon-to-be-frozen milestones owns —
worth doing if a *third* consumer needs the same projection, not
justified for two.

---

## Item 4: `InMemoryVectorIndex` and `LexicalRetriever`'s BM25 index are rebuilt from scratch on every single call — what does that cost at scale?

**Status: latency *measurement* now correctly excludes this cost
(Reviewer #2's Revision 2); the cost itself is unchanged — see Part 1's
Revision 2 "Remaining Limitations."** Original anticipated comment and
response retained below.

**Anticipated comment.** *"Every `retrieve()` call rebuilds the BM25
index and re-embeds every file from zero, with no caching across
calls. For a dataset-construction run issuing many queries against the
same repository, isn't that wasteful?"*

**Response (still current).** Yes, and deliberately out of scope for this milestone:
unlike Parser and Feature Extraction, nothing in this milestone's
requirements list asks for caching or incremental execution ("Requirements"
lists determinism, not incrementality). Rebuilding per call keeps each
`retrieve()` call a pure function of its arguments with no hidden
mutable state to reason about, which is the simpler, more obviously
-correct design for a first implementation. For a real
multi-query-per-repository dataset-construction run, this is a real,
quantifiable cost (BM25 build is O(total corpus tokens); embedding is
O(files)) — listed explicitly in Failure Modes below and as a Future
Extension Point (a `RetrievalExecutor` that holds a per-repository
index/embedding cache, invalidated by `commit_sha`, mirroring Parser's
own commit-keyed cache design) rather than silently assumed acceptable
at any scale.

---

## Item 5: `feature_vector` is a required parameter used for exactly one thing — is that a real dependency or padding?

**Anticipated comment.** *"`execute_all` requires a `FeatureVector` but
only ever reads `feature_vector.resource.repository_size_category`.
Couldn't `repository_model.files` give you the same file count
directly, making `feature_vector` an unnecessary required argument?"*

**Response.** `repository_model.files`' length *could* substitute for
this one specific read, correct — but the requirement names
`FeatureVector` as a required input to this subsystem explicitly ("Given:
RepositoryModel, FeatureVector, Developer Query"), and `MismatchedInputsError`'s
consistency check (verifying `feature_vector` actually corresponds to
`repository_model`) is a real, independent correctness guard this
subsystem provides given that input, not busywork. The deliberately
narrow *use* of `feature_vector` (documented in `README.md` and in
`execute_all`'s own docstring) is the more important design decision
here: it would have been easy to reach for `feature_vector.query.*`
-derived signals to make retrieval "smarter" per query, and that
temptation was explicitly declined because it would blur into the
excluded Task Classifier/Router's job. The parameter is required by
specification and used for exactly one, narrow, justified purpose —
not padding, but also not exploited beyond that one purpose.

---

## Failure Modes

| Failure | Behavior | Notes |
|---|---|---|
| `query_text` is not a `str` (e.g. `None`) | `InvalidQueryError` | Raised before any retrieval work begins. |
| `feature_vector` was computed from a different repository/commit than `repository_model` | `MismatchedInputsError` | Compares `repository_id` and `commit_sha` on both inputs. |
| `query_text` is an empty string | Lexical and Graph return empty results (no tokens to match); Dense returns an arbitrary, score-`0.0`, deterministic ranking (a zero query vector has zero cosine similarity with everything, so ties are broken by file path); Hybrid reflects whatever Lexical/Dense/Graph produced | Not an error in any strategy — see `STRATEGY_COMPARISON.md`. |
| Query names no symbol defined anywhere in the repository | Graph Retrieval returns an empty result (no seed to expand from) | Expected, not an error — most queries about *behavior* rather than a specific named symbol will hit this. |
| Repository has zero files | Every strategy returns an empty result, `context_token_count=0`, no division-by-zero anywhere | Verified directly by `test_execute_all_on_empty_repository_does_not_crash`. |
| A file has an unusually large `size_bytes` relative to the rest of the repository | `context_token_count` for any strategy that retrieves it is dominated by that one file | Not a bug -- token estimation is a direct, honest function of retrieved file sizes; a dataset consumer surprised by this should look at which files were retrieved, not at the estimator. |
| Two files tie exactly on score | Broken deterministically by `file_path` ascending, in every strategy (`common.rank_scores`, and independently, identically, in `InMemoryVectorIndex.search`) | Required for "Deterministic execution" — `dict`/`set` iteration order is not itself a cross-call reproducibility guarantee. |
| `RetrievalExecutorSettings`'s `lexical_*_weight` or `hybrid_*_weight` fields don't sum to 1.0 | Raised at settings construction time (`pydantic.ValidationError`), not at first retrieval call | Fails fast at configuration time rather than producing a silently miscalibrated combined score later. |
| `HashingEmbedder` given two texts that happen to hash to the same bucket pattern | A cosine similarity that overstates true relatedness | An inherent, accepted property of the hashing trick at any fixed dimensionality — mitigated, not eliminated, by a larger `embedding_dimensions`; see `STRATEGY_COMPARISON.md`. |
| Very large repository (many files) | No hard limit is enforced; latency scales with `top_k`, corpus size (BM25/embedding), and `max_graph_hops` (BFS) | `RetrievalExecutor` scales `top_k` down when `feature_vector.resource.repository_size_category` is `LARGE`, bounding output size and some downstream cost, but does not itself cap BM25-build or embedding cost -- see Item 4 above and Future Extension Points in `README.md`. |
| `SentenceTransformerEmbedder` given an uncached or unreachable model name | Raw `OSError`, not `EmbeddingError` | Pre-existing gap in `tara.context.embedder` (out of scope to fix — see Part 1, Revision 3); not silently swallowed, propagates cleanly through `DenseRetriever`. |
| `RetrievalExecutorSettings`'s `lexical_*_weight`/`hybrid_*_weight` fields don't sum to `1.0` | `pydantic.ValidationError` at settings construction | Same row as above, restated: fails fast, not at first use of the miscalibrated weights. |

## Summary

| # | Concern | Status |
|---|---|---|
| 1 | `HashingEmbedder` has no real semantic understanding | Accepted, documented; mechanism claim is accurate, quality ceiling is stated explicitly |
| 2 | Real embedding backend (`SentenceTransformerEmbedder`) untested here | **Resolved** — Part 1, Revision 3 |
| 3 | Graph-projection logic duplicated from Feature Extraction rather than shared | Deliberate, matches established precedent for not coupling to another frozen milestone's private internals |
| 4 | No caching across repeated calls against the same repository | Deliberate, out of this milestone's stated scope; **latency measurement now excludes this cost (Part 1, Revision 2), the cost itself remains a Future Extension Point** |
| 5 | `feature_vector`'s one narrow use | Required by specification; deliberately not exploited beyond a size-based latency adaptation |
| R1 | Hybrid normalization formula undocumented | **Resolved** — Part 1, Revision 1 |
| R2 | Latency protocol undocumented and, on inspection, not actually honored by the code (index construction was included) | **Resolved** — Part 1, Revision 2 |
| R3 | No integration test against a real embedding backend | **Resolved** — Part 1, Revision 3; surfaced a real, unfixed gap in `tara.context.embedder`'s exception handling along the way |

No code outside `evaluation/rts_builder/retrieval_executor/` (and its
own tests, plus `pyproject.toml`'s dev-dependency list) was modified.
Repository Loader, Parser, and Feature Extraction were not touched.
`tests/rts_builder/retrieval_executor/` now has 59 tests (47 original +
6 `test_latency_protocol.py` + 6 `test_sentence_transformer_integration.py`),
all passing alongside the full existing project suite.
