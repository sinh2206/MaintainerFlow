# MaintainerFlow

MaintainerFlow turns GitHub pull-request webhooks into safe, evidence-backed, non-blocking Check
Runs, shadow-mode Issue triage, deterministic release drafts, and reproducible offline evaluation.
The current `v1.0.0` workflow combines:

- **CP1 — ingestion:** signed, idempotent GitHub webhook delivery and recovery.
- **CP2 — intelligence:** reproducible summary, risk, evidence, suggested tests, and review focus.
- **CP3 — publishing:** policy-gated GitHub Checks through a leased transactional outbox.
- **CP4 — repository intelligence:** Issue classification, priority/label suggestions, lexical
  duplicate ranking, Python AST/dependency context, and repository-history evidence.
- **CP5 — release and evaluation:** merged-PR changelogs, evidence-backed breaking candidates,
  contributor lists, 60-case PR-risk comparison, smoke/upgrade gates, and OSS documentation.

```text
GitHub webhook → API → PostgreSQL delivery → Dramatiq worker → PR analysis
               → analysis + audit + outbox → GitHub Check queued/in_progress/completed
               ↘ Issue triage + repository cache → suggestion audit (no GitHub write)
GitHub compare/tags → Release Assistant → persisted human-review draft (no GitHub write)
Versioned datasets → Static/AI proxy/Hybrid/History runners → JSON/Markdown report
```

The default `shadow` mode is neutral and cannot merge, close, label, release, edit branches, or
change repository contents. Gemini is optional; static analysis remains available when Gemini is
disabled or unavailable.

This checkout is a `v1.0.0` release candidate: local unit/integration/E2E, fresh-wheel, Compose,
PostgreSQL migration/race, lint, type, smoke, and benchmark gates pass. The semantic tag, a public
demo installation, an independent human fresh-user run, and external beta repositories are
external acceptance gates and are not claimed as completed here.

## Requirements

For the recommended Docker installation:

- Git.
- Docker Desktop or another Docker Compose-compatible engine using Linux containers.
- A public HTTPS URL that forwards to local port `8000` for real GitHub webhooks.
- A GitHub account allowed to create and install a GitHub App.

For development and local CLI analysis, also install Python `3.12` and
[`uv`](https://docs.astral.sh/uv/getting-started/installation/).

## Installation from start to finish

### 1. Clone and create local configuration

```powershell
git clone https://github.com/sinh2206/MaintainerFlow.git
Set-Location MaintainerFlow
Copy-Item .env.example .env
```

On macOS/Linux, use `cp .env.example .env` instead. `.env` is ignored by Git.

Generate a webhook secret of at least 16 characters. PowerShell example:

```powershell
$bytes = [byte[]]::new(32)
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$webhookSecret = [Convert]::ToHexString($bytes).ToLower()
$webhookSecret
```

Put that value in `.env`:

```dotenv
MAINTAINERFLOW_GITHUB_WEBHOOK_SECRET=<generated-secret>
```

Never commit `.env`, a `.pem` file, a GitHub installation token, or a Gemini API key.

### 2. Start the local stack once

Keep the initial safe defaults below until the GitHub App has been created:

```dotenv
MAINTAINERFLOW_WORKFLOW_ENABLED=false
MAINTAINERFLOW_CHECK_PUBLISH_ENABLED=false
MAINTAINERFLOW_AI_ENABLED=false
```

Start the stack:

```powershell
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
```

Expected responses are `{"status":"ok"}` and `{"status":"ready"}`. The `db`, `redis`, `api`,
`worker`, and `recovery` services must be running; `migrate` should exit successfully.

Expose `http://localhost:8000` through a development HTTPS tunnel of your choice. Keep the tunnel
running and note its public origin, for example `https://maintainerflow.example.test`. GitHub's
documentation lists Smee, ngrok, localtunnel, and Hookdeck as development options; do not use an
unauthenticated development relay as a production endpoint.

### 3. Create the GitHub App

Open **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App** and configure:

| Setting | Value |
| --- | --- |
| GitHub App name | A unique name, for example `MaintainerFlow <account>` |
| Homepage URL | This repository URL or your deployment homepage |
| Webhook | Active |
| Webhook URL | `https://<public-origin>/webhooks/github` |
| Webhook secret | Exactly the value in `.env` |
| OAuth/user authorization | Not required |

Set only these repository permissions:

| Permission | Access |
| --- | --- |
| Contents | Read-only |
| Pull requests | Read-only |
| Checks | Read and write |
| Issues | Read-only |

Subscribe only to these events:

- **Pull request** — MaintainerFlow handles `opened` and `synchronize`.
- **Issues** — MaintainerFlow handles `opened` only.
- **Check run** — MaintainerFlow handles feedback-only `requested_action` events.

After creating the App:

1. Copy the numeric **App ID**; do not use the Client ID.
2. Under **Private keys**, generate and download a private key.
3. Store the `.pem` outside this repository.
4. Open **Install App** and install it only on a disposable test repository first.

Convert the PEM to a single line containing literal `\n` separators:

```powershell
(Get-Content C:\secure\maintainerflow.private-key.pem -Raw).Trim() -replace "`r?`n", "\n"
```

Copy the printed value into `.env` inside double quotes, then enable the workflow:

```dotenv
MAINTAINERFLOW_GITHUB_APP_ID=<numeric-app-id>
MAINTAINERFLOW_GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
MAINTAINERFLOW_WORKFLOW_ENABLED=true
MAINTAINERFLOW_CHECK_PUBLISH_ENABLED=true
MAINTAINERFLOW_CHECK_MODE=shadow
MAINTAINERFLOW_ISSUE_TRIAGE_ENABLED=true
MAINTAINERFLOW_REPOSITORY_INTELLIGENCE_ENABLED=true
MAINTAINERFLOW_INTELLIGENCE_RETENTION_DAYS=30
MAINTAINERFLOW_ISSUE_STORE_BODY=false
MAINTAINERFLOW_REPOSITORY_STORE_SOURCE_CODE=false
```

GitHub may generate a `BEGIN PRIVATE KEY` header instead; preserve the downloaded header and
footer exactly. At runtime, installation tokens are restricted again to the event repository. PR
publishing requests `contents:read`, `pull_requests:read`, and
`checks:write`; Issue triage requests `contents:read`, `pull_requests:read`, and `issues:read`
without Checks write permission.

Issue bodies and repository source are processed transiently but not persisted by default. Enabling
either storage option is an explicit privacy decision; cached intelligence and triage records expire
after `MAINTAINERFLOW_INTELLIGENCE_RETENTION_DAYS`.

### 4. Optionally enable Gemini

CP2 works without AI. To add validated semantic signals, create a Gemini API key and set:

```dotenv
MAINTAINERFLOW_AI_ENABLED=true
MAINTAINERFLOW_GEMINI_API_KEY=<your-key>
MAINTAINERFLOW_GEMINI_MODEL=gemini-3.5-flash-lite
MAINTAINERFLOW_AI_TIMEOUT_SECONDS=30
```

`gemini-3.5-flash-lite` is the default model. Provider timeout, rate limiting, malformed output, or
an outage produces a `PARTIAL` report while retaining static evidence; it does not fail the whole
PR workflow.

### Environment-variable reference

`.env.example` is the copy-ready local template. The table below lists every behavior-affecting
group; secret values are conditional and must never be committed.

| Variable | Default/example | Purpose |
| --- | --- | --- |
| `MAINTAINERFLOW_ENVIRONMENT` | `development` locally | Environment label included in configuration checks/log context. |
| `MAINTAINERFLOW_LOG_LEVEL` | `INFO` | Runtime log level. |
| `MAINTAINERFLOW_GITHUB_APP_ID` | required positive integer | GitHub App identity; not the OAuth Client ID. |
| `MAINTAINERFLOW_GITHUB_WEBHOOK_SECRET` | required, ≥16 characters | Verifies the raw webhook body with HMAC-SHA256. |
| `MAINTAINERFLOW_GITHUB_PRIVATE_KEY` | empty by default | Full PEM; required only when workflow processing is enabled. |
| `MAINTAINERFLOW_GITHUB_API_URL` | `https://api.github.com` | GitHub REST base URL. |
| `MAINTAINERFLOW_GITHUB_API_VERSION` | `2026-03-10` | Version header sent to GitHub. |
| `MAINTAINERFLOW_DATABASE_URL` | Compose PostgreSQL URL | Async SQLAlchemy URL using `postgresql+asyncpg` or test-only `sqlite+aiosqlite`. |
| `MAINTAINERFLOW_REDIS_URL` | `redis://redis:6379/0` | Dramatiq queue connection; `rediss://` is also accepted. |
| `MAINTAINERFLOW_WORKFLOW_ENABLED` | `false` | Enables worker fetch/analysis; requires the App private key. |
| `MAINTAINERFLOW_CHECK_PUBLISH_ENABLED` | `false` | Enables policy-gated Check writes; requires workflow enabled. |
| `MAINTAINERFLOW_CHECK_MODE` | `shadow` | `shadow` is always neutral; `suggestion` may publish non-blocking advice. |
| `MAINTAINERFLOW_ISSUE_TRIAGE_ENABLED` | `false` | Enables read-only Issue classification/suggestions. |
| `MAINTAINERFLOW_REPOSITORY_INTELLIGENCE_ENABLED` | `false` | Enables tree/AST/dependency/history context. |
| `MAINTAINERFLOW_AI_ENABLED` | `false` | Enables optional Gemini semantic signals. |
| `MAINTAINERFLOW_GEMINI_API_KEY` | empty | Required only when AI is enabled. |
| `MAINTAINERFLOW_GEMINI_MODEL` | `gemini-3.5-flash-lite` | Gemini model ID. |
| `MAINTAINERFLOW_AI_TIMEOUT_SECONDS` | `30` | Provider deadline; timeout falls back to a partial static report. |
| `MAINTAINERFLOW_ANALYSIS_STORE_DIFF` | `false` | Raw-diff persistence policy; keep disabled unless explicitly reviewed. |
| `MAINTAINERFLOW_ANALYSIS_MAX_DIFF_BYTES` | `1000000` | Maximum diff bytes accepted by analysis. |
| `MAINTAINERFLOW_REPOSITORY_STORE_SOURCE_CODE` | `false` | Opt-in source archive storage; requires repository intelligence. |
| `MAINTAINERFLOW_ISSUE_STORE_BODY` | `false` | Opt-in Issue-body storage; requires Issue triage. |
| `MAINTAINERFLOW_INTELLIGENCE_RETENTION_DAYS` | `30` | Expiry for repository/history/Issue intelligence records. |
| `MAINTAINERFLOW_GITHUB_HISTORY_RATE_LIMIT_FLOOR` | `100` | Stops history collection before exhausting GitHub quota. |
| `MAINTAINERFLOW_DELIVERY_LEASE_SECONDS` | `60` | Delivery-worker lease duration. |
| `MAINTAINERFLOW_RECOVERY_INTERVAL_SECONDS` | `30` | Recovery scan interval. |
| `MAINTAINERFLOW_RECOVERY_BATCH_SIZE` | `100` | Maximum deliveries recovered per scan. |
| `MAINTAINERFLOW_OUTBOX_LEASE_SECONDS` | `60` | GitHub publisher lease duration. |
| `MAINTAINERFLOW_OUTBOX_BATCH_SIZE` | `20` | Maximum publish commands per dispatch batch. |
| `MAINTAINERFLOW_OUTBOX_MAX_ATTEMPTS` | `5` | Retry ceiling before dead letter. |

### 5. Validate configuration and restart

Build the final image, validate the environment without printing secrets, and recreate services so
the new `.env` is loaded:

```powershell
docker compose build
docker compose run --rm --no-deps api maintainerflow config-check
docker compose up -d --force-recreate
docker compose ps
docker compose logs migrate worker --tail 100
```

Expected migration head: `0005_release_assistant`. Check it directly with:

```powershell
docker compose exec -T db psql -U maintainerflow -d maintainerflow -Atc `
  "SELECT version_num FROM alembic_version;"
```

### 6. Verify the real workflow

In the repository where the App is installed:

1. Open a pull request.
2. Confirm the App webhook delivery returns HTTP `202`.
3. Open the PR's **Checks** section.
4. Confirm one **MaintainerFlow** Check reaches `completed`.
5. In `shadow` mode, confirm its conclusion is neutral and it shows risk, suggested tests, and
   review focus.
6. Push another commit and confirm the `synchronize` event creates one Check for the new head SHA.
7. Open an issue and confirm one `issue.triage.suggested` audit record is created without a label,
   close, assign, comment, or Check Run side effect.

Inspect local persistence without exposing report contents:

```powershell
docker compose exec -T db psql -U maintainerflow -d maintainerflow -c `
  "SELECT id,action,status,attempts FROM deliveries ORDER BY id DESC LIMIT 5;"

docker compose exec -T db psql -U maintainerflow -d maintainerflow -c `
  "SELECT id,risk_level,status,publish_status,github_check_id FROM analyses ORDER BY id DESC LIMIT 5;"

docker compose exec -T db psql -U maintainerflow -d maintainerflow -c `
  "SELECT event_type,status,attempts,last_error FROM outbox_events ORDER BY id DESC LIMIT 10;"

docker compose exec -T db psql -U maintainerflow -d maintainerflow -c `
  "SELECT issue_number,classification,confidence,priority FROM issue_analyses ORDER BY id DESC LIMIT 10;"

docker compose exec -T db psql -U maintainerflow -d maintainerflow -c `
  "SELECT from_ref,to_ref,review_status,created_at FROM release_drafts ORDER BY id DESC LIMIT 10;"
```

Expected final states are `deliveries.status=completed`, `analyses.publish_status=completed`, and
`outbox_events.status=sent`. Re-delivery and worker retry reuse the existing Check instead of
creating unbounded duplicates.

## Operating modes

| Mode | Settings | Behavior |
| --- | --- | --- |
| Local static CLI | No stack required | Analyze a committed fixture; no GitHub write |
| Ingestion only | `MAINTAINERFLOW_WORKFLOW_ENABLED=false`, `MAINTAINERFLOW_CHECK_PUBLISH_ENABLED=false` | Validate CP1 webhook/queue behavior |
| Full static workflow | `MAINTAINERFLOW_WORKFLOW_ENABLED=true`, `MAINTAINERFLOW_CHECK_PUBLISH_ENABLED=true`, `MAINTAINERFLOW_AI_ENABLED=false` | CP1 → CP2 static → CP3 Check |
| Full Gemini workflow | Above plus `MAINTAINERFLOW_AI_ENABLED=true` and key | Static report plus validated Gemini signals |
| Issue triage | `WORKFLOW_ENABLED=true`, `ISSUE_TRIAGE_ENABLED=true` | Store shadow suggestions/audit; no GitHub write |
| Repository context | Above plus `REPOSITORY_INTELLIGENCE_ENABLED=true` | Cache tree/AST/graph/history by commit SHA and enrich PR risk |
| Release preview | Local `release --input` command | Render/export a deterministic draft; publishing is unavailable in v1.0 |
| Offline evaluation | Local `benchmark --suite all` command | Run locked datasets; no provider request or billable API call |

`MAINTAINERFLOW_CHECK_PUBLISH_ENABLED=true` is rejected unless
`MAINTAINERFLOW_WORKFLOW_ENABLED=true`; Issue triage and repository intelligence have the same
requirement. New installations should remain in `shadow` mode until live behavior has been reviewed
on a test repository.

## Local analysis without GitHub

```powershell
uv sync --frozen --extra dev
uv run maintainerflow analyze `
  --input benchmarks/datasets/pr-risk/fixtures/05-authentication.json
```

To exercise Gemini from the CLI:

```powershell
$env:GEMINI_API_KEY = "<your-key>"
uv run maintainerflow analyze `
  --input benchmarks/datasets/pr-risk/fixtures/04-core-no-tests.json `
  --ai
```

The command prints a versioned `AnalysisResult` JSON document.

## Release Assistant

Preview the included three-PR demo fixture, then export the exact same Markdown bytes:

```powershell
uv run maintainerflow release --input examples/demo/release-input.json
uv run maintainerflow release `
  --input examples/demo/release-input.json `
  --output release-notes.md
```

The input is provider-neutral merged-PR JSON with repository, `from_ref`, `to_ref`, compare URL,
labels, authors, changed files, and optional category rules. The GitHub service can collect
published release tags and merged PRs across a compare range with pagination/rate-budget limits;
the CLI fixture path makes preview and review reproducible without credentials.

Categories use explicit first-match precedence: `feature`, `fix`, `performance`, `docs`, then
`chore`. Breaking signals are candidates with provenance, never an automatic semantic-version
decision. Every candidate requires maintainer confirmation. `--publish` is deliberately rejected
in v1.0, so this command cannot create a GitHub Release or mutate a repository.

## Reproducible benchmarks

Run both CP2 PR-risk and CP4 Issue-triage suites and export reports:

```powershell
uv run maintainerflow benchmark --suite all --format json --output benchmark-report.json
uv run maintainerflow benchmark --suite all --format markdown --output benchmark-report.md
```

The PR-risk manifest contains 60 manually reviewed synthetic scenarios with fixed
train/validation/test splits. On the locked 30-case test split, the committed v2 report records
Macro-F1 `0.6678` for Static-only, `0.5693` for the offline AI proxy, `0.8380` for Hybrid, and
`0.9129` for Hybrid+History. These are reproducible project benchmarks—not claims about a hosted
Gemini model or real-world maintainer productivity. Latency is machine-dependent and cost is a
declared estimate; no API call or charge occurs.

Run the complete local smoke check after the stack is already running, or start it automatically:

```powershell
uv run python scripts/smoke_test.py --start
```

## Tests

Run the full credential-free quality gate:

```powershell
uv sync --frozen --extra dev
uv run ruff format --check .
uv run ruff check .
uv run mypy src/maintainerflow
uv run pytest -m "not e2e"
uv run pytest -m e2e
uv run maintainerflow benchmark --suite all --format json
uv run python scripts/smoke_test.py --skip-docker
```

The contract suite traverses CP1 ingestion → CP2 analysis → CP3 Check outbox → CP4 Issue triage →
CP5 release persistence in one repository. Hard cases cover replay/idempotency, two concurrent
PostgreSQL transactions, pagination, rate-budget truncation, every input permutation, hostile
Markdown/URL/control characters, provider retry duplicates, AI outage, prompt injection, wheel
installation in a clean virtualenv, report drift, and CP4→CP5 upgrade/downgrade data preservation.

With Docker running, test health and real PostgreSQL delivery handling:

```powershell
$env:RUN_E2E = "1"
$env:MAINTAINERFLOW_GITHUB_WEBHOOK_SECRET = $webhookSecret
uv run pytest -m e2e
```

The synthetic webhook tests should be run with `MAINTAINERFLOW_WORKFLOW_ENABLED=false`;
installation ID `77` is intentionally fake. The suite additionally performs a real PostgreSQL
schema round-trip and release-write race in isolated temporary databases. The credentialed
five-PR GitHub gate remains a manual test described in
[`docs/testing-checkpoint-3.md`](docs/testing-checkpoint-3.md).

## Troubleshooting

### Docker named pipe is missing or the API refuses connections

Start Docker Desktop, wait until its engine reports ready, and ensure it is using Linux containers:

```powershell
docker context ls
docker info
docker compose up --build -d
docker compose ps
```

Do not run health requests until `api` is healthy. If it is not, inspect
`docker compose logs migrate api worker --tail 200`.

### Webhook returns `401`

The GitHub App webhook secret and `MAINTAINERFLOW_GITHUB_WEBHOOK_SECRET` differ. Correct `.env`,
recreate the services, and redeliver the event from the GitHub App delivery page.

### Webhook returns `202` but no Check appears

Verify all of the following:

- `MAINTAINERFLOW_WORKFLOW_ENABLED=true` and `MAINTAINERFLOW_CHECK_PUBLISH_ENABLED=true`.
- The App ID is numeric and the complete private key is present.
- The App is installed on that repository.
- Contents and Pull requests are read-only; Checks is read and write.
- The event is `pull_request.opened` or `pull_request.synchronize`.
- `docker compose logs worker --tail 200` has no authentication or permission error.
- `outbox_events` is not `dead_letter`; `last_error` contains only a sanitized error class/code.

### Gemini is unavailable

Confirm the API key and model ID, then inspect the Check limitations. MaintainerFlow intentionally
completes a `PARTIAL` static report instead of failing the delivery.

### Port `8000` is already in use

Stop the conflicting process or change the host side of the API mapping in `compose.yaml`, then make
the tunnel and GitHub App webhook URL point to that new local port.

## Shutdown and data

```powershell
docker compose down
```

PostgreSQL and Redis data remain in named volumes. `docker compose down -v` permanently removes
those local volumes; use it only when you intentionally want a clean database.

## Security and privacy boundary

- Webhook HMAC-SHA256 is checked against the raw body before JSON parsing.
- Only supported PR, Issue-opened, and feedback events enter business logic.
- Redis messages contain only an internal delivery ID.
- Full diffs are analyzed transiently and are not persisted.
- Issue bodies and source archives are not persisted unless their separate opt-in settings are true;
  CP4 records have bounded retention and repository-scoped deletion paths.
- Secret-like report content is redacted before database persistence and GitHub rendering.
- Annotations require a safe changed-file path, line, provenance, and confidence.
- Outbox leases, unique idempotency keys, bounded retries, and dead letters prevent retry storms.
- Check actions are feedback only: `useful/not_useful` in shadow mode and
  `accept/reject/useful` in suggestion mode.
- Release generation persists a review-pending draft and audit event but creates no outbox event;
  GitHub Release publishing is not implemented in v1.0.

The included Compose configuration is intended for local development and evaluation. Before a
public production deployment, use managed secrets, replace development database credentials,
terminate HTTPS at a trusted proxy, back up PostgreSQL, monitor dead letters, and define retention.

## Project documentation

- [Checkpoint acceptance criteria](checkpoint.md)
- [Contributing guide](CONTRIBUTING.md)
- [Architecture](docs/architecture.md)
- [OSS evidence status](docs/oss-evidence-status.md)
- [Three-minute demo runbook](docs/demo-video.md)
- [Five-case manual evaluation evidence](docs/evaluation-evidence.md)
- [GitHub App setup](docs/github-app-setup.md)
- [Self-hosting and upgrades](docs/self-hosting.md)
- [Security model](docs/security.md)
- [Privacy and retention](docs/privacy.md)
- [Roadmap](docs/roadmap.md)
- [Changelog](CHANGELOG.md)
- [Local demo](examples/demo/README.md)
- [Good first contribution tasks](.github/GOOD_FIRST_ISSUES.md)
- [Testing CP1](docs/testing-checkpoint-1.md)
- [Testing CP2](docs/testing-checkpoint-2.md)
- [Testing CP3](docs/testing-checkpoint-3.md)
- [Testing CP4](docs/testing-checkpoint-4.md)
- [Testing CP5](docs/testing-checkpoint-5.md)
- [GitHub App permissions](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app)
- [GitHub App webhooks](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/using-webhooks-with-github-apps)
- [Gemini latest models](https://ai.google.dev/gemini-api/docs/latest-model)

## License

MaintainerFlow is licensed under the terms in [LICENSE](LICENSE).
