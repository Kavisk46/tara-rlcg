# Strategy Comparison — RTS Builder Retrieval Executor (Milestone 5)

All four strategies implement the same interface (`.retrieve(model,
query_text, top_k) -> StrategyResult`, or, for Hybrid, `.combine(...)`)
and share the same output contract (`RetrievedFile`, `retrieval_score`,
`retrieval_latency_ms`, `context_token_count`). What differs is the
signal each one uses and what that implies for a dataset built from
their results.

| | Lexical | Dense | Graph | Hybrid |
|---|---|---|---|---|
| **Signal** | BM25 + exact identifier match + keyword overlap over synthetic per-file documents | Cosine similarity between query and per-file embeddings | BFS proximity (hop-decayed) from identifier-matched seed files, over import/call/inheritance edges | Weighted sum of the other three's normalized scores |
| **Reused component** | `tara.retrieval.bm25_index.BM25Index` | `tara.context.embedder.Embedder` (default: `HashingEmbedder`) | None (self-contained BFS) | `tara.retrieval.utils.normalize_scores` |
| **Needs a seed/anchor?** | No — scores every document against the query directly | No — embeds and scores every document directly | **Yes** — requires at least one exact identifier match; empty query or a query naming no known symbol yields an empty result | No — operates on the union of the other three's results |
| **Sensitive to** | Vocabulary overlap between the query and docstrings/symbol names | Overall semantic/textual similarity (as captured by the embedding backend) | Repository structure (import/call/inheritance density); vocabulary only for seed-finding | Whatever the other three are sensitive to, blended |
| **Degrades to empty result when** | Query shares no token with any file's document text | Never — always returns up to `top_k` files (an empty-query/degenerate case yields an arbitrary, score-0 ranking; see `REVIEW_RESPONSE.md`) | No seed found (empty query, or query names no symbol in the repository) | Only if all three inputs are themselves empty |
| **Deterministic given fixed inputs?** | Yes | Yes (`HashingEmbedder` has no randomness) | Yes | Yes |
| **Typical latency shape (per the frozen protocol — see below)** | O(query terms × postings) — BM25 index build happens every call but is *excluded* from `retrieval_latency_ms` | O(files) to embed + O(files) brute-force cosine search — vector-index build is *excluded* | O(seeds + reachable files) BFS, bounded by `max_graph_hops` — adjacency-map build is *excluded* | O(files in the union) — cheapest of the four, since it does no re-computation and has no excluded phase |
| **What a dataset consumer should read into a high score** | The query's vocabulary literally appears in this file's structural metadata | This file's assembled document text is textually/lexically similar to the query, by the default backend's coarse hashing signal — *not* semantic understanding unless a real model backend is plugged in | This file is structurally close to something the query explicitly named | A blend, only as informative as its three configured weights make it |

## Hybrid Score Normalization (frozen, Reviewer #2 Revision 1)

Hybrid's "weighted sum of the other three's normalized scores" row
above, made exact: each strategy's own `retrieved_files` scores are
independently **min-max normalized** to `[0, 1]`
(`tara.retrieval.utils.normalize_scores`; an all-tied or single-file
strategy result normalizes every score to `1.0`, not `0/0`), then:

```
Hybrid(f) = α·L'(f) + β·D'(f) + γ·G'(f)         α + β + γ = 1, default α=β=γ=1/3
```

where `L'(f)`, `D'(f)`, `G'(f)` are file `f`'s normalized score under
each strategy, or `0` if `f` wasn't among that strategy's own
`retrieved_files` (normalization happens *within* each strategy's own
result set, never across the union). See `README.md`'s "Hybrid Score
Normalization" section for the full formal statement (with the
piecewise normalization definition) and `config.yaml` for the
machine-readable record. Implemented in
`hybrid_retrieval.py:HybridRetriever.combine`; weights are
`RetrievalExecutorSettings.hybrid_lexical_weight`/`hybrid_dense_weight`/`hybrid_graph_weight`.

## Latency Measurement Protocol (frozen, Reviewer #2 Revision 2)

`retrieval_latency_ms` starts immediately before `retrieve()` and ends
immediately after ranked results are returned, but only *included*
phases are actually accumulated: embedding generation, vector search,
graph traversal, and score computation. *Excluded*: repository loading
(never happens in this subsystem), index construction (BM25/vector
-index/adjacency-map build), and model download. See `README.md`'s
"Latency Measurement Protocol" section for the full per-strategy
breakdown and the rationale for why "starts before `retrieve()`" and
"excludes index construction" aren't contradictory, and
[`latency_protocol.py`](latency_protocol.py)/[`config.yaml`](config.yaml)
for the frozen, machine-readable definition.

## When strategies agree vs. disagree

- **Lexical and Graph tend to agree** on the seed file itself (Graph's
  seed *is* an exact identifier match, which Lexical also scores
  highly) but diverge on everything else: Lexical's next-best files are
  vocabulary matches; Graph's are structural neighbors, which may share
  no vocabulary with the query at all.
- **Dense (with the default `HashingEmbedder`) is the strategy most
  likely to look arbitrary to a human reviewer** for short, low
  -vocabulary-overlap queries: feature hashing captures token
  *presence*, not meaning, so two files sharing no real semantic
  relationship can still score similarly if their hashed token sets
  happen to collide. See `REVIEW_RESPONSE.md` for why this is an
  accepted, documented property of the default backend, not a defect.
- **Hybrid is only as good as its inputs and weights.** With the
  default equal-thirds weighting, a file only one strategy strongly
  favors is diluted by the other two's silence (a `0.0` contribution)
  on that file — by design (see `README.md`), not a bug; a dataset
  -construction pass that wants a different tradeoff should tune
  `hybrid_*_weight`, not read this as Hybrid "missing" what Lexical or
  Graph found (both of *their* results remain independently available
  on the same `RetrievalExecutionResult`).

## Why all four, unconditionally, for every query

This milestone deliberately never picks a "best" strategy — every
strategy runs for every query, and all four `StrategyResult`s are
retained. That is what makes this milestone's output usable by a later
(explicitly out-of-scope) Oracle Utility Computation stage: a per
-strategy utility label requires having actually executed every
candidate strategy, not just the one a router would have chosen.
