import pytest

from maintainerflow.core.errors import InvalidEventPayloadError, UnsupportedEventError
from maintainerflow.github.events import parse_event


@pytest.mark.parametrize("action", ["opened", "synchronize"])
def test_parses_supported_pull_request_actions(
    github_payload: dict[str, object], action: str
) -> None:
    github_payload["action"] = action
    event = parse_event("pull_request", github_payload)

    assert event.action == action
    assert event.repository.owner == "sinh2206"
    assert event.pull_request.number == 5


@pytest.mark.parametrize(
    ("event", "action"),
    [("issues", "opened"), ("pull_request", "closed"), ("push", None)],
)
def test_rejects_unsupported_events(
    github_payload: dict[str, object], event: str, action: str | None
) -> None:
    github_payload["action"] = action
    with pytest.raises(UnsupportedEventError):
        parse_event(event, github_payload)


def test_rejects_malformed_supported_payload(github_payload: dict[str, object]) -> None:
    github_payload.pop("repository")
    with pytest.raises(InvalidEventPayloadError):
        parse_event("pull_request", github_payload)
