"""Lexical Retrieval module.

Provides exact/keyword search over a repository's parsed structural
context (`tara.context.models.RepositoryContext`): a BM25 index over
symbol and file text, symbol/file lookup helpers, and a ranking engine
that turns raw search matches into the ordered `RetrievedContext` a
`RetrievalPlan` calls for. No semantic embedding, no graph traversal,
and no LLM call happen anywhere in this module.
"""
from __future__ import annotations
