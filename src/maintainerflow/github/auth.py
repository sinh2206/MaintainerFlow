import hashlib
import hmac

from maintainerflow.core.errors import InvalidSignatureError


def verify_webhook_signature(body: bytes, signature: str | None, secret: str) -> None:
    if not signature or not signature.startswith("sha256="):
        raise InvalidSignatureError("missing or malformed webhook signature")

    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise InvalidSignatureError("invalid webhook signature")
