"""Context Fusion: the top-level entry point merging multiple RetrievedContexts into a FusedContext.

`ContextFusion.fuse` is the only public method most callers need;
`Deduplicator`, `ScoreMerger`, `BaselineReranker`, and `TokenBudgeter`
are each independently unit-tested and independently substitutable
(Dependency Inversion, matching every other multi-component TARA stage),
but this class is what wires them into the actual pipeline
PROJECT_SPEC.md §20 describes:

    dedupe -> merge scores -> [rerank if plan.rerank] -> cut to top_k -> token-budget

The top_k cut happens here, not inside any retriever: every concrete
`Retriever` (`LexicalRetriever`, `DenseRetriever`, `GraphRetriever`)
documents this exact division of responsibility on its own `retrieve`
method, and truncates only to `RetrievalPlan.candidate_limit` (a larger,
pre-fusion pool) for exactly this reason.
"""
from __future__ import annotations

from collections.abc import Sequence

from tara.core.exceptions import ContextFusionError
from tara.fusion.deduplication import DeduplicatedCandidate, Deduplicator
from tara.fusion.models import FusedChunk, FusedContext
from tara.fusion.reranker import BaselineReranker
from tara.fusion.score_merge import ScoreMerger
from tara.fusion.token_budget import TokenBudgeter
from tara.retrieval.models import RetrievedContext
from tara.routing.models import RetrievalPlan


class ContextFusion:
    """Merges one or more `RetrievedContext`s into a single `FusedContext`.

    All collaborators are injected, each defaulting to its own
    dependency-free construction when omitted -- matching
    `LexicalRetriever`/`DenseRetriever`/`GraphRetriever`'s constructor
    pattern of accepting substitutable collaborators rather than always
    building its own.
    """

    def __init__(
        self,
        deduplicator: Deduplicator | None = None,
        score_merger: ScoreMerger | None = None,
        reranker: BaselineReranker | None = None,
        token_budgeter: TokenBudgeter | None = None,
    ) -> None:
        """Construct the fusion pipeline.

        Args:
            deduplicator: Groups chunks by `chunk_id` across inputs.
                Defaults to a plain `Deduplicator()`.
            score_merger: Merges each dedup group's per-retriever
                scores into one `fused_score`. Defaults to a plain
                `ScoreMerger()` (equal weighting across retrievers) --
                a caller wanting `TaraSettings.fusion_retriever_weights`
                honored must construct and inject
                `ScoreMerger(retriever_weights=settings.fusion_retriever_weights)`
                explicitly.
            reranker: Orders fused chunks by descending `fused_score`
                when invoked. Defaults to a plain `BaselineReranker()`.
            token_budgeter: Counts and enforces the token budget.
                Defaults to a plain `TokenBudgeter()` (the dependency-free
                char/4 estimate).
        """
        self._deduplicator = deduplicator or Deduplicator()
        self._score_merger = score_merger or ScoreMerger()
        self._reranker = reranker or BaselineReranker()
        self._token_budgeter = token_budgeter or TokenBudgeter()

    def fuse(
        self,
        query: str,
        retrieved_contexts: Sequence[RetrievedContext],
        plan: RetrievalPlan,
        token_budget: int,
    ) -> FusedContext:
        """Fuse `retrieved_contexts` into a single `FusedContext` for `query`, per `plan`.

        Args:
            query: The query every context in `retrieved_contexts` was
                retrieved for. Validated against each context's own
                `.query` (see Raises).
            retrieved_contexts: One `RetrievedContext` per retriever
                that ran, ideally in a fixed, deterministic order (e.g.
                `RetrievalOrchestrator.execute`'s own output order) --
                determines both the canonical chunk chosen for a
                cross-retriever duplicate and the deterministic
                first-seen order used when `plan.rerank` is false.
                Empty, or containing only empty contexts, is handled
                cleanly and yields an empty, non-truncated `FusedContext`.
            plan: The plan that produced `retrieved_contexts`. Only
                `.rerank` and `.top_k` are read; `plan` itself is never
                modified.
            token_budget: Maximum total tokens to include, e.g.
                `TaraSettings().fusion_token_budget`. Not sourced from
                `plan` -- `RetrievalPlan` has no token-budget field
                (confirmed by inspection: budget is a fusion-stage
                concern, not a retrieval-planning one).

        Returns:
            The fused, deduplicated, (optionally) reranked, top_k-cut,
            token-budgeted result.

        Raises:
            ContextFusionError: If any `RetrievedContext.query` in
                `retrieved_contexts` disagrees with `query` -- a
                caller/wiring defect (mixing results from two different
                queries into one fusion call), not a normal "no
                results" case, so this raises rather than silently
                fusing mismatched data.
        """
        self._validate_query_consistency(query, retrieved_contexts)

        deduplicated = self._deduplicator.deduplicate(retrieved_contexts)
        candidate_count = len(deduplicated)

        fused_chunks = [self._build_fused_chunk(candidate) for candidate in deduplicated]

        if plan.rerank:
            fused_chunks = self._reranker.rerank(fused_chunks)

        top_k_chunks = fused_chunks[: plan.top_k]

        budgeted_chunks, truncated = self._token_budgeter.apply(top_k_chunks, token_budget)
        total_tokens = sum(chunk.token_count for chunk in budgeted_chunks)

        contributing_kinds = sorted(
            {context.retriever_kind.value for context in retrieved_contexts}
        )

        return FusedContext(
            query=query,
            chunks=budgeted_chunks,
            total_tokens=total_tokens,
            truncated=truncated,
            candidate_count=candidate_count,
            metadata={
                "reranked": plan.rerank,
                "contributing_retrievers": contributing_kinds,
                "token_budget": token_budget,
            },
        )

    def _build_fused_chunk(self, candidate: DeduplicatedCandidate) -> FusedChunk:
        merged_score = self._score_merger.merge(candidate.source_scores)
        token_count = self._token_budgeter.count_tokens(candidate.chunk.content)
        return FusedChunk(
            chunk_id=candidate.chunk.chunk_id,
            node_type=candidate.chunk.node_type,
            name=candidate.chunk.name,
            file_path=candidate.chunk.file_path,
            start_line=candidate.chunk.start_line,
            end_line=candidate.chunk.end_line,
            content=candidate.chunk.content,
            docstring=candidate.chunk.docstring,
            fused_score=merged_score,
            found_by=candidate.found_by,
            source_scores=candidate.source_scores,
            token_count=token_count,
        )

    @staticmethod
    def _validate_query_consistency(
        query: str, retrieved_contexts: Sequence[RetrievedContext]
    ) -> None:
        for context in retrieved_contexts:
            if context.query != query:
                raise ContextFusionError(
                    f"RetrievedContext for retriever {context.retriever_kind.value!r} was "
                    f"retrieved for query {context.query!r}, but fuse() was called with query "
                    f"{query!r}."
                )
