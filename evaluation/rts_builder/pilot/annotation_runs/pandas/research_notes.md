# Research Notes — pandas Pilot Annotation Run

Reflective notes from constructing this pilot run against pandas at
commit `d0d07d18f9fe855529997e3fe16cf1d0c8ce5eb8` (version
`3.1.0.dev0`, a development snapshot 1495 commits past the
`v3.1.0.dev0` tag). Observations and judgments, not additional data —
everything factual referenced here was already established in
`repository_summary.md`, `annotation_drafts.jsonl`, or
`validation_report.md`.

## 1. Interesting repository findings

- **pandas is the seventh and largest repository processed in this
  project's pilot runs**: `pandas/core/frame.py` alone (19,651 lines)
  is more than twice the size of SQLAlchemy's largest file
  (`sql/compiler.py`, 8,398 lines, the previous record-holder), and
  `frame.py` + `series.py` + `generic.py` together total 42,709 lines
  — more than the entirety of several prior pilot repositories'
  `core/` packages combined.
- **pandas has an unusually rich diagnostic surface in its own
  changelog**: `doc/source/whatsnew/v3.1.0.rst` (760 lines, read in
  full) documents well over 150 individual bug-fix bullet points
  across 19 sections, plus large Enhancements and Performance
  sections — by far the most extensive single-file changelog read in
  any pilot run to date (exceeding even SQLAlchemy's 12 separate
  `unreleased_21/` fragments in combined content, though SQLAlchemy's
  fragment-per-change convention made individual entries easier to
  cross-reference).
- **Two distinct, already-implemented mechanisms were found to
  quietly satisfy queries whose initial grounding search (a
  name-based grep) missed them**: `ExtensionArray._groupby_op`
  (`arrays/base.py:3009`, found while drafting the original
  `pandas-005`) and `DataFrame.__arrow_c_stream__`/
  `Series.__arrow_c_stream__` (found while drafting the original
  `pandas-006`). Both were caught during Phase 3/4 drafting itself —
  before either query reached `queries.jsonl` in its flawed form —
  unlike the SQLAlchemy run's `sqlalchemy-008`, which was drafted,
  written to every downstream artifact, and only caught during the
  Phase 11 audit. This run's earlier catch reflects a deliberate
  practice adjustment: verifying a Feature query's "this doesn't
  exist" premise with more than one search term before finalizing it.
- **`merge_asof`'s own docstring is unusually explicit about its
  precondition** ("Both DataFrames must be first sorted by the merge
  key in ascending order before calling this function") — a rare case
  where a query's grounding could be confirmed from a single
  docstring sentence rather than requiring cross-referencing multiple
  files.

## 2. Commit-specific observations

- Version `3.1.0.dev0` per `git describe --tags`
  (`v3.1.0.dev0-1495-gd0d07d18f9`) — a development snapshot, not a
  tagged release, similar in spirit to SQLAlchemy's `2.1.0b4` beta but
  further from any stable release point (1495 commits past the last
  tag, versus a numbered beta).
- **This run's changelog review was the broadest in absolute content
  volume of any pilot run to date**: the full 760-line `v3.1.0.rst`
  was read across two tool calls, covering all 19 confirmed section
  headers (Enhancements, Notable bug fixes, API changes, Deprecations,
  Performance, and 14 dtype/subsystem-specific Bug Fixes subsections
  including one — I/O — initially missed by an automated header-regex
  search and found only by a manual follow-up read of the file's
  un-grepped middle section).
- **The I/O bug-fixes section header uses a 3-character underline
  (`^^^` under `I/O`, 3 characters) that an initial regex search
  requiring 4+ carets did not match**, causing the section to be
  skipped on the first pass. This was caught by manually reading the
  file's remaining un-reviewed line range rather than trusting the
  regex-derived section list to be complete — a useful reminder that
  automated structural scans of a document can have blind spots that
  only a direct read catches, mirroring this run's two premise
  -correction findings in spirit (a targeted search missing something
  a broader read or a different search term would have caught).

## 3. Annotation difficulties

- **Two Feature-category queries required replacement during
  drafting**, both for the same underlying reason: a name-based grep
  for a specific expected method/attribute name (`to_arrow`,
  `_groupby_op`-as-absent) returned no match, but a broader or
  differently-termed follow-up search found the capability already
  implemented under a different name or in a different class than
  first searched for (`__arrow_c_stream__` instead of `to_arrow`;
  `_groupby_op` existing directly on the generic `ExtensionArray` base
  class rather than being absent entirely). Both were caught and
  corrected before being written to `queries.jsonl` in their flawed
  form, avoiding the cross-artifact propagation burden the SQLAlchemy
  run's `sqlalchemy-008` correction required.
- **Scale made picking a single "correct" test file harder for
  `pandas-013`** than for a typical testing query: 16 confirmed
  modules exist under `pandas/tests/extension/base/`
  (`accumulate.py`, `casting.py`, `constructors.py`, `dim2.py`,
  `dtype.py`, `getitem.py`, `groupby.py`, `index.py`, `interface.py`,
  `io.py`, `methods.py`, `missing.py`, `ops.py`, `printing.py`,
  `reduce.py`, `reshaping.py`, `setitem.py`), and `interface.py` was
  selected as primary based on name plausibility alone, not content
  verification — flagged explicitly for the annotator in
  `human_annotation_checklist.md`.
- **`pandas-014`'s cross-engine framing required deliberately avoiding
  restating any of the many already-fixed per-engine I/O
  inconsistencies** documented in the 760-line changelog's I/O
  section (read in full) — the query was written at a level of
  generality ("investigate a test where behavior differs by engine")
  that describes the general class of issue without duplicating any
  one of the dozens of specific, already-resolved `read_csv`/
  `read_json`/`read_sas` engine-inconsistency bullets found there.

## 4. Threats to validity

- **Single-pass AI search, not independently cross-checked** — same
  limitation disclosed in all six prior pilot runs.
- **The 760-line `v3.1.0.rst` was read in full, but pandas's much
  longer historical changelog (dozens of files from `v0.13.0.rst`
  through `v3.0.5.rst`) was not** — an already-fixed issue from an
  earlier release cycle that resembles a plausible bug-fix query topic
  could exist undetected outside the window actually read.
- **No code was executed, no test was run, and no Cython extension
  module (`pandas/_libs/`) was built, read in depth, or profiled** —
  all findings are static-inspection-only, consistent with every prior
  pilot run, and especially significant here given pandas's heavy
  reliance on Cython for performance-critical paths.
- **Both premise corrections (`pandas-005`→sorted-merge,
  `pandas-006`→per-column na_rep) were confirmed absent only by grep
  for one or two specific term(s)**, not an exhaustive read of every
  relevant file; a differently-named mechanism satisfying either
  replacement query's premise cannot be fully ruled out without a more
  exhaustive search than this session performed — explicitly flagged
  in `human_annotation_checklist.md`.
- **Extremely large surface area relative to the fixed query budget**:
  `pandas/core/computation/`, `pandas/core/window/`, `pandas/tseries/`,
  `pandas/plotting/`, `pandas/_libs/`, and the large majority of
  `pandas/io/`'s format-specific readers/writers (Excel, JSON, SQL,
  HDF5, SAS, Stata, XML, HTML, ORC, Iceberg, etc.) were never touched
  by this round's 20 queries — the most acute version of the coverage
  caveat already raised for Celery and SQLAlchemy in this project's
  prior pilot runs, given pandas's size relative to even those two
  large repositories.

## 5. Potential reviewer concerns

1. **"Why were two Feature queries' premises wrong during initial
   drafting?"** — Addressed directly in `validation_report.md` §9 and
   this document's §1/§3: both are disclosed as genuine findings, not
   minimized, and both were corrected before propagating to any
   downstream artifact (unlike the SQLAlchemy run's equivalent, which
   required a later Phase 11 correction across many files). This
   reflects a real methodological improvement carried forward from
   that run's lesson.
2. **"Why is the I/O whatsnew section's coverage inconsistent with
   the rest of the changelog review?"** — Addressed in §2: an
   automated header-regex search initially missed the section due to
   a 3-vs-4-caret underline-length assumption; caught and corrected by
   a manual read of the remaining file range before `queries.jsonl`
   was finalized, so no downstream artifact was affected.
3. **"Was `pandas-014`'s open-ended framing a way to avoid being
   pinned down?"** — No; it is a deliberate response to the changelog
   review finding dozens of specific, already-fixed per-engine
   inconsistencies that would each individually collide with a
   narrower query — the general framing is the correct response to
   that specific finding, not an evasion, and is explained as such in
   the query's own `notes` field.

## 6. Recommendations

- Before grading begins, independently verify both premise-correction
  gaps (`pandas-005`'s "no non-presorted approximate join" and
  `pandas-006`'s "no per-column na_rep") more exhaustively than this
  session's targeted grep, given that each underpins its entire query.
- Resolve `pandas-013`'s primary-candidate ambiguity among the 16
  `pandas/tests/extension/base/` modules by reading each one's actual
  content rather than relying on filename plausibility.
- A future round revisiting this repository should specifically target
  the entirely-untouched areas identified in `dataset_statistics.md`
  §9 (`core/computation/`, `core/window/`, `tseries/`, `plotting/`,
  `_libs/`, and most of `io/`'s format-specific readers) — given
  pandas's exceptional size, a single 20-query round can only ever
  sample a very small fraction of it, and these represent genuinely
  distinct, unexplored territory rather than variations on subsystems
  already covered.
- Given this run's experience catching two flawed Feature-query
  premises during drafting itself (rather than only during a later
  Phase 11 audit, as in the SQLAlchemy run), the practice of following
  up an initial "no match found" grep with at least one differently
  -termed search before finalizing a Feature query is worth carrying
  forward explicitly as a standard drafting step in future rounds, not
  just as an audit-time safety net.
