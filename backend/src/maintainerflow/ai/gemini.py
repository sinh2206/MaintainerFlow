import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError

from maintainerflow.ai.base import (
    AIAnalysisInput,
    AIAnalysisOutput,
    AIProviderError,
    AIProviderMetadata,
    AIProviderResult,
)

DEFAULT_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"


class GeminiProvider:
    def __init__(
        self,
        api_key: SecretStr,
        *,
        model: str = "gemini-3.5-flash-lite",
        timeout: float = 30,
        max_retries: int = 2,
        retry_delay: float = 0.2,
        endpoint: str = DEFAULT_ENDPOINT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.endpoint = endpoint
        self.client = client
        self.system_instruction = (
            Path(__file__)
            .with_name("prompts")
            .joinpath("pr_analysis.md")
            .read_text(encoding="utf-8")
        )

    @staticmethod
    def _output_text(payload: dict[str, Any]) -> str:
        if isinstance(payload.get("output_text"), str):
            return str(payload["output_text"])
        for step in reversed(payload.get("steps", [])):
            if step.get("type") != "model_output":
                continue
            texts = [
                item.get("text", "")
                for item in step.get("content", [])
                if item.get("type") == "text"
            ]
            if texts:
                return "".join(texts)
        raise AIProviderError("invalid_response", retryable=False)

    async def analyze(self, request: AIAnalysisInput) -> AIProviderResult:
        body = {
            "model": self.model,
            "input": request.model_dump_json(),
            "system_instruction": self.system_instruction,
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": AIAnalysisOutput.model_json_schema(),
            },
        }
        owned_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=self.timeout)
        started = time.perf_counter()
        try:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.post(
                        self.endpoint,
                        headers={"x-goog-api-key": self.api_key.get_secret_value()},
                        json=body,
                        timeout=self.timeout,
                    )
                except httpx.TimeoutException as exc:
                    if attempt < self.max_retries:
                        await asyncio.sleep(self.retry_delay * (2**attempt))
                        continue
                    raise AIProviderError("timeout", retryable=True) from exc
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self.max_retries:
                        await asyncio.sleep(self.retry_delay * (2**attempt))
                        continue
                    code = "rate_limited" if response.status_code == 429 else "unavailable"
                    raise AIProviderError(code, retryable=True)
                if response.is_error:
                    raise AIProviderError(f"http_{response.status_code}", retryable=False)
                try:
                    payload = response.json()
                    output = AIAnalysisOutput.model_validate_json(self._output_text(payload))
                except (json.JSONDecodeError, ValidationError, TypeError, KeyError) as exc:
                    raise AIProviderError("invalid_response", retryable=False) from exc
                usage = payload.get("usage", {})
                return AIProviderResult(
                    output=output,
                    metadata=AIProviderMetadata(
                        provider="gemini",
                        model=self.model,
                        latency_ms=int((time.perf_counter() - started) * 1000),
                        input_tokens=usage.get("total_input_tokens"),
                        output_tokens=usage.get("total_output_tokens"),
                    ),
                )
            raise AIProviderError("unavailable", retryable=True)
        finally:
            if owned_client:
                await client.aclose()
