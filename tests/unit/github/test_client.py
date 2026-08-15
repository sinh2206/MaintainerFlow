import base64

import httpx
import pytest
from pydantic import SecretStr

from maintainerflow.core.errors import PermanentDependencyError, TransientDependencyError
from maintainerflow.core.schemas import RepositoryRef
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


@pytest.mark.asyncio
async def test_other_4xx_is_typed_permanent_failure() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(404))
    async with httpx.AsyncClient(transport=transport) as client:
        github = GitHubClient(SecretStr("token"), client=client)
        with pytest.raises(PermanentDependencyError):
            await github.fetch_pull_request("owner", "repo", 7)


@pytest.mark.asyncio
async def test_lists_issues_with_pagination_and_filters_pull_requests() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        if page == 1:
            rows = [
                {
                    "id": index,
                    "number": index,
                    "title": f"Bug {index}",
                    "body": "crash",
                    "html_url": f"https://github.test/issues/{index}",
                    "labels": [{"name": "bug"}],
                }
                for index in range(1, 100)
            ]
            rows.append({**rows[0], "id": 500, "number": 500, "pull_request": {}})
            return httpx.Response(200, json=rows, headers={"x-ratelimit-remaining": "50"})
        return httpx.Response(
            200,
            json=[
                {
                    "id": 101,
                    "number": 101,
                    "title": "Final bug",
                    "body": "error",
                    "html_url": "https://github.test/issues/101",
                    "labels": [],
                }
            ],
            headers={"x-ratelimit-remaining": "49"},
        )

    repository = RepositoryRef(github_id=1, owner="owner", name="repo")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        issues = await GitHubClient(SecretStr("token"), client=client).list_issues(repository)

    assert len(issues) == 100
    assert issues[0].labels == ("bug",)
    assert all(item.number != 500 for item in issues)


@pytest.mark.asyncio
async def test_history_stops_before_next_request_at_rate_budget() -> None:
    paths: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json=[], headers={"x-ratelimit-remaining": "100"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await GitHubClient(SecretStr("token"), client=client).fetch_repository_history(
            "owner", "repo", rate_limit_floor=100
        )

    assert result.truncated_by_budget
    assert paths == ["/repos/owner/repo/pulls"]


@pytest.mark.asyncio
async def test_release_range_deduplicates_prs_across_commits_and_paginates_files() -> None:
    def pull() -> dict[str, object]:
        return {
            "id": 700,
            "number": 7,
            "title": "feat: add release assistant",
            "html_url": "https://github.test/owner/repo/pull/7",
            "user": {"login": "alice"},
            "body": "Release preview",
            "labels": [{"name": "feature"}],
            "merged_at": "2026-08-01T00:00:00Z",
            "merge_commit_sha": "merge7",
        }

    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        headers = {"x-ratelimit-remaining": "500", "x-ratelimit-reset": "1"}
        if "/compare/" in path:
            return httpx.Response(
                200, json={"commits": [{"sha": "c1"}, {"sha": "c2"}]}, headers=headers
            )
        if path.endswith(("/commits/c1/pulls", "/commits/c2/pulls")):
            return httpx.Response(200, json=[pull()], headers=headers)
        if path.endswith("/pulls/7/files"):
            page = int(request.url.params["page"])
            count = 100 if page == 1 else 1
            return httpx.Response(
                200,
                json=[{"filename": f"src/file_{page}_{index}.py"} for index in range(count)],
                headers=headers,
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await GitHubClient(SecretStr("token"), client=client).fetch_release_range(
            "owner", "repo", "v0.4.0", "v1.0.0"
        )

    assert not result.truncated_by_budget
    assert result.compare_url.endswith("/compare/v0.4.0...v1.0.0")
    assert len(result.pull_requests) == 1
    assert result.pull_requests[0].number == 7
    assert len(result.pull_requests[0].changed_files) == 101


@pytest.mark.asyncio
async def test_release_tags_paginate_and_exclude_drafts_or_missing_tags() -> None:
    pages: list[int] = []

    def handle(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        pages.append(page)
        if page == 1:
            rows = [{"tag_name": f"v1.0.{index}", "draft": index == 0} for index in range(100)]
        else:
            rows = [
                {"tag_name": "v0.4.0", "draft": False, "prerelease": True},
                {"tag_name": "", "draft": False},
            ]
        return httpx.Response(200, json=rows, headers={"x-ratelimit-remaining": "500"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        tags = await GitHubClient(SecretStr("token"), client=client).list_release_tags(
            "owner", "repo"
        )

    assert pages == [1, 2]
    assert len(tags) == 100
    assert "v1.0.0" not in tags
    assert tags[-1] == "v0.4.0"


@pytest.mark.asyncio
async def test_release_range_honors_budget_before_per_commit_calls() -> None:
    paths: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(
            200,
            json={"commits": [{"sha": "c1"}]},
            headers={"x-ratelimit-remaining": "100"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await GitHubClient(SecretStr("token"), client=client).fetch_release_range(
            "owner", "repo", "v0.4.0", "v1.0.0", rate_limit_floor=100
        )

    assert result.truncated_by_budget
    assert result.pull_requests == ()
    assert paths == ["/repos/owner/repo/compare/v0.4.0...v1.0.0"]
