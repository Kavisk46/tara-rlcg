"""Data contracts for the LLM Interface: `Prompt` (input) and `GeneratedCode` (output).

Per PROJECT_SPEC.md §21: the LLM Interface consumes a `Prompt` -- already
assembled by `tara.generation.prompt.PromptBuilder` from the original
query, a `FusedContext`, and optionally a `TaskClassification` -- and
produces a `GeneratedCode` result. Deliberately two separate models,
mirroring how `RetrievedContext` (input to fusion) and `FusedContext`
(output of fusion) are kept distinct in `tara.fusion`.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Prompt(BaseModel):
    """An assembled prompt, ready to hand to a `CodeGenerator`.

    Kept as two parts (`system`/`user`) rather than one flat string:
    every mainstream chat-completion API (OpenAI, Anthropic) accepts
    system instructions and user content as distinct fields, and
    collapsing that distinction here would force every future concrete
    provider adapter to re-derive it. `PromptBuilder` is the only
    component that constructs a `Prompt`; a `CodeGenerator` only ever
    consumes one -- this is the interface boundary between prompt
    construction and LLM invocation.
    """

    system: str = Field(
        ...,
        description="Fixed, provider-facing instructions describing the assistant's role and "
        "constraints.",
    )
    user: str = Field(
        ...,
        min_length=1,
        description="The assembled user-facing content: query, optional task context, and "
        "retrieved code context.",
    )


class GeneratedCode(BaseModel):
    """The complete output of a single `CodeGenerator.generate` call.

    Per PROJECT_SPEC.md §21: "Provider, model identifier, and all
    generation parameters used for any reported result must be recorded
    in `GeneratedCode.metadata`" -- `metadata` is where provider-specific
    detail (provider name, temperature, max_tokens, finish reason, ...)
    belongs; the typed fields below are the small set of values every
    provider is expected to be able to report directly.
    """

    text: str = Field(
        ..., description="The generated text. May be empty, e.g. a provider-side content filter."
    )
    model: str = Field(
        ...,
        min_length=1,
        description="The concrete model identifier that produced `text`, e.g. 'gpt-4o-mini' or "
        "'fake-model'.",
    )
    prompt_tokens: int | None = Field(
        default=None,
        ge=0,
        description="Prompt token count, if the provider reports one. None when unavailable.",
    )
    completion_tokens: int | None = Field(
        default=None,
        ge=0,
        description="Completion token count, if the provider reports one. None when unavailable.",
    )
    latency_ms: float = Field(
        ...,
        ge=0.0,
        description="Wall-clock duration of the `generate` call that produced this result, in ms.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific detail: provider name, generation parameters (e.g. "
        "temperature), finish reason, raw usage payload, etc. Not part of the stable contract.",
    )
