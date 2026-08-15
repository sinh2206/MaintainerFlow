from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from maintainerflow.core.schemas import Evidence, Risk


class AISignal(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str = Field(min_length=1, max_length=64)
    path: str | None = Field(default=None, max_length=4096)
    line: int | None = Field(default=None, ge=1)
    message: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0, le=1)


class AIAnalysisInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    body: str
    diff_excerpt: str = Field(max_length=100_000)
    files: tuple[str, ...]
    static_risk: Risk
    static_evidence: tuple[Evidence, ...]


class AIAnalysisOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary: str = Field(min_length=1, max_length=2000)
    risk_adjustment: float = Field(default=0, ge=-2, le=2)
    risk_reasons: tuple[AISignal, ...] = ()
    suggested_tests: tuple[str, ...] = ()
    review_focus: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class AIProviderMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    latency_ms: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)


class AIProviderResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    output: AIAnalysisOutput
    metadata: AIProviderMetadata


class AIProviderError(Exception):
    def __init__(self, code: str, *, retryable: bool) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(code)


class AIProvider(Protocol):
    async def analyze(self, request: AIAnalysisInput) -> AIProviderResult: ...
