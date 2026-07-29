# TARA Task Taxonomy: Semantic Reference

**Status:** Semantic reference document. **Not a routing specification.**

## Purpose and scope

This document defines six software-engineering task categories in terms of *what a developer means* when they issue that kind of query against a repository, and *what information a retrieval system would need* to serve that intent well. It exists to sharpen shared understanding of task semantics — for classifier design, for dataset annotation (e.g., TIQS, see `PROJECT_SPEC.md` §22), and for reasoning about retrieval quality — independent of any specific implementation.

**This document deliberately does not specify routing decisions.** It does not say "Bug Fix → strategy X" or name any `RoutingStrategy` / `RetrieverKind` value from the implemented system. "Expected retrieval priorities" below describes *what kind of information matters most and why*, in qualitative terms a human or a future policy designer can reason about — it is an input to routing design, not a routing rule itself. Mapping these semantics onto concrete retrieval strategies is a separate, later design decision and is out of scope here.

**Relationship to `tara.core.types.TaskType`:** the implemented classifier (`PROJECT_SPEC.md` §17) uses a 13-member taxonomy tuned for routing (`SEARCH`, `EXPLAIN`, `DEBUG`, `BUG_FIX`, `REFACTOR`, `GENERATE`, `TEST`, `DOCUMENTATION`, `ARCHITECTURE`, `DEPENDENCY_ANALYSIS`, `SECURITY`, `PERFORMANCE`, `UNKNOWN`). The six categories below are not a 1:1 replacement for that enum. Some overlap loosely (Refactoring ↔ `REFACTOR`, Documentation ↔ `DOCUMENTATION`, Test Generation ↔ `TEST`); others do not (Feature Implementation is narrower than `GENERATE`; **API Usage has no current analog** in the implemented taxonomy and is treated here as a distinct semantic category worth naming explicitly, since "how do I correctly call X" is a materially different information need from both "explain X" and "build something new"). Reconciling or extending the implemented enum against this document is a future decision, not an implication of this document.

---

## 1. Bug Fix

### Intent
The developer has identified an existing behavior that deviates from expected/correct behavior and wants to locate the root cause and correct it. This is a *diagnostic-then-corrective* task: success requires causal reasoning over existing code (why does this happen?) before any code is changed, and the correction must not introduce new regressions.

### Typical developer queries
- "Fix the crash when parsing empty files"
- "Why does `get_user_by_id` return `None` for valid ids?"
- "This test is failing intermittently — what's going on?"
- "The login form throws a 500 error when the password field is empty"
- "Users report that pagination skips the last page"

### Required repository context
- The specific function/module implicated by an error message, stack trace, or symptom description, when one is given
- Call sites / callers of the implicated function, to understand the conditions under which it is invoked
- Existing tests exercising the implicated behavior — these reveal expected behavior and sometimes an exact reproduction case
- Recent modification history for the implicated file or function, where available (bugs disproportionately trace to recently changed code)
- Data-model / schema definitions relevant to the failure, when the bug involves malformed or unexpected data
- Error-handling and logging code near the failure point

### Important retrieval signals
- Verbatim identifiers or literal strings from stack traces / error messages — exact-match retrieval matters heavily here, since a stack trace names exact functions and lines
- File paths mentioned or implied by the query
- Symptom-descriptive language ("crash," "returns None," "throws," "intermittent," "off by one") that hints at *where in the causal chain* the defect sits, without naming the defect itself
- Control-flow/call relationships, since root cause is frequently upstream of the observed symptom
- Recency signals, where retrievable, since the most recently touched code near a symptom is disproportionately likely to be implicated

### Potential retrieval failures
- Retrieving only the symptom location and missing the root cause, which may sit several call-frames upstream
- Over-indexing on literal error-message vocabulary and missing conceptually related code that doesn't share that vocabulary
- Missing the relevant test file, which often states *intended* behavior most clearly
- Retrieving a stale or superseded code path in a codebase with multiple implementations of similar functionality
- Conflating a bug report about *misuse* of a correctly-implemented API with a bug in the *implementation itself* — these require different context and a different fix location

### Expected retrieval priorities
Precision on the exact implicated symptom location matters most — an approximate match wastes a diagnostic pass. Beyond that, priority shifts toward *causally upstream* context (callers, dependencies, data flow) over merely *topically similar* context, because the task is tracing a causal chain, not surveying related functionality. Existing tests for the implicated area are high-value because they encode expected behavior explicitly, functioning as a correctness oracle rather than illustrative material. Depth along the causal path matters more than breadth across the codebase.

---

## 2. Feature Implementation

### Intent
The developer wants to add new capability that does not yet exist in the requested form. Unlike Bug Fix (correcting existing behavior against an existing, if implicit, spec), this is generative and additive: success requires understanding enough of the existing system to integrate new code consistently with it, without there being any specific existing defect to reason about.

### Typical developer queries
- "Add support for exporting reports as PDF"
- "Implement a caching layer for the retriever"
- "Add a `--dry-run` flag to the CLI"
- "We need rate limiting on the public API endpoints"
- "Create a new endpoint for bulk user import"

### Required repository context
- Existing implementations of *structurally similar* features, to establish the codebase's conventions (how are new CLI flags typically wired up? how are new endpoints typically registered?)
- The extension point(s) the new feature must integrate with — a router, a registry, a base class meant to be subclassed
- Configuration and dependency-injection wiring, since a new feature typically needs to be constructed and registered somewhere, not only implemented in isolation
- Relevant data models / schemas the new feature will read from or write to
- Existing tests for structurally similar features, as a template for how the new feature should be tested

### Important retrieval signals
- Domain terminology from the request mapped onto existing concepts (e.g., "export," "report," "PDF" — code handling adjacent concepts like other export formats is highly relevant even if nothing does *this exact thing* yet)
- Architectural/structural keywords ("endpoint," "flag," "middleware," "handler," "plugin") that point to a codebase *pattern* to follow, more than to any single file
- Interface / abstract-base-class definitions, since new implementations typically must conform to an existing contract
- Directory and module conventions (where do similar things live?), even absent strong textual similarity
- Configuration files and settings objects likely to need a new entry

### Potential retrieval failures
- Retrieving code that is topically related by keyword overlap but architecturally irrelevant (e.g., matching "export" in an unrelated logging utility rather than the actual report-generation subsystem)
- Missing the *convention-setting* example — failing to surface the one analogous existing feature that should serve as the implementation template, especially when it doesn't share vocabulary with the request
- Retrieving too narrowly (a single file) when feature work typically requires touching several coordinated locations (model, handler, registration, tests, docs)
- Missing structural (not nominal) extension points — e.g., a class that must be registered in a factory dict elsewhere, which no keyword or embedding similarity to the request would surface without following references
- Retrieving deprecated or half-migrated versions of a pattern in a codebase that is mid-refactor

### Expected retrieval priorities
Structural coverage and exemplar completeness take priority over narrow precision: this task benefits more from seeing one or two well-chosen analogous implementations *end-to-end* (model, logic, registration, and test) than from many narrowly keyword-matched fragments. Discovering the codebase's conventions matters at least as much as discovering any specific reusable code. Because "the new code" has no existing implementation to retrieve, the retrieval target is necessarily a *proxy* (an analogous feature) rather than a ground-truth location — a distinction that separates this task's retrieval objective from Bug Fix's.

---

## 3. Refactoring

### Intent
The developer wants to change the *internal structure* of existing code without changing its externally observable behavior — improving readability, reducing duplication, changing an implementation strategy, or preparing code for an upcoming change. Success requires a complete and accurate picture of everything that depends on the code being changed, since an incomplete picture risks silently breaking a caller.

### Typical developer queries
- "Refactor `RepositoryParser` to reduce duplication between the sync and async paths"
- "Extract the validation logic in `UserService` into its own class"
- "Rename `getData` to `fetchUserProfile` across the codebase"
- "Split this 800-line module into smaller files"
- "Replace the custom retry loop with the `tenacity` library"

### Required repository context
- The complete definition of the symbol(s) being refactored (full source, not only the signature)
- Every call site / usage of the symbol(s) being refactored across the entire repository, not only the local module — this is the single most safety-critical context need for this task
- Subclasses, interface implementations, or other structural relationships (inheritance, protocol conformance) that a signature or behavior change would break
- Existing tests covering the affected code, as the primary safety net establishing "behavior preserved"
- Any public API surface / exported-symbol boundary the refactor must not silently change, if the symbol is part of the package's public contract

### Important retrieval signals
- Exact symbol identity — this task needs *every* occurrence of a specific symbol, not a topically similar sample, so precise identity matching outweighs semantic similarity
- Import statements and re-export chains, since a symbol may be referenced under an alias or via a re-export
- Structural/graph relationships (class hierarchies, interface implementations) over purely textual similarity
- Test file naming/location conventions that typically co-locate with the module under test
- Explicit "public API" markers (e.g., `__all__`, package-level exports) indicating higher blast-radius risk

### Potential retrieval failures
- Incomplete recall of call sites — even one missed usage is a correctness risk in a way that is more forgiving for, e.g., Documentation or Feature Implementation
- Missing indirect usages: calls through dynamic dispatch, reflection/dynamic-attribute access, or a re-exported alias that doesn't textually match the original name
- Conflating a same-named symbol in an unrelated scope (shadowing) with the actual target
- Accurately finding *existing* tests but failing to signal that some usage has *no* test coverage — itself critical information for assessing refactor risk
- Under-weighting cross-file/cross-package structural relationships relative to file-local context, precisely where refactoring risk concentrates

### Expected retrieval priorities
Recall and completeness dominate over precision for "find every usage": a refactor with 95% of call sites found is materially more dangerous than one with 70% found and explicitly flagged as incomplete, because silent gaps are the failure mode, not noisy-but-visible false positives. Structural/relational retrieval (call graph, type hierarchy) matters disproportionately relative to topical similarity, since what breaks in a refactor is structurally connected to the changed symbol, not merely related to it in subject matter. Tests covering the change are high priority as a correctness oracle, not merely as illustrative context.

---

## 4. API Usage

### Intent
The developer wants to understand *how to correctly call or integrate with* an existing function, class, module, or dependency already present in (or used by) the repository. This is a comprehension task oriented toward correct invocation — it sits between pure explanation ("what does X do") and generative work ("build something new using X").

### Typical developer queries
- "How do I use the `Embedder` interface to add a new embedding provider?"
- "What arguments does `RetrievalPlanner.plan` expect?"
- "How is `TaraSettings` supposed to be configured?"
- "What's the correct way to construct a `RepositoryContext` in a test?"
- "How do other parts of the codebase call the FAISS index?"

### Required repository context
- The full signature and docstring of the API in question (parameters, types, return value, documented exceptions)
- The abstract interface/contract the API belongs to, if any — usage requirements are often defined at the interface level rather than the concrete implementation
- Multiple *existing call sites* of the same API elsewhere in the codebase, which collectively demonstrate idiomatic usage more reliably than the definition alone
- Factory, builder, or dependency-injection wiring that constructs the objects involved, since correct usage often depends on how an object is expected to be obtained, not only how its methods are called
- Related configuration or environment requirements the API implicitly depends on (required settings, required prior initialization)

### Important retrieval signals
- The exact symbol name being asked about — near-mandatory exact match, since the question concerns one specific, named thing
- Docstrings and type annotations at the definition site, unusually high-value text for this task relative to others
- Call-site frequency and diversity — an API called in several different ways across the codebase is a stronger collective usage signal than any single call site
- Test files exercising the API, which often demonstrate minimal/canonical usage more clearly than production call sites entangled with unrelated business logic
- Import-graph position (what the API imports, and is imported by), establishing where it fits in the system

### Potential retrieval failures
- Retrieving the definition with no example call sites, leaving a correct-but-underspecified signature and no idiomatic usage pattern
- Retrieving an outdated or deprecated overload/version of a symbol in a codebase with multiple historical variants of a similarly-named API
- Conflating a same-named API from an external dependency with a same-named internal symbol, especially in dynamically-typed languages
- Missing implicit preconditions (required setup, ordering constraints, required configuration) that live only in prose documentation or in the pattern of existing call sites, not in the signature
- Surfacing call sites that themselves represent incorrect or legacy usage, with no signal distinguishing canonical from incidental usage

### Expected retrieval priorities
The definition/signature/docstring is the anchor and must be retrieved with high precision, but is insufficient alone — retrieval should favor a *small number of representative call sites* over either the bare definition or an exhaustive, undifferentiated list of every call site (contrast with Refactoring, where exhaustiveness of usages is itself the priority; here, representativeness and clarity are). Test-based usage examples should be weighted at least as highly as production call sites, since they tend to be more minimal and pedagogically clear. Structural signals (what constructs this, what this depends on) matter secondarily, to fill in implicit setup requirements the signature alone doesn't state.

---

## 5. Documentation

### Intent
The developer wants to produce or improve human-readable explanatory material about existing code — a docstring, a README section, an architecture note, an inline comment — without changing the code's behavior. This is fundamentally a summarization-and-explanation task grounded in accurately understanding what the code already does and why.

### Typical developer queries
- "Write a docstring for `GraphBuilder.build`"
- "Document the routing policy design in the README"
- "Add comments explaining why `_module_stem` strips leading dots"
- "Generate API documentation for the `context` package"
- "Explain the retry logic in `SentenceTransformerEmbedder` for a design doc"

### Required repository context
- The full implementation of the symbol(s) being documented, including any non-obvious control flow or edge-case handling that documentation should surface
- Existing docstrings/comments nearby, to match the codebase's established documentation style and terminology
- The symbol's callers/usages, to understand which aspects of its behavior are actually load-bearing for other code — documentation should emphasize what matters to callers, not merely restate the implementation
- Related design-decision context where available (commit messages, existing ADRs, related README sections), since good documentation of non-obvious code typically needs the rationale, not only the mechanism
- The symbol's own tests, which often encode intended behavior more precisely than the implementation alone (an implementation can have incidental behavior; a test states intended behavior)

### Important retrieval signals
- The literal symbol name and its immediate source span — exact match is essential, since a docstring for the wrong function is actively harmful, not merely unhelpful
- Existing documentation style/tone elsewhere in the same file or module, for consistency
- Presence of non-obvious logic (an unusual regex, a magic constant, a workaround), which should be preferentially surfaced as needing explanation, over routine/self-explanatory code
- Terminology already used consistently in nearby documentation, to be reused rather than re-coined
- Cross-references — other places already describing this symbol or a closely related one, to avoid duplicated or inconsistent explanation

### Potential retrieval failures
- Retrieving only the function signature without the implementation body, producing documentation that restates the type signature without adding explanatory value
- Missing the *reason* for non-obvious code, since design rationale often lives outside the function itself (a commit message, an adjacent comment, a design document) and may not be retrievable by symbol-based lookup alone
- Generating documentation inconsistent with the codebase's existing conventions because nearby stylistic exemplars weren't surfaced
- Documenting incidental implementation detail as if it were a guaranteed contract, because the retrieval didn't distinguish "what the tests assert" from "what the implementation currently happens to do"
- Missing that a symbol is already documented elsewhere (a README, an ADR), leading to duplicated or contradictory documentation

### Expected retrieval priorities
High-precision retrieval of the target symbol's full implementation is the non-negotiable baseline. Beyond that, priority should favor *rationale-bearing* context (tests, comments, related design notes) over simply more code, since the differentiator between a useful and a shallow docstring is usually the "why" — comparatively sparse, and requiring active retrieval rather than assumed co-location with the "what." Stylistic/conventional context (nearby documentation) is a secondary but real priority, keeping generated documentation consistent with the rest of the repository rather than technically correct but stylistically foreign.

---

## 6. Test Generation

### Intent
The developer wants to produce new automated tests for existing (or newly implemented) code — verifying behavior, covering edge cases, or establishing a regression safety net. This requires understanding both the code's intended behavior and the codebase's existing testing conventions and infrastructure.

### Typical developer queries
- "Write unit tests for `SymbolIndex`"
- "Add edge-case tests for empty and malformed queries in the classifier"
- "Generate tests covering the context-capability downgrade logic in the planner"
- "Test that `TreeSitterRepositoryParser` handles a missing repository path"
- "Increase test coverage for the import-resolution heuristic"

### Required repository context
- The full implementation of the code under test, including every branch and edge case that should be exercised by at least one test
- Existing tests in the same module/package, to match testing conventions (fixture usage, naming patterns, assertion style, mocking approach)
- Test fixtures and factory helpers already available in the suite (e.g., a shared `conftest.py`), which new tests should reuse rather than duplicate
- The dependencies of the code under test, to determine what must be mocked/faked versus exercised directly — already-established conventions for this (e.g., "never load a real embedding model in tests") are critical, repository-specific context
- Any documented or inferable contract (docstring, type hints, existing tests) establishing what counts as *correct* behavior for a given input, since that is the oracle new tests must assert against

### Important retrieval signals
- The exact identity of the code under test (the specific function/class named or implied by the query)
- Existing test file(s) for the same or sibling modules, both as a style template and to avoid duplicating an already-existing test
- Conditional branches, exception paths, and boundary conditions within the implementation — these directly source "what needs a test case," making full-body retrieval of the implementation more valuable here than a signature or summary alone
- Fixture and mock/stub conventions already established elsewhere in the suite, to be discovered and reused rather than reinvented per new test
- Type hints and model/field constraints, which directly suggest boundary-value and invalid-input test cases

### Potential retrieval failures
- Retrieving the implementation but missing existing test-suite conventions, producing tests that are individually correct but structurally inconsistent with the rest of the suite (e.g., duplicating a fixture that already exists elsewhere)
- Missing branches or exception paths within the implementation, leading to superficially plausible tests that don't actually improve coverage of the riskiest code paths
- Failing to retrieve the dependencies that must be mocked, resulting in tests that would attempt real I/O, real model loading, or other expense/non-determinism the rest of the suite deliberately avoids
- Missing already-existing tests for the same behavior, leading to redundant rather than incremental test generation
- Treating incidental current behavior — not asserted anywhere as intentional — as the correctness oracle, producing tests that lock in accidental behavior rather than intended behavior

### Expected retrieval priorities
Full-body retrieval of the implementation under test is essential, and specifically prioritized for control-flow completeness (every branch, every exception path) rather than a truncated or summarized view, since test-generation quality is bounded by whether every path was even seen. Existing test-suite conventions and fixtures are a close second priority — this task is unusually sensitive to codebase-local convention (more so than, say, Bug Fix), because a generated test that passes but violates the suite's established patterns (e.g., loading a real model when convention is to mock it) is a meaningful quality failure even when the test itself is green. Cross-file breadth beyond the immediate module and its existing tests is comparatively low priority.

---

## Cross-cutting observations

A few patterns recur across all six categories and are worth naming explicitly, since they are properties of *task semantics* rather than of any one category, and are likely to generalize if this taxonomy is extended to further task types:

- **Exact-identity needs vs. topical-similarity needs are not the same axis and don't move together.** Refactoring and Documentation both need exact symbol identity, but Refactoring needs *exhaustive* recall of that identity's occurrences while Documentation needs only the *one* definition site plus rationale — "how precisely must the target be identified" and "how broad must the retrieved set be" are independent dimensions per task.
- **Some tasks retrieve a ground truth; others retrieve a proxy.** Bug Fix, Refactoring, API Usage, Documentation, and Test Generation all have a real, existing target to find. Feature Implementation does not — there is no existing "correct answer" location, only analogous prior art, which is a qualitatively different retrieval objective and likely a different failure mode (a bad proxy is misleading in a way a bad exact-match is merely wrong).
- **Tests are load-bearing context across nearly every category, not only for Test Generation.** They recur as a correctness oracle for Bug Fix, a safety net for Refactoring, a usage example for API Usage, and a behavioral ground truth for Documentation. This suggests test-code retrieval deserves first-class treatment generally, not only when the task is explicitly about tests.
- **"Why," not just "what," is the recurring scarce resource.** Bug Fix, Feature Implementation, Refactoring rationale, and Documentation all benefit from design intent that frequently is not co-located with the implementation (commit messages, ADRs, prose docs) — implementation-only retrieval systematically under-serves any task that requires rationale, not only Documentation specifically.
