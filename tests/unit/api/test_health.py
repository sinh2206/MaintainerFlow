from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from maintainerflow import __version__


def test_liveness_is_independent_from_database(
    app_client: tuple[TestClient, list[int], str],
) -> None:
    client, _, _ = app_client
    client.app.state.database.ping = AsyncMock(return_value=False)

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").status_code == 503


def test_readiness_when_database_is_available(
    app_client: tuple[TestClient, list[int], str],
) -> None:
    client, _, _ = app_client
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_openapi_reports_package_version(
    app_client: tuple[TestClient, list[int], str],
) -> None:
    client, _, _ = app_client
    assert client.get("/openapi.json").json()["info"]["version"] == __version__
