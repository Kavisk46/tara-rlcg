# Reproducibility Package — RTS Dataset v1.0

Phase 9 of the merged-dataset assembly. Everything a second researcher
needs to independently re-derive `queries_master.jsonl`,
`draft_relevance_master.jsonl`, and the `train`/`validation`/`test`
splits from the same 8 repositories' annotation-run artifacts, and to
verify the delivered files are bit-for-bit what this session actually
produced.

## Pinned commits

| Repository | Pinned commit SHA |
|---|---|
| fastapi | `a375f6b948b99fa4260129856bbf11d037f363ef` |
| flask | `6a2f545bfd8ed31e19066a299296917e034aca58` |
| requests | `1f6589ec3a1ee910f9a65cc3ceac60b26677bc0e` |
| click | `00e592cea702e0b2caa0dee42489fdb1c22cd845` |
| celery | `f109abf852525b69a1b6eee0457c6cd5561e0529` |
| sqlalchemy | `dc6a8b18a5bcda653e34aab2a70c7469dcd4300d` |
| pandas | `d0d07d18f9fe855529997e3fe16cf1d0c8ce5eb8` |
| scikit-learn | `9b9be3abddd88675c5dc2e3623e652cb7545a26c` |

Each was re-verified against the corresponding local clone's `git
rev-parse HEAD` at the start of this assembly session (see
`repository_inventory.md` §"Pinned commit verification") — all 8
matched with 0 drift.

## Pipeline version

This is **RTS Dataset v1.0** — the first unified merge of this
project's pilot repository-annotation outputs. It consumes the output
of the (separately versioned) 11-phase per-repository annotation
workflow across 8 sequential sessions, and is itself produced by a
distinct, single 10-phase assembly workflow (Repository Discovery →
Schema Validation → Merge Queries → Merge Draft Relevance → Dataset
Validation → Dataset Statistics → Dataset Split → Dataset Card →
Reproducibility Package → Publication Audit), executed once, in this
session.

## Schema version

`1.0`, per the TARA project's frozen Schema Version declaration. This
merged dataset introduces no new schema — it normalizes the two
field-naming/structural variants found across the 8 source
repositories (see `schema_validation_report.md`) into one canonical
representation, without altering the semantic content of any field.

## Build environment

| | |
|---|---|
| Build timestamp (UTC) | `2026-08-07T17:10:54Z` |
| Python version used for merge/validation scripts | 3.12.6 |
| Operating system | Windows (win32) |
| Merge script | `merge_rts_dataset.py` (ad hoc, not part of any frozen TARA component — a new script written for this assembly session only) |

## Required dependencies

The merge, validation, and split logic in this session used only the
Python standard library: `json`, `os`, `hashlib`, `random`,
`collections` (`Counter`, `defaultdict`). No third-party package
(pandas, numpy, etc.) was used to produce any output file, so
reproducing this exact assembly requires nothing beyond a standard
CPython 3.x interpreter.

## Input digests

SHA-256 of each of the 16 source files actually consumed by this
merge (`queries.jsonl` and `draft_relevance_judgments.jsonl` from each
of the 8 repositories), computed directly against the files as they
exist in `annotation_runs/` at the time of this build:

| File | SHA-256 |
|---|---|
| `fastapi/queries.jsonl` | `99a8c6b722bbecb3623b817f7ac9b68c2ac09390d7bc8cac3a4f3a45eb324c67`[^trunc] |
| `fastapi/draft_relevance_judgments.jsonl` | `f4188011e1403c94b335cfbb118f3a436924e7c274f66081f4bf993f4baecb36`[^trunc] |
| `flask/queries.jsonl` | `cb45f1f90d54cc23e8baefcab2173a1bf3b4c2efa0c64cf1e9f4c8c3a7e816ad`[^trunc] |
| `flask/draft_relevance_judgments.jsonl` | `1015470fca9be1d1b4d40dfdaa456197ba3a811f373f7b698665ef7908fef512`[^trunc] |
| `requests/queries.jsonl` | `7ac39a2435947defe6147954382755316cee331836318e405974a71652302fd7`[^trunc] |
| `requests/draft_relevance_judgments.jsonl` | `13a8d0fb0da9929c559f2184d426e754c5f0da67f881c2694aff90e080bb548b`[^trunc] |
| `click/queries.jsonl` | `c68265e53541f466babb417b785f14189aad15dd298eda1844714616706fb901`[^trunc] |
| `click/draft_relevance_judgments.jsonl` | `7d9513e67eb398eec22af0b895aa6a036585d103ef585a01a006c62e2e357874`[^trunc] |
| `celery/queries.jsonl` | `9d4fca979d63ec8ceb95b0b30438df37adac45ceb784dfaef17ece2875bc090c`[^trunc] |
| `celery/draft_relevance_judgments.jsonl` | `9d0e70706ba09d891e49794eba142bd06ba2cfc7f2797ff44e0e5199888074d6`[^trunc] |
| `sqlalchemy/queries.jsonl` | `0a5d4de9e9a91d230a46161ef0e1ba376cfd2b7165a36f9b331abec6f5be74c4`[^trunc] |
| `sqlalchemy/draft_relevance_judgments.jsonl` | `08bf1d5c823db02912909cce94d8b9e78fd8c5d9e571959d03f2e6ffc6519fa9`[^trunc] |
| `pandas/queries.jsonl` | `cd3bf2ce60b82b118854b701eaafb8471f20f9611fb5410ce94fb6884e163a95`[^trunc] |
| `pandas/draft_relevance_judgments.jsonl` | `bda264e38293ab6e05afd4273d5d792421a66c3ae88072ccfa4d97d8389dfbea`[^trunc] |
| `scikit-learn/queries.jsonl` | `065cec0fd9141bb04dcf6f8e68eea11ab84777cdbd7e484962fa3d4e578c6452`[^trunc] |
| `scikit-learn/draft_relevance_judgments.jsonl` | `2c8ba450eaba3f463ffed166eb86a048bebfd9754d139e006868cd62275192e2`[^trunc] |

[^trunc]: Each digest is a standard 64-hex-character SHA-256 as
    computed by Python's `hashlib.sha256(open(path,
    "rb").read()).hexdigest()`; recompute directly against the source
    files to verify — do not rely on transcription in this table for
    anything beyond a quick sanity check.

**Combined input digest** (SHA-256 of the 16 digests above,
concatenated as hex strings in the fixed order shown, re-hashed):
`a37b0eb968f9583d568e9c9538979cf5e8d0741e179d119465529ff277ed9dab`

## Output digests

SHA-256 of each file this session actually wrote to
`merged_dataset/`:

| File | SHA-256 |
|---|---|
| `queries_master.jsonl` | `51c4458b11c2a3b8f9c803b1ac18236c9947a454ee95c0e63a6cb273bc148273` |
| `draft_relevance_master.jsonl` | `af457ea3d027d71b6e39a0b195f321c9ce5b2eabba0bca50313bc98cb2dee8ea` |
| `train.jsonl` | `bf23e11694230fdf10005c696caf9eeaa181d87abdf3ad61ef25851c6100b6d0` |
| `validation.jsonl` | `94ceb6e37c75ef3da18e4ddde4fead162bc66234d9e3cfba5141b580614ce793` |
| `test.jsonl` | `e2b9b521b5c15b27b402547ede5578b4e0cb29fec0f243288b78c3d50cc7cfc4` |

**Combined output digest** (SHA-256 of the 5 digests above,
concatenated as hex strings in the fixed order shown, re-hashed):
`d249c57936a99c0cfe120b92ea55cb0d3eb702896a850a70b747d5707a73814f`

A second researcher who reproduces this pipeline against the same 16
input files byte-for-byte, using the same merge/split logic described
in `query_merge_report.md`, `relevance_merge_report.md`, and the split
methodology below, should obtain these exact output digests.

## Split methodology and random seed

`train.jsonl` / `validation.jsonl` / `test.jsonl` (112 / 24 / 24 rows,
a 70% / 15% / 15% split) were produced as follows:

1. Fix `SEED = 42` and instantiate one `random.Random(42)` generator.
2. Process the 8 repositories in the fixed order
   `[fastapi, flask, requests, click, celery, sqlalchemy, pandas,
   scikit-learn]` (the mission's "Available Repositories" order).
3. For each repository, take its 20 `query_id`s, **sorted
   lexicographically** (a deterministic starting order, independent of
   file-read order), then shuffle that list in place using the single
   shared `Random(42)` instance (so each repository's shuffle consumes
   the generator's state sequentially, making the overall assignment a
   deterministic function of the fixed repository order + seed, not of
   any parallel or unordered operation).
4. Assign the first 14 shuffled IDs to `train`, the next 3 to
   `validation`, and the last 3 to `test` — an exact 14/3/3 split per
   repository, chosen because it divides each repository's fixed
   20-query contribution evenly into a clean 70/15/15 ratio with no
   remainder.
5. For each assigned `query_id`, build a self-contained record: the
   query's own fields (`query_id`, `repository_id`, `category`,
   `difficulty`, `query_text`, `notes`) plus a `candidates` array of
   every matching row from `draft_relevance_master.jsonl`, sorted by
   `file` path for a deterministic row order.
6. Write each split file with rows sorted by `query_id`.

**Why stratify by repository only, not by category**: each
repository's 20 queries are already fixed at 4/4/3/3/2/2/2 across the
7 categories; splitting a 2-query category 70/15/15 has no clean
integer solution, so this assembly chose to guarantee exact repository
balance (14/3/3 per repository, every split) rather than force an
uneven, less-transparent per-category stratification. The resulting
category distribution per split is reported descriptively in
`dataset_statistics.md`-adjacent split statistics below, not
guaranteed to be exactly proportional.

**Resulting balance** (recomputed directly from the written files):

| Split | Rows | Repository balance | Category distribution | Difficulty distribution |
|---|---|---|---|---|
| train | 112 | 14 per repository (all 8) | bug_fix 22, feature_implementation 23, refactoring 18, testing 20, documentation 13, api_usage 8, code_search 8 | easy 23, medium 68, hard 21 |
| validation | 24 | 3 per repository (all 8) | bug_fix 4, feature_implementation 4, refactoring 3, testing 3, documentation 2, api_usage 4, code_search 4 | easy 7, medium 12, hard 5 |
| test | 24 | 3 per repository (all 8) | bug_fix 6, feature_implementation 5, refactoring 3, testing 1, documentation 1, api_usage 4, code_search 4 | easy 9, medium 12, hard 3 |

**To reproduce**: use CPython (the exact `random.Random` shuffle
algorithm is implementation-specific to CPython's Mersenne Twister
and is not guaranteed to match other Python implementations or major
version lines with a different `random` module implementation);
process repositories in the exact order listed in step 2; sort each
repository's `query_id`s lexicographically before shuffling. Deviating
from any of these three details will produce a different, though
still valid, 70/15/15 split.

## Directory structure

```
evaluation/rts_builder/pilot/
├── annotation_runs/                    (INPUT -- frozen, unmodified by this session)
│   ├── fastapi/            (9 files -- missing annotation_metrics.json)
│   ├── flask/              (10 files)
│   ├── requests/           (10 files)
│   ├── click/              (10 files)
│   ├── celery/             (10 files)
│   ├── sqlalchemy/         (10 files)
│   ├── pandas/             (10 files)
│   └── scikit-learn/       (10 files)
└── merged_dataset/                     (OUTPUT -- produced entirely by this session)
    ├── repository_inventory.md
    ├── queries_master.jsonl
    ├── draft_relevance_master.jsonl
    ├── train.jsonl
    ├── validation.jsonl
    ├── test.jsonl
    ├── schema_validation_report.md
    ├── query_merge_report.md
    ├── relevance_merge_report.md
    ├── validation_report.md
    ├── dataset_statistics.md
    ├── dataset_card.md
    ├── reproducibility.md          (this file)
    └── README.md
```

No file under `annotation_runs/` was created, modified, or deleted by
this assembly session — every artifact under `merged_dataset/` is new
output, and every finding about `annotation_runs/`'s contents (missing
files, schema drift) is a disclosure about pre-existing state, not a
change this session made.
