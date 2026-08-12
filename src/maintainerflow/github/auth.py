import hashlib
import hmac
import time

import httpx
import jwt
from pydantic import SecretStr

from maintainerflow.core.errors import (
    InvalidSignatureError,
    PermanentDependencyError,
    TransientDependencyError,
)


def verify_webhook_signature(body: bytes, signature: str | None, secret: str) -> None:
    if not signature or not signature.startswith("sha256="):
        raise InvalidSignatureError("missing or malformed webhook signature")

    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise InvalidSignatureError("invalid webhook signature")


class GitHubAppAuthenticator:
    def __init__(
        self,
        app_id: int,
        private_key: SecretStr,
        *,
        base_url: str = "https://api.github.com",
        api_version: str = "2026-03-10",
        timeout: float = 20,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.app_id = app_id
        self.private_key = private_key
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self.timeout = timeout
        self.client = client

    def app_jwt(self) -> str:
        now = int(time.time())
        key = self.private_key.get_secret_value().replace("\\n", "\n")
        return jwt.encode(
            {"iat": now - 60, "exp": now + 540, "iss": str(self.app_id)},
            key,
            algorithm="RS256",
        )

    async def installation_token(
        self,
        installation_id: int,
        *,
        repository_id: int | None = None,
        issues_read: bool = False,
        checks_write: bool = True,
    ) -> SecretStr:
        owned_client = self.client is None
        client = self.client or httpx.AsyncClient()
        permissions = {"contents": "read", "pull_requests": "read"}
        if checks_write:
            permissions["checks"] = "write"
        if issues_read:
            permissions["issues"] = "read"
        body: dict[str, object] = {"permissions": permissions}
        if repository_id is not None:
            body["repository_ids"] = [repository_id]
        try:
            try:
                response = await client.post(
                    f"{self.base_url}/app/installations/{installation_id}/access_tokens",
                    headers={
                        "Accept": "application/vnd.github+json",
                        "Authorization": f"Bearer {self.app_jwt()}",
                        "X-GitHub-Api-Version": self.api_version,
                    },
                    json=body,
                    timeout=self.timeout,
                )
            except httpx.TimeoutException as exc:
                raise TransientDependencyError("GitHub token request timed out") from exc
            if response.status_code == 429 or response.status_code >= 500:
                raise TransientDependencyError("GitHub token service unavailable")
            if response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0":
                raise TransientDependencyError("GitHub token rate limit exhausted")
            if response.is_error:
                raise PermanentDependencyError(
                    f"GitHub token request rejected ({response.status_code})"
                )
            token = response.json().get("token")
            if not isinstance(token, str) or not token:
                raise PermanentDependencyError("GitHub token response was invalid")
            return SecretStr(token)
        finally:
            if owned_client:
                await client.aclose()
