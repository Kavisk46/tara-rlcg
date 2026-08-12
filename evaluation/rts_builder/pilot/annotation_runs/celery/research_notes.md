# Research Notes — Celery Pilot Annotation Run

Reflective notes from constructing this pilot run against Celery at
commit `f109abf852525b69a1b6eee0457c6cd5561e0529`. Observations and
judgments, not additional data — everything factual referenced here
was already established in `repository_summary.md`,
`annotation_drafts.jsonl`, or `validation_report.md`.

## 1. Interesting repository findings

- **Celery is, by a wide margin, the largest and most subsystem-rich
  repository processed across this project's five pilot runs**: 161
  `.py` files across 12 subpackages under `celery/`, versus 17-48 in
  the other four. `canvas.py` alone (2,443 lines) is larger than the
  entire `src/click/` package's `core.py` was as a *fraction* of its
  package.
- **`celery/app/backends.py`'s `BACKEND_ALIASES` dict is an unusually
  clean, self-documenting confirmation of "which backends exist"** —
  reading one ~20-line file gave a complete, authoritative short-name
  -to-class mapping, more directly useful for grounding `celery-005`/
  `celery-019` than the FastAPI/Flask/Requests/Click runs' equivalent
  "grep for class definitions across many files" approach.
- **`celery/bootsteps.py`'s generic step/blueprint framework is
  genuinely reused**, not just an abstract pattern: `worker/components.py`
  defines six concrete subclasses (`Timer`, `Hub`, `Pool`, `Beat`,
  `StateDB`, `Consumer`) that together assemble the actual worker
  startup sequence — confirmed by direct class-hierarchy inspection,
  not asserted from the framework's existence alone.
- **`celery/app/autoretry.py` was found, read, and promoted from a
  weakly-grounded secondary candidate to the primary answer for
  `celery-017` during drafting** (not left for Phase 11 to catch) —
  its `add_autoretry_behaviour` function is a precise, complete match
  for "make a task automatically retry when a specific exception is
  raised," found by following up on a filename that looked too good
  not to check.

## 2. Commit-specific observations

- Version `5.6.2`, released 2026-01-04 per `Changelog.rst`'s own
  `:release-date:` field — directly consistent with `celery/__init__.py`'s
  `__version__` string, a useful cross-check performed during this run.
- Unlike the Click pilot run (which read `CHANGES.md` extensively) or
  the other three runs (which did not read their changelog at all),
  this run made a **deliberate, disclosed middle-ground choice**: read
  only the top ~60 lines of `Changelog.rst` (the 5.6.0-5.6.2 sections),
  enough to identify two specific already-fixed issues relevant to
  query grounding, without attempting the same depth of changelog
  review Click received (which would be disproportionate given
  Celery's much larger overall surface area for a fixed 20-query
  budget).
- Two confirmed already-fixed issues directly shaped query authoring:
  (1) "Fix recursive WorkController instantiation in DjangoWorkerFixup"
  (5.6.2) — avoided as a Bug Fix query target; (2) "Revoked tasks now
  immediately update backend status to REVOKED" (5.6.2) — `celery-003`
  was deliberately written to describe a different, still-open
  scenario (general custom-backend state reporting) rather than this
  specific, already-resolved one, with the distinction explicitly
  recorded in the query's own `notes` field and reinforced in
  `annotation_drafts.jsonl`'s `ambiguity_notes`.
- **The `flaky` pytest marker's real definition lives in
  `t/integration/conftest.py`, not in `pyproject.toml`** (which only
  registers the marker's name for `--strict-markers`), and its
  concrete applications are concentrated in `t/integration/`, which
  `pyproject.toml`'s own `testpaths = "t/unit/"` setting excludes from
  a default `pytest` invocation. Found during the Phase 11 audit
  resolving `celery-013` (see §3) — an example of a fact that a
  surface-level read of configuration alone (the marker's name) would
  not have surfaced without following the mechanism to its actual
  source.

## 3. Annotation difficulties

- **Scale made "primary vs. secondary" harder to judge for
  cross-cutting subsystems.** `celery-009` (worker startup refactor)
  has TWO high-confidence primary candidates (`bootsteps.py` and
  `worker/components.py`) because the generic mechanism and its
  concrete, load-bearing use are both independently central — a
  judgment call flagged for the annotator rather than artificially
  resolved to a single file.
- **`celery-013` was not resolved to a specific file during the
  initial drafting pass** — the `flaky` pytest marker's *name* was
  confirmed directly in `pyproject.toml`, but its actual definition
  and applications were not searched for at that point, leaving this
  query with zero primary candidates going into Phase 7. This is a
  different, more concrete gap than the prior four runs' equivalent
  "no evidence of an actual flaky test was found at all" — here,
  strong evidence a flaky test EXISTS (the marker mechanism) was
  already in hand, just not which one. **The gap was closed during the
  Phase 11 audit**: a direct search of `t/` (not `t/unit/`, which
  turned out to be the wrong location — see §2) found the marker's
  real definition in `t/integration/conftest.py` and 10+ applications
  in `t/integration/test_canvas.py`. See `README.md`'s Phase 11 audit
  for the full account, and note that `validation_report.md`,
  `dataset_statistics.md`, and `annotation_metrics.json` were all
  updated after this resolution to keep every artifact consistent with
  the final state, not the mid-process one.
- **A real duplicate candidate was introduced and caught by Phase 7's
  own validation script**, not by a separate self-review step:
  `celery-020` initially listed the same file twice (once per class
  within it). This is the first pilot run where the validation script
  itself (as opposed to a Phase 11 audit re-read) caught and drove a
  correction — arguably validation working exactly as intended.

## 4. Threats to validity

- **Single-pass AI search, not independently cross-checked** — same
  limitation disclosed in all four prior pilot runs.
- **`kombu` and `billiard` are external dependencies not present in
  this local checkout** — any query whose true root cause lies in
  either (plausible for `celery-001`'s message-chain behavior or
  `celery-004`'s pool-process behavior, both of which interact with
  `kombu`'s async layer or `billiard`'s process pool) cannot be fully
  resolved from this repository alone.
- **Only ~60 lines of `Changelog.rst` were read**, versus a much more
  thorough review for the Click pilot run — a deliberate proportionality
  choice (§2), but it means additional already-fixed issues relevant to
  this run's other 18 queries may exist undetected in the unread
  remainder.
- **144 `t/unit/` test files and 161 package files were overwhelmingly
  existence-confirmed only, not content-read** — a much larger
  fraction than any prior pilot run, an unavoidable consequence of
  fixing the query/search budget at 20 regardless of repository size.
- **No code was executed, no test was run, no bug was reproduced** —
  consistent with all four prior pilot runs' identical limitation.

## 5. Potential reviewer concerns

1. **"Why is package-file coverage (8.7%) so much lower than every
   prior run (47-71%)?"** — Addressed directly in `dataset_statistics.md`
   §9: an expected, size-driven artifact (161 vs. 17-48 files), not
   evidence of weaker search effort. The subpackage-level coverage
   (33%) is offered as a fairer, size-normalized comparison point.
2. **"celery-013 initially had no primary candidate — was that
   incomplete work?"** — At the end of Phase 4/Phase 7 it genuinely
   was incomplete, disclosed as such rather than papered over,
   consistent with this project's established practice (see
   fastapi-013/flask-013/requests-013/click-013) of reporting absence
   of evidence rather than manufacturing a plausible-looking answer.
   The gap was then closed during the Phase 11 audit with a concrete,
   verified finding (see §3), and every downstream artifact was
   updated to reflect the resolved state — a reviewer comparing
   `validation_report.md`'s final numbers against this run's `README.md`
   Phase 11 section should find them consistent, not contradictory.
3. **"Was the celery-020 duplicate a sign of carelessness?"** — It was
   a genuine drafting error, caught by the validation script exactly
   as Phase 7 is designed to do, and corrected with full disclosure in
   `validation_report.md` §3 rather than silently fixed. A reviewer
   should read this as the validation process working, not failing.

## 6. Recommendations

- Before grading begins, run the 10+ `@flaky`-decorated tests in
  `t/integration/test_canvas.py` (and the one in
  `t/integration/test_worker.py`) against the pinned commit to
  determine which is currently, actually unreliable — `celery-013`'s
  remaining open question after the Phase 11 audit.
- Resolve the two directory-level candidates (`celery-004`,
  `celery-005`) to specific files.
- A future round revisiting this repository should specifically target
  the seven entirely-untouched subpackages identified in
  `dataset_statistics.md` §9 (`apps/`, `bin/`, `concurrency/`,
  `contrib/`, `events/`, `fixups/`, `loaders/`) — given Celery's size,
  a single 20-query round can only ever sample a small fraction of it,
  and these seven represent genuinely distinct, unexplored territory
  (CLI commands, execution-pool backends, framework integrations,
  event monitoring) rather than variations on subsystems already
  covered.
- Given this run's positive experiences with autoretry.py (found by
  following up on a promising filename), the celery-020 catch
  (validation script working as intended), and the celery-013
  resolution (a Phase 11 audit turning a disclosed gap into a concrete
  finding, with every affected artifact updated for consistency
  afterward), all three practices — reading a suspiciously-well-named
  file fully before relegating it to secondary status, treating
  validation-script findings as real corrections rather than
  formalities, and treating the Phase 11 audit as a genuine
  opportunity to close gaps rather than a final rubber stamp — are
  worth carrying forward explicitly into future rounds, including the
  eventual sixth and seventh repositories in this project's pilot plan.
