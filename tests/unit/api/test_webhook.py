import json

from fastapi.testclient import TestClient

from tests.helpers import signature


def headers(body: bytes, secret: str, delivery: str = "delivery-1") -> dict[str, str]:
    return {
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": delivery,
        "X-Hub-Signature-256": signature(body, secret),
        "Content-Type": "application/json",
    }


def test_invalid_signature_does_not_enqueue(
    app_client: tuple[TestClient, list[int], str], github_payload: dict[str, object]
) -> None:
    client, queued, _ = app_client
    response = client.post(
        "/webhooks/github",
        content=json.dumps(github_payload),
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "invalid-signature",
            "X-Hub-Signature-256": "sha256=invalid",
        },
    )

    assert response.status_code == 401
    assert queued == []


def test_valid_webhook_is_enqueued_once(
    app_client: tuple[TestClient, list[int], str],
    github_payload: dict[str, object],
    webhook_secret: str,
) -> None:
    client, queued, _ = app_client
    body = json.dumps(github_payload, separators=(",", ":")).encode()

    first = client.post("/webhooks/github", content=body, headers=headers(body, webhook_secret))
    duplicate = client.post("/webhooks/github", content=body, headers=headers(body, webhook_secret))

    assert first.status_code == 202
    assert first.json()["status"] == "accepted"
    assert duplicate.status_code == 202
    assert duplicate.json() == {"status": "duplicate", "delivery_id": first.json()["delivery_id"]}
    assert queued == [first.json()["delivery_id"]]


def test_unsupported_event_is_acknowledged_without_enqueue(
    app_client: tuple[TestClient, list[int], str],
    github_payload: dict[str, object],
    webhook_secret: str,
) -> None:
    client, queued, _ = app_client
    github_payload["action"] = "closed"
    body = json.dumps(github_payload).encode()
    response = client.post("/webhooks/github", content=body, headers=headers(body, webhook_secret))

    assert response.status_code == 202
    assert response.json() == {"status": "ignored", "delivery_id": None}
    assert queued == []


def test_malformed_json_returns_400_after_valid_signature(
    app_client: tuple[TestClient, list[int], str], webhook_secret: str
) -> None:
    client, queued, _ = app_client
    body = b"{not-json"
    response = client.post("/webhooks/github", content=body, headers=headers(body, webhook_secret))

    assert response.status_code == 400
    assert queued == []
