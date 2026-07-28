"""Embedding layer for the Repository Context Extractor.

Defines the `Embedder` interface every embedding provider implements, a
`SentenceTransformerEmbedder` reference implementation, and the logic
that turns a `ParsedRepository`'s symbols into the text inputs those
providers embed. Swapping providers (OpenAI, VoyageAI, a local ONNX
model, ...) means writing one new `Embedder` subclass; nothing else in
`tara.context` changes.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tara.context.models import build_symbol_node_id
from tara.core.config import TaraSettings
from tara.core.exceptions import EmbeddingError
from tara.core.logging import get_logger
from tara.parsing.models import CodeSymbol, ParsedFile, ParsedRepository, SymbolKind

logger = get_logger(__name__)

_EMBEDDABLE_KINDS = frozenset({SymbolKind.CLASS, SymbolKind.FUNCTION, SymbolKind.METHOD})


class Embedder(ABC):
    """Abstract contract for turning text into a dense embedding vector."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Embed a single piece of text.

        Args:
            text: The text to embed, typically the output of
                `EmbeddingInput.to_text`.

        Returns:
            A dense embedding vector as a list of floats. Dimensionality
            is provider-specific and must never be hardcoded by callers.

        Raises:
            EmbeddingError: If the provider fails to produce a vector.
        """
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts, preserving order.

        The default implementation calls `embed` once per item;
        providers with native batch support (nearly all of them) should
        override this for throughput.
        """
        return [self.embed(text) for text in texts]


class SentenceTransformerEmbedder(Embedder):
    """`Embedder` backed by a local `sentence-transformers` model.

    The model is loaded lazily on first use, so constructing an embedder
    -- or a `RepositoryContextExtractor` that holds one -- never
    triggers a model download or device allocation by itself. This
    matters for tests and for any code path that builds a
    `RepositoryContext` without embeddings.
    """

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        settings: TaraSettings | None = None,
    ) -> None:
        """Construct the embedder.

        Args:
            model_name: Sentence-Transformers model identifier. Defaults
                to `settings.embedding_model_name` (`BAAI/bge-small-en-v1.5`)
                when omitted.
            device: Torch device to load the model on, e.g. "cpu" or
                "cuda". Defaults to `settings.embedding_device`.
            settings: Configuration source for the defaults above.
                Defaults to `TaraSettings()` (environment defaults) when
                omitted.
        """
        settings = settings or TaraSettings()
        self._model_name = model_name or settings.embedding_model_name
        self._device = device or settings.embedding_device
        self._model: Any = None

    def _ensure_model(self) -> Any:
        """Load the underlying SentenceTransformer model on first use."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise EmbeddingError(
                    "sentence-transformers is required for SentenceTransformerEmbedder; "
                    "install it with `pip install sentence-transformers`."
                ) from exc

            logger.info("Loading embedding model %s on device %s", self._model_name, self._device)
            self._model = SentenceTransformer(self._model_name, device=self._device)
        return self._model

    def embed(self, text: str) -> list[float]:
        """See `Embedder.embed`."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """See `Embedder.embed_batch`. Encodes the whole batch in one model call."""
        if not texts:
            return []
        model = self._ensure_model()
        try:
            vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        except Exception as exc:  # noqa: BLE001 - normalize provider failures to EmbeddingError
            raise EmbeddingError(f"Failed to embed {len(texts)} text(s) with {self._model_name}: {exc}") from exc
        return [vector.tolist() for vector in vectors]


@dataclass(frozen=True)
class EmbeddingInput:
    """The identity and assembled text of a single symbol ready to be embedded."""

    symbol_id: str
    file_path: str
    symbol_name: str
    signature: str
    docstring: str
    source_code: str

    def to_text(self) -> str:
        """Assemble the final string passed to `Embedder.embed`.

        Combines file path, symbol name, signature, docstring, and
        source code, per the Context Extractor's embedding contract --
        embedding only the symbol name would lose almost all of the
        semantic signal a retriever needs.
        """
        sections = [f"File: {self.file_path}", f"Symbol: {self.symbol_name}"]
        if self.signature:
            sections.append(f"Signature: {self.signature}")
        if self.docstring:
            sections.append(f"Docstring: {self.docstring}")
        if self.source_code:
            sections.append(f"Code:\n{self.source_code}")
        return "\n".join(sections)


def iter_embedding_inputs(parsed_repository: ParsedRepository) -> Iterator[EmbeddingInput]:
    """Yield one `EmbeddingInput` per embeddable symbol in `parsed_repository`.

    Only classes, functions, and methods are embedded (imports and
    module-level variables carry little standalone semantic value and
    are skipped, per the "embed only supported symbols" performance
    requirement). Each file's bytes are read at most once -- to slice
    per-symbol source text via the byte offsets `RepositoryParser`
    already recorded -- and this function is a generator, so a caller
    processing embeddings in batches never holds the whole repository's
    source in memory at once.

    Args:
        parsed_repository: The structural parse to derive embedding
            inputs from.

    Yields:
        One `EmbeddingInput` per class/function/method symbol, in file
        order.
    """
    for parsed_file in parsed_repository.files:
        embeddable_symbols = [symbol for symbol in parsed_file.symbols if symbol.kind in _EMBEDDABLE_KINDS]
        if not embeddable_symbols:
            continue

        source_bytes = _read_file_bytes(parsed_file)
        for symbol in embeddable_symbols:
            yield _build_embedding_input(parsed_file, symbol, source_bytes)


def _read_file_bytes(parsed_file: ParsedFile) -> bytes | None:
    """Read a parsed file's raw bytes for source-snippet extraction.

    Returns None (rather than raising) when the file is no longer
    readable at `absolute_path`, so a single missing/moved file degrades
    embedding quality for that file instead of aborting the whole
    repository.
    """
    try:
        return Path(parsed_file.absolute_path).read_bytes()
    except OSError as exc:
        logger.warning("Skipping source extraction for %s: %s", parsed_file.path, exc)
        return None


def _build_embedding_input(parsed_file: ParsedFile, symbol: CodeSymbol, source_bytes: bytes | None) -> EmbeddingInput:
    """Build the `EmbeddingInput` for a single symbol, using the same id scheme as `GraphBuilder`."""
    symbol_id = build_symbol_node_id(parsed_file.path, symbol.name, symbol.parent, symbol.start_line)

    source_code = ""
    signature = ""
    if source_bytes is not None:
        source_code = source_bytes[symbol.start_byte : symbol.end_byte].decode("utf-8", errors="replace")
        signature = source_code.splitlines()[0].strip() if source_code else ""

    return EmbeddingInput(
        symbol_id=symbol_id,
        file_path=parsed_file.path,
        symbol_name=symbol.name,
        signature=signature,
        docstring=symbol.docstring or "",
        source_code=source_code,
    )


class RepositoryEmbedder:
    """Generates embeddings for every embeddable symbol in a `ParsedRepository`.

    Wraps an injected `Embedder` with the batching, logging, and
    id-assignment policy the Context Extractor stage needs, so
    `RepositoryContextExtractor` only ever calls `embed_repository` and
    owns no embedding-specific logic itself.
    """

    def __init__(self, embedder: Embedder, batch_size: int = 64) -> None:
        """Construct the service.

        Args:
            embedder: The embedding provider to batch requests through.
            batch_size: Maximum number of texts sent to `embedder` per
                `embed_batch` call.
        """
        self._embedder = embedder
        self._batch_size = batch_size

    def embed_repository(self, parsed_repository: ParsedRepository) -> dict[str, list[float]]:
        """Return `symbol_id -> embedding vector` for every embeddable symbol.

        Args:
            parsed_repository: The structural parse to embed.

        Returns:
            A dict keyed by the same symbol-node ids `GraphBuilder`
            assigns, so embeddings can always be correlated back to
            graph nodes and `SymbolIndex` records.
        """
        start = time.perf_counter()
        embeddings: dict[str, list[float]] = {}
        batch: list[EmbeddingInput] = []

        def flush() -> None:
            if not batch:
                return
            vectors = self._embedder.embed_batch([item.to_text() for item in batch])
            for item, vector in zip(batch, vectors):
                embeddings[item.symbol_id] = vector
            batch.clear()

        for embedding_input in iter_embedding_inputs(parsed_repository):
            batch.append(embedding_input)
            if len(batch) >= self._batch_size:
                flush()
        flush()

        elapsed = time.perf_counter() - start
        logger.info(
            "Generated %d embeddings in %.3fs (batch_size=%d)", len(embeddings), elapsed, self._batch_size
        )
        return embeddings
