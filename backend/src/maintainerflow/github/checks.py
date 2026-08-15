from datetime import UTC, datetime
from pathlib import PurePosixPath
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from maintainerflow.core.errors import PermanentDependencyError, TransientDependencyError
from maintainerflow.core.sanitize import sanitize_text
from maintainerflow.core.schemas import (
    AnalysisResult,
    CheckAction,
    CheckAnnotation,
    CheckPolicyDecision,
    GitHubCheckCommand,
    GitHubCheckStartCommand,
)


def safe_text(value: str, limit: int) -> str:
    return sanitize_text(value, limit, escape_markdown=True)


def _safe_path(path: str) -> bool:
    candidate = PurePosixPath(path)
    return not candidate.is_absolute() and ".." not in candidate.parts


def _check_id(payload: dict[str, object]) -> int:
    value = payload.get("id")
    if not isinstance(value, int):
        raise PermanentDependencyError("github_check_id_missing")
    return value


def build_check_command(
    *,
    analysis_id: int,
    installation_id: int,
    repository_github_id: int,
    owner: str,
    repository: str,
    head_sha: str,
    result: AnalysisResult,
    decision: CheckPolicyDecision,
    provisional_external_id: str | None = None,
) -> GitHubCheckCommand:
    title = f"MaintainerFlow: {result.risk.level.value.upper()} risk ({result.risk.score}/10)"
    sections = [
        safe_text(result.summary, 4_000),
        "## Suggested tests",
        *(f"- {safe_text(item, 500)}" for item in result.suggested_tests[:20]),
        "## Review focus",
        *(f"- {safe_text(item, 500)}" for item in result.review_focus[:20]),
    ]
    if result.limitations:
        sections.extend(
            ["## Limitations", *(f"- {safe_text(item, 500)}" for item in result.limitations[:20])]
        )
    annotations = tuple(
        CheckAnnotation(
            path=item.path,
            start_line=item.line,
            end_line=item.line,
            annotation_level="warning" if result.risk.score >= 7 else "notice",
            title=safe_text(item.kind.replace("_", " ").title(), 255),
            message=safe_text(item.message, 1_000),
        )
        for item in result.evidence
        if item.path and item.line and item.confidence >= 0.7 and _safe_path(item.path)
    )[:50]
    action_labels = {
        "accept": ("Accept", "Accept this recommendation"),
        "reject": ("Reject", "Reject this recommendation"),
        "useful": ("Useful", "Mark this report useful"),
        "not_useful": ("Not useful", "Mark this report not useful"),
    }
    actions = tuple(
        CheckAction(
            label=action_labels[item][0], description=action_labels[item][1], identifier=item
        )
        for item in decision.actions[:3]
    )
    return GitHubCheckCommand(
        analysis_id=analysis_id,
        installation_id=installation_id,
        repository_github_id=repository_github_id,
        owner=owner,
        repository=repository,
        head_sha=head_sha,
        external_id=str(analysis_id),
        provisional_external_id=provisional_external_id,
        conclusion=decision.conclusion,
        title=safe_text(title, 255),
        summary=safe_text(result.summary, 65_535),
        text="\n".join(sections)[:65_535],
        annotations=annotations,
        actions=actions,
    )


class GitHubRateLimitError(TransientDependencyError):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, retry_after)
        super().__init__("github_rate_limited")


class GitHubChecksClient:
    def __init__(
        self,
        token: SecretStr,
        *,
        base_url: str = "https://api.github.com",
        api_version: str = "2026-03-10",
        timeout: float = 20,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self.timeout = timeout
        self.client = client

    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        *,
        json: object | None = None,
    ) -> httpx.Response:
        try:
            response = await client.request(
                method,
                url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self.token.get_secret_value()}",
                    "X-GitHub-Api-Version": self.api_version,
                },
                timeout=self.timeout,
                json=json,
            )
        except httpx.TimeoutException as exc:
            raise TransientDependencyError("github_timeout") from exc
        if response.status_code in {403, 429} and (
            response.headers.get("retry-after")
            or response.headers.get("x-ratelimit-remaining") == "0"
        ):
            retry_after = response.headers.get("retry-after")
            raise GitHubRateLimitError(
                int(retry_after) if retry_after and retry_after.isdigit() else 60
            )
        if response.status_code >= 500:
            raise TransientDependencyError("github_unavailable")
        if response.is_error:
            raise PermanentDependencyError(f"github_http_{response.status_code}")
        return response

    async def _find_checks(
        self,
        client: httpx.AsyncClient,
        *,
        owner: str,
        repository: str,
        head_sha: str,
    ) -> tuple[str, list[dict[str, object]]]:
        slug = f"{quote(owner, safe='')}/{quote(repository, safe='')}"
        root = f"{self.base_url}/repos/{slug}"
        listed = await self._request(
            client,
            "GET",
            f"{root}/commits/{head_sha}/check-runs?check_name=MaintainerFlow&filter=all&per_page=100",
        )
        return root, listed.json().get("check_runs", [])

    async def start(self, command: GitHubCheckStartCommand) -> int:
        owned_client = self.client is None
        client = self.client or httpx.AsyncClient(follow_redirects=True)
        try:
            root, checks = await self._find_checks(
                client,
                owner=command.owner,
                repository=command.repository,
                head_sha=command.head_sha,
            )
            existing = next(
                (item for item in checks if item.get("external_id") == command.external_id),
                checks[0] if checks else None,
            )
            if existing:
                check_id = _check_id(existing)
                if existing.get("status") == "completed":
                    return check_id
            else:
                created = await self._request(
                    client,
                    "POST",
                    f"{root}/check-runs",
                    json={
                        "name": "MaintainerFlow",
                        "head_sha": command.head_sha,
                        "external_id": command.external_id,
                        "status": "queued",
                    },
                )
                check_id = _check_id(created.json())
            timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            await self._request(
                client,
                "PATCH",
                f"{root}/check-runs/{check_id}",
                json={"name": "MaintainerFlow", "status": "in_progress", "started_at": timestamp},
            )
            return check_id
        finally:
            if owned_client:
                await client.aclose()

    async def publish(self, command: GitHubCheckCommand) -> int:
        owned_client = self.client is None
        client = self.client or httpx.AsyncClient(follow_redirects=True)
        try:
            root, checks = await self._find_checks(
                client,
                owner=command.owner,
                repository=command.repository,
                head_sha=command.head_sha,
            )
            external_ids = {command.external_id, command.provisional_external_id}
            existing = next(
                (item for item in checks if item.get("external_id") in external_ids),
                None,
            )
            if existing:
                check_id = _check_id(existing)
            else:
                created = await self._request(
                    client,
                    "POST",
                    f"{root}/check-runs",
                    json={
                        "name": "MaintainerFlow",
                        "head_sha": command.head_sha,
                        "external_id": command.external_id,
                        "status": "queued",
                    },
                )
                check_id = _check_id(created.json())
            timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            await self._request(
                client,
                "PATCH",
                f"{root}/check-runs/{check_id}",
                json={"name": "MaintainerFlow", "status": "in_progress", "started_at": timestamp},
            )
            await self._request(
                client,
                "PATCH",
                f"{root}/check-runs/{check_id}",
                json={
                    "name": "MaintainerFlow",
                    "status": "completed",
                    "external_id": command.external_id,
                    "conclusion": command.conclusion,
                    "completed_at": timestamp,
                    "output": {
                        "title": command.title,
                        "summary": command.summary,
                        "text": command.text,
                        "annotations": [
                            item.model_dump(mode="json") for item in command.annotations
                        ],
                    },
                    "actions": [item.model_dump(mode="json") for item in command.actions],
                },
            )
            return check_id
        finally:
            if owned_client:
                await client.aclose()
