import pytest
from pydantic import ValidationError

from maintainerflow.config import Settings


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "github_app_id": 1,
        "github_webhook_secret": "test-webhook-secret-value",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "redis_url": "redis://localhost:6379/15",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"workflow_enabled": True, "github_private_key": ""},
        {"ai_enabled": True, "gemini_api_key": ""},
        {"check_publish_enabled": True},
        {"issue_triage_enabled": True},
        {"repository_intelligence_enabled": True},
        {"issue_store_body": True},
        {"repository_store_source_code": True},
    ],
)
def test_enabled_features_require_credentials_and_workflow(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        settings(**overrides)


def test_full_workflow_configuration_is_valid() -> None:
    configured = settings(
        workflow_enabled=True,
        check_publish_enabled=True,
        github_private_key="private-key",
        ai_enabled=True,
        gemini_api_key="gemini-key",
    )
    assert configured.check_mode == "shadow"
