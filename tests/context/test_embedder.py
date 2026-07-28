"""Unit tests for the embedding layer. No real embedding model is loaded or downloaded."""
from __future__ import annotations

from pathlib import Path

from tara.context.embedder import Embedder, RepositoryEmbedder, iter_embedding_inputs
from tara.context.models import build_symbol_node_id
from tara.core.types import Language
from tara.parsing.models import CodeSymbol, ParsedFile, ParsedRepository, SymbolKind


class FakeEmbedder(Embedder):
    """Deterministic, model-free `Embedder` for tests."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [float(len(text))]


class BatchCountingEmbedder(Embedder):
    """Tracks how many times `embed_batch` is invoked, to assert on batching behavior."""

    def __init__(self) -> None:
        self.batch_calls = 0

    def embed(self, text: str) -> list[float]:
        return [0.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.batch_calls += 1
        return [[float(len(t))] for t in texts]


def test_iter_embedding_inputs_covers_every_class_function_and_method(
    parsed_sample_repository: ParsedRepository,
) -> None:
    inputs = list(iter_embedding_inputs(parsed_sample_repository))
    names = {item.symbol_name for item in inputs}
    assert names == {"Greeter", "greet", "main", "add"}


def test_embedding_input_text_includes_all_required_fields(parsed_sample_repository: ParsedRepository) -> None:
    inputs = {item.symbol_name: item for item in iter_embedding_inputs(parsed_sample_repository)}
    greeter = inputs["Greeter"]

    assert greeter.file_path == "app.py"
    assert greeter.docstring == "Greets users by name."
    assert greeter.source_code.startswith("class Greeter")

    text = greeter.to_text()
    assert "File: app.py" in text
    assert "Symbol: Greeter" in text
    assert "Docstring: Greets users by name." in text
    assert "class Greeter" in text


def test_embedding_input_symbol_id_matches_graph_id_scheme(parsed_sample_repository: ParsedRepository) -> None:
    app_file = parsed_sample_repository.get_file("app.py")
    assert app_file is not None
    greeter_symbol = next(s for s in app_file.symbols if s.name == "Greeter")

    inputs = {item.symbol_name: item for item in iter_embedding_inputs(parsed_sample_repository)}
    expected_id = build_symbol_node_id("app.py", "Greeter", None, greeter_symbol.start_line)
    assert inputs["Greeter"].symbol_id == expected_id


def test_repository_embedder_returns_vector_per_symbol(parsed_sample_repository: ParsedRepository) -> None:
    fake = FakeEmbedder()
    embeddings = RepositoryEmbedder(fake, batch_size=2).embed_repository(parsed_sample_repository)

    assert len(embeddings) == 4
    assert all(isinstance(vector, list) for vector in embeddings.values())
    assert fake.calls


def test_repository_embedder_batches_calls(parsed_sample_repository: ParsedRepository) -> None:
    counting = BatchCountingEmbedder()
    RepositoryEmbedder(counting, batch_size=2).embed_repository(parsed_sample_repository)

    # 4 embeddable symbols with batch_size=2 -> exactly 2 flushes.
    assert counting.batch_calls == 2


def test_iter_embedding_inputs_handles_unreadable_file_gracefully(tmp_path: Path) -> None:
    missing_file = ParsedFile(
        path="ghost.py",
        absolute_path=str(tmp_path / "does-not-exist.py"),
        language=Language.PYTHON,
        size_bytes=10,
        content_hash="deadbeef",
        symbols=[
            CodeSymbol(
                name="ghost_fn",
                kind=SymbolKind.FUNCTION,
                start_line=0,
                end_line=1,
                start_byte=0,
                end_byte=10,
            )
        ],
    )
    repository = ParsedRepository(root_path=str(tmp_path), files=[missing_file])

    results = list(iter_embedding_inputs(repository))
    assert len(results) == 1
    assert results[0].source_code == ""
    assert results[0].signature == ""


def test_iter_embedding_inputs_skips_files_with_no_embeddable_symbols(tmp_path: Path) -> None:
    empty_file = ParsedFile(
        path="empty.py",
        absolute_path=str(tmp_path / "empty.py"),
        language=Language.PYTHON,
        size_bytes=0,
        content_hash="0",
        symbols=[],
    )
    repository = ParsedRepository(root_path=str(tmp_path), files=[empty_file])

    assert list(iter_embedding_inputs(repository)) == []
