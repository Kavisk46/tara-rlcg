# Research Notes — Requests Pilot Annotation Run

Reflective notes from constructing this pilot run against Requests at
commit `1f6589ec3a1ee910f9a65cc3ceac60b26677bc0e`. Observations and
judgments, not additional data — everything factual referenced here
was already established in `repository_summary.md`,
`annotation_drafts.jsonl`, or `validation_report.md`.

## 1. Interesting repository findings

- **`hooks.py` contains a literal, self-acknowledged limitation in its
  own source comment**: `HOOKS: list[str] = ["response"]` followed by
  `# TODO: response is the only one`. This is the strongest-grounded
  feature query in this entire run (requests-005) — the gap it
  addresses is stated by the codebase itself, not inferred by search.
- **A confirmed, precise gap in `Session`'s default-attribute set**:
  `Session.__init__` sets persistent defaults for nine distinct
  settings (headers, auth, proxies, hooks, params, verify, cert,
  max_redirects, trust_env, stream) but not `timeout` — grounding
  requests-007 in a directly-verified absence, not a guess about what
  might be missing.
- **A confirmed structural asymmetry in the auth classes**:
  `HTTPBasicAuth` defines `__eq__`/`__ne__` (inherited by
  `HTTPProxyAuth`), while `HTTPDigestAuth` independently redefines its
  own — grounding requests-011 in a directly-observed inconsistency,
  not a presumed one.
- **This repository has no `docs_src/`-style executable-example
  directory (FastAPI) and no `examples/` directory (Flask)** —
  documentation here is prose-`.rst`-only. This is the third distinct
  documentation-organization pattern observed across three pilot runs,
  worth noting as a genuine structural difference in this project's
  target repositories, not a deficiency of Requests specifically.

## 2. Commit-specific observations

- Version `2.34.2` at this pinned commit (`src/requests/__version__.py`).
- Dependency versions pinned in `pyproject.toml`
  (`urllib3>=1.26,<3`, `certifi>=2023.5.7`, `idna>=2.5,<4`,
  `charset_normalizer>=2,<4`) bound how confidently any
  encoding/certificate/URL-handling query (requests-004, requests-008,
  requests-015, requests-019) can be attributed to this repository
  alone versus its dependencies — see §3.
- `tests/test_adapters.py`'s single existing test explicitly
  references `https://github.com/psf/requests/issues/6643` in its
  docstring — a concrete, citable link between this repository's test
  suite and its own issue-tracker history, found by direct read, not
  inferred.
- No commit-specific architectural change on the scale of Flask's
  3.2 `RequestContext`/`AppContext` merge (found in the prior pilot
  run) was discovered here — `HISTORY.md` was not read in this pass
  (see Threats to Validity), so this is a statement about what was
  found, not a claim that no such change exists.

## 3. Annotation difficulties

- **The external-dependency boundary problem recurred a third time**,
  now for `urllib3`/`certifi`/`idna`/`charset_normalizer`. Four of this
  run's 20 queries (requests-001/adapters wrapping urllib3's
  connection pooling, requests-004/encoding detection possibly
  delegating to charset_normalizer, requests-008/certs.py wrapping
  certifi, requests-015/documentation of the same) have some plausible
  root-cause exposure outside this repository. This is now a
  consistent pattern across all three pilot runs (FastAPI/Starlette,
  Flask/Werkzeug, Requests/urllib3+certifi+idna+charset_normalizer) —
  see `research_notes.md`'s Recommendations for a proposed mitigation.
- **`requests-008` required resolving a "is this already implemented?"
  question mid-search** — the existing, documented `verify=` parameter
  already covers passing a custom CA bundle path, which materially
  overlaps with what the query asks for. Flagged explicitly rather
  than silently either dropping the query or asserting a gap that may
  not exist.
- **No dedicated test files exist for cookies, auth, or sessions** —
  unlike FastAPI/Flask, where most subsystems had at least one small,
  focused test file, Requests concentrates most of its test coverage
  into one 3,094-line `test_requests.py`. This made regression-test
  candidates for requests-002/003/006/012 weaker (existence-confirmed
  only, specific test functions not enumerated) than the equivalent
  candidates in either prior run.

## 4. Threats to validity

- **Single-pass AI search, not independently cross-checked** — same
  limitation disclosed in both prior pilot runs.
- **`urllib3`, `certifi`, `idna`, `charset_normalizer` are external
  dependencies not present in this local checkout.** Any query whose
  true implementation lives in one of them cannot be fully resolved
  from this repository alone.
- **`HISTORY.md` (66KB) was not read in this pass.** Given Flask's
  prior pilot run found its single most important fact (the context
  merge) embedded in a docstring that happened to be read for an
  unrelated reason, it is plausible `HISTORY.md` contains a comparably
  important fact this run did not surface.
- **`test_requests.py` (3,094 lines) and `test_utils.py` (1,013 lines)
  were never opened in this pass** — both are large enough that
  meaningful undiscovered content (existing coverage, or its absence)
  is likely. Every candidate referencing either file is
  existence-confirmed only.
- **No code was executed, no test was run, no bug was reproduced** —
  consistent with both prior pilot runs' identical limitation.

## 5. Potential reviewer concerns

1. **"Why is average candidate count (2.35) noticeably lower than the
   other two repositories (4.05, 3.10)?"** — Addressed directly in
   `dataset_statistics.md` §4: attributed to Requests' smaller
   codebase, not to shallower search effort. A reviewer comparing
   raw counts across repositories without normalizing for codebase
   size could otherwise draw the wrong conclusion.
2. **"Why do `api.py` and `exceptions.py` — both prominently described
   in `repository_summary.md` — have zero queries?"** — Disclosed
   directly in `dataset_statistics.md` §9 as a genuine gap between
   architectural description and actual query coverage, not hidden or
   rationalized away.
3. **"Is `requests-008` a real feature gap or not?"** — Explicitly
   flagged as unresolved (§7 of `validation_report.md`); a reviewer
   should not find this ambiguity discovered independently and treated
   as a defect this run failed to catch — it is disclosed prominently
   in four separate artifacts.

## 6. Recommendations

- Before grading begins, hold a short adjudication pass specifically on
  requests-008 and requests-013 (this run's two speculative queries),
  mirroring the recommendation made in both prior pilot runs' research
  notes.
- Given the external-dependency boundary problem has now recurred in
  all three pilot runs on different dependency pairs (Starlette,
  Werkzeug, and now urllib3/certifi/idna/charset_normalizer), this is
  no longer a one-off observation but a pattern worth addressing at
  the project level: consider whether future annotation runs should
  have read-only access to each target repository's key runtime
  dependencies, specifically to resolve "is the true root cause in
  this repository or its dependency" questions that recurred in
  fastapi-002, flask-001/008, and requests-001/004/008/015 alike.
- A future round revisiting this repository should specifically target
  `src/requests/api.py` and `src/requests/exceptions.py` — both
  architecturally significant (per `repository_summary.md`) and
  entirely absent from this run's 20 queries (per
  `dataset_statistics.md` §9).
- Consider reading `HISTORY.md` (or at least its most recent entries)
  in a future round for this repository, given the precedent set by
  Flask's context-merge discovery.
