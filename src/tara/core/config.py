"""Runtime configuration for TARA, sourced from environment variables.

All settings are exposed through a single `TaraSettings` object so every
component receives configuration via constructor injection rather than
reading `os.environ` directly. This keeps components unit-testable in
isolation from the process environment and makes every tunable
discoverable in one place.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TaraSettings(BaseSettings):
    """Centralized, environment-driven configuration for the TARA pipeline.

    Every field can be overridden by an environment variable named
    `TARA_<FIELD_NAME>` (uppercased), or by an entry in a local `.env`
    file. See `.env.example` for the full list.
    """

    model_config = SettingsConfigDict(env_prefix="TARA_", env_file=".env", extra="ignore")

    # --- Repository parsing ---
    max_file_size_bytes: int = Field(
        default=1_000_000,
        description="Source files larger than this many bytes are skipped during parsing.",
    )
    ignored_directories: list[str] = Field(
        default_factory=list,
        description="Additional directory names to exclude from parsing, beyond the built-in defaults (.git, node_modules, venv, etc.).",
    )

    # --- Repository context / dense retrieval ---
    embedding_model_name: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="Sentence-Transformers model used to embed code chunks for dense retrieval and the Repository Context Extractor.",
    )
    embedding_device: str = Field(
        default="cpu",
        description="Torch device used for embedding inference, e.g. 'cpu' or 'cuda'.",
    )
    faiss_index_path: str = Field(
        default=".tara/faiss.index",
        description="Filesystem path where the FAISS dense index is persisted.",
    )

    # --- Task classification ---
    task_classifier_model_name: str = Field(
        default="microsoft/codebert-base",
        description="Transformers model used as the backbone for task classification.",
    )

    # --- Code generation ---
    llm_model_name: str = Field(
        default="gpt-4o-mini",
        description="Identifier of the LLM used for final code generation.",
    )

    # --- Service ---
    log_level: str = Field(
        default="INFO",
        description="Root log level for the TARA logging subsystem.",
    )
    api_host: str = Field(default="0.0.0.0", description="Host the FastAPI service binds to.")
    api_port: int = Field(default=8000, description="Port the FastAPI service binds to.")
