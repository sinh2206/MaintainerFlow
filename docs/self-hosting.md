# Self-hosting

The included Compose stack is a reproducible single-host baseline, not a managed production
platform. Production operators own TLS, secret management, backups, retention, monitoring and
capacity planning.

## Prerequisites

- Docker Engine/Desktop with Compose v2.
- A public HTTPS hostname for the webhook.
- A GitHub App configured from [github-app-setup.md](github-app-setup.md).
- Optional Gemini API access only after reviewing [privacy.md](privacy.md).

For local development without Docker, install Python 3.12 and `uv`.

## First deployment

Copy `.env.example` to `.env`, replace every example credential, and keep the file outside backups
or encrypt it. The Compose database hostname is `db` and Redis hostname is `redis`.

Validate before starting:

```powershell
docker compose config
docker compose build
docker compose up -d
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
```

The one-shot `migrate` service runs `alembic upgrade head` before API/worker startup. `api`, `db` and
`redis` should be healthy; `worker` and `recovery` should remain running. Inspect failures with
`docker compose logs --tail 200 SERVICE`.

Never use the example PostgreSQL password for an internet-connected deployment. Restrict port 8000
behind an HTTPS reverse proxy and expose only `/webhooks/github` plus health endpoints as needed.
Apply body-size and rate limits at the proxy without rewriting the signed webhook body.

## Production configuration

Minimum hardening:

- Inject App PEM, webhook secret, database credentials and optional Gemini key from a secret
  manager; make them readable only by the runtime identity.
- Use managed/external PostgreSQL and Redis with authentication, encrypted transport, private
  networking and tested failover where availability requires it.
- Run containers read-only where practical, retain the non-root image user, pin image digests and
  scan images before deployment.
- Keep `shadow`, raw-diff/source/body storage off initially. Enable Check publishing only after a
  test repository succeeds.
- Limit installation scope to selected repositories. Protect release tags and the GitHub Actions
  release environment.
- Centralize logs and alert on failed-safe deliveries, expired leases, dead-letter outbox rows,
  signature failures, GitHub rate limits and provider outages.

The application can safely retry deliveries/outbox work, but PostgreSQL remains the coordination
point. Scale workers only after load tests against the same database/Redis. Run one recovery
scheduler per deployment unless duplicate scans have been tested. The current API exposes no
built-in metrics or authentication layer beyond webhook signature verification.

## Backup and restore

Back up PostgreSQL before every upgrade and on a tested schedule. Redis queue persistence is useful
operationally but is not a substitute for PostgreSQL backup.

Example logical backup from the Compose network:

```powershell
docker compose exec -T db pg_dump -U maintainerflow -d maintainerflow -Fc > maintainerflow.dump
Get-FileHash maintainerflow.dump -Algorithm SHA256
```

Store the dump and checksum encrypted, separate from the host, with a retention period matching
your privacy policy. Test restoration regularly into an empty isolated database:

```powershell
docker compose exec -T db createdb -U maintainerflow maintainerflow_restore
Get-Content -AsByteStream maintainerflow.dump |
  docker compose exec -T db pg_restore -U maintainerflow -d maintainerflow_restore --clean --if-exists
```

Do not point a restore exercise at production. After restore, run `alembic current`, application
smoke tests and row-count/audit checks before switching traffic.

## Upgrade

1. Read [CHANGELOG.md](../CHANGELOG.md) and migration notes for every skipped version.
2. Back up PostgreSQL and record current image digest/tag and `alembic current`.
3. Fetch a signed/reviewed semantic tag and verify release `SHA256SUMS`.
4. Build/pull the new image while old services still run.
5. Enter a maintenance window if the migration is not documented as backwards compatible.
6. Run `docker compose run --rm migrate`, then restart API/worker/recovery with the same version.
7. Verify `/health`, `/ready`, delivery processing, audit and a test-repository PR.

Application rollback does not automatically downgrade the schema. Prefer a forward fix. Run
`alembic downgrade` only when that release explicitly documents a safe downgrade and a restore has
been tested. If a migration fails, stop writers and restore the pre-upgrade backup rather than
guessing at partial schema changes.

## Operational smoke test

From a source checkout:

```powershell
uv sync --frozen --extra dev
uv run python scripts/smoke_test.py --start
```

Use no flag when the Compose stack is already running, or `--skip-docker` for the local
install/fixture checks only. A full production smoke test also needs a GitHub App test installation;
the repository cannot supply those credentials.
