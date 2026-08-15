# MaintainerFlow backend

The backend contains the installable `maintainerflow` Python package, database migrations and its
container image. Repository-wide Python dependency and quality configuration remains in the root
`pyproject.toml` so the backend, CLI, benchmarks and root test suites share one locked environment.

```powershell
uv sync --extra dev
uv run uvicorn maintainerflow.api.main:app --reload
uv run alembic upgrade head
uv run pytest
```

Keep HTTP routes and worker tasks thin. Use `services/` for orchestration, `core/` for contracts and
policy, and `github/`, `ai/` and `persistence/` as external adapters.
