import hashlib
import hmac

from maintainerflow.core.schemas import (
    EventEnvelope,
    InstallationRef,
    PullRequestRef,
    RepositoryRef,
)


def signature(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def make_envelope() -> EventEnvelope:
    return EventEnvelope(
        event="pull_request",
        action="opened",
        repository=RepositoryRef(github_id=1, owner="owner", name="repo"),
        installation=InstallationRef(github_id=2),
        pull_request=PullRequestRef(number=3, base_sha="a" * 40, head_sha="b" * 40),
    )
