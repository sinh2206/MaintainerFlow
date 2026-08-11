import base64

import httpx
import pytest
from pydantic import SecretStr

from maintainerflow.core.errors import TransientDependencyError
from maintainerflow.github.client import GitHubClient


@pytest.mark.asyncio
async def test_fetches_metadata_paginated_files_diff_and_content() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/pulls/7"):
            return httpx.Response(
                200,
                json={
                    "title": "PR",
                    "body": "Body",
                    "base": {"sha": "a" * 40, "repo": {"id": 10}},
                    "head": {"sha": "b" * 40},
                },
            )
        if path.endswith("/pulls/7/files"):
            page = int(request.url.params["page"])
            count = 100 if page == 1 else 1
            return httpx.Response(
                200,
                json=[
                    {
                        "filename": f"src/file_{page}_{index}.py",
                        "status": "modified",
                        "additions": 1,
                        "deletions": 0,
                    }
                    for index in range(count)
                ],
            )
        if "/compare/" in path:
            return httpx.Response(
                200,
                text="diff --git a/a.py b/a.py",
                headers={"x-ratelimit-remaining": "42", "x-ratelimit-reset": "123"},
            )
        if "/contents/" in path:
            return httpx.Response(200, json={"content": base64.b64encode(b"content").decode()})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        github = GitHubClient(SecretStr("token"), client=client)
        fetched = await github.fetch_pull_request("owner", "repo", 7)
        content = await github.fetch_file_content("owner", "repo", "src/a.py", "b" * 40)
    assert len(fetched.source.changed_files) == 101
    assert fetched.source.diff.startswith("diff --git")
    assert fetched.rate_limit.remaining == 42
    assert content == b"content"


@pytest.mark.asyncio
async def test_rate_limit_is_typed_transient_failure() -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(403, headers={"x-ratelimit-remaining": "0"})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        github = GitHubClient(SecretStr("token"), client=client)
        with pytest.raises(TransientDependencyError):
            await github.fetch_pull_request("owner", "repo", 7)
