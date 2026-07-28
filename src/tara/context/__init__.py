"""Repository Context Extractor pipeline stage.

Turns a `tara.parsing.models.ParsedRepository` into a
`tara.context.models.RepositoryContext`: a directed graph of
repository/file/class/function/method nodes, a fast symbol index over
that graph, and (optionally) dense embeddings for every class, function,
and method. This is the semantic substrate later stages (GraphRAG,
hybrid retrieval, AI agents) consume. Nothing in this package calls an
LLM.
"""
from __future__ import annotations
