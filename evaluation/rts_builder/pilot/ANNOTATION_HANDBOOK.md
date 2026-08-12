# TARA RTS Pilot — Query Annotation Handbook

## 1. Purpose

This handbook guides human annotators writing the developer queries for
the RTS Pilot Dataset's 8 selected repositories (see
`REPOSITORY_SELECTION_PLAN.md`). A query in this dataset is a
**realistic developer request or question about a specific
repository**, later used to drive Feature Extraction, Retrieval
Executor, and Oracle Utility. Query quality directly determines
dataset quality — a vague or unrealistic query produces uninformative
retrieval-quality signal no matter how good the underlying retrieval
strategies are.

**Target volume:** 20–25 queries per repository, distributed across
the 7 categories below. A suggested per-category target (adjust per
repository as natural fit allows — do not force an unnatural query into
a category just to hit a number):

| Category | Target count |
|---|---|
| Bug Fix | 3–4 |
| Feature Implementation | 3–4 |
| Refactoring | 3 |
| Testing | 3 |
| API Usage | 3–4 |
| Documentation | 2–3 |
| Code Search | 3 |

## 2. General principles (apply to every category)

- **Ground the query in the repository's actual domain**, but do not
  assert specific implementation facts you have not personally
  verified by reading the code at the pinned commit. If you have not
  opened the file, do not claim to know what it contains.
- **Write as a developer would actually ask, not as a test-case
  author would.** "Fix the bug in the retry logic when a connection
  times out" reads naturally; "Verify that function X returns Y when
  input Z is provided" does not.
- **One query, one intent.** Do not bundle a bug fix and a
  documentation request into the same query text.
- **Avoid repository-internal jargon the query itself would need to
  already know the answer to.** A query that names the exact private
  function to change is not really testing retrieval — it's handing
  the answer to the system being evaluated.
- **Length matters less than specificity.** A short, specific query
  ("Fix incorrect timezone handling when parsing ISO 8601 strings with
  no offset") is better than a long, vague one.
- **Every query must be answerable from the repository's own source
  at the pinned commit** — not from general Python/library knowledge,
  and not from external documentation the repository itself doesn't
  contain.

## 3. Category guides

### 3.1 Bug Fix

**Definition:** A request to correct code that produces incorrect,
unexpected, or crashing behavior.

**What makes a good query**
- Describes an observable symptom (wrong output, exception, crash),
  not a guessed root cause.
- Specifies enough context (inputs, conditions) to make the bug
  reproducible in principle.
- Reflects a plausible real-world usage scenario for that repository's
  domain.

**What makes a poor query**
- States the fix instead of the symptom ("Change the `if` condition
  on line 42 to use `<=` instead of `<`") — this presupposes the
  answer.
- Is symptom-free ("There's a bug somewhere in the parser") — nothing
  for retrieval to latch onto.
- Describes behavior that isn't actually a bug (a documented
  limitation, or expected behavior under invalid input).

**Examples** *(generic — adapt to each repository's real domain,
without asserting unverified internal details)*
- "Fix the crash that occurs when `<operation>` is called with an
  empty `<collection type>`."
- "`<component>` silently returns an incorrect result instead of
  raising when given a malformed `<input type>`."
- "Requests to `<feature>` intermittently fail under concurrent
  access — investigate and fix the race condition."

**Common mistakes**
- Writing the query as an imperative code-change instruction rather
  than a bug description.
- Copy-pasting a real issue-tracker title verbatim without confirming
  it still reproduces at the pinned commit.
- Describing a bug in a dependency, not in the repository itself.

**Quality checklist**
- [ ] Describes a symptom, not a fix.
- [ ] Plausible for this repository's actual domain.
- [ ] Does not name the specific function/line to change.
- [ ] Reproducible in principle from the description given.

---

### 3.2 Feature Implementation

**Definition:** A request to add new functionality that does not
currently exist.

**What makes a good query**
- Describes a capability gap in terms of user-visible behavior, not
  internal design.
- Is scoped to something plausibly reviewable as a single change (a
  new method, option, or small subsystem) — not "add support for
  everything X does."
- Fits naturally within the repository's existing domain and
  conventions.

**What makes a poor query**
- Requests a feature the repository almost certainly already has
  (check first, or phrase generically enough to be safe).
- Is so large in scope it isn't really one feature ("rewrite the
  entire configuration system").
- Prescribes the exact API shape ("add a method
  `do_thing_v2(x, y, z=None)`") rather than describing the need.

**Examples**
- "Add support for `<a plausible new input/output format>` when
  `<performing some existing operation>`."
- "Allow `<a configurable behavior>` to be overridden per-call instead
  of only at initialization."
- "Add an option to `<existing operation>` that produces `<a
  reasonable variant of its current output>`."

**Common mistakes**
- Describing a feature request that is actually a bug fix in disguise
  ("fix" framed as "add correct handling for...").
- Requesting something out of scope for the repository's actual
  domain (e.g. a UI feature for a pure library).
- Being too vague to distinguish from a dozen other possible features.

**Quality checklist**
- [ ] Describes user-visible need, not implementation.
- [ ] Scoped to a single, reviewable unit of work.
- [ ] Plausibly not already present (to the annotator's knowledge).
- [ ] Fits the repository's actual domain.

---

### 3.3 Refactoring

**Definition:** A request to restructure or clean up existing code
*without* changing its external behavior.

**What makes a good query**
- Names a code-quality concern (duplication, unclear naming,
  excessive complexity, tight coupling) in general terms.
- Is behavior-preserving by nature — nothing about the query should
  imply new functionality.
- Points at a kind of code (e.g. "the error-handling in `<area>`"),
  not a specific verified construct.

**What makes a poor query**
- Actually requests a behavior change dressed up as refactoring.
- Is so generic it could apply to almost any codebase ("clean up the
  code") — no retrieval signal at all.
- Prescribes the exact refactored structure ("extract this into a
  class named `FooHandler`").

**Examples**
- "Simplify the duplicated `<kind of logic>` that appears in multiple
  places handling `<some operation>`."
- "Reduce the complexity of `<a described area of functionality>`
  by breaking it into smaller, more focused pieces."
- "Improve naming consistency across `<a described group of related
  functions/classes>`."

**Common mistakes**
- Blurring the line with Feature Implementation by sneaking in new
  behavior.
- Targeting something too small to be meaningfully "refactored" (a
  single one-line function).
- Assuming a specific existing structure the annotator hasn't verified.

**Quality checklist**
- [ ] Explicitly behavior-preserving.
- [ ] Names a genuine code-quality concern, not a vague generality.
- [ ] Does not prescribe the resulting structure.
- [ ] Distinct in intent from a bug fix or feature request.

---

### 3.4 Testing

**Definition:** A request to write new tests, extend test coverage, or
fix a broken/flaky test.

**What makes a good query**
- Specifies what behavior needs coverage, in terms of the feature or
  edge case, not the exact test function to write.
- Reflects a realistic testing gap (edge cases, error paths, a
  described feature area) rather than "add more tests" generically.
- For flaky/broken-test queries: describes the symptom (intermittent
  failure, outdated assertion) plausibly, not a guessed cause.

**What makes a poor query**
- Asks for a specific test file/function by exact name the annotator
  has not verified exists or doesn't exist.
- Is indistinguishable from a generic "improve test coverage"
  instruction with no scoping.
- Requests tests for behavior that would itself require a Feature
  Implementation first.

**Examples**
- "Add test coverage for `<operation>`'s behavior when given
  `<a described edge-case input>`."
- "The existing tests for `<described feature area>` don't cover the
  error path when `<a plausible failure condition>` occurs — add
  coverage."
- "Investigate and fix the intermittently failing test related to
  `<described feature area>`."

**Common mistakes**
- Writing a query that is really a bug-fix request wearing a testing
  label.
- Naming a specific test file/class without having confirmed it
  exists at the pinned commit.
- Being too broad ("write more tests for the whole module").

**Quality checklist**
- [ ] Scoped to a specific behavior or edge case, not "more tests" in general.
- [ ] Does not name unverified specific test identifiers.
- [ ] Clearly a testing task, not a relabeled bug fix or feature.

---

### 3.5 API Usage

**Definition:** A question about how to correctly use an existing
public API, function, or class — not a request to change code.

**What makes a good query**
- Phrased as a genuine "how do I..." or "what is the correct way
  to..." question a real user of the library would ask.
- Targets a plausibly public-facing capability of the repository, not
  an internal implementation detail.
- Answerable by pointing to the right code + its usage pattern, not
  by writing new code.

**What makes a poor query**
- Is actually a bug report or feature request in disguise.
- Asks about a capability that plausibly isn't public API at all.
- Is answerable purely from general Python knowledge, without needing
  this repository's specific code at all.

**Examples**
- "How do I configure `<a described capability>` when using
  `<a described component>`?"
- "What is the recommended way to `<perform a plausible common task>`
  with this library?"
- "How should `<a described object/class>` be extended or
  subclassed to customize `<some behavior>`?"

**Common mistakes**
- Writing a query answerable entirely from generic Python/library
  conventions, giving retrieval nothing repository-specific to find.
- Asking about a private/internal mechanism no real user would be
  expected to interact with directly.
- Conflating "how do I use X" with "please implement X for me."

**Quality checklist**
- [ ] A genuine usage question, not a disguised bug/feature request.
- [ ] Requires this repository's actual code to answer, not just general knowledge.
- [ ] Targets plausibly public-facing functionality.

---

### 3.6 Documentation

**Definition:** A request to write, correct, or improve documentation —
docstrings, README content, usage guides, or inline comments.

**What makes a good query**
- Identifies a plausible documentation gap or inaccuracy in terms of
  what a reader would need but not find.
- Scoped to a describable area (a feature, a module's public API), not
  "document everything."
- Distinguishes clearly between "missing" and "incorrect" documentation
  if that distinction matters to the request.

**What makes a poor query**
- Requests documentation for something that would first require a
  Feature Implementation.
- Is unscoped ("improve the docs").
- Asks for documentation of an internal detail no public consumer
  would need.

**Examples**
- "Add usage documentation for `<a described public capability>`
  that currently has no explained example."
- "The docstring for `<a described component>` doesn't mention what
  happens when `<a plausible edge case>` — update it."
- "Write a short usage guide for `<a described common workflow>`
  using this library."

**Common mistakes**
- Targeting internal/private code that shouldn't have user-facing
  documentation in the first place.
- Being so broad the query provides no retrieval signal.
- Requesting documentation that would require guessing undocumented
  behavior rather than describing existing, verifiable behavior.

**Quality checklist**
- [ ] Targets a specific, describable documentation gap.
- [ ] Concerns public-facing (not internal-only) functionality.
- [ ] Does not require inventing behavior to document.

---

### 3.7 Code Search

**Definition:** A pure navigational request — "find where X is
implemented/defined/handled" — with no implied change.

**What makes a good query**
- Asks to locate functionality described in behavioral terms ("where
  is `<described behavior>` implemented"), not by an exact,
  pre-known identifier.
- Reflects a genuine "I need to find this before I can work on it"
  developer moment.
- Has a plausible, findable answer within the repository.

**What makes a poor query**
- Already names the exact file/class/function being searched for —
  nothing left to retrieve.
- Is answerable by "it's not in this repository" (asks about
  functionality that belongs to a dependency).
- Is really a disguised API-usage or bug-fix query.

**Examples**
- "Where is `<a described behavior>` implemented in this codebase?"
- "Find the code responsible for `<a described cross-cutting
  concern, e.g. input validation for X>`."
- "Locate where `<a described configuration option>` is read and
  applied."

**Common mistakes**
- Naming the target identifier directly, collapsing the query into a
  trivial exact-match lookup.
- Searching for something that lives in a dependency, not this
  repository.
- Overlapping so closely with an API Usage query that the category
  distinction is lost — Code Search is about *locating*, API Usage is
  about *how to use once found*.

**Quality checklist**
- [ ] Describes behavior/functionality, not an exact identifier.
- [ ] The answer plausibly exists within this repository.
- [ ] Distinct in intent from an API Usage question.

---

## 4. `queries.jsonl` schema (annotation stage)

This is the **annotator-facing** schema — richer than the pipeline's
final input format, to support tracking, review, and quality control
before ground-truth relevance grades are added in a separate pass (see
§5).

| Field | Type | Required | Description |
|---|---|---|---|
| `query_id` | string | yes | Stable identifier assigned by the annotator or tooling at write time (e.g. `<repository_id>-<sequential number>`). Used for tracking/review only — not part of the frozen pipeline schema. |
| `repository_id` | string | yes | Must match a `repository_id` in the pilot's `manifest.json` exactly. |
| `category` | string | yes | One of: `bug_fix`, `feature_implementation`, `refactoring`, `testing`, `api_usage`, `documentation`, `code_search`. |
| `difficulty` | string | yes | One of `easy`, `medium`, `hard` (see definitions below). |
| `query` | string | yes | The developer query text itself, written per the guidance above. |
| `notes` | string | no | Annotator notes: rationale, uncertainty flags, suggested-but-unconfirmed relevant areas, or anything a reviewer should know. Never treated as ground truth. |

**Difficulty levels**

| Level | Definition |
|---|---|
| `easy` | Answerable by inspecting a single function or file in isolation. |
| `medium` | Requires understanding a small group of related files, or a class together with its direct usages. |
| `hard` | Requires reasoning across multiple modules, a non-trivial call chain, or broader architectural understanding. |

**Example (illustrative placeholders only — not a real repository claim):**

```jsonl
{"query_id": "example-repo-001", "repository_id": "example-repo", "category": "bug_fix", "difficulty": "medium", "query": "Fix the crash that occurs when the configuration loader is given an empty file.", "notes": "Symptom-based; annotator has not identified the specific file responsible."}
{"query_id": "example-repo-002", "repository_id": "example-repo", "category": "code_search", "difficulty": "easy", "query": "Where is input validation performed before a request is processed?", "notes": "Pure navigation query, no implied change."}
```

## 5. Relationship to the pipeline's `queries.jsonl` input

This annotation-stage file is **not** what `QueryIterator` consumes
directly. The frozen `QuerySpec` schema
(`evaluation/rts_builder/dataset_builder/DatasetSchema.md` §1.2)
requires `repository_id`, `query_text`, and `relevance_grades`. The
mapping is:

- `query` (this handbook) → `query_text` (pipeline input).
- `relevance_grades` is **not** produced by query-writing annotators
  at this stage — it is added in a separate, subsequent relevance
  -annotation pass, by an annotator (or process) working directly
  against the repository's actual files at the pinned commit, per the
  project's established convention that ground-truth relevance is an
  externally-supplied input.
- `query_id`, `category`, `difficulty`, and `notes` are retained
  separately as **tracking/review metadata** — they are useful for
  annotation QA and later dataset analysis (e.g. per-category/per
  -difficulty breakdowns) but are not part of the pipeline's required
  input schema. If retained downstream, they should be attached via
  `QuerySpec`-external bookkeeping (e.g. a side table keyed by
  `repository_id` + `query_text`), not by modifying the frozen schema.

## 6. Pre-submission checklist (per repository)

- [ ] 20–25 queries total, spread across all 7 categories per the
      suggested targets in §1.
- [ ] No two queries are near-duplicates of each other in intent.
- [ ] Every query passes its category's quality checklist (§3).
- [ ] No query asserts a specific internal implementation detail the
      annotator has not personally verified at the pinned commit.
- [ ] No query already contains its own answer (exact file/function
      names, prescribed fixes, prescribed API shapes).
- [ ] `query_id` values are unique within the repository.
- [ ] `category` values use exactly the 7 defined labels (no
      free-text variants).
- [ ] `difficulty` is assigned thoughtfully, not defaulted to one
      value for every query.
