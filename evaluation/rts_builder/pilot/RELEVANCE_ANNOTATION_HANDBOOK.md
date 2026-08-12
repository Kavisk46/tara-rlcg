# TARA RTS Pilot — Relevance Judgment Annotation Handbook

## 1. Purpose

This handbook governs how human annotators produce
`relevance_judgments.jsonl`: for every developer query in
`queries.jsonl` (see `ANNOTATION_HANDBOOK.md`), the set of source files
a developer would need to consult or modify to resolve that query, each
graded on a 0–3 relevance scale. These are the ground-truth labels
Oracle Utility's Recall@k/MRR/NDCG/Context Precision computations
depend on entirely — the dataset's scientific validity rests on this
protocol being applied consistently.

**This document defines a protocol, not a set of labels.** No actual
relevance judgment for any real file in any of the pilot's 8
repositories is asserted anywhere in this handbook — every example
below uses placeholder file paths and a fictional example repository.

**Relevance grades**

| Grade | Label | Meaning |
|---|---|---|
| 0 | Not relevant | No bearing on resolving the query; a developer would not open this file. |
| 1 | Slightly relevant | Tangential — touched incidentally, or provides minor supporting context, but not central to resolving the query. |
| 2 | Relevant | A file a developer would clearly need to read or modify; contains directly related logic but is not the primary locus of the change. |
| 3 | Highly relevant | The primary file(s) where the core logic or change lives — what the query is fundamentally "about." |

## 2. How to decide relevance

**The test to apply, per candidate file:** *"Would a competent
developer, actually resolving this query, need to open this file —
either to understand context or to make a change?"* Grade is a
function of how central that need is, not of file size, prominence, or
how interesting the file looks.

**Procedure:**

1. Read the query text and restate, privately, what a developer would
   actually need to do to resolve it.
2. Search the repository broadly before grading anything — by
   filename, by keyword/grep on terms from the query, by following
   imports from an obvious starting point, and by checking for
   relevant tests. **Recall matters as much as precision**: a
   relevance set that only contains the first file you happened to
   find is a common and serious annotation failure.
3. For every candidate file surfaced by that search, assign a grade
   using the table in §1 — do not default to "relevant" for everything
   the search turned up; a file appearing in a grep match is not
   automatically even grade 1.
4. Explicitly consider test files. For **Testing**-category queries,
   the relevant test file(s) are often the highly-relevant (3) target.
   For other categories, a test file that would need updating
   alongside an implementation change is typically grade 1–2, not 3 —
   the implementation is still the primary locus unless the query is
   specifically about the tests themselves.
5. Write a short rationale for every file graded 1 or above (see §9's
   schema) — a grade with no rationale is not acceptable for
   submission.

**Grading files with mixed relevant/irrelevant content:** the schema
grades whole files, not lines or functions. If the relevant content is
a small fraction of an otherwise-unrelated, large "grab-bag" file, grade
conservatively (typically 1–2, not 3) — retrieving that whole file
still provides worse practical context than a focused file would, which
is exactly what Oracle Utility's `context_precision` metric is designed
to penalize.

**Generated, vendored, or migration code:** grade 0 (i.e., omit — see
§9) by default, unless the query is specifically about that generated
content. Retrieval performance over auto-generated code is not
representative of the research question this dataset supports.

## 3. Multi-file relevance

Most queries have more than one relevant file — an interface and its
implementation, a caller and callee, an implementation and its
directly-affected test. Annotators must identify the **complete**
relevant set, not stop at the first plausible file.

- Not every relevant file gets the same grade. A typical query might
  have one or two files at grade 3 (the true focal point), a small
  number at grade 2 (directly involved but secondary), and a few at
  grade 1 (tangential context).
- **Avoid grade inflation.** Do not grade every file a feature module
  happens to touch as highly relevant. If you find yourself grading
  more than roughly 8–10 files as relevant (grade ≥ 1) for one query,
  stop and reconsider: either the underlying query was scoped too
  broadly (flag it back to query authoring — see
  `ANNOTATION_HANDBOOK.md`), or grades are inflated and should be
  revisited.
- A query legitimately having **zero** relevant files above grade 0 is
  possible but rare (e.g. a query about functionality this repository
  turns out not to have). Do not let this happen silently — see §8's
  validation rule for empty relevance sets.

## 4. Tie handling

**Ties between files at the same grade are expected and correct — do
not artificially break them.** If two files are genuinely equally
central to resolving a query, both should receive the same grade
(commonly both at grade 3). NDCG and the other Oracle Utility metrics
are designed for graded, tie-permitting relevance; inventing an
arbitrary ranking between two equally-relevant files to "avoid a tie"
actively corrupts the ground truth.

**When genuinely torn between two *adjacent* grades for the same file**
(e.g. unsure whether a file is a 2 or a 3), the default is to **choose
the lower grade**. Over-grading (false positives in the relevant set)
distorts Recall@k/Context Precision more harmfully than a single file
being graded one level conservatively — this is a deliberate,
documented bias toward precision in the ground truth itself, and
should be applied consistently, not case-by-case.

This is a different concept from `StrategyOracleRow.tied_with`
(Oracle Utility's own, separately-computed notion of *strategies* tying
on `utility_score`) — nothing in this section concerns that mechanism.

## 5. Ambiguous cases

- **A query plausibly admits more than one reasonable interpretation.**
  Grade relevance for every plausible interpretation you identify while
  searching, not just the first one you thought of — and record the
  ambiguity explicitly in `notes`. If the ambiguity changes the grade
  of two or more files by a full level or more, flag the query itself
  for review rather than resolving it unilaterally; the query may need
  to be rewritten for specificity (see `ANNOTATION_HANDBOOK.md` §2).
- **A file is relevant only under one interpretation.** Grade according
  to the most natural, most likely reading a real developer would take,
  and note the alternative interpretation and its effect on grading.
- **Uncertain whether a file counts as "the repository's own code" vs.
  vendored/generated content.** Default to treating anything not
  hand-maintained by the project's own contributors as out of scope
  (grade 0 / omit) — see §2.

## 6. Inter-annotator disagreement

**Double annotation.** At minimum, a stratified sample of queries (and
ideally all queries, budget permitting) should be independently graded
by two annotators before either sees the other's judgments.

**What counts as disagreement requiring adjudication:**
- Any file where the two annotators' grades differ by 2 or more levels
  (e.g. one says 0/omitted, the other says 2 or 3).
- Any file graded relevant (≥ 1) by one annotator that the other
  annotator's candidate search did not even surface — this is a
  **recall** disagreement, not just a grading disagreement, and is
  treated with equal seriousness.

A difference of exactly one grade level (e.g. 2 vs. 3) on a file both
annotators did identify is common and not automatically escalated,
though it still contributes to the agreement metric below.

**Adjudication process.** A third annotator — ideally more senior or
otherwise not involved in either original pass — reviews every flagged
disagreement independently, makes a final determination, and records a
written rationale. The adjudicator's grade becomes the value in the
final aggregated `relevance_judgments.jsonl` (see §9); it does not
average or split the difference between the two original grades.

**Agreement metric.** Report a **quadratic-weighted Cohen's kappa**
per repository (and overall) across all double-annotated queries —
weighted, not simple/unweighted kappa, because a 2-vs-3 disagreement is
a much smaller failure than a 0-vs-3 disagreement and the metric should
reflect that. Report this figure in `DATASET_CARD.md`'s Threats to
Validity section once computed; it is a property of the actual
annotation run and cannot be stated in advance by this protocol
document.

A query with persistently low agreement across annotators, even after
adjudication, is itself a signal — it likely means the query is
ambiguous or the repository's relevant code is inherently ambiguous for
that request, and should be flagged in `notes` even after a final grade
is recorded.

## 7. Quality control

- **Calibration before independent work begins.** All annotators
  jointly grade a small shared practice set (not drawn from the 8
  pilot repositories) and discuss discrepancies against this handbook
  before starting independent annotation, so grade definitions are
  aligned up front rather than discovered as systematic bias later.
- **Spot-check auditing.** A QC reviewer re-examines a random sample
  (recommended: at least 10%) of completed, single-annotated judgments
  against this handbook's criteria, independent of the double
  -annotation/adjudication process in §6.
- **Annotator-level statistics.** Track, per annotator: average number
  of files graded relevant per query, average grade given, and time
  spent per query. Outliers (e.g. an annotator who grades nearly every
  candidate a 3, or completes judgments implausibly fast) should be
  flagged for review or recalibration, not silently accepted.
- **Automated structural checks run before any judgment is accepted**
  — see §8; these are necessary but not sufficient for quality (they
  catch schema violations, not bad-but-well-formed judgments).
- **Every judgment file is versioned.** Corrections after initial
  submission go through a recorded revision (who changed what, and
  why), never a silent, untracked edit — consistent with this
  project's broader reproducibility discipline
  (`dataset_builder/README.md`'s Reproducibility Guarantees).

## 8. Validation rules

Automatically checkable, before `relevance_judgments.jsonl` is merged
into the pipeline's `queries.jsonl`:

- Every grade in the **final aggregated** file must be in `{1, 2, 3}`
  — grade `0` is never written explicitly in the final file; a file's
  absence from `relevance_grades` *is* its grade-0 status, per
  `RelevanceJudgment.relevance_grades`'s own established convention
  ("a file absent from this mapping is not relevant"). A `0` value
  found in the final file is a schema violation, not a valid judgment.
- Grades must be whole numbers in `{1, 2, 3}`, even though the
  underlying field type is `float` (`dict[str, float]`, matching
  `RelevanceJudgment`). The float type exists for downstream schema
  flexibility, not to invite intermediate values like `1.5` — this
  protocol does not use fractional grades.
- Every `file_path` key must exist in the repository's tree at the
  exact pinned `commit_sha` — a relevance grade for a nonexistent path
  is a hard error, not a warning.
- File paths must be relative to the repository root and use forward
  slashes, matching the convention already established in
  `dataset_builder/DatasetSchema.md`'s `queries.jsonl` examples.
- Every `(repository_id, commit_sha, query_text)` triple in
  `relevance_judgments.jsonl` must have a matching entry in the
  query-writing output (`ANNOTATION_HANDBOOK.md`'s `queries.jsonl`) —
  no orphaned relevance judgments, and no query left without one.
- No query may have an empty `relevance_grades` mapping without an
  explicit, reviewed justification recorded in `notes` — a silently
  empty relevance set is far more likely to be an annotation gap than a
  genuine finding (a genuine "this repository has no relevant code for
  this query" case is legitimate but should be rare and always
  reviewed; Oracle Utility's own documented behavior for a query with
  no relevant files is `quality_score = 0.0`, not an error).
- The majority of queries should have **at least one** file graded 3.
  A query with only grade-1/2 files and nothing at grade 3 is not
  automatically wrong, but is a QC flag worth a second look — it can
  indicate either a genuinely diffuse query or under-grading.

## 9. `relevance_judgments.jsonl` schema

Two related files, produced in sequence: raw per-annotator judgments
(the working artifact §6's disagreement/adjudication process operates
on), and the final aggregated file (what actually merges into the
pipeline's input).

### 9.1 Raw per-annotator judgments (working artifact, pre-adjudication)

| Field | Type | Required | Description |
|---|---|---|---|
| `query_id` | string | yes | Matches the `query_id` from `ANNOTATION_HANDBOOK.md`'s `queries.jsonl`. |
| `repository_id` | string | yes | Must match a `repository_id` in the pilot's `manifest.json`. |
| `commit_sha` | string | yes | The pinned commit this judgment was made against. |
| `query_text` | string | yes | Copied from the query record, for auditability without a join. |
| `annotator_id` | string | yes | Stable identifier for the annotator who produced this record. |
| `file_judgments` | array of objects | yes | One entry per candidate file the annotator explicitly considered: `{"file_path": string, "grade": int (0-3), "rationale": string}`. Unlike the final file, grade `0` **is** recorded here explicitly — it documents that a candidate was considered and rejected, which is valuable QC signal distinct from a file never having been searched for at all. |
| `search_method` | string | no | Brief description of how candidates were found (grep terms used, starting file, etc.) — supports recall auditing. |
| `time_spent_minutes` | number | no | For the annotator-statistics QC check in §7. |
| `notes` | string | no | Ambiguity flags, uncertainty, anything a reviewer or adjudicator should know. |

```jsonl
{"query_id": "example-repo-001", "repository_id": "example-repo", "commit_sha": "<40-char sha>", "query_text": "Fix the crash that occurs when the configuration loader is given an empty file.", "annotator_id": "ann-01", "file_judgments": [{"file_path": "<path/to/config_loader.py>", "grade": 3, "rationale": "Primary file implementing configuration loading; the crash described would originate here."}, {"file_path": "<path/to/config_schema.py>", "grade": 1, "rationale": "Defines the schema the loader validates against; may need a related check but is not the primary fix location."}, {"file_path": "<path/to/unrelated_module.py>", "grade": 0, "rationale": "Considered via grep for 'config' but unrelated to file loading specifically."}], "search_method": "grep for 'config' and 'load', then followed imports from the CLI entry point", "time_spent_minutes": 6, "notes": ""}
```

### 9.2 Final aggregated file (pipeline-facing)

| Field | Type | Required | Description |
|---|---|---|---|
| `query_id` | string | yes | Tracking/review metadata only — not part of the frozen `RelevanceJudgment` schema (see §10). |
| `repository_id` | string | yes | Matches `RelevanceJudgment.repository_id`. |
| `commit_sha` | string | yes | Matches `RelevanceJudgment.commit_sha`. |
| `query_text` | string | yes | Matches `RelevanceJudgment.query_text`. |
| `relevance_grades` | object (string → number) | yes | `file_path -> grade`, grades in `{1, 2, 3}` only (see §8) — this object, unchanged, becomes `RelevanceJudgment.relevance_grades` / the corresponding entry in `QuerySpec.relevance_grades`. |
| `contributing_annotator_ids` | array of strings | yes | Every annotator whose raw judgment fed this result. |
| `inter_annotator_agreement` | number or null | no | Per-query agreement figure if double-annotated; `null` if single-annotated. |
| `adjudicated` | boolean | yes | Whether a disagreement required §6's adjudication process. |
| `adjudicator_id` | string or null | no | Set iff `adjudicated` is `true`. |
| `notes` | string | no | Carried-forward ambiguity/QC notes relevant to the final result. |

```jsonl
{"query_id": "example-repo-001", "repository_id": "example-repo", "commit_sha": "<40-char sha>", "query_text": "Fix the crash that occurs when the configuration loader is given an empty file.", "relevance_grades": {"<path/to/config_loader.py>": 3, "<path/to/config_schema.py>": 1}, "contributing_annotator_ids": ["ann-01", "ann-02"], "inter_annotator_agreement": 0.87, "adjudicated": false, "adjudicator_id": null, "notes": ""}
```

## 10. Relationship to the pipeline's `queries.jsonl` input

Neither file in §9 is consumed directly by `QueryIterator`. The final
merge step combines, per `(repository_id, query_text)`:

- `query_text` from `ANNOTATION_HANDBOOK.md`'s query-writing output, and
- `relevance_grades` from §9.2's final aggregated file,

into one `QuerySpec` record matching
`dataset_builder/DatasetSchema.md` §1.2 exactly. `query_id`,
`contributing_annotator_ids`, `inter_annotator_agreement`,
`adjudicated`, `adjudicator_id`, and `notes` are retained as external
tracking/provenance metadata (e.g. for `DATASET_CARD.md`'s Threats to
Validity section) — they are **not** added as fields on the frozen
`QuerySpec`/`RelevanceJudgment` schemas. This mirrors exactly how
`ANNOTATION_HANDBOOK.md` §5 already handles `query_id`/`category`/
`difficulty` for the query-writing side.

## 11. Pre-submission checklist (per repository)

- [ ] Every query in `queries.jsonl` has exactly one corresponding
      entry in the final aggregated `relevance_judgments.jsonl`.
- [ ] Every `file_path` verified to exist at the pinned `commit_sha`.
- [ ] Every grade in the final file is an integer in `{1, 2, 3}` —
      no `0`s, no fractional values.
- [ ] Every relevant file has a rationale recorded in the raw
      per-annotator file it originated from.
- [ ] Any query with zero relevant files has an explicit, reviewed
      justification in `notes`.
- [ ] Double-annotation coverage and adjudication completed per §6 for
      the agreed sample (or all queries).
- [ ] Per-repository inter-annotator agreement computed and recorded.
- [ ] Annotator-level QC statistics (§7) reviewed for outliers.
- [ ] No relevance label anywhere in this handbook or its examples is
      a real judgment about a real file in any of the 8 pilot
      repositories.
