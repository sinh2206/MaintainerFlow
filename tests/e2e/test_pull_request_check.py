import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from maintainerflow.core.policies import decide_check_policy
from maintainerflow.core.schemas import GitHubCheckStartCommand, PullRequestSource
from maintainerflow.github.checks import GitHubChecksClient, build_check_command
from maintainerflow.services.analyze_pull_request import analyze_pull_request

DATASET = Path(__file__).parents[2] / "benchmarks/datasets/pr-risk"
pytestmark = pytest.mark.e2e


async def test_five_pr_heads_each_get_one_completed_check() -> None:
    checks: dict[str, dict[str, object]] = {}
    history: dict[int, list[str]] = {}
    posts = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal posts
        body = json.loads(request.content or b"{}")
        if request.method == "GET":
            head = request.url.path.split("/commits/", 1)[1].split("/", 1)[0]
            return httpx.Response(
                200, json={"check_runs": [checks[head]] if head in checks else []}
            )
        if request.method == "POST":
            posts += 1
            check_id = 100 + posts
            checks[body["head_sha"]] = {
                "id": check_id,
                "external_id": body["external_id"],
                "status": body["status"],
            }
            history[check_id] = [body["status"]]
            return httpx.Response(201, json={"id": check_id})
        check_id = int(request.url.path.rsplit("/", 1)[1])
        history[check_id].append(body["status"])
        for check in checks.values():
            if check["id"] == check_id:
                check["status"] = body["status"]
                if "external_id" in body:
                    check["external_id"] = body["external_id"]
        return httpx.Response(200, json={})

    manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    http = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    publisher = GitHubChecksClient(SecretStr("token"), client=http)
    for analysis_id, case in enumerate(manifest["fixtures"][:5], start=1):
        source = PullRequestSource.model_validate_json(
            (DATASET / case["path"]).read_text(encoding="utf-8")
        )
        run = await analyze_pull_request(source)
        start = GitHubCheckStartCommand(
            delivery_id=analysis_id,
            installation_id=1,
            repository_github_id=source.repository.github_id,
            owner=source.repository.owner,
            repository=source.repository.name,
            head_sha=source.head_sha,
            external_id=f"delivery:{analysis_id}",
        )
        command = build_check_command(
            analysis_id=analysis_id,
            installation_id=1,
            repository_github_id=source.repository.github_id,
            owner=source.repository.owner,
            repository=source.repository.name,
            head_sha=source.head_sha,
            result=run.result,
            decision=decide_check_policy(run.result, mode="shadow"),
            provisional_external_id=start.external_id,
        )
        assert await publisher.start(start)
        check_id = await publisher.publish(command)
        assert await publisher.publish(command) == check_id
    await http.aclose()

    assert posts == len(checks) == 5
    assert all(check["status"] == "completed" for check in checks.values())
    assert all(
        states[:4] == ["queued", "in_progress", "in_progress", "completed"]
        for states in history.values()
    )
