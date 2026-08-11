import json

import httpx
import pytest
from pydantic import SecretStr

from maintainerflow.ai.base import AIAnalysisInput, AIAnalysisOutput, AIProviderError
from maintainerflow.ai.gemini import GeminiProvider
from maintainerflow.core.enums import RiskLevel
from maintainerflow.core.schemas import Risk


def request() -> AIAnalysisInput:
    return AIAnalysisInput(
        title="PR",
        body="Body",
        diff_excerpt="diff",
        files=("src/a.py",),
        static_risk=Risk(score=4, level=RiskLevel.MEDIUM, confidence=0.9),
        static_evidence=(),
    )


def provider(handler: httpx.MockTransport) -> GeminiProvider:
    return GeminiProvider(
        SecretStr("test-gemini-key"),
        client=httpx.AsyncClient(transport=handler),
        max_retries=0,
    )


@pytest.mark.asyncio
async def test_valid_structured_response() -> None:
    output = AIAnalysisOutput(summary="Safe summary", suggested_tests=("Run unit tests",))

    def handle(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "steps": [
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": output.model_dump_json()}],
                    }
                ],
                "usage": {"total_input_tokens": 10, "total_output_tokens": 5},
            },
        )

    result = await provider(httpx.MockTransport(handle)).analyze(request())
    assert result.output == output
    assert result.metadata.input_tokens == 10


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["malformed", "timeout", "rate_limit"])
async def test_typed_failures_do_not_expose_raw_output(mode: str) -> None:
    secret_raw = "raw-provider-secret-output"

    def handle(request_: httpx.Request) -> httpx.Response:
        if mode == "timeout":
            raise httpx.ReadTimeout("timeout", request=request_)
        if mode == "rate_limit":
            return httpx.Response(429, json={"error": secret_raw})
        return httpx.Response(
            200,
            json={
                "steps": [
                    {
                        "type": "model_output",
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps({"summary": secret_raw, "risk_adjustment": 99}),
                            }
                        ],
                    }
                ]
            },
        )

    with pytest.raises(AIProviderError) as caught:
        await provider(httpx.MockTransport(handle)).analyze(request())
    assert secret_raw not in str(caught.value)
