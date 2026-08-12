# RTS Pilot — Repository Selection Plan

Produced during the scientific-validation planning phase, as a Research
Data Curator deliverable. This is a curation plan, not pipeline code —
it does not modify or extend any subsystem under
`evaluation/rts_builder/`.

## Selection criteria applied

- Python-only (matches Parser's Milestone 2 V1 scope — non-Python
  repositories would fail or degrade in Feature Extraction/Parser).
- Mature (multi-year history) and, to the best of available knowledge,
  actively maintained — **maintenance cadence should be re-verified at
  pin time**; no live lookup was performed to produce this plan.
- Structurally rich: real class hierarchies, decorators, plugin/
  extension points, cross-module imports — the kind of structure
  Feature Extraction's graph/structural features and Retrieval
  Executor's graph strategy are designed to exercise.
- Spread across genuinely distinct domains, not eight variations on
  "web framework."
- Only license identity is asserted below (long-stable, widely
  documented facts about long-established projects). Exact current
  file counts, LOC, and contributor/maintenance activity are **not**
  independently verified here and are marked accordingly — see the
  Verification Checklist (§4).

## 1. The 8 repositories

| # | Repository | GitHub URL | Primary Domain | Approx. Size | License | Reason for Inclusion |
|---|---|---|---|---|---|---|
| 1 | FastAPI | https://github.com/tiangolo/fastapi | Async-first web API framework (Pydantic validation, dependency injection, auto-generated OpenAPI docs) | Medium | MIT | A modern, type-hint-driven API framework architecturally distinct from Flask's WSGI microframework — request/response validation, dependency injection, and async request handling give a different cross-file structure (routing, dependency graphs, Pydantic models) than either Flask or the ORM-focused repositories in this set. |
| 2 | Flask | https://github.com/pallets/flask | Web microframework | Small | BSD-3-Clause | Deliberately minimal core plus a documented extension pattern — a useful small-scale, low-complexity contrast to FastAPI's more structured, type-hint-driven design within the same broad domain (web), good for testing retrieval on shallow repos. |
| 3 | requests | https://github.com/psf/requests | HTTP client library | Small | Apache-2.0 | Compact, single-purpose library; one of the most widely referenced Python packages, good for queries about a focused public API surface rather than a whole application. |
| 4 | pandas | https://github.com/pandas-dev/pandas | Data analysis / dataframes | Large | BSD-3-Clause | Large, heavily-typed, mixed Python/C-extension codebase with a very wide public API — stresses Feature Extraction's structural/resource features differently than a pure-web-framework repo. |
| 5 | scikit-learn | https://github.com/scikit-learn/scikit-learn | Machine learning | Large | BSD-3-Clause | Deep class-inheritance hierarchies (estimator/transformer base classes) — good for exercising Retrieval Executor's graph strategy (inheritance/import graphs) specifically. |
| 6 | Click | https://github.com/pallets/click | CLI tooling / developer tooling | Small | BSD-3-Clause | Decorator-heavy, composition-oriented design distinct from both the web and data-science domains above; small enough to contrast with the Large-category repos in this set. |
| 7 | SQLAlchemy | https://github.com/sqlalchemy/sqlalchemy | Database ORM / toolkit | Large | MIT | A standalone ORM/SQL toolkit (Core vs. ORM layering, dialect abstraction) commonly paired with API frameworks like FastAPI for persistence, since FastAPI itself has no built-in ORM — a structurally distinct data-layer counterpart to the pilot's web-framework repositories, useful for strategy-comparison queries. |
| 8 | Celery | https://github.com/celery/celery | Distributed task queue / async job processing | Medium | BSD-3-Clause | Distinct domain (async/distributed execution) not otherwise represented; broker/backend abstraction layer gives another distinct structural pattern. |

**Caveat on "Size":** these are qualitative judgments from general
knowledge of each project's scope, not measured from a checked-out
commit. Recompute `resource_repository_size_category` from actual
`FeatureExtractionSettings` thresholds once each repository is cloned —
do not treat this column as authoritative.

**Domain-overlap note:** #1/#2/#7 all touch "web/data-layer" broadly,
but at meaningfully different architectural scales and layers
(async-first API framework vs. WSGI microframework vs. standalone
ORM) — flagged here rather than silently presented as fully
independent.

## 2. `manifest.json` schema

Matches `RepositorySpec` exactly, as already defined and frozen in
`evaluation/rts_builder/dataset_builder/DatasetSchema.md` §1.1 — this
plan does not propose any schema change.

| Field | Type | Required | Notes |
|---|---|---|---|
| `repository_id` | string | yes | Stable, unique identifier used throughout every pipeline stage's checkpointing/statistics. |
| `source_url` | string | yes | Passed directly to `RepositoryLoader.load_repository`. |
| `commit_sha` | string | yes | Must be a full 40-character SHA once pinned (`RepositoryLoader`'s own requirement) — use the literal placeholder string `"TO_BE_PINNED"` until then. |
| `metadata` | object (string→string) | no | Free-form, passthrough only — never read or validated by any pipeline stage. Used below to carry domain/size/license/reason for human reference. |

## 3. Example `manifest.json`

```json
[
  {
    "repository_id": "fastapi",
    "source_url": "https://github.com/tiangolo/fastapi.git",
    "commit_sha": "TO_BE_PINNED",
    "metadata": {
      "domain": "web-framework-async-api",
      "size_category": "medium",
      "license": "MIT",
      "reason": "Type-hint/Pydantic-driven async API framework -- dependency injection, request/response validation, auto-generated OpenAPI docs."
    }
  },
  {
    "repository_id": "flask",
    "source_url": "https://github.com/pallets/flask.git",
    "commit_sha": "TO_BE_PINNED",
    "metadata": {
      "domain": "web-framework-micro",
      "size_category": "small",
      "license": "BSD-3-Clause",
      "reason": "Minimal-core microframework, small-scale contrast to FastAPI's more structured, type-hint-driven design within the web domain."
    }
  },
  {
    "repository_id": "requests",
    "source_url": "https://github.com/psf/requests.git",
    "commit_sha": "TO_BE_PINNED",
    "metadata": {
      "domain": "http-client",
      "size_category": "small",
      "license": "Apache-2.0",
      "reason": "Compact, single-purpose, widely-referenced HTTP client library."
    }
  },
  {
    "repository_id": "pandas",
    "source_url": "https://github.com/pandas-dev/pandas.git",
    "commit_sha": "TO_BE_PINNED",
    "metadata": {
      "domain": "data-analysis",
      "size_category": "large",
      "license": "BSD-3-Clause",
      "reason": "Large mixed Python/C-extension codebase with a very wide public API."
    }
  },
  {
    "repository_id": "scikit-learn",
    "source_url": "https://github.com/scikit-learn/scikit-learn.git",
    "commit_sha": "TO_BE_PINNED",
    "metadata": {
      "domain": "machine-learning",
      "size_category": "large",
      "license": "BSD-3-Clause",
      "reason": "Deep estimator/transformer inheritance hierarchies -- exercises graph/inheritance features."
    }
  },
  {
    "repository_id": "click",
    "source_url": "https://github.com/pallets/click.git",
    "commit_sha": "TO_BE_PINNED",
    "metadata": {
      "domain": "cli-tooling",
      "size_category": "small",
      "license": "BSD-3-Clause",
      "reason": "Decorator-heavy, composition-oriented design distinct from the web/data-science repos."
    }
  },
  {
    "repository_id": "sqlalchemy",
    "source_url": "https://github.com/sqlalchemy/sqlalchemy.git",
    "commit_sha": "TO_BE_PINNED",
    "metadata": {
      "domain": "database-orm",
      "size_category": "large",
      "license": "MIT",
      "reason": "Standalone ORM/Core toolkit with dialect abstraction -- commonly used as the persistence layer for API frameworks like FastAPI in practice, which has no built-in ORM of its own."
    }
  },
  {
    "repository_id": "celery",
    "source_url": "https://github.com/celery/celery.git",
    "commit_sha": "TO_BE_PINNED",
    "metadata": {
      "domain": "distributed-task-queue",
      "size_category": "medium",
      "license": "BSD-3-Clause",
      "reason": "Distributed/async job-processing domain, not otherwise represented in this set."
    }
  }
]
```

Note: `RepositoryIterator` will accept this file as-is (it validates
shape, not that `commit_sha` is a resolvable commit) — but
`RepositoryLoader` will fail on `"TO_BE_PINNED"` since it is not a
40-character SHA. **This manifest is not runnable until every
`commit_sha` is pinned.**

## 4. Checklist: pinning commit SHAs before dataset generation

1. **Decide a pinning policy up front and apply it uniformly** — e.g.
   "latest tagged stable release as of pin date" vs. "HEAD of default
   branch as of pin date." Record whichever policy is chosen; mixing
   policies across repositories in the same pilot is a threat-to
   -validity worth avoiding.
2. **Resolve each chosen ref to its full 40-character commit SHA** —
   via `git ls-remote <url> <tag-or-branch>` or the GitHub API, not by
   hand-copying a shortened SHA from a web UI (`RepositoryLoader`
   requires the full 40 characters).
3. **Record how and when each SHA was resolved** — the ref name used,
   the resolution date, and the tool/command used. This is provenance
   for `DATASET_CARD.md`'s Reproducibility section, not optional
   bookkeeping.
4. **Re-verify the license at the pinned commit specifically**, not
   just from the repository's current default-branch `LICENSE` file —
   licenses can (rarely) change between versions, and the
   `metadata.license` value above should reflect the pinned commit's
   actual license file.
5. **Sanity-check the pinned commit is buildable/importable as pure
   Python** — a commit mid-way through an unfinished refactor, or one
   that temporarily broke, would degrade Parser/Feature Extraction
   output quality for every query against that repository.
6. **Replace every `"TO_BE_PINNED"` with its resolved SHA** in
   `manifest.json`.
7. **Recompute and record `input_digest`** — pinning changes
   `manifest.json`'s bytes, so this is a new `input_digest` under the
   Dataset Builder's existing reproducibility mechanism
   (`evaluation/rts_builder/dataset_builder/DatasetSchema.md` §2.6);
   do not treat the pre-pin and post-pin manifests as interchangeable.
8. **Run `RepositoryIterator` over the pinned manifest as a dry-run
   validation step** before full dataset generation — it fails fast
   (`ManifestError`) on shape/duplicate-`repository_id` problems,
   cheaply, before any clone/parse work begins.
9. **Commit the pinned `manifest.json` to version control** (or
   otherwise archive it) as the authoritative, citable input for this
   pilot — an unpinned or silently-re-pinned manifest breaks the
   reproducibility guarantee the rest of the pipeline is built around.
