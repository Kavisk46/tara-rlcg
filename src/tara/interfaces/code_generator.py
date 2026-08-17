"""Abstract interface for the LLM Interface (generation) pipeline stage.

`CodeGenerator` is the provider-agnostic contract the generation stage
depends on, deliberately mirroring `tara.context.embedder.Embedder`'s
shape (an abstract single-call method) -- PROJECT_SPEC.md §21 names this
pairing explicitly. A concrete provider adapter (OpenAI, Anthropic, ...)
would implement `generate`; nothing upstream of it
(`tara.generation.prompt`, `tara.generation.service`) depends on any
specific provider's SDK.

No concrete network provider is implemented against this interface yet:
this project has no LLM API credentials or configuration in place (see
`TaraSettings` / `.env.example`), so the only implementation shipped
alongside this interface is
`tara.generation.fake_provider.FakeCodeGenerator`, a deterministic,
network-free stand-in.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from tara.generation.models import GeneratedCode, Prompt


class CodeGenerator(ABC):
    """Contract for invoking an LLM to produce code from an assembled `Prompt`."""

    @abstractmethod
    def generate(self, prompt: Prompt) -> GeneratedCode:
        """Invoke the underlying model on `prompt`.

        Args:
            prompt: An already-assembled `Prompt` (see
                `tara.generation.prompt.PromptBuilder`). A `CodeGenerator`
                performs no prompt construction of its own -- assembling
                prompt text from a query, `FusedContext`, and optional
                `TaskClassification` is `PromptBuilder`'s responsibility,
                kept deliberately separate so prompt design can change
                without touching provider invocation, and provider
                invocation can be tested without prompt-assembly logic
                in the way.

        Returns:
            A `GeneratedCode` result: the generated text, the model
            identifier that produced it, token counts where available,
            call latency, and any provider-specific metadata.

        Raises:
            CodeGenerationError: If the provider fails to produce a
                valid result, e.g. a network failure, an API error, or
                a response that cannot be parsed into `GeneratedCode`.
        """
        raise NotImplementedError
