import hashlib
import hmac

import pytest

from maintainerflow.core.errors import InvalidSignatureError
from maintainerflow.github.auth import verify_webhook_signature

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
