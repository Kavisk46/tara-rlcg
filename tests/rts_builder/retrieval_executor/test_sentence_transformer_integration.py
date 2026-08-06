"""Integration test: `DenseRetriever` with a real `SentenceTransformerEmbedder` backend.

Reviewer #2, Minor Revision, Revision 3. Uses a small model
(`sentence-transformers/all-MiniLM-L6-v2`) that must already be present
in the local Hugging Face cache -- Hugging Face's offline mode
(`HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE`) is forced on at module import
time (before `sentence_transformers`/`huggingface_hub` are imported at
all -- see the env-var block below for why that ordering matters), so
no test here can ever reach the network, in CI or anywhere else. If the
model isn't cached, the module-scoped fixture that loads it calls
`pytest.skip` (not a failure) -- offline mode turns "not cached" into a
fast, local, deterministic skip rather than a network attempt.
"""
from __future__ import annotations

import os

_OFFLINE_ENV_VARS = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")

# Must be set as *module-level code, before* `sentence_transformers`/`huggingface_hub` are
# imported anywhere in this process (including by `pytest.importorskip` just below):
# `huggingface_hub` reads `HF_HUB_OFFLINE` into a module-level constant at import time, not
# per-call, so setting it later (e.g. inside a fixture, which only runs at test-execution
# time, well after collection-time imports) has no effect -- confirmed the hard way: an
# earlier version of this file set these inside an autouse fixture and the "uncached model"
# test below still made a real HTTP request to huggingface.co and got a live 401 response
# back, rather than failing locally. `setdefault` respects a caller's own pre-set value.
for _env_var in _OFFLINE_ENV_VARS:
    os.environ.setdefault(_env_var, "1")

import pytest  # noqa: E402

pytest.importorskip("sentence_transformers", reason="sentence-transformers is an optional, heavy dependency")

from evaluation.rts_builder.parser.models import RepositoryModel  # noqa: E402
from evaluation.rts_builder.retrieval_executor.config import RetrievalExecutorSettings  # noqa: E402
from evaluation.rts_builder.retrieval_executor.dense_retrieval import DenseRetriever  # noqa: E402
from evaluation.rts_builder.retrieval_executor.models import RetrievalStrategyName  # noqa: E402
from evaluation.rts_builder.retrieval_executor.vector_index import InMemoryVectorIndex  # noqa: E402
from tara.context.embedder import SentenceTransformerEmbedder  # noqa: E402

_CACHED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_UNCACHED_MODEL_NAME = "sentence-transformers/this-model-is-not-cached-anywhere-xyz"


@pytest.fixture(scope="module")
def sentence_transformer_embedder() -> SentenceTransformerEmbedder:
    """A real, locally-cached `SentenceTransformerEmbedder`, loaded once for this whole module.

    Module-scoped: loading a real model is comparatively expensive
    (hundreds of milliseconds to a few seconds even from a warm local
    cache), and nothing in this test module mutates the embedder, so
    every test safely shares one loaded instance.
    """
    embedder = SentenceTransformerEmbedder(model_name=_CACHED_MODEL_NAME, device="cpu")
    try:
        embedder.embed("warm-up")
    except Exception as exc:  # noqa: BLE001 - any failure here means "not usable offline", handled uniformly
        pytest.skip(f"{_CACHED_MODEL_NAME} is not available in the local Hugging Face cache: {exc}")
    return embedder


@pytest.fixture
def semantic_repository_model(tmp_path) -> RepositoryModel:  # type: ignore[no-untyped-def]
    """A tiny, directly-constructed `RepositoryModel` with two semantically distinct files.

    `parser.py` is about parsing source code; `database.py` is about
    database connections -- distinct enough vocabulary that a real
    sentence-embedding model should reliably rank one above the other
    for a parsing-themed query, unlike `HashingEmbedder`'s
    token-presence-only signal (see `STRATEGY_COMPARISON.md`).
    """
    from evaluation.rts_builder.parser.models import NormalizedFile

    files = [
        NormalizedFile(
            path="parser.py", size_bytes=200, content_hash="hash-parser",
            module_docstring="Parses source code files into an abstract syntax tree.",
            function_count=0, class_count=0, import_count=0,
        ),
        NormalizedFile(
            path="database.py", size_bytes=200, content_hash="hash-database",
            module_docstring="Manages database connections and executes SQL queries.",
            function_count=0, class_count=0, import_count=0,
        ),
    ]
    return RepositoryModel(
        repository_id="semantic-repo", commit_sha="a" * 40, root_path=str(tmp_path),
        files=files, functions=[], classes=[], imports=[],
        import_graph=[], call_graph=[], inheritance_graph=[], parse_errors=[],
    )


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------


def test_embedding_generation_produces_a_real_dense_vector(
    sentence_transformer_embedder: SentenceTransformerEmbedder,
) -> None:
    vector = sentence_transformer_embedder.embed("parse the repository into an abstract syntax tree")

    assert isinstance(vector, list)
    assert len(vector) > 0
    assert all(isinstance(component, float) for component in vector)
    assert any(component != 0.0 for component in vector)


def test_embedding_generation_is_consistent_for_the_same_text(
    sentence_transformer_embedder: SentenceTransformerEmbedder,
) -> None:
    first = sentence_transformer_embedder.embed("parse the repository")
    second = sentence_transformer_embedder.embed("parse the repository")
    assert first == second


# ---------------------------------------------------------------------------
# Vector search + retrieved results, via DenseRetriever end-to-end
# ---------------------------------------------------------------------------


def test_dense_retriever_with_a_real_embedder_ranks_semantically_relevant_file_first(
    sentence_transformer_embedder: SentenceTransformerEmbedder, semantic_repository_model: RepositoryModel
) -> None:
    retriever = DenseRetriever(
        embedder=sentence_transformer_embedder,
        vector_index=InMemoryVectorIndex(),
        settings=RetrievalExecutorSettings(),
    )

    result = retriever.retrieve(semantic_repository_model, "how do I parse a Python file into an AST?", top_k=10)

    assert result.strategy_name is RetrievalStrategyName.DENSE
    assert len(result.retrieved_files) == 2
    assert result.retrieved_files[0].file_path == "parser.py"
    assert result.retrieved_files[0].score > result.retrieved_files[1].score
    assert result.retrieval_latency_ms >= 0.0
    assert result.context_token_count > 0


def test_dense_retriever_with_a_real_embedder_reranks_for_a_differently_themed_query(
    sentence_transformer_embedder: SentenceTransformerEmbedder, semantic_repository_model: RepositoryModel
) -> None:
    retriever = DenseRetriever(
        embedder=sentence_transformer_embedder,
        vector_index=InMemoryVectorIndex(),
        settings=RetrievalExecutorSettings(),
    )

    result = retriever.retrieve(semantic_repository_model, "how do I connect to a SQL database?", top_k=10)

    assert result.retrieved_files[0].file_path == "database.py"


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


def test_uncached_model_fails_fast_offline_rather_than_hanging_or_reaching_the_network() -> None:
    """An uncached model, with offline mode forced, must fail immediately and locally.

    `tara.context.embedder.SentenceTransformerEmbedder._ensure_model`
    does not currently wrap the `SentenceTransformer(...)` constructor
    call in a try/except -- only the `import sentence_transformers`
    statement is guarded, raising `EmbeddingError`. An uncached model
    therefore surfaces the underlying `huggingface_hub`/`OSError`
    directly, not `EmbeddingError`. This is a real, pre-existing gap in
    `tara.context.embedder` (out of scope to fix here -- "Do NOT modify
    any other subsystem"; see REVIEW_RESPONSE.md), so this test asserts
    the actual, current failure behavior rather than the arguably
    -more-correct one: the failure is an `OSError`, it happens fast
    (no long network timeout, because offline mode is forced), and it
    is not silently swallowed anywhere in this call chain.
    """
    embedder = SentenceTransformerEmbedder(model_name=_UNCACHED_MODEL_NAME, device="cpu")

    with pytest.raises(OSError, match="offline mode|couldn't connect|Can't load"):
        embedder.embed("this will fail because the model is not cached and we are offline")


def test_dense_retriever_propagates_an_uncached_model_failure_rather_than_swallowing_it(
    semantic_repository_model: RepositoryModel,
) -> None:
    """`DenseRetriever` must not hide or misreport a failing embedder -- the caller needs to know."""
    embedder = SentenceTransformerEmbedder(model_name=_UNCACHED_MODEL_NAME, device="cpu")
    retriever = DenseRetriever(embedder=embedder, vector_index=InMemoryVectorIndex(), settings=RetrievalExecutorSettings())

    with pytest.raises(OSError):
        retriever.retrieve(semantic_repository_model, "any query", top_k=10)
