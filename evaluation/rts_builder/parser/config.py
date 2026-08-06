"""Configuration for the RTS Builder's Parser subsystem (Python-only V1).

Kept separate from ``tara.core.config.TaraSettings`` and
``evaluation.rts_builder.config.RepositoryLoaderSettings``: this
milestone is self-contained (see ``README.md``'s "Design Decisions" for
why it does not reuse ``tara.parsing``), so it owns its own, complete
configuration surface rather than borrowing fields from a settings
object built for a different (multi-language, Tree-sitter-based)
pipeline.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ParserSettings(BaseSettings):
    """Environment-driven configuration for ``PythonParserPipeline``.

    Every field can be overridden by an environment variable named
    ``RTS_PARSER_<FIELD_NAME>`` (uppercased), or by an entry in a local
    ``.env`` file. See ``evaluation/rts_builder/parser/.env.example``
    for the full list.
    """

    model_config = SettingsConfigDict(env_prefix="RTS_PARSER_", env_file=".env", extra="ignore")

    cache_root: str = Field(
        default=".rts_cache/parsed",
        description="Local directory under which per-repository repository_model.json cache "
        "entries are written, one subdirectory per repository_id.",
    )
    force_reparse: bool = Field(
        default=False,
        description="If True, always re-parse and rebuild, ignoring any cached repository_model.json "
        "for the requested (repository_id, commit_sha) even if one exists.",
    )
    max_file_size_bytes: int = Field(
        default=2_000_000,
        gt=0,
        description="Python source files larger than this many bytes are skipped during the walk.",
    )
    ignored_directories: list[str] = Field(
        default_factory=list,
        description="Additional directory names to exclude from the walk, beyond the built-in "
        "defaults (.git, __pycache__, .venv, node_modules, etc.).",
    )
    enable_call_graph: bool = Field(
        default=True,
        description="If True, build the call graph via name-based call-site resolution. If False, "
        "RepositoryModel.call_graph is always empty and no call resolution is performed.",
    )
    enable_inheritance_graph: bool = Field(
        default=True,
        description="If True, build the class inheritance graph via name-based base-class "
        "resolution. If False, RepositoryModel.inheritance_graph is always empty.",
    )
