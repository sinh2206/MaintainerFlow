# Testing Checkpoint 2

Checkpoint 2 is valid only when the deterministic engine, persistence contract, fixtures, CLI, and
optional-provider failure path all pass. A Gemini key is not required for the automated gate.

## 1. Install and run the quality gate

```powershell
uv sync --frozen --extra dev
uv run ruff check .
uv run mypy backend/src/maintainerflow
uv run pytest -m "not e2e"
uv run pytest tests/e2e/test_cli_analyze.py -m e2e
```

The CLI E2E test loads all entries in `benchmarks/datasets/pr-risk/manifest.json`. At least 9/10
must match their allowed category; the committed baseline is 10/10.

## 2. Manual static demo

```powershell
uv run maintainerflow analyze `
  --input benchmarks/datasets/pr-risk/fixtures/05-authentication.json
```

Expected: JSON schema version `1`, `risk.level=high`, evidence kinds
`authentication_change` and `missing_tests`, plus focused test suggestions.

Run a docs-only fixture and confirm it remains LOW:

```powershell
uv run maintainerflow analyze `
  --input benchmarks/datasets/pr-risk/fixtures/01-readme-only.json
```

## 3. Optional Gemini demo

Store the key only in the process environment or an ignored local env file. Then run:

```powershell
$env:GEMINI_API_KEY = "<your-key>"
uv run maintainerflow analyze `
  --input benchmarks/datasets/pr-risk/fixtures/04-core-no-tests.json `
  --ai
```

Expected: `provider_metadata.provider=gemini` and model `gemini-3.5-flash-lite`. Invalid JSON,
timeout, and rate-limit behavior are covered with mocked HTTP responses; raw provider output is not
propagated through exceptions.

## 4. Migration and privacy checks

Run Alembic upgrade, downgrade, upgrade, then `alembic check` against a disposable database. The
integration tests also assert that one snapshot creates only one analysis and that
`analysis_snapshots` has hashes/version metadata but no full-diff column.
