# Testing Checkpoint 3

Checkpoint 3 passes locally when CP1 ingestion reaches CP2 analysis, the Check lifecycle is
idempotent, and failure/security gates pass. A Gemini key is not required.

## 1. Automated gate

```powershell
uv sync --frozen --extra dev
uv run ruff check .
uv run mypy src/maintainerflow
uv run pytest -m "not e2e"
uv run pytest tests/e2e/test_pull_request_check.py `
  tests/e2e/test_ai_outage.py `
  tests/e2e/test_prompt_injection.py -m e2e
```

The worker integration tests prove `delivery → analysis → outbox → completed Check`. The local E2E
uses a fake GitHub transport for five distinct head SHAs and repeats every publish; it expects one
Check per SHA with `queued → in_progress → completed`. It also covers AI timeout and adversarial
content without requiring credentials or making external writes.

## 2. Migration gate

Against a disposable database, run:

```powershell
uv run alembic upgrade 0001_foundation
uv run alembic upgrade 0002_pr_analysis
uv run alembic upgrade 0003_checks_outbox_audit
uv run alembic downgrade 0002_pr_analysis
uv run alembic upgrade head
uv run alembic check
```

Expected head: `0003_checks_outbox_audit`, with no new upgrade operations detected.

## 3. Docker regression for CP1

Leave `MAINTAINERFLOW_WORKFLOW_ENABLED=false` when no GitHub App private key is configured:

```powershell
docker compose up --build -d
$env:RUN_E2E = "1"
$env:MAINTAINERFLOW_GITHUB_WEBHOOK_SECRET = "<same value as .env>"
uv run pytest tests/e2e/test_compose_startup.py tests/e2e/test_webhook_flow.py -m e2e
```

This confirms the original CP1 fail-safe path still starts and completes deliveries.

## 4. Live GitHub App gate

Use a disposable test repository. Configure the permissions and events listed in the README, point
the App webhook to `/webhooks/github`, install the App, enable
`MAINTAINERFLOW_WORKFLOW_ENABLED` and `MAINTAINERFLOW_CHECK_PUBLISH_ENABLED`, then open five PRs
with different head SHAs.

For each PR, verify:

1. Exactly one **MaintainerFlow** Check appears.
2. It reaches `completed`; in `shadow` mode its conclusion is `neutral`.
3. `external_id` becomes the persisted analysis ID.
4. Re-delivering the webhook does not create another Check.
5. The Check exposes only feedback actions and cannot merge, close, label, or edit the PR.

The automated suite cannot replace this credentialed external gate. Do not use production
repositories for first validation and never commit the webhook secret, private key, installation
token, or Gemini key.
