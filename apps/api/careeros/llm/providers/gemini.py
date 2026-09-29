"""Google Gemini via the google-genai SDK (Gemini API key or Vertex AI with ADC)."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from careeros.config import Settings
from careeros.core.errors import ConfigurationError, LLMProviderError
from careeros.db.base import EMBEDDING_DIM
from careeros.llm.embeddings import CalibratedRange, l2_normalize
from careeros.llm.types import GenerationRequest, GenerationResult, StructuredOutput

_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


def build_gemini_client(settings: Settings) -> Any:
    from google import genai

    if settings.gemini_use_vertexai:
        if not settings.google_cloud_project:
            raise ConfigurationError("GOOGLE_CLOUD_PROJECT is required for Gemini on Vertex AI")
        return genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.gemini_vertex_location,
        )
    if settings.gemini_api_key is None:
        raise ConfigurationError("Gemini needs GEMINI_API_KEY or GEMINI_USE_VERTEXAI=true")
    return genai.Client(api_key=settings.gemini_api_key.get_secret_value())


def _wrap_error(exc: Exception) -> LLMProviderError:
    status = getattr(exc, "code", None)
    retryable = isinstance(status, int) and status in _RETRYABLE_STATUS
    return LLMProviderError(
        f"Gemini request failed ({status or type(exc).__name__})",
        details={"provider": "gemini", "status": status},
        retryable=retryable,
    )


class GeminiProvider:
    name = "gemini"

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._client = client or build_gemini_client(settings)

    @staticmethod
    def _contents(request: GenerationRequest) -> list[Any]:
        from google.genai import types

        return [
            types.Content(
                role="model" if message.role == "assistant" else "user",
                parts=[types.Part.from_text(text=message.content)],
            )
            for message in request.messages
        ]

    async def _call(self, request: GenerationRequest, model: str, **config: Any) -> Any:
        from google.genai import errors as genai_errors
        from google.genai import types

        try:
            return await self._client.aio.models.generate_content(
                model=model,
                contents=self._contents(request),
                config=types.GenerateContentConfig(
                    system_instruction=request.system,
                    max_output_tokens=request.max_tokens,
                    temperature=request.temperature,
                    **config,
                ),
            )
        except genai_errors.APIError as exc:
            raise _wrap_error(exc) from exc

    @staticmethod
    def _usage(response: Any) -> tuple[int | None, int | None]:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return None, None
        return usage.prompt_token_count, usage.candidates_token_count

    async def generate(self, request: GenerationRequest, *, model: str) -> GenerationResult:
        started = time.perf_counter()
        response = await self._call(request, model)
        input_tokens, output_tokens = self._usage(response)
        return GenerationResult(
            text=response.text or "",
            provider=self.name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    async def structured_generate(
        self, request: GenerationRequest, json_schema: dict[str, object], *, model: str
    ) -> StructuredOutput:
        started = time.perf_counter()
        response = await self._call(
            request,
            model,
            response_mime_type="application/json",
            response_json_schema=json_schema,
        )
        try:
            data = json.loads(response.text or "")
        except json.JSONDecodeError as exc:
            raise LLMProviderError(
                "Gemini returned invalid JSON", details={"provider": "gemini"}, retryable=True
            ) from exc
        if not isinstance(data, dict):
            raise LLMProviderError("Gemini returned a non-object result", retryable=True)
        input_tokens, output_tokens = self._usage(response)
        return StructuredOutput(
            data=data,
            provider=self.name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=(time.perf_counter() - started) * 1000,
        )


class GeminiEmbedder:
    dimensions = EMBEDDING_DIM
    _batch_size = 100

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.model = settings.gemini_embedding_model
        self._client = client or build_gemini_client(settings)
        # Cosine ranges differ per model (measured: embedding-001 scores unrelated text ~0.7).
        self._range = (
            CalibratedRange(0.62, 0.92)
            if self.model.endswith("embedding-001")
            else CalibratedRange(0.45, 0.85)
        )
        self._per_text = False

    async def _request(self, contents: list[str], task_type: str) -> list[list[float]]:
        from google.genai import errors as genai_errors
        from google.genai import types

        try:
            response = await self._client.aio.models.embed_content(
                model=self.model,
                contents=contents,
                config=types.EmbedContentConfig(
                    task_type=task_type, output_dimensionality=self.dimensions
                ),
            )
        except genai_errors.APIError as exc:
            raise _wrap_error(exc) from exc
        vectors: list[list[float]] = []
        for embedding in response.embeddings or []:
            values = [float(v) for v in (embedding.values or [])]
            if len(values) != self.dimensions:
                raise LLMProviderError("Unexpected embedding size from Gemini")
            # Truncated (MRL) Gemini embeddings must be re-normalised.
            vectors.append(l2_normalize(values))
        return vectors

    async def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        for offset in range(0, len(texts), self._batch_size):
            batch = texts[offset : offset + self._batch_size]
            if not self._per_text:
                result = await self._request(batch, task_type)
                if len(result) == len(batch):
                    vectors.extend(result)
                    continue
                # Multimodal embedding models treat a list as parts of ONE input and return a
                # single vector. Never mis-assign vectors: switch to one request per text.
                self._per_text = True
            semaphore = asyncio.Semaphore(4)

            async def one(text: str, sem: asyncio.Semaphore = semaphore) -> list[float]:
                async with sem:
                    [vector] = await self._request([text], task_type)
                    return vector

            vectors.extend(await asyncio.gather(*(one(text) for text in batch)))
        return vectors

    def calibrate(self, cosine_similarity: float) -> float:
        return self._range(cosine_similarity)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts, "RETRIEVAL_DOCUMENT")

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([text], "RETRIEVAL_QUERY"))[0]
