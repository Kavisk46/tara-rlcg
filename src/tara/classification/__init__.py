"""Task Classifier pipeline stage.

Analyzes a raw developer query -- without calling an LLM -- to
determine what kind of software-engineering task it represents, which
retrieval strategy (lexical, semantic, graph, or hybrid) is likely to
serve it best, and what repository entities (symbols, file paths,
keywords, a language hint) a retriever should search for. Classification
is deterministic: the same query always produces the same
`tara.classification.models.TaskClassification`, no ML model or network
call involved.
"""
from __future__ import annotations
