# Testing Checkpoint 4

CP4 is accepted only when its offline benchmark, CP1–CP4 contracts, PostgreSQL migration, and
privacy defaults all pass.

## Credential-free checks

```powershell
uv sync --frozen --extra dev
uv run ruff format --check .
uv run ruff check .
uv run mypy src/maintainerflow
uv run pytest -m "not e2e"
uv run pytest tests/e2e/test_issue_triage.py -m e2e
uv run python benchmarks/runners/issue_triage.py
```

Required benchmark thresholds are Macro F1 `>= 0.80` and duplicate Recall@3 `>= 0.75`. The runner
prints dataset versions, Macro F1, Recall@3, and MRR and exits non-zero below either threshold.

## Compose and migration checks

```powershell
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
docker compose run --rm --no-deps migrate alembic check
```

Expected migration head is `0004_issue_repository_context`. Test downgrade/upgrade only against a
disposable database, never a production database.

## Live GitHub smoke test

The GitHub App needs `Contents: read`, `Pull requests: read`, `Issues: read`, and the `Issues` event.
Enable `WORKFLOW_ENABLED`, `ISSUE_TRIAGE_ENABLED`, and optionally
`REPOSITORY_INTELLIGENCE_ENABLED`; keep both content-storage settings false.

Open one test issue. The delivery must complete with an `issue_analyses` row and an
`issue.triage.suggested` audit event. Confirm no label, assignment, close, comment, Check Run, or
repository content change was created. Repository intelligence may raise PR risk through traceable
criticality/history evidence; the ablation unit test proves the same PR has a lower static score
without that context.
