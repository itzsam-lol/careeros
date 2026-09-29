"""Routes each logical AI task to its configured provider and model.

Agents first ask `uses_llm(task)`: when a task is routed to `local`, they run their
deterministic heuristic path instead of calling a model. Every provider call is retried with
exponential backoff + jitter for transient errors and metered through a `UsageSink`.
"""

from __future__ import annotations

import asyncio
import functools
import json
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from careeros.config import LLMProviderName, LLMTask, Settings
from careeros.core.errors import ConfigurationError, LLMProviderError
from careeros.core.logging import get_logger
from careeros.llm.embeddings import HashingEmbedder
from careeros.llm.schema_utils import schema_for
from careeros.llm.types import (
    Embedder,
    GenerationRequest,
    GenerationResult,
    LLMMessage,
    LLMProvider,
    StructuredOutput,
    UsageEvent,
)
from careeros.llm.usage import NullUsageSink, UsageSink

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R", GenerationResult, StructuredOutput)


class LLMRouter:
    def __init__(
        self,
        settings: Settings,
        *,
        usage: UsageSink | None = None,
        providers: dict[str, LLMProvider] | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self._settings = settings
        self._usage = usage or NullUsageSink()
        self._providers: dict[str, LLMProvider] = dict(providers or {})
        self._embedder = embedder

    # --- routing ---------------------------------------------------------------------------

    def provider_name(self, task: LLMTask) -> LLMProviderName:
        return self._settings.provider_for(task)

    def uses_llm(self, task: LLMTask) -> bool:
        return self.provider_name(task) != "local"

    def model_for(self, task: LLMTask) -> str:
        provider = self.provider_name(task)
        model = self._settings.model_for(provider, task)
        if not model:
            raise ConfigurationError(
                f"No model configured for {provider}/{task.value}: set "
                f"{provider.upper()}_MODEL_{task.value.upper()} or {provider.upper()}_MODEL_DEFAULT"
            )
        return model

    def _provider(self, name: LLMProviderName) -> LLMProvider:
        if name not in self._providers:
            if name == "bedrock":
                from careeros.llm.providers.bedrock import BedrockClaudeProvider

                self._providers[name] = BedrockClaudeProvider(self._settings)
            elif name == "gemini":
                from careeros.llm.providers.gemini import GeminiProvider

                self._providers[name] = GeminiProvider(self._settings)
            else:
                raise ConfigurationError(
                    f"Task is routed to local heuristics, not a model ({name})"
                )
        return self._providers[name]

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            name = self._settings.embedding_provider
            if name == "bedrock":
                from careeros.llm.providers.bedrock import BedrockEmbedder

                self._embedder = MeteredEmbedder(BedrockEmbedder(self._settings), self._usage, name)
            elif name == "gemini":
                from careeros.llm.providers.gemini import GeminiEmbedder

                self._embedder = MeteredEmbedder(GeminiEmbedder(self._settings), self._usage, name)
            else:
                self._embedder = HashingEmbedder()
        return self._embedder

    # --- calls -----------------------------------------------------------------------------

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        provider_name = self.provider_name(request.task)
        provider = self._provider(provider_name)
        model = self.model_for(request.task)
        return await self._metered(
            lambda: provider.generate(request, model=model),
            task=request.task,
            provider=provider_name,
            model=model,
            operation="generate",
        )

    async def structured(self, request: GenerationRequest, schema: type[T]) -> T:
        """Schema-constrained generation with one self-repair round on validation failure."""
        provider_name = self.provider_name(request.task)
        provider = self._provider(provider_name)
        model = self.model_for(request.task)
        json_schema = schema_for(schema)
        current = request
        for attempt in range(2):
            output = await self._metered(
                functools.partial(provider.structured_generate, current, json_schema, model=model),
                task=request.task,
                provider=provider_name,
                model=model,
                operation="structured",
            )
            try:
                return schema.model_validate(output.data)
            except ValidationError as exc:
                log.warning(
                    "llm_schema_validation_failed",
                    task=request.task.value,
                    attempt=attempt,
                    errors=exc.error_count(),
                )
                if attempt == 1:
                    raise LLMProviderError(
                        "The AI provider returned output that failed validation", retryable=False
                    ) from exc
                problems = "; ".join(
                    f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
                    for err in exc.errors()[:8]
                )
                current = replace(
                    request,
                    messages=[
                        *request.messages,
                        LLMMessage("assistant", json.dumps(output.data)[:6000]),
                        LLMMessage(
                            "user",
                            f"Your output failed schema validation ({problems}). "
                            "Return a corrected result that follows the schema exactly.",
                        ),
                    ],
                )
        raise AssertionError("unreachable")  # pragma: no cover

    async def _metered(
        self,
        call: Callable[[], Awaitable[R]],
        *,
        task: LLMTask,
        provider: str,
        model: str,
        operation: str,
    ) -> R:
        attempts = self._settings.llm_max_retries + 1
        for attempt in range(attempts):
            started = time.perf_counter()
            try:
                result = await asyncio.wait_for(call(), timeout=self._settings.llm_timeout_seconds)
            except (LLMProviderError, TimeoutError) as exc:
                retryable = isinstance(exc, TimeoutError) or exc.retryable
                await self._usage.record(
                    UsageEvent(
                        task=task.value,
                        provider=provider,
                        model=model,
                        operation=operation,  # type: ignore[arg-type]
                        success=False,
                        latency_ms=(time.perf_counter() - started) * 1000,
                        error_type=type(exc).__name__,
                    )
                )
                if not retryable or attempt == attempts - 1:
                    if isinstance(exc, TimeoutError):
                        raise LLMProviderError("The AI provider timed out", retryable=True) from exc
                    raise
                delay = min(20.0, 1.5 * 2**attempt) * (0.5 + random.random())
                log.info("llm_retry", task=task.value, attempt=attempt + 1, delay_s=round(delay, 2))
                await asyncio.sleep(delay)
                continue
            await self._usage.record(
                UsageEvent(
                    task=task.value,
                    provider=provider,
                    model=model,
                    operation=operation,  # type: ignore[arg-type]
                    success=True,
                    latency_ms=result.latency_ms or (time.perf_counter() - started) * 1000,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                )
            )
            return result
        raise AssertionError("unreachable")  # pragma: no cover


class MeteredEmbedder:
    """Records every remote embedding call in the usage sink."""

    def __init__(self, inner: Embedder, usage: UsageSink, provider: str) -> None:
        self._inner = inner
        self._usage = usage
        self._provider = provider
        self.model = inner.model
        self.dimensions = inner.dimensions

    def calibrate(self, cosine_similarity: float) -> float:
        return self._inner.calibrate(cosine_similarity)

    async def _metered(
        self, call: Callable[[], Awaitable[list[list[float]]]], count: int
    ) -> list[list[float]]:
        started = time.perf_counter()
        try:
            vectors = await call()
        except Exception as exc:
            await self._usage.record(
                UsageEvent(
                    task="embedding",
                    provider=self._provider,
                    model=self.model,
                    operation="embed",
                    success=False,
                    latency_ms=(time.perf_counter() - started) * 1000,
                    error_type=type(exc).__name__,
                    metadata={"texts": count},
                )
            )
            raise
        await self._usage.record(
            UsageEvent(
                task="embedding",
                provider=self._provider,
                model=self.model,
                operation="embed",
                success=True,
                latency_ms=(time.perf_counter() - started) * 1000,
                metadata={"texts": count},
            )
        )
        return vectors

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._metered(lambda: self._inner.embed_documents(texts), len(texts))

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self._metered(lambda: _as_batch(self._inner.embed_query(text)), 1)
        return vectors[0]


async def _as_batch(single: Awaitable[list[float]]) -> list[list[float]]:
    return [await single]
