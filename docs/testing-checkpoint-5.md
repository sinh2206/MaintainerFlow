# Testing Checkpoint 5

CP5 is split into an automated technical gate and external/live acceptance. The first is
reproducible from this checkout; it must not be used to claim the second.

## 1. Credential-free gate

```powershell
uv sync --frozen --extra dev
uv run ruff format --check .
uv run ruff check .
uv run mypy backend/src/maintainerflow
uv run pytest -m "not e2e"
uv run pytest -m e2e
uv run maintainerflow benchmark --suite all --format json --output benchmark-report.json
uv run python scripts/smoke_test.py --skip-docker
```

Docker-dependent cases skip when `RUN_E2E` is absent. The remaining E2E cases still build/install a
wheel into a new virtualenv, replay release/benchmark commands in clean processes, test hostile
input, and verify deterministic bytes/metrics.

## 2. Compose, PostgreSQL and migration gate

Keep workflow publishing disabled because the synthetic installation is not real:

```dotenv
MAINTAINERFLOW_WORKFLOW_ENABLED=false
MAINTAINERFLOW_CHECK_PUBLISH_ENABLED=false
```

Then run:

```powershell
docker compose up --build -d --wait
uv run python scripts/smoke_test.py
$env:RUN_E2E = "1"
$env:MAINTAINERFLOW_GITHUB_WEBHOOK_SECRET = "<same value as .env>"
uv run pytest -m e2e
```

Expected: all six long-running services are healthy, Alembic is at
`0005_release_assistant`, schema drift is empty, CP4 data survives the CP5 upgrade/downgrade, and
two concurrent transactions for the same release input create one draft identity.

## 3. Inspect release and benchmark output

```powershell
uv run maintainerflow release `
  --input examples/demo/release-input.json `
  --output demo-notes.md
uv run maintainerflow benchmark `
  --suite all `
  --format markdown `
  --output benchmark-report.md
```

Run each twice and compare with `Get-FileHash`. Release notes must keep PR/compare provenance,
deduplicate contributors, flag breaking candidates for human confirmation, and omit raw HTML.
`--publish` must fail safely. The benchmark report must label AI-only as an offline deterministic
proxy, include dataset/strategy versions, and separate stable metrics from variable latency/cost.

## 4. External acceptance still requiring humans

Before creating the `v1.0.0` annotated tag:

1. Have someone who did not build the project follow README + GitHub App setup from a fresh clone.
2. Complete the credentialed five-PR gate from [Testing CP3](testing-checkpoint-3.md).
3. Create and document a public demo repository from `examples/demo/repository`.
4. Have a maintainer review MaintainerFlow-generated release notes and every breaking candidate.
5. Collect permissioned historical-PR ground truth and external beta feedback; do not relabel the
   current synthetic 60-case dataset as historical evidence.

Record commit/tag, platform, commands, results, reviewers, repository scope, and limitations without
copying secrets, private source, webhook bodies, or provider payloads.
