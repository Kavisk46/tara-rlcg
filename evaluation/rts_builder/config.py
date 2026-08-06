"""Configuration for the RTS Builder's Repository Loader (Milestone 1).

Kept as its own settings object, separate from `tara.core.config.TaraSettings`,
since the RTS Builder is data-construction tooling that *consumes* the
`tara` package rather than being part of it (`evaluation/__init__.py`);
mixing its configuration into `TaraSettings` would blur that boundary.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RepositoryLoaderSettings(BaseSettings):
    """Environment-driven configuration for `RepositoryLoader`.

    Every field can be overridden by an environment variable named
    `RTS_<FIELD_NAME>` (uppercased), or by an entry in a local `.env`
    file. See `evaluation/rts_builder/.env.example` for the full list.
    """

    model_config = SettingsConfigDict(env_prefix="RTS_", env_file=".env", extra="ignore")

    clone_root: str = Field(
        default=".rts_cache/repositories",
        description="Local directory under which repositories are cloned, one subdirectory per repository_id.",
    )
    clone_timeout_seconds: int = Field(
        default=300,
        gt=0,
        description="Maximum time allowed for a single git clone operation before it is aborted.",
    )
    ignored_directories: list[str] = Field(
        default_factory=list,
        description="Additional directory names excluded from file/directory counts, beyond the built-in "
        "defaults (.git, node_modules, __pycache__, venv, etc.).",
    )
    max_file_count_warning_threshold: int = Field(
        default=100_000,
        gt=0,
        description="File count above which a warning is logged, since it may indicate a misconfigured "
        "clone (e.g. build artifacts or a dependency directory not excluded).",
    )
    lock_timeout_seconds: int = Field(
        default=600,
        gt=0,
        description="Maximum time to wait to acquire the per-repository lock before raising "
        "RepositoryLockError. Held for the full duration of a load_repository() call, so this "
        "should comfortably exceed the slowest expected clone/fetch.",
    )
    initialize_submodules: bool = Field(
        default=False,
        description="If True, recursively initialize and update git submodules so their content "
        "is included in file/directory counts and language detection. If False (default), "
        "submodule directories are left uninitialized and excluded from all counts, and their "
        "paths are recorded on Repository.submodules instead. Defaults to False so loading a "
        "repository never implicitly clones additional, unvetted third-party repositories.",
    )
