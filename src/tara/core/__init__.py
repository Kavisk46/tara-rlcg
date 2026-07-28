"""Cross-cutting infrastructure shared by every TARA pipeline stage.

Contains configuration (`tara.core.config`), logging setup
(`tara.core.logging`), the exception hierarchy (`tara.core.exceptions`),
and shared enums (`tara.core.types`). Nothing in this package depends on
any other TARA subpackage, so it can be imported safely from anywhere.
"""
from __future__ import annotations
