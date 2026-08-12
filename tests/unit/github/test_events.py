import pytest

from maintainerflow.core.errors import InvalidEventPayloadError, UnsupportedEventError
from maintainerflow.core.schemas import CheckRunFeedbackEnvelope
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


def test_parses_allowlisted_check_feedback() -> None:
    payload = {
        "action": "requested_action",
        "requested_action": {"identifier": "useful"},
        "check_run": {"name": "MaintainerFlow", "external_id": "42"},
        "installation": {"id": 2},
        "repository": {"id": 1, "name": "repo", "owner": {"login": "owner"}},
        "sender": {"id": 3, "login": "human", "type": "User"},
    }
    event = parse_event("check_run", payload)
    assert isinstance(event, CheckRunFeedbackEnvelope)
    assert event.analysis_id == 42 and event.identifier == "useful"


def test_rejects_unknown_check_feedback_action() -> None:
    payload = {
        "action": "requested_action",
        "requested_action": {"identifier": "merge"},
        "check_run": {"name": "MaintainerFlow", "external_id": "42"},
        "installation": {"id": 2},
        "repository": {"id": 1, "name": "repo", "owner": {"login": "owner"}},
        "sender": {"id": 3, "login": "human", "type": "User"},
    }
    with pytest.raises(UnsupportedEventError):
        parse_event("check_run", payload)
