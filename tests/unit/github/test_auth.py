import hashlib
import hmac
import json

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import SecretStr

from maintainerflow.core.errors import InvalidSignatureError
from maintainerflow.github.auth import GitHubAppAuthenticator, verify_webhook_signature

SECRET = "a-sufficiently-long-test-secret"
BODY = b'{"action":"opened"}'


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def test_accepts_valid_signature() -> None:
    verify_webhook_signature(BODY, sign(BODY), SECRET)


@pytest.mark.parametrize("value", [None, "", "sha1=abc", "sha256=deadbeef"])
def test_rejects_missing_or_invalid_signature(value: str | None) -> None:
    with pytest.raises(InvalidSignatureError):
        verify_webhook_signature(BODY, value, SECRET)


def test_rejects_body_changed_by_one_byte() -> None:
    with pytest.raises(InvalidSignatureError):
        verify_webhook_signature(BODY + b" ", sign(BODY), SECRET)


@pytest.mark.asyncio
async def test_installation_token_uses_minimal_scoped_permissions() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()

    def handle(request: httpx.Request) -> httpx.Response:
        claims = jwt.decode(
            request.headers["authorization"].removeprefix("Bearer "),
            options={"verify_signature": False},
        )
        assert claims["iss"] == "123"
        assert json.loads(request.content) == {
            "permissions": {"contents": "read", "pull_requests": "read", "checks": "write"},
            "repository_ids": [456],
        }
        return httpx.Response(201, json={"token": "installation-token"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        auth = GitHubAppAuthenticator(123, SecretStr(pem), client=client)
        token = await auth.installation_token(7, repository_id=456)
    assert token.get_secret_value() == "installation-token"
