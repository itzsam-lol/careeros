"""Claude via Amazon Bedrock (Converse API) and Titan text embeddings."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any

from careeros.config import Settings
from careeros.core.errors import ConfigurationError, LLMProviderError
from careeros.db.base import EMBEDDING_DIM
from careeros.llm.embeddings import CalibratedRange, l2_normalize
from careeros.llm.types import GenerationRequest, GenerationResult, StructuredOutput

_RETRYABLE_CODES = frozenset(
    {
        "ThrottlingException",
        "ServiceUnavailableException",
        "InternalServerException",
        "ModelNotReadyException",
        "ModelTimeoutException",
        "ModelStreamErrorException",
    }
)
_TOOL_NAME = "submit_result"


def _secret(value: Any) -> str | None:
    return value.get_secret_value() if value is not None else None


def build_bedrock_client(settings: Settings) -> Any:
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise ConfigurationError("boto3 is required for the Bedrock provider") from exc
    session = boto3.session.Session(
        aws_access_key_id=_secret(settings.aws_access_key_id),
        aws_secret_access_key=_secret(settings.aws_secret_access_key),
        aws_session_token=_secret(settings.aws_session_token),
        region_name=settings.aws_region,
    )
    return session.client(
        "bedrock-runtime",
        config=Config(
            read_timeout=int(settings.llm_timeout_seconds),
            connect_timeout=10,
            retries={"max_attempts": 1, "mode": "standard"},  # the router owns retries
        ),
    )


async def _invoke(fn: Callable[..., Any], **kwargs: Any) -> Any:
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        return await asyncio.to_thread(fn, **kwargs)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", "ClientError"))
        raise LLMProviderError(
            f"Bedrock request failed ({code})",
            details={"provider": "bedrock", "code": code},
            retryable=code in _RETRYABLE_CODES,
        ) from exc
    except BotoCoreError as exc:
        raise LLMProviderError(
            "Could not reach Bedrock", details={"provider": "bedrock"}, retryable=True
        ) from exc


class BedrockClaudeProvider:
    name = "bedrock"

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._client = client or build_bedrock_client(settings)

    @staticmethod
    def _messages(request: GenerationRequest) -> list[dict[str, Any]]:
        return [{"role": m.role, "content": [{"text": m.content}]} for m in request.messages]

    async def generate(self, request: GenerationRequest, *, model: str) -> GenerationResult:
        started = time.perf_counter()
        response = await _invoke(
            self._client.converse,
            modelId=model,
            system=[{"text": request.system}],
            messages=self._messages(request),
            inferenceConfig={"maxTokens": request.max_tokens, "temperature": request.temperature},
        )
        blocks = response.get("output", {}).get("message", {}).get("content", [])
        text = "".join(block.get("text", "") for block in blocks)
        usage = response.get("usage") or {}
        return GenerationResult(
            text=text,
            provider=self.name,
            model=model,
            input_tokens=usage.get("inputTokens"),
            output_tokens=usage.get("outputTokens"),
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    async def structured_generate(
        self, request: GenerationRequest, json_schema: dict[str, object], *, model: str
    ) -> StructuredOutput:
        """Forces a single tool call whose input schema is the requested output schema."""
        started = time.perf_counter()
        tool = {
            "toolSpec": {
                "name": _TOOL_NAME,
                "description": "Submit the final result. It must follow the input schema exactly.",
                "inputSchema": {"json": json_schema},
            }
        }
        response = await _invoke(
            self._client.converse,
            modelId=model,
            system=[{"text": request.system}],
            messages=self._messages(request),
            inferenceConfig={"maxTokens": request.max_tokens, "temperature": request.temperature},
            toolConfig={"tools": [tool], "toolChoice": {"tool": {"name": _TOOL_NAME}}},
        )
        blocks = response.get("output", {}).get("message", {}).get("content", [])
        usage = response.get("usage") or {}
        for block in blocks:
            tool_use = block.get("toolUse")
            if tool_use and isinstance(tool_use.get("input"), dict):
                return StructuredOutput(
                    data=tool_use["input"],
                    provider=self.name,
                    model=model,
                    input_tokens=usage.get("inputTokens"),
                    output_tokens=usage.get("outputTokens"),
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
        raise LLMProviderError(
            "Bedrock did not return a structured result", details={"provider": "bedrock"}
        )


class BedrockEmbedder:
    """Amazon Titan Text Embeddings v2 at 1024 dimensions (normalised)."""

    dimensions = EMBEDDING_DIM

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.model = settings.bedrock_embedding_model
        self._client = client or build_bedrock_client(settings)
        self._semaphore = asyncio.Semaphore(4)
        self._range = CalibratedRange(0.18, 0.72)

    async def _embed_one(self, text: str) -> list[float]:
        async with self._semaphore:
            response = await _invoke(
                self._client.invoke_model,
                modelId=self.model,
                body=json.dumps(
                    {"inputText": text[:40_000], "dimensions": self.dimensions, "normalize": True}
                ),
                contentType="application/json",
                accept="application/json",
            )
        payload = json.loads(response["body"].read())
        vector = [float(v) for v in payload["embedding"]]
        if len(vector) != self.dimensions:
            raise LLMProviderError("Unexpected embedding size from Bedrock")
        return l2_normalize(vector)

    def calibrate(self, cosine_similarity: float) -> float:
        return self._range(cosine_similarity)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return list(await asyncio.gather(*(self._embed_one(t) for t in texts)))

    async def embed_query(self, text: str) -> list[float]:
        return await self._embed_one(text)
