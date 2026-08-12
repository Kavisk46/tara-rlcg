# Repository Summary — pandas

Produced against the real local repository at
`C:\Projects\tara-rlcg\pandas`, pinned commit
`d0d07d18f9fe855529997e3fe16cf1d0c8ce5eb8` (verified via `git
rev-parse HEAD` before any inspection began; `git describe --tags`
reports `v3.1.0.dev0-1495-gd0d07d18f9`, a development snapshot 1495
commits past the `v3.1.0.dev0` tag). Every claim below traces to a
direct directory listing, `grep`, `wc -l`, or full-text read of the
repository at this commit — nothing is asserted from memory of pandas
generally.

## 1. Project overview

pandas is a Python data-analysis library built around two primary data
structures, `Series` (1D) and `DataFrame` (2D), plus a shared `Index`
system for labeling axes. The Python-level package lives under
`pandas/`; performance-critical routines are implemented in Cython
under `pandas/_libs/` (confirmed: `.pyx`/`.pxd`/`.pyi` files for
`algos`, `arrays`, `groupby`, `hashtable`, `index`, `indexing`,
`internals`, and more). At this commit the changelog in
`doc/source/whatsnew/v3.1.0.rst` is the active in-development release
notes file, consistent with the `3.1.0.dev0` version reported by `git
describe`.

## 2. Architecture summary

- **`pandas/core/`**: the Python-level implementation of `Series`,
  `DataFrame`, `Index`, `GroupBy`, and all computational/reshaping
  logic. This is by far the largest and most central package.
- **`pandas/_libs/`**: Cython-compiled extension modules backing
  performance-sensitive operations (hash tables, algorithms, the
  internals block-management primitives, groupby aggregation kernels).
- **`pandas/io/`**: readers/writers for external formats (CSV, Excel,
  JSON, Parquet, SQL, HDF5, SAS, Stata, XML, HTML, clipboard, ORC,
  Iceberg, pickle, feather).
- **`pandas/arrays`, `pandas/api`**: the public-facing re-export
  surface for extension arrays and the extension API.
- **`pandas/tseries/`**: time-series offset/frequency machinery
  supporting the datetime-like functionality documented extensively in
  `doc/source/whatsnew/v3.1.0.rst`'s Datetimelike/Timedelta/Timezones/
  Period sections.
- **`pandas/plotting/`**: the `.plot` accessor's plotting backends.
- **`pandas/_testing/`** and **`pandas/testing.py`**: pandas's own
  internal test-support utilities (`asserters.py`,
  `_hypothesis.py`, `_io.py`, `_warnings.py`, `contexts.py`,
  `compat.py`), distinct from `pandas/tests/`, the test suite itself.

## 3. Important packages

Confirmed via a top-level listing of `pandas/core/`:

| Package | Role |
|---|---|
| `internals/` | The `BlockManager`/`Block` machinery that physically stores a `DataFrame`'s column data, grouped by dtype into blocks. |
| `indexes/` | `Index` and its specialized subclasses (`RangeIndex`, `MultiIndex`, `DatetimeIndex`, `PeriodIndex`, `IntervalIndex`, `CategoricalIndex`, etc.). |
| `groupby/` | The `GroupBy`/`SeriesGroupBy`/`DataFrameGroupBy` split-apply-combine machinery. |
| `arrays/` | pandas's own `ExtensionArray` implementations (`Categorical`, `IntegerArray`/masked arrays, `DatetimeArray`, `TimedeltaArray`, `PeriodArray`, `IntervalArray`, `SparseArray`, Arrow-backed arrays under `arrays/arrow/`). |
| `reshape/` | `merge`, `concat`, `pivot`, `melt`, `crosstab`-style reshaping operations. |
| `computation/` | The `eval`/`query` expression-evaluation engine (`expr.py`, `engines.py`, `ops.py`, `pytables.py`). |
| `dtypes/` | dtype inference, casting, and the dtype class hierarchy (`dtypes.py`, `cast.py`, `common.py`, `inference.py`). |
| `window/` | Rolling/expanding/EWM window computation. |
| `resample.py`, `sorting.py`, `nanops.py`, `algorithms.py` | Top-level `core/` modules for resampling, sorting, NaN-aware reduction ops, and general algorithms (`factorize`, `unique`, `isin`, etc.). |

## 4. Major modules

Confirmed by direct file reads and `grep -n "^class "` against the
files below:

- **`pandas/core/frame.py`** (19,651 lines — the single largest file
  confirmed across this project's seven pilot repositories to date)
  — defines `class DataFrame(NDFrame, OpsMixin)`.
- **`pandas/core/series.py`** (10,193 lines) — defines `class
  Series(base.IndexOpsMixin, NDFrame)`.
- **`pandas/core/generic.py`** (12,865 lines) — defines `class
  NDFrame(PandasObject, indexing.IndexingMixin)`, the shared base
  class underlying both `Series` and `DataFrame`.
- **`pandas/core/indexes/base.py`** (8,592 lines) — defines `class
  Index(IndexOpsMixin, PandasObject)`.
- **`pandas/core/internals/managers.py`** — defines
  `BaseBlockManager`, `BlockManager` (which also inherits from
  `libinternals.BlockManager`, a Cython type), and
  `SingleBlockManager` (used by `Series`).
- **`pandas/core/internals/blocks.py`** (2,516 lines) — defines
  `Block(PandasObject, libinternals.Block)` and its subclasses
  `EABackedBlock`, `ExtensionBlock`, `NumpyBlock`,
  `NDArrayBackedExtensionBlock`, `DatetimeLikeBlock`.
- **`pandas/core/groupby/groupby.py`** (5,966 lines) — defines
  `GroupByPlot`, `BaseGroupBy`, and `GroupBy(BaseGroupBy[NDFrameT])`,
  the shared grouping machinery.
- **`pandas/core/groupby/generic.py`** — defines `NamedAgg`,
  `SeriesGroupBy(GroupBy[Series])`, and
  `DataFrameGroupBy(GroupBy[DataFrame])`.
- **`pandas/core/reshape/merge.py`** — defines the `merge()`,
  `merge_ordered()`, and `merge_asof()` public functions plus the
  `_MergeOperation`/`_CrossMergeOperation`/`_OrderedMerge`/
  `_AsOfMerge` implementation classes.
- **`pandas/core/arrays/base.py`** — defines `ExtensionArray`, the
  abstract base class for all pandas extension array dtypes, plus
  `ExtensionArrayNaResult`, `ExtensionOpsMixin`,
  `ExtensionScalarOpsMixin`.

## 5. DataFrame execution flow

Confirmed from `generic.py`, `frame.py`, and `internals/managers.py`:
`DataFrame` and `Series` both derive from the shared `NDFrame` base
class, which provides most axis-aware, dtype-generic operations.
Column data is not stored directly on `DataFrame`; instead a
`BlockManager` (`internals/managers.py`) holds one or more `Block`
objects (`internals/blocks.py`), each grouping same-dtype columns
together for vectorized operation — `ExtensionBlock` /
`NDArrayBackedExtensionBlock` / `DatetimeLikeBlock` handle
extension-array-backed columns distinctly from plain-NumPy
`NumpyBlock`s. `Series` uses the lighter-weight `SingleBlockManager`.
Row/column selection (`.loc`, `.iloc`, `__getitem__`/`__setitem__`) is
implemented via `indexing.IndexingMixin`, which `NDFrame` inherits
directly. Group-wise computation (`.groupby(...)`) constructs a
`SeriesGroupBy`/`DataFrameGroupBy` (`groupby/generic.py`) built on the
shared `GroupBy` base (`groupby/groupby.py`), which performs
split-apply-combine against the underlying block-managed data.
Reshaping operations such as `merge()` (`reshape/merge.py`) operate
across `DataFrame`/`Index` objects and, like most of `core/`, are
implemented in pure Python/NumPy with Cython (`_libs/`) used for
inner-loop-critical operations (join algorithms, hashing, groupby
aggregation kernels).

## 6. IO architecture

Confirmed via `pandas/io/` top-level listing: format-specific
readers/writers exist as top-level modules (`feather_format.py`,
`html.py`, `orc.py`, `parquet.py`, `pickle.py`, `pytables.py` [HDF5],
`sas.py`/`sas` subpackage, `spss.py`, `sql.py`, `stata.py`, `xml.py`,
`iceberg.py`) plus dedicated subpackages for the more complex formats:
`parsers/` (CSV/text parsing, with `base_parser.py`,
`c_parser_wrapper.py`, `python_parser.py`, `arrow_parser_wrapper.py`,
and the public `readers.py` entry point), `excel/`, `json/`,
`clipboard/`, `formats/` (output rendering: `csvs.py`, `excel.py`,
`html.py`, `xml.py`, `format.py`, `style.py`/`style_render.py`,
`console.py`, `info.py`, `printing.py`). The CSV reader in particular
supports multiple selectable backends (`engine="c"`, evidenced by the
large number of `engine="c"`-specific performance-improvement entries
in `doc/source/whatsnew/v3.1.0.rst`, plus `python_parser.py` and
`arrow_parser_wrapper.py` for the Python and PyArrow engines
respectively).

## 7. Testing strategy

Confirmed via `pandas/tests/` top-level listing: a very large,
subsystem-mirroring test tree (`frame/`, `series/`, `indexes/`,
`groupby/`, `io/`, `reshape/`, `extension/`, `arrays/`, `internals/`,
`indexing/`, `resample/`, `window` [as part of broader dirs],
`interchange/`, `copy_view/`, `arithmetic/`, `computation/`,
`reductions/`, `scalar/`, `strings/`, `plotting/`, `dtypes/`,
`construction/`, `apply/`, `base/`, `config/`, `libs/`, plus top-level
`test_*.py` files for algos, aggregation, common utilities, CPU
detection, downstream-package compatibility, errors, expressions,
flags, multilevel indexing, nanops, and optional dependencies).
`pandas/tests/extension/` in particular has a dedicated `base/`
subpackage of reusable extension-array test mixins plus per-dtype test
modules (`test_arrow.py`, `test_categorical.py`, `test_datetime.py`,
`test_interval.py`, `test_masked.py`, `test_numpy.py`, `test_period.py`,
`test_sparse.py`, `test_string.py`) and example third-party-style
extension array implementations (`decimal/`, `json/`, `list/`,
`date/`, `array_with_attr/`, `uuid/`) used to exercise the
`ExtensionArray` interface generically. pandas's own test-support
utilities live in `pandas/_testing/` (`asserters.py` for
`assert_frame_equal`-style helpers, `_hypothesis.py`,
`_io.py`, `_warnings.py`, `contexts.py`, `compat.py`).

## 8. Documentation structure

Confirmed via `doc/source/` listing: `doc/source/whatsnew/` holds one
`.rst` file per release (from `v0.13.0.rst` through the current
in-development `v3.1.0.rst`, 760 lines, read in full this session).
`doc/source/user_guide/` and `doc/source/getting_started/` hold
narrative/tutorial documentation. `doc/source/reference/` holds the
API reference source, split by area (`frame.rst`, `series.rst`,
`groupby.rst`, `indexing.rst`, `io.rst`, `arrays.rst`, `extensions.rst`,
`window.rst`, `resampling.rst`, `offset_frequency.rst`,
`missing_value.rst`, `style.rst`, `testing.rst`, `plotting.rst`,
`options.rst`, `general_functions.rst`, `aliases.rst`, `index.rst`).
`doc/source/development/` holds contributor-facing documentation,
including `extending.rst` (writing custom `ExtensionArray`s),
`internals.rst`, `copy_on_write.rst`, and `contributing_codebase.rst`.

## 9. Potential annotation challenges

- **This is the largest repository processed in this project's seven
  pilot runs by a wide margin**: `pandas/core/frame.py` alone (19,651
  lines) exceeds SQLAlchemy's largest file
  (`sql/compiler.py`, 8,398 lines) by more than 2x, and `generic.py`
  (12,865) and `series.py` (10,193) are each independently larger than
  any single file in five of the six prior pilot repositories.
- **`doc/source/whatsnew/v3.1.0.rst` (760 lines, read in full) documents
  a very large number of already-fixed bugs and already-implemented
  features at this pinned commit** across Categorical, Datetimelike,
  Timedelta, Timezones, Numeric, Conversion, Strings, Interval,
  Indexing, Missing, MultiIndex, Period, Plotting, Groupby/resample/
  rolling, Reshaping, Sparse, ExtensionArray, Styler, and Other
  sections, plus a large Enhancements and Performance improvements
  section — Phase 2 query authoring must avoid describing any of
  these specific, already-resolved behaviors as open Bug Fix targets.
  Given the sheer volume (over 150 individual bug-fix bullet points),
  this run cross-checks candidate Bug Fix query topics against specific
  sections of this file (by area: Groupby/resample/rolling, Reshaping,
  Indexing, Conversion, ExtensionArray) rather than attempting to
  memorize every individual entry, and documents which specific areas
  were checked in `queries.jsonl`'s `notes` fields.
- **Cython (`_libs/`) implementation details are largely opaque to
  static inspection** — `.pyx` source is readable, but the compiled
  behavior of performance-critical paths (hash tables, groupby
  aggregation kernels) cannot be verified without building the
  extension modules, which this session did not do.
- **Extremely broad surface area relative to the fixed 20-query
  budget**: `pandas/core/` alone spans well over a dozen subpackages
  plus dozens of large top-level modules; only a small fraction can be
  represented in any single annotation round.

## 10. Threats to validity

- **Single-session, single-pass repository inspection** — not
  independently cross-checked by a second reviewer or a second AI
  pass, consistent with every prior pilot run in this project.
- **The 760-line `v3.1.0.rst` whatsnew file was read in full, but
  pandas's much longer historical changelog (`v0.13.0.rst` through
  `v3.0.5.rst`, dozens of files) was not** — an already-fixed issue
  from an earlier release cycle that happens to resemble a plausible
  bug-fix query topic could exist undetected outside the window
  actually read.
- **No code was executed, no test was run, and no Cython extension
  was built or profiled** — all findings are static-inspection-only,
  consistent with every prior pilot run.
- **Development/pre-release version**: `v3.1.0.dev0-1495-g...` is a
  development snapshot, not a tagged release; APIs and behaviors
  documented in `v3.1.0.rst` may still change before an actual 3.1.0
  release.
- **Scale relative to the fixed query budget**: with dozens of `core/`
  subpackages and modules, `_libs/` Cython internals, and a very large
  `io/` surface, 20 queries can only sample a very small fraction of
  the overall codebase — the most acute version of the coverage
  caveat already raised for Celery and SQLAlchemy in this project's
  prior pilot runs.
