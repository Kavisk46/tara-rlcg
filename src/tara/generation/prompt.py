"""Prompt construction for the LLM Interface.

Turns a query, a `FusedContext`, and an optional `TaskClassification`
into an assembled `Prompt`, independent of any LLM provider. Kept
deliberately separate from `tara.interfaces.code_generator.CodeGenerator`
(the invocation side): `PromptBuilder` makes no network call and knows
nothing about any specific provider, so prompt design can be iterated on
and tested without a provider in the loop, and provider adapters can be
tested without prompt-assembly logic in the loop. See
`tara.generation.service.CodeGenerationService`, which wires the two
together.
"""
from __future__ import annotations

from enum import Enum

from tara.classification.models import TaskClassification
from tara.fusion.models import FusedChunk, FusedContext
from tara.generation.models import Prompt

_SYSTEM_MESSAGE = (
    "You are a code-generation assistant working inside a specific software "
    "repository. Answer the developer's query using only the repository context "
    "provided below. If the provided context is insufficient to answer "
    "confidently, say so explicitly rather than inventing repository details "
    "that were not retrieved."
)


class PromptTemplate(str, Enum):
    """Named prompt-assembly variants.

    `WITH_TASK_CLASSIFICATION` exists specifically as PROJECT_SPEC.md
    §21/§26's ablation lever A9: "Surfacing `TaskClassification` to the
    LLM prompt vs. not... tests whether the classification itself is a
    useful generation-time signal beyond its use in retrieval." Neither
    variant is asserted here to produce better generations -- that is
    an empirical question for the (not-yet-run) evaluation this
    milestone explicitly does not start.
    """

    BASELINE = "baseline"
    WITH_TASK_CLASSIFICATION = "with_task_classification"


class PromptBuilder:
    """Assembles a `Prompt` from a query, a `FusedContext`, and an optional `TaskClassification`.

    Stateless aside from its configured `template`: a single instance
    can be reused freely across queries. Formats each `FusedChunk` with
    enough provenance (file path, symbol name, line range) to be both
    human-inspectable and machine-parseable, per PROJECT_SPEC.md §20.4's
    formatting requirement for this exact hand-off.
    """

    def __init__(self, template: PromptTemplate = PromptTemplate.BASELINE) -> None:
        """Construct the builder.

        Args:
            template: Which named variant to assemble. Defaults to
                `BASELINE` (query + context only, no `TaskClassification`
                surfaced) -- the conservative default, consistent with
                this milestone's own instruction not to assume any
                particular prompt design is superior ahead of evaluation.
        """
        self._template = template

    def build(
        self,
        query: str,
        fused_context: FusedContext,
        task_classification: TaskClassification | None = None,
    ) -> Prompt:
        """Assemble a `Prompt` for `query`, per this builder's configured `template`.

        Args:
            query: The original developer query text.
            fused_context: The fused, deduplicated, budgeted context to
                include, e.g. the output of
                `tara.fusion.fusion.ContextFusion.fuse`. An empty
                `fused_context.chunks` (no candidates retrieved) is
                handled cleanly, producing a prompt that says so
                explicitly rather than an empty or malformed section.
            task_classification: The query's `TaskClassification`, if
                available. Only included in the assembled prompt when
                this builder's `template` is
                `PromptTemplate.WITH_TASK_CLASSIFICATION`; passing one
                in under `PromptTemplate.BASELINE` is not an error, it
                is simply unused -- "where appropriate" per this stage's
                own contract.

        Returns:
            An assembled `Prompt`, ready for `CodeGenerator.generate`.
        """
        sections = [f"# Developer Query\n{query}"]

        surface_classification = self._template is PromptTemplate.WITH_TASK_CLASSIFICATION
        if surface_classification and task_classification is not None:
            sections.append(self._format_task_classification(task_classification))

        sections.append(self._format_context(fused_context))

        return Prompt(system=_SYSTEM_MESSAGE, user="\n\n".join(sections))

    @staticmethod
    def _format_task_classification(classification: TaskClassification) -> str:
        return (
            "# Task Classification\n"
            f"Task type: {classification.task_type.value}\n"
            f"Recommended retrieval strategy: {classification.retriever_kind.value}"
        )

    @staticmethod
    def _format_context(fused_context: FusedContext) -> str:
        if not fused_context.chunks:
            return "# Repository Context\n(No repository context was retrieved for this query.)"

        sections = ["# Repository Context"]
        sections.extend(PromptBuilder._format_chunk(chunk) for chunk in fused_context.chunks)
        if fused_context.truncated:
            sections.append(
                "(Note: additional relevant context existed but was omitted to fit the token "
                "budget.)"
            )
        return "\n\n".join(sections)

    @staticmethod
    def _format_chunk(chunk: FusedChunk) -> str:
        location = chunk.file_path
        if chunk.start_line is not None and chunk.end_line is not None:
            location += f":{chunk.start_line}-{chunk.end_line}"
        header = f"## {chunk.name} ({location})"
        docstring = f"{chunk.docstring}\n" if chunk.docstring else ""
        return f"{header}\n{docstring}```\n{chunk.content}\n```"
