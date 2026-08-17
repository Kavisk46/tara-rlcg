"""Top-level entry point for the LLM Interface stage.

`(query, FusedContext, TaskClassification) -> GeneratedCode`, per
PROJECT_SPEC.md §15/§21.
"""
from __future__ import annotations

from tara.classification.models import TaskClassification
from tara.fusion.models import FusedContext
from tara.generation.models import GeneratedCode
from tara.generation.prompt import PromptBuilder
from tara.interfaces.code_generator import CodeGenerator


class CodeGenerationService:
    """Composes prompt assembly and provider invocation to fulfil the generation-stage contract.

    Both collaborators are injected (Dependency Inversion, matching
    every other multi-component TARA stage): a caller substitutes
    `code_generator` to swap providers, and `prompt_builder` to swap
    prompt design, independently of each other. This class contains no
    web-framework or API-layer code of any kind -- it is a plain
    library entry point a future FastAPI service would call into, never
    the reverse.
    """

    def __init__(
        self, code_generator: CodeGenerator, prompt_builder: PromptBuilder | None = None
    ) -> None:
        """Construct the service.

        Args:
            code_generator: The provider to invoke, e.g.
                `tara.generation.fake_provider.FakeCodeGenerator` (the
                only implementation this milestone ships -- no real
                network provider exists yet, see that module's
                docstring) or a future concrete adapter.
            prompt_builder: Assembles the `Prompt` handed to
                `code_generator`. Defaults to a plain `PromptBuilder()`
                (the `BASELINE` template) when omitted.
        """
        self._code_generator = code_generator
        self._prompt_builder = prompt_builder or PromptBuilder()

    def generate(
        self,
        query: str,
        fused_context: FusedContext,
        task_classification: TaskClassification | None = None,
    ) -> GeneratedCode:
        """Generate code for `query`, grounded in `fused_context`.

        Args:
            query: The original developer query text.
            fused_context: The fused, budgeted retrieval context to
                ground generation in, e.g. the output of
                `tara.fusion.fusion.ContextFusion.fuse`.
            task_classification: The query's `TaskClassification`, if
                available. Only actually used by the underlying
                `PromptBuilder` when it is configured with
                `PromptTemplate.WITH_TASK_CLASSIFICATION`; passing one
                to a `BASELINE`-configured service is accepted, not an
                error.

        Returns:
            The `GeneratedCode` result from `code_generator`.

        Raises:
            CodeGenerationError: If `code_generator` fails to produce a
                result. Propagated as-is, not wrapped -- this service
                adds no error-handling behavior of its own beyond what
                `CodeGenerator.generate` already contracts.
        """
        prompt = self._prompt_builder.build(query, fused_context, task_classification)
        return self._code_generator.generate(prompt)
