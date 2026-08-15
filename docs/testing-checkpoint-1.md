# Testing Checkpoint 1

## 1. Automated tests

```powershell
uv sync --extra dev
uv run ruff check .
uv run mypy backend/src/maintainerflow
uv run pytest -m "not e2e"
```

Expected: Ruff and mypy exit `0`; all selected tests pass.

## 2. Start the real stack

Start a Docker-compatible daemon, then:

```powershell
Copy-Item .env.example .env
```

Set a unique value of at least 16 characters for
`MAINTAINERFLOW_GITHUB_WEBHOOK_SECRET` in `.env`, then run:

```powershell
docker compose up --build -d --wait
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
```

Expected: `db`, `redis`, `api`, `worker`, `recovery`, and `frontend` are running; health is `ok` and readiness
is `ready`. `migrate` should have exited successfully.

## 3. Signed, invalid, and duplicate webhook tests

Use the same secret as `.env`:

```powershell
$secret = "your-webhook-secret"
uv run python scripts/send_test_webhook.py --secret $secret --delivery manual-001
uv run python scripts/send_test_webhook.py --secret $secret --delivery manual-001
```

Expected: the first response is `accepted`; the second is `duplicate` with the same internal ID.
Check that only one row exists and the worker completed it:

```powershell
docker compose exec -T db psql -U maintainerflow -d maintainerflow -c `
  "SELECT github_delivery_id,status,attempts FROM deliveries WHERE github_delivery_id='manual-001';"
```

Expected: one row, `status=completed`, `attempts=1`.

Now send an invalid signature:

```powershell
uv run python scripts/send_test_webhook.py --secret $secret `
  --delivery invalid-001 --invalid-signature
```

Expected: HTTP `401`. Confirm that no row was stored:

```powershell
docker compose exec -T db psql -U maintainerflow -d maintainerflow -c `
  "SELECT count(*) FROM deliveries WHERE github_delivery_id='invalid-001';"
```

Expected: `0`.

## 4. Run Docker E2E tests

With the stack running, export the secret used by `.env`:

```powershell
$env:RUN_E2E = "1"
$env:MAINTAINERFLOW_GITHUB_WEBHOOK_SECRET = $secret
uv run pytest -m e2e
```

The E2E suite verifies service startup and waits until a signed webhook reaches `completed` in
PostgreSQL.

## 5. Real GitHub App demo

1. Create a GitHub App owned by your account or organization.
2. Set its Webhook URL to a public HTTPS tunnel ending in `/webhooks/github`.
3. Use exactly the same webhook secret as `.env`.
4. Grant repository metadata read access and pull-request read access only; subscribe to Pull
   request events.
5. Install the app on a disposable public test repository.
6. Open a PR, then push another commit to exercise both `opened` and `synchronize`.
7. In the GitHub App delivery page, verify HTTP `202` for both deliveries.
8. Run the database query below and verify two distinct completed delivery IDs:

```powershell
docker compose exec -T db psql -U maintainerflow -d maintainerflow -c `
  "SELECT github_delivery_id,action,status,attempts FROM deliveries ORDER BY id DESC LIMIT 10;"
```

Capture the GitHub delivery response and the database result for the Checkpoint 1 demo evidence.
Checkpoint 1 does not create a GitHub Check Run; that begins in Checkpoint 3.

## 6. Shutdown

```powershell
docker compose down
```

Use `docker compose down -v` only when you intentionally want to delete the local PostgreSQL and
Redis volumes.
