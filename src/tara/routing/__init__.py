"""Task-Guided Adaptive Router pipeline stage.

Decides *what* to retrieve with and *how* -- never retrieval itself, no
LLM, no repository traversal, no embedding generation. Turns a
`tara.classification.models.TaskClassification` plus a
`tara.context.models.RepositoryContext` into a
`tara.routing.models.RetrievalPlan`: which retriever kinds should run,
in what order, sequentially or in parallel, with what top-k/candidate
pool/graph depth, and whether reranking is warranted.
"""
from __future__ import annotations
