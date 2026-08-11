from pydantic import ValidationError

from maintainerflow.core.errors import InvalidEventPayloadError, UnsupportedEventError
from maintainerflow.core.schemas import (
    EventEnvelope,
    InstallationRef,
    JsonObject,
    PullRequestRef,
    RepositoryRef,
)

SUPPORTED_ACTIONS = frozenset({"opened", "synchronize"})


def parse_event(event_name: str, payload: JsonObject) -> EventEnvelope:
    action = payload.get("action")
    if event_name != "pull_request" or action not in SUPPORTED_ACTIONS:
        raise UnsupportedEventError(f"unsupported GitHub event: {event_name}.{action}")

    try:
        repository = payload["repository"]
        owner = repository["owner"]
        installation = payload["installation"]
        pull_request = payload["pull_request"]
        return EventEnvelope(
            event="pull_request",
            action=action,
            repository=RepositoryRef(
                github_id=repository["id"],
                owner=owner["login"],
                name=repository["name"],
            ),
            installation=InstallationRef(github_id=installation["id"]),
            pull_request=PullRequestRef(
                number=pull_request["number"],
                base_sha=pull_request["base"]["sha"],
                head_sha=pull_request["head"]["sha"],
            ),
        )
    except (KeyError, TypeError, ValidationError) as exc:
        raise InvalidEventPayloadError("invalid pull_request payload") from exc
