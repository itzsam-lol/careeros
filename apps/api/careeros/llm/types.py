from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Protocol

from careeros.config import LLMTask


class EmbeddingPurpose(StrEnum):
    DOCUMENT = "DOCUMENT"
    QUERY = "QUERY"


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(slots=True)
class GenerationRequest:
    task: LLMTask
    system: str
    messages: list[LLMMessage]
    max_tokens: int = 2048
    temperature: float = 0.2


@dataclass(frozen=True, slots=True)
class GenerationResult:
    text: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class StructuredOutput:
    """Raw JSON object returned by a provider for a schema-constrained request."""

    data: dict[str, object]
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class UsageEvent:
    task: str
    provider: str
    model: str
    operation: Literal["generate", "structured", "embed"]
    success: bool
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    error_type: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class LLMProvider(Protocol):
    name: str

    async def generate(self, request: GenerationRequest, *, model: str) -> GenerationResult: ...

    async def structured_generate(
        self, request: GenerationRequest, json_schema: dict[str, object], *, model: str
    ) -> StructuredOutput: ...


class Embedder(Protocol):
    model: str
    dimensions: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...

    def calibrate(self, cosine_similarity: float) -> float:
        """Map a raw cosine similarity to a 0..1 relevance score for this embedding model."""
        ...
