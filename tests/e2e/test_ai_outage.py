from pathlib import Path

import pytest

from maintainerflow.ai.base import AIAnalysisInput, AIProviderError
from maintainerflow.core.enums import AnalysisStatus
from maintainerflow.core.policies import decide_check_policy
from maintainerflow.core.schemas import PullRequestSource
from maintainerflow.github.checks import build_check_command
from maintainerflow.services.analyze_pull_request import analyze_pull_request

FIXTURE = Path(__file__).parents[2] / "benchmarks/datasets/pr-risk/fixtures/04-core-no-tests.json"
pytestmark = pytest.mark.e2e


class OfflineProvider:
    async def analyze(self, _: AIAnalysisInput) -> None:
        raise AIProviderError("timeout", retryable=True)


async def test_ai_outage_keeps_static_partial_check() -> None:
    source = PullRequestSource.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    run = await analyze_pull_request(source, ai_provider=OfflineProvider())
    command = build_check_command(
        analysis_id=1,
        installation_id=1,
        repository_github_id=source.repository.github_id,
        owner=source.repository.owner,
        repository=source.repository.name,
        head_sha=source.head_sha,
        result=run.result,
        decision=decide_check_policy(run.result, mode="shadow"),
    )
    assert run.result.status == AnalysisStatus.PARTIAL
    assert run.result.evidence
    assert "AI analysis unavailable" in command.text
    assert command.conclusion == "neutral"
