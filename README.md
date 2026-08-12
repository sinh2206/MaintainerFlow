# MaintainerFlow

MaintainerFlow is a safe, evidence-backed maintainer intelligence engine. Checkpoint 1 ingests
GitHub webhooks idempotently, Checkpoint 2 creates reproducible PR analysis, and Checkpoint 3
publishes a non-blocking GitHub Check through an idempotent transactional outbox.

## Quick start

```bash
Copy-Item .env.example .env
# Replace MAINTAINERFLOW_GITHUB_WEBHOOK_SECRET in .env
docker compose up --build
```

Verify the stack:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Expected responses are `{"status":"ok"}` and `{"status":"ready"}`.

Analyze a versioned local PR fixture without a GitHub token or AI key:

```bash
uv run maintainerflow analyze \
  --input benchmarks/datasets/pr-risk/fixtures/05-authentication.json
```

Gemini is optional. To add semantic signals, provide an ignored/local `GEMINI_API_KEY` and append
`--ai`. The default model is `gemini-3.5-flash-lite`; provider failure retains the static report.

## Enable the GitHub Check workflow

Create a GitHub App with these minimum repository permissions:

- **Contents:** Read-only
- **Pull requests:** Read-only
- **Checks:** Read and write

Subscribe only to **Pull request** and **Check run** events. Install it only on repositories that
MaintainerFlow should analyze. Then set these local values in `.env`:

```dotenv
MAINTAINERFLOW_GITHUB_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
MAINTAINERFLOW_WORKFLOW_ENABLED=true
MAINTAINERFLOW_CHECK_PUBLISH_ENABLED=true
MAINTAINERFLOW_CHECK_MODE=shadow
```

`shadow` is the recommended first mode: every result is non-blocking and neutral. The installation
token is additionally narrowed to the current repository and to `contents:read`,
`pull_requests:read`, and `checks:write`. MaintainerFlow never requests permission to merge, close,
label, release, or modify repository contents.

## Local quality gate

```bash
uv sync --extra dev
uv run ruff check .
uv run mypy src/maintainerflow
uv run pytest -m "not e2e"
```

See [checkpoint.md](checkpoint.md) for acceptance criteria and
[CONTRIBUTING.md](CONTRIBUTING.md) for development instructions. The complete manual, Docker,
duplicate-delivery, and real GitHub App test procedure is in
[docs/testing-checkpoint-1.md](docs/testing-checkpoint-1.md).
Checkpoint 2 validation and the 10-fixture benchmark are documented in
[docs/testing-checkpoint-2.md](docs/testing-checkpoint-2.md).
Checkpoint 3 setup, automated gates, and the live five-PR verification are in
[docs/testing-checkpoint-3.md](docs/testing-checkpoint-3.md).

## Security boundary

- Only `pull_request.opened` and `pull_request.synchronize` are queued.
- `X-Hub-Signature-256` is verified against the raw request body before JSON parsing.
- Redis messages contain only the internal delivery ID; the webhook secret and raw body are not
  logged.
- Processing is at-least-once and idempotent through the unique GitHub delivery ID.
- Check creation and completion use leased outbox records and `external_id=analysis_id`; retry
  reuses the existing Check instead of creating another.
- Untrusted report text and secret-like values are sanitized before persistence and GitHub output.
- Requested actions are feedback-only: `accept`, `reject`, `useful`, or `not_useful`.

MaintainerFlow does not merge, close, label, release, or persist the full diff.
