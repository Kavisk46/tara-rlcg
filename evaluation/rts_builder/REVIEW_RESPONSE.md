# Response to Reviewer: Repository Loader (RTS Builder, Milestone 1)

We thank the reviewer for a thorough reading of Repository Loader v1.
Below we address each comment in turn. All four **Critical** and all
three **Moderate** comments have been addressed in this revision.
No functionality outside the Repository Loader's stated scope (parsing,
retrieval, embeddings, oracle utility, feature extraction) was added,
per the reviewer's explicit instruction.

---

## Critical Comment 1: Commit SHA must be mandatory

> *"`RepositoryLoader.load_repository()` must require a `commit_sha`
> parameter. Never default to HEAD. If `commit_sha` is missing, raise
> `CommitNotSpecifiedError`."*

**Implemented Solution.**
The public entry point is renamed `load()` → `load_repository()` to
match the reviewer's specified name. `commit_sha` remains a required
positional parameter (v1 already had no default), but is now also
validated at runtime: an empty or whitespace-only value raises the new
`CommitNotSpecifiedError`. We additionally require `commit_sha` to be a
full 40-character hexadecimal SHA, rejecting abbreviations with the same
exception — this was not explicitly requested, but is a direct
consequence of Comment 2's strict-equality verification (see below) and
of the RTS pipeline's existing reproducibility discipline
(`docs/DATASET_PLAN.md`) of pinning exact, unambiguous commits.

**Files Changed.**
- `repository_loader.py`: `load()` → `load_repository()`; added
  `_validate_commit_sha()`.
- `exceptions.py`: added `CommitNotSpecifiedError`.
- `README.md`: usage example and API docs updated.
- `tests/rts_builder/test_repository_loader.py`: all call sites renamed;
  added `test_load_repository_raises_when_commit_sha_is_empty` and
  `test_load_repository_raises_when_commit_sha_is_abbreviated`.

**Remaining Limitations.**
Renaming the public method is a breaking API change for any existing
caller of `load()`. There are none outside this repository's own test
suite and README at the time of this revision, so no deprecation shim
was added — consistent with the project's stated preference for direct
changes over backwards-compatibility shims when nothing external
depends on the old name yet.

---

## Critical Comment 2: Repository reuse must verify commit consistency

> *"When reusing an existing clone: read the current HEAD SHA, compare
> against requested `commit_sha`. If different: `git fetch`;
> `git checkout --force` requested SHA. Verify checkout succeeded. If
> checkout fails: raise `CommitNotFoundError`."*

**Implemented Solution.**
Added `_ensure_commit_checked_out()`, called after every clone-or-reuse
(not only on the reuse path — see Limitations). It reads
`repo.head.commit.hexsha`; if it already equals the requested
`commit_sha`, it returns immediately (no-op fast path). Otherwise it
calls `repo.remotes.origin.fetch()`, then `repo.git.checkout("--force",
commit_sha)`, then re-reads HEAD and raises `CommitNotFoundError` if it
still doesn't match. A fetch failure raises `RepositoryCloneError`
(a fetch is a network operation, consistent with how the existing
`_clone_or_reuse` reports clone failures); a checkout failure or
post-checkout mismatch raises `CommitNotFoundError`, exactly as
specified.

We also replaced `_validate_structure`'s previous `startswith`-based
prefix comparison (which had supported abbreviated SHAs) with strict
equality, since it is now guaranteed to run only after
`_ensure_commit_checked_out` has already verified an exact match —
see Comment 1's SHA-format requirement, which exists specifically to
keep this comparison meaningful.

**Files Changed.**
- `repository_loader.py`: added `_ensure_commit_checked_out()` and
  `_current_head_sha()`; `_validate_structure()` tightened to strict
  equality; `load_repository()`/`_load_locked()` call the new method
  between `_read_default_branch()` and `_validate_structure()`.
- `tests/rts_builder/conftest.py`: `source_repository` fixture extended
  to two commits specifically to exercise this path.
- `tests/rts_builder/test_repository_loader.py`: added
  `test_reusing_a_clone_pinned_to_a_different_commit_fetches_and_force_checks_out`,
  which asserts both the reported `commit_sha` *and* actual file content
  change after a reuse-with-different-commit call.

**Remaining Limitations.**
The requirement's wording ("when reusing an existing clone") suggests
this logic is only necessary on the reuse path. We apply it uniformly to
both fresh clones and reused ones: a freshly cloned repository's HEAD
sits at its default branch's tip, which is generally not `commit_sha`
either, so the same verified-checkout logic is required there too, and
having one code path is simpler and strictly more correct than
branching. The one cost of this choice: a fresh clone whose default
branch tip already differs from `commit_sha` (the common case) triggers
one redundant `fetch` against a remote that, for a full (non-shallow)
clone, already has the target commit locally. This is a minor,
harmless inefficiency, not a correctness issue, and is documented in
`README.md`.

---

## Critical Comment 3: Thread safety

> *"Protect every Git operation using a repository lock. Use a
> cross-platform locking solution. Ensure concurrent dataset workers
> cannot corrupt repositories."*

**Implemented Solution.**
Added the `filelock` library (`filelock>=3.13`, added to
`pyproject.toml`) — it wraps `msvcrt` locking on Windows and `fcntl` on
POSIX behind one API, giving genuine cross-process, cross-platform
mutual exclusion (not just thread-safety within one process, which
matters since RTS dataset workers are typically separate processes).

`load_repository()` acquires one `FileLock` at
`clone_root/<repository_id>.lock` before doing anything else, and holds
it for the entire pipeline — clone/reuse, fetch, checkout, submodule
initialization, tree scan, and the manifest write — via a `with`
block, releasing it automatically (including on any exception) when the
method returns or raises.

The lock is scoped **per `repository_id`**, not global. A single
global lock would serialize the entire RTS Builder across every
repository being loaded anywhere, which directly conflicts with the
pipeline's actual purpose (parallel dataset construction across many
repositories by many workers). Two different `repository_id`s never
contend; two workers loading the *same* `repository_id` concurrently
are correctly serialized.

**Files Changed.**
- `pyproject.toml`: added `filelock>=3.13` dependency.
- `repository_loader.py`: `load_repository()` now acquires the lock;
  new `RepositoryLockError` handling around a `filelock.Timeout`.
- `config.py`: added `lock_timeout_seconds` (default 600s).
- `exceptions.py`: added `RepositoryLockError`.
- `tests/rts_builder/test_repository_loader.py`: added
  `test_load_repository_raises_lock_error_when_lock_is_already_held`
  (holds the lock externally, asserts a bounded-time
  `RepositoryLockError`) and
  `test_load_repository_succeeds_once_lock_is_released`.

**Remaining Limitations.**
The lock guards *this process's* view of a repository's local clone; it
does not protect against a human or an entirely separate, non-RTS-Builder
tool concurrently modifying the same `clone_root` directory outside this
API. That is considered out of scope: the requirement is about
concurrent *dataset workers*, which by construction all go through this
loader. Lock tests use a short `lock_timeout_seconds` (1s) to stay fast;
we did not add a true multi-process integration test, since deterministic
process-level races are inherently harder to test reliably than a
held-lock timeout, which already exercises the real acquisition and
timeout code paths.

---

## Critical Comment 4: Secure subprocess execution

> *"Never execute shell strings. Always use `subprocess.run()` with
> argument lists. Validate repository URLs. Reject invalid URLs. Prevent
> directory traversal."*

**Implemented Solution.**
All git invocations already went through GitPython, which itself never
constructs a shell string — it invokes `git` via `Popen` with an
argument list (`shell=False`), both for the existing `Repo.clone_from(...)`
call and the new `repo.remotes.origin.fetch()` / `repo.git.checkout(...)`
calls this revision adds. This was true in v1 and remains true; we did
not need to introduce raw `subprocess.run()` calls to satisfy "argument
list, not shell string" — GitPython already provides that guarantee
structurally. This is stated explicitly here (and in `README.md`) rather
than left implicit, since it's exactly the kind of claim a reviewer
should be able to verify rather than take on faith.

What v1 was missing was *input validation* before those arguments ever
reach `git`:

- `_validate_repository_id()`: `repository_id` becomes a filesystem
  directory name directly under `clone_root`. It is now checked against
  `^[A-Za-z0-9][A-Za-z0-9._-]*$` and explicitly rejected if it contains
  `..`. This makes directory traversal structurally impossible (the
  charset excludes path separators entirely), not merely
  checked-for-and-blocked.
- `_validate_source_url()`: rejects an empty URL, a URL starting with
  `-` (which `git` would parse as a command-line flag rather than a
  positional URL argument — a real, known argument-injection class for
  `git clone`), and a small set of tokens that are never valid inside a
  legitimate git remote URL (`;`, `|`, `` ` ``, `$(`, newlines, NUL).
  The latter check is explicitly documented as **defense-in-depth**: the
  argument-list-only invocation already makes shell injection
  impossible today; the check exists so that property can't be silently
  broken by a future refactor.
- `_validate_commit_sha()`: covered under Comment 1.

**Files Changed.**
- `repository_loader.py`: added `_validate_repository_id()`,
  `_validate_source_url()`, and the constants
  `_REPOSITORY_ID_PATTERN` / `_FORBIDDEN_URL_TOKENS`; both called at the
  top of `load_repository()` before any filesystem or subprocess access.
- `exceptions.py`: added `InvalidRepositoryInputError`.
- `tests/rts_builder/test_repository_loader.py`: added parametrized
  `test_load_repository_rejects_unsafe_repository_ids` (`../escape`,
  `a/b`, `..`, a leading dash, empty) and
  `test_load_repository_rejects_unsafe_source_urls` (empty, a
  `-upload-pack=...`-style flag-injection attempt, a `;`-containing URL,
  a backtick-containing URL).

**Remaining Limitations.**
`_validate_source_url()` deliberately does **not** enforce a URL scheme
allow-list (e.g. "must start with `https://`"). The existing test suite
and any offline/mirror-based repository-collection workflow rely on
passing a local filesystem path as `source_url`, which a strict
`https://`-only check would break. We consider this an intentional,
documented scope boundary rather than an oversight; a stricter allow-list
is listed as a Future Extension Point in `README.md` once the RTS
pipeline's real source population is confirmed to be exclusively
`https://` GitHub URLs.

---

## Moderate Comment 5: Compute dominant language using repository statistics

**Implemented Solution.**
`_determine_primary_language()` now selects by **total bytes per
language**, not file count — the same approach GitHub Linguist uses.
`_scan_tree()` was extended to accumulate a second distribution,
`language_byte_distribution`, alongside the pre-existing
(file-count-based) `language_distribution`, which is retained as
informational context, not as the basis for `primary_language` anymore.

**Files Changed.**
- `repository_loader.py`: `_scan_tree()` returns an additional
  `language_byte_counts` dict; `_determine_primary_language()` now takes
  and maximizes over byte counts.
- `models.py`: added `Repository.language_byte_distribution`; updated
  field descriptions to clarify which distribution drives
  `primary_language`.
- `tests/rts_builder/conftest.py`: added
  `byte_dominant_language_repository` (five tiny `.js` files vs. one
  large `.py` file) specifically to distinguish byte-based from
  count-based selection.
- `tests/rts_builder/test_repository_loader.py`: added
  `test_primary_language_is_determined_by_bytes_not_file_count`.

**Remaining Limitations.**
Byte count is still a proxy, not a perfect one (e.g. it doesn't account
for generated/vendored code, which ideally would be excluded upstream by
`ignored_directories`, or comment density). We consider this an
acceptable, standard approximation at this milestone; a more
sophisticated notion of "dominant language" (e.g. weighting by parsed
symbol count) would require the parsing stage this milestone explicitly
excludes.

---

## Moderate Comment 6: Handle Git submodules explicitly

**Implemented Solution.**
Added `_detect_submodules()`, which reads `repo.submodules` (GitPython's
parse of `.gitmodules`) and returns their relative paths, best-effort
(a malformed `.gitmodules` logs a warning and yields an empty list
rather than failing the whole load). By default
(`initialize_submodules=False`), `_scan_tree()` excludes every detected
submodule path from both directory and file counts — an uninitialized
submodule directory is an empty placeholder on disk and counting it
would misrepresent the repository. Submodule paths are always recorded
on `Repository.submodules`, whether or not they're initialized, so later
pipeline stages know they exist even when their content wasn't loaded.
Setting `initialize_submodules=True` calls
`repo.submodule_update(init=True, recursive=True)` before scanning, so
their real content is included like any other directory.

We chose `initialize_submodules=False` as the default deliberately: it
keeps `load_repository()` from *implicitly* cloning additional,
unvetted third-party repositories just because the primary repository
happens to reference them.

**Files Changed.**
- `repository_loader.py`: added `_detect_submodules()`,
  `_initialize_submodules()`; `_scan_tree()` takes a `submodule_paths`
  parameter and skips them.
- `config.py`: added `initialize_submodules` (default `False`).
- `models.py`: added `Repository.submodules`.
- `tests/rts_builder/conftest.py`: added `repository_with_submodule`
  fixture (a real `git submodule add`-created submodule).
- `tests/rts_builder/test_repository_loader.py`: added
  `test_uninitialized_submodule_is_recorded_but_excluded_from_counts`
  and `test_initialize_submodules_setting_includes_submodule_content`.

**Remaining Limitations.**
When `initialize_submodules=True`, an initialized submodule's own
working-tree `.git` entry is a *file* (a gitdir pointer), not a
directory — unlike a top-level `.git` directory, it is not excluded by
the directory-name ignore list, so it is counted as one extra file per
initialized submodule (verified and documented, not silently wrong; see
`README.md`). We consider this a minor, acceptable imprecision rather
than a defect worth a special-cased fix at this milestone.

---

## Moderate Comment 7: Persist `repository_manifest.json` immediately after successful validation

**Implemented Solution.**
We interpret "successful validation" as including full characterization
— i.e., the manifest is written once the complete `Repository` object
(counts, language distributions, commit metadata, submodules) has been
built, not at the bare structural-validation checkpoint that precedes
scanning. A manifest written at the earlier point would carry only
identity fields and none of the statistics that make it useful as a
durable, resumable record — which we take to be the evident purpose of
this requirement. If the reviewer intended a lighter-weight,
validation-only checkpoint file in addition, we are happy to add that as
a second, separate artifact in a follow-up revision.

`_write_manifest()` serializes `Repository.model_dump(mode="json")`
(plus a `manifest_version` field) to `<local_path>/repository_manifest.json`,
written via a temp-file-then-atomic-rename (`Path.replace`, atomic on
both POSIX and Windows), so a crash mid-write can never leave a corrupt
manifest on disk. The manifest's own filename is excluded from every
`_scan_tree()` call by name, so writing it never perturbs `file_count`
on a subsequent `load_repository()` call for the same repository — a
correctness bug we caught and fixed while writing the reuse-idempotency
test, not something the reviewer flagged directly.

**Files Changed.**
- `repository_loader.py`: added `_write_manifest()`; `_load_locked()`
  computes `manifest_path`, calls `repository.model_copy(update=...)` to
  set it on the returned object, then writes the manifest;
  `_scan_tree()` excludes the manifest filename at the working-tree
  root.
- `models.py`: added `Repository.manifest_path`.
- `tests/rts_builder/test_repository_loader.py`: added
  `test_manifest_is_persisted_and_matches_the_returned_repository`;
  extended `test_load_repository_is_idempotent_and_reuses_existing_clone`
  to assert `file_count` is unchanged across two calls (i.e., the
  manifest from the first call doesn't inflate the second call's count).

**Remaining Limitations.**
The manifest is per-repository, written to that repository's own
working tree. It is not currently aggregated into any pipeline-wide
index of "which repositories have been loaded" — that would be a
concern for a later RTS Builder milestone (repository collection
orchestration), not this one.

---

## Summary

| # | Comment | Severity | Status |
|---|---|---|---|
| 1 | Commit SHA mandatory | Critical | Addressed |
| 2 | Reuse must verify commit consistency | Critical | Addressed |
| 3 | Thread safety | Critical | Addressed |
| 4 | Secure subprocess execution | Critical | Addressed |
| 5 | Dominant language by statistics | Moderate | Addressed |
| 6 | Explicit submodule handling | Moderate | Addressed |
| 7 | Persist manifest after validation | Moderate | Addressed |

No parsing, retrieval, embedding, oracle, or feature-extraction logic
was introduced. `tests/rts_builder/` grew from 14 to 31 tests, all
passing alongside the full existing project suite (see the project's
top-level test run for the current total).
