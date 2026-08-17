"""LLM Interface: assembles prompts from retrieved context and invokes a provider-agnostic LLM.

See `tara.interfaces.code_generator.CodeGenerator` for the provider
contract, `tara.generation.prompt.PromptBuilder` for prompt assembly,
and `tara.generation.service.CodeGenerationService` for the top-level
entry point tying the two together. `PROJECT_SPEC.md` §21 describes this
stage's design rationale.

No concrete network provider is implemented here: no LLM API credentials
or configuration exist yet in this project (see `TaraSettings`), so this
package ships only the provider-agnostic interface, prompt assembly, and
`FakeCodeGenerator` -- a deterministic, network-free stand-in used by
every test in this package and available for credential-free local runs.
"""
from __future__ import annotations

from tara.generation.fake_provider import FakeCodeGenerator
from tara.generation.models import GeneratedCode, Prompt
from tara.generation.prompt import PromptBuilder, PromptTemplate
from tara.generation.service import CodeGenerationService

__all__ = [
    "CodeGenerationService",
    "FakeCodeGenerator",
    "GeneratedCode",
    "Prompt",
    "PromptBuilder",
    "PromptTemplate",
]
