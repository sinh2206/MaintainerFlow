import base64
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from maintainerflow.core.errors import PermanentDependencyError, TransientDependencyError
from maintainerflow.core.schemas import ChangedFile, ChangeType, PullRequestSource, RepositoryRef

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
