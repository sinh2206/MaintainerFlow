# Contributing to MaintainerFlow

Thank you for helping build safe, evidence-backed maintainer tooling. Small, focused pull requests
with tests are the easiest to review. By participating, follow our [Code of Conduct](CODE_OF_CONDUCT.md).

Do not use public issues for vulnerabilities; follow [SECURITY.md](SECURITY.md).

## Development setup

Install Git, Python 3.12 and `uv`, then:

```powershell
git clone https://github.com/sinh2206/MaintainerFlow.git
Set-Location MaintainerFlow
uv sync --frozen --extra dev
Copy-Item .env.example .env
uv run maintainerflow config-check
```

The checked-in lock file is authoritative. Explain and review every `uv.lock` change. Local static
analysis and release preview do not need Docker, GitHub credentials or a Gemini key. Integration
with PostgreSQL/Redis uses:

```powershell
docker compose up -d --build
docker compose run --rm migrate alembic upgrade head
Invoke-RestMethod http://localhost:8000/ready
```

Use only fake keys and project-owned fixtures. Never commit `.env`, PEM files, real webhook payloads,
private source/diffs, access tokens or production database dumps.

## Before opening a pull request

Run the full local gate:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src/maintainerflow
uv run pytest -m "not e2e"
uv run pytest -m e2e
docker compose run --rm migrate alembic upgrade head
docker compose run --rm --no-deps migrate alembic check
uv run maintainerflow benchmark --suite all --format json
uv run python scripts/smoke_test.py --skip-docker
```

Docker-dependent E2E cases require a healthy Compose stack plus `RUN_E2E=1`. Provider/GitHub live
tests are never required for fork pull requests and must not expose secrets. If a command cannot run
on your platform, describe exactly which one and why in the PR.

## Architecture rules

- Keep FastAPI routes and Dramatiq actors thin; orchestration belongs in `services`.
- Keep domain behavior deterministic and side-effect free in `analysis`, `issue`, `release`, and
  `core`. Domain code must not depend on framework, database or environment settings.
- Put GitHub/provider I/O behind typed adapters. Bound pagination, response size, retries and rate
  budget; classify retryable and permanent failures.
- Persist business data and its outbox/audit event in one transaction. Make delivery and GitHub
  writes idempotent.
- Treat PR/issue/repository text as hostile. Do not execute repository code. Validate schemas,
  sanitize rendered output, redact secrets and add adversarial tests.
- Default new writes, AI, source/body storage and elevated permissions off. Document privacy,
  retention and deletion effects for every new data field.
- Add an Alembic migration for model changes. Test upgrade from the previous release and ensure
  `alembic check` reports no drift; do not rewrite a released migration.
- Preserve versioned input/output schemas or document a migration and compatibility window.

Read [docs/architecture.md](docs/architecture.md), [docs/security.md](docs/security.md) and
[docs/privacy.md](docs/privacy.md) before changing a trust boundary.

## Tests and evaluation

Every behavior change needs its smallest useful unit test and a cross-checkpoint integration/E2E
test when it touches webhook, persistence, worker, policy, outbox, repository context or release
flow. Prefer assertions on invariants over implementation details. Include negative, malformed,
duplicate, concurrent, retry, truncation and unauthorized-input cases where relevant.

Benchmark/dataset changes must include:

- stable case IDs, manifest/schema version, source/provenance and license;
- a fixed split decided before measuring results, including hard negatives where applicable;
- ground-truth annotation guidance and reviewer identity/process without personal data;
- no private code, issue text, credentials or fabricated claims of external users;
- the command, commit, Python/platform, strategy/model version, sample counts and limitations in the
  report;
- separate deterministic metrics from variable AI latency/cost/model output.

Do not tune a rule on the test split and then report that split as an independent result. Generated
or synthetic data must be labeled as such.

## Pull request process

1. Search existing issues/PRs; discuss large designs or permission/data changes first.
2. Branch from `main`; keep unrelated formatting/refactors out of the change.
3. Add code, tests, migrations and user/operator docs together.
4. Complete the PR template, including security/privacy, compatibility and benchmark impact.
5. Ensure CI passes and address review. Maintainers may request smaller commits or an ADR.

Contributions are licensed under the repository's [MIT License](LICENSE). Do not submit material you
do not have permission to contribute.

## Version and release process

MaintainerFlow uses semantic `vMAJOR.MINOR.PATCH` tags. Breaking configuration/schema/API changes
require an explicit migration note and normally a major version. Maintainers:

1. Update package version and `CHANGELOG.md`.
2. Generate deterministic candidate notes with `maintainerflow release --input ... --output ...`.
3. Review every breaking candidate and compare/PR link; the CLI never publishes a release.
4. Run the full gate and create an annotated semantic tag on the reviewed commit.
5. Let `release.yml` rebuild and re-run the gate. Its publish job alone receives `contents: write`
   and runs only after successful gates/artifact checksum generation.

Never move a published tag or edit an old release artifact. Publish a new patch release instead.
