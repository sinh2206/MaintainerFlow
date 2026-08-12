import base64
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from maintainerflow.analysis.history import (
    HistoricalCommit,
    HistoricalPullRequest,
    collect_history_evidence,
)
from maintainerflow.analysis.languages.base import RepositoryFile
from maintainerflow.core.errors import PermanentDependencyError, TransientDependencyError
from maintainerflow.core.schemas import (
    ChangedFile,
    ChangeType,
    Evidence,
    PullRequestSource,
    RepositoryRef,
)
from maintainerflow.issue.schemas import IssueSource

STATUS_MAP: dict[str, ChangeType] = {
    "added": "added",
    "removed": "deleted",
    "modified": "modified",
    "renamed": "renamed",
    "changed": "modified",
    "copied": "added",
}


@dataclass(frozen=True)
class RateLimitMetadata:
    remaining: int | None
    reset_at: int | None


@dataclass(frozen=True)
class FetchedPullRequest:
    source: PullRequestSource
    rate_limit: RateLimitMetadata


@dataclass(frozen=True)
class FetchedHistory:
    evidence: tuple[Evidence, ...]
    rate_limit: RateLimitMetadata
    truncated_by_budget: bool = False


class GitHubClient:
    def __init__(
        self,
        token: SecretStr,
        *,
        timeout: float = 20,
        max_pages: int = 20,
        base_url: str = "https://api.github.com",
        api_version: str = "2026-03-10",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.token = token
        self.timeout = timeout
        self.max_pages = max_pages
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self.client = client

    @staticmethod
    def _rate_limit(response: httpx.Response) -> RateLimitMetadata:
        def integer(name: str) -> int | None:
            value = response.headers.get(name)
            return int(value) if value and value.isdigit() else None

        return RateLimitMetadata(integer("x-ratelimit-remaining"), integer("x-ratelimit-reset"))

    async def _get(self, client: httpx.AsyncClient, url: str, *, accept: str) -> httpx.Response:
        try:
            response = await client.get(
                url,
                headers={
                    "Accept": accept,
                    "Authorization": f"Bearer {self.token.get_secret_value()}",
                    "X-GitHub-Api-Version": self.api_version,
                },
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise TransientDependencyError("GitHub request timed out") from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise TransientDependencyError("GitHub API temporarily unavailable")
        if response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0":
            raise TransientDependencyError("GitHub API rate limit exhausted")
        if response.is_error:
            raise PermanentDependencyError(f"github_http_{response.status_code}")
        return response

    async def _paginate(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        rate_limit_floor: int = 0,
    ) -> tuple[list[dict[str, Any]], RateLimitMetadata, bool]:
        items: list[dict[str, Any]] = []
        rate = RateLimitMetadata(None, None)
        for page in range(1, self.max_pages + 1):
            separator = "&" if "?" in url else "?"
            response = await self._get(
                client,
                f"{url}{separator}per_page=100&page={page}",
                accept="application/vnd.github+json",
            )
            page_items = response.json()
            if not isinstance(page_items, list):
                raise PermanentDependencyError("github_invalid_page")
            items.extend(page_items)
            rate = self._rate_limit(response)
            if rate.remaining is not None and rate.remaining <= rate_limit_floor:
                return items, rate, True
            if len(page_items) < 100:
                return items, rate, False
        return items, rate, True

    @staticmethod
    def _issue(item: dict[str, Any], repository: RepositoryRef) -> IssueSource:
        labels = tuple(
            str(label.get("name", "")) if isinstance(label, dict) else str(label)
            for label in item.get("labels", [])
        )
        return IssueSource(
            repository=repository,
            github_id=int(item["id"]),
            number=int(item["number"]),
            title=str(item.get("title", "")),
            body=str(item.get("body") or ""),
            url=str(item.get("html_url") or item.get("url")),
            labels=tuple(label for label in labels if label),
        )

    async def fetch_issue(self, repository: RepositoryRef, number: int) -> IssueSource:
        slug = f"{quote(repository.owner, safe='')}/{quote(repository.name, safe='')}"
        owned_client = self.client is None
        client = self.client or httpx.AsyncClient()
        try:
            response = await self._get(
                client,
                f"{self.base_url}/repos/{slug}/issues/{number}",
                accept="application/vnd.github.raw+json",
            )
            payload = response.json()
            if "pull_request" in payload:
                raise PermanentDependencyError("github_issue_is_pull_request")
            return self._issue(payload, repository)
        finally:
            if owned_client:
                await client.aclose()

    async def fetch_default_branch_sha(self, owner: str, repo: str) -> str:
        slug = f"{quote(owner, safe='')}/{quote(repo, safe='')}"
        owned_client = self.client is None
        client = self.client or httpx.AsyncClient()
        try:
            metadata = await self._get(
                client,
                f"{self.base_url}/repos/{slug}",
                accept="application/vnd.github+json",
            )
            branch = quote(str(metadata.json()["default_branch"]), safe="")
            commit = await self._get(
                client,
                f"{self.base_url}/repos/{slug}/commits/{branch}",
                accept="application/vnd.github+json",
            )
            return str(commit.json()["sha"])
        finally:
            if owned_client:
                await client.aclose()

    async def list_issues(
        self,
        repository: RepositoryRef,
        *,
        state: str = "all",
        rate_limit_floor: int = 0,
    ) -> tuple[IssueSource, ...]:
        slug = f"{quote(repository.owner, safe='')}/{quote(repository.name, safe='')}"
        owned_client = self.client is None
        client = self.client or httpx.AsyncClient()
        try:
            rows, _, _ = await self._paginate(
                client,
                f"{self.base_url}/repos/{slug}/issues?state={quote(state)}",
                rate_limit_floor=rate_limit_floor,
            )
            return tuple(self._issue(row, repository) for row in rows if "pull_request" not in row)
        finally:
            if owned_client:
                await client.aclose()

    async def list_repository_labels(self, owner: str, repo: str) -> tuple[str, ...]:
        slug = f"{quote(owner, safe='')}/{quote(repo, safe='')}"
        owned_client = self.client is None
        client = self.client or httpx.AsyncClient()
        try:
            rows, _, _ = await self._paginate(client, f"{self.base_url}/repos/{slug}/labels")
            return tuple(str(item["name"]) for item in rows)
        finally:
            if owned_client:
                await client.aclose()

    async def fetch_repository_files(
        self,
        owner: str,
        repo: str,
        sha: str,
        *,
        max_files: int = 1_000,
        max_file_bytes: int = 200_000,
    ) -> tuple[RepositoryFile, ...]:
        slug = f"{quote(owner, safe='')}/{quote(repo, safe='')}"
        owned_client = self.client is None
        client = self.client or httpx.AsyncClient()
        try:
            response = await self._get(
                client,
                f"{self.base_url}/repos/{slug}/git/trees/{quote(sha)}?recursive=1",
                accept="application/vnd.github+json",
            )
            rows = response.json().get("tree", [])
            selected = [row for row in rows if row.get("type") == "blob"][:max_files]
            files = []
            for row in selected:
                path = str(row["path"])
                size = int(row.get("size", 0))
                content = (
                    await self.fetch_file_content(owner, repo, path, sha)
                    if path.endswith(".py") and size <= max_file_bytes
                    else None
                )
                files.append(
                    RepositoryFile(
                        path=path,
                        sha=str(row["sha"]),
                        size=size,
                        content=(
                            content.decode("utf-8", errors="replace")
                            if content is not None
                            else None
                        ),
                    )
                )
            return tuple(files)
        finally:
            if owned_client:
                await client.aclose()

    async def fetch_repository_history(
        self,
        owner: str,
        repo: str,
        *,
        rate_limit_floor: int = 100,
        limit: int = 20,
    ) -> FetchedHistory:
        slug = f"{quote(owner, safe='')}/{quote(repo, safe='')}"
        base = f"{self.base_url}/repos/{slug}"
        owned_client = self.client is None
        client = self.client or httpx.AsyncClient()
        rate = RateLimitMetadata(None, None)
        truncated = False
        pulls: list[HistoricalPullRequest] = []
        commits: list[HistoricalCommit] = []
        try:
            pull_rows, rate, truncated = await self._paginate(
                client,
                f"{base}/pulls?state=closed",
                rate_limit_floor=rate_limit_floor,
            )
            for pull in pull_rows[:limit]:
                if rate.remaining is not None and rate.remaining <= rate_limit_floor:
                    truncated = True
                    break
                number = int(pull["number"])
                file_rows, rate, stopped = await self._paginate(
                    client, f"{base}/pulls/{number}/files", rate_limit_floor=rate_limit_floor
                )
                if stopped:
                    truncated = True
                    break
                review_rows, rate, review_stopped = await self._paginate(
                    client, f"{base}/pulls/{number}/reviews", rate_limit_floor=rate_limit_floor
                )
                truncated = truncated or stopped or review_stopped
                pulls.append(
                    HistoricalPullRequest(
                        github_id=int(pull["id"]),
                        number=number,
                        url=str(pull["html_url"]),
                        title=str(pull.get("title", "")),
                        files=tuple(str(item["filename"]) for item in file_rows),
                        reviewer_logins=tuple(
                            str(item["user"]["login"])
                            for item in review_rows
                            if item.get("user", {}).get("login")
                        ),
                    )
                )
            if rate.remaining is not None and rate.remaining <= rate_limit_floor:
                return FetchedHistory(collect_history_evidence(tuple(pulls), ()), rate, True)
            commit_rows, rate, stopped = await self._paginate(
                client, f"{base}/commits", rate_limit_floor=rate_limit_floor
            )
            truncated = truncated or stopped
            for item in commit_rows[:limit]:
                if rate.remaining is not None and rate.remaining <= rate_limit_floor:
                    truncated = True
                    break
                detail = await self._get(
                    client,
                    f"{base}/commits/{item['sha']}",
                    accept="application/vnd.github+json",
                )
                rate = self._rate_limit(detail)
                payload = detail.json()
                commits.append(
                    HistoricalCommit(
                        sha=str(payload["sha"]),
                        url=str(payload["html_url"]),
                        message=str(payload.get("commit", {}).get("message", "")),
                        files=tuple(str(file["filename"]) for file in payload.get("files", [])),
                    )
                )
            return FetchedHistory(
                collect_history_evidence(tuple(pulls), tuple(commits)), rate, truncated
            )
        finally:
            if owned_client:
                await client.aclose()

    async def fetch_pull_request(self, owner: str, repo: str, number: int) -> FetchedPullRequest:
        slug = f"{quote(owner, safe='')}/{quote(repo, safe='')}"
        base_url = f"{self.base_url}/repos/{slug}"
        owned_client = self.client is None
        client = self.client or httpx.AsyncClient()
        try:
            metadata_response = await self._get(
                client, f"{base_url}/pulls/{number}", accept="application/vnd.github+json"
            )
            metadata = metadata_response.json()
            files: list[ChangedFile] = []
            for page in range(1, self.max_pages + 1):
                response = await self._get(
                    client,
                    f"{base_url}/pulls/{number}/files?per_page=100&page={page}",
                    accept="application/vnd.github+json",
                )
                page_items = response.json()
                files.extend(
                    ChangedFile(
                        path=item["filename"],
                        previous_path=item.get("previous_filename"),
                        change_type=STATUS_MAP.get(str(item.get("status")), "unknown"),
                        additions=item.get("additions", 0),
                        deletions=item.get("deletions", 0),
                        patch=item.get("patch", ""),
                    )
                    for item in page_items
                )
                if len(page_items) < 100:
                    break
            base_sha = metadata["base"]["sha"]
            head_sha = metadata["head"]["sha"]
            diff_response = await self._get(
                client,
                f"{base_url}/compare/{base_sha}...{head_sha}",
                accept="application/vnd.github.v3.diff",
            )
            source = PullRequestSource(
                repository=RepositoryRef(
                    github_id=metadata["base"]["repo"]["id"], owner=owner, name=repo
                ),
                number=number,
                base_sha=base_sha,
                head_sha=head_sha,
                title=metadata.get("title", ""),
                body=metadata.get("body") or "",
                diff=diff_response.text,
                changed_files=tuple(files),
            )
            return FetchedPullRequest(source, self._rate_limit(diff_response))
        finally:
            if owned_client:
                await client.aclose()

    async def fetch_file_content(self, owner: str, repo: str, path: str, sha: str) -> bytes:
        slug = f"{quote(owner, safe='')}/{quote(repo, safe='')}"
        url = f"{self.base_url}/repos/{slug}/contents/{quote(path)}?ref={quote(sha)}"
        owned_client = self.client is None
        client = self.client or httpx.AsyncClient()
        try:
            response = await self._get(client, url, accept="application/vnd.github+json")
            payload = response.json()
            return base64.b64decode(payload["content"], validate=True)
        finally:
            if owned_client:
                await client.aclose()
