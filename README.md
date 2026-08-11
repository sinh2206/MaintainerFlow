# MaintainerFlow

MaintainerFlow is a safe, evidence-backed maintainer intelligence engine. Checkpoint 1 provides
idempotent GitHub webhook ingestion; Checkpoint 2 adds reproducible PR summaries, risk scores,
risk evidence, suggested tests, and review focus without writing anything back to GitHub.

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

## Security boundary

- Only `pull_request.opened` and `pull_request.synchronize` are queued.
- `X-Hub-Signature-256` is verified against the raw request body before JSON parsing.
- Redis messages contain only the internal delivery ID; the webhook secret and raw body are not
  logged.
- Processing is at-least-once and idempotent through the unique GitHub delivery ID.

MaintainerFlow does not merge, close, label, or release anything in Checkpoint 1.
Checkpoint 2 also performs no GitHub write action and never persists the full diff.
