from pydantic import ValidationError

from maintainerflow.core.errors import InvalidEventPayloadError, UnsupportedEventError
from maintainerflow.core.schemas import (
    CheckRunFeedbackEnvelope,
    EventEnvelope,
    InstallationRef,
    IssueEventEnvelope,
    IssueRef,
    JsonObject,
    PullRequestRef,
    RepositoryRef,
)

SUPPORTED_ACTIONS = frozenset({"opened", "synchronize"})
FEEDBACK_ACTIONS = frozenset({"accept", "reject", "useful", "not_useful"})


def parse_event(
    event_name: str, payload: JsonObject
) -> EventEnvelope | IssueEventEnvelope | CheckRunFeedbackEnvelope:
    action = payload.get("action")
    if event_name == "check_run" and action == "requested_action":
        try:
            requested_action = payload["requested_action"]
            identifier = requested_action["identifier"]
            check_run = payload["check_run"]
            repository = payload["repository"]
            owner = repository["owner"]
            installation = payload["installation"]
            sender = payload["sender"]
            if identifier not in FEEDBACK_ACTIONS or check_run.get("name") != "MaintainerFlow":
                raise UnsupportedEventError(f"unsupported check action: {identifier}")
            return CheckRunFeedbackEnvelope(
                repository=RepositoryRef(
                    github_id=repository["id"],
                    owner=owner["login"],
                    name=repository["name"],
                ),
                installation=InstallationRef(github_id=installation["id"]),
                analysis_id=int(check_run["external_id"]),
                identifier=identifier,
                actor_id=sender["id"],
                actor_login=sender["login"],
                actor_type=sender["type"],
            )
        except UnsupportedEventError:
            raise
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise InvalidEventPayloadError("invalid check_run payload") from exc
    if event_name == "issues" and action == "opened":
        try:
            repository = payload["repository"]
            owner = repository["owner"]
            installation = payload["installation"]
            issue = payload["issue"]
            return IssueEventEnvelope(
                event="issues",
                action="opened",
                repository=RepositoryRef(
                    github_id=repository["id"], owner=owner["login"], name=repository["name"]
                ),
                installation=InstallationRef(github_id=installation["id"]),
                issue=IssueRef(github_id=issue["id"], number=issue["number"]),
            )
        except (KeyError, TypeError, ValidationError) as exc:
            raise InvalidEventPayloadError("invalid issues payload") from exc
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
