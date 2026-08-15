# Privacy and data handling

MaintainerFlow is currently self-hosted. The operator is the data controller for repository and user
data; the project maintainers do not receive deployment data unless the operator deliberately sends
it in a report.

## Data flow

| Source | Data read | Stored by default | External destination |
| --- | --- | --- | --- |
| GitHub webhook | Delivery ID, event/action, installation, repository, PR/issue identifiers and SHAs | Minimal envelope and processing state | PostgreSQL/Redis in the operator environment |
| Pull request APIs | Title, body, diff, file metadata and SHAs | Hashes, derived report/evidence and audit; raw diff is off by default | Optional Gemini request when AI is enabled |
| Repository APIs | Tree, selected Python source, commits, reviews and URLs | Derived graph/history/cache; source archive is off by default | None beyond the self-hosted services |
| Issue APIs | Title, body, labels and duplicate candidates | Classification/evidence/suggestions; full body is off by default | None in the current issue triage path |
| Check feedback | GitHub actor ID/login and accept/reject/useful action | Audit event | PostgreSQL |
| Release/benchmark CLI | Explicit local fixture/manifests | User-selected output and optional release draft/audit | None unless a maintainer later uploads reviewed artifacts |

PostgreSQL is authoritative. Redis carries queue messages and persistence data configured by the
operator; it must be protected as potentially sensitive metadata.

## Optional Gemini processing

With `MAINTAINERFLOW_AI_ENABLED=true`, MaintainerFlow sends the PR title/body, changed file names, a
bounded diff excerpt, and static risk/evidence to the configured Gemini endpoint. Do not enable this
mode for data that policy forbids sending to that provider. Provider retention, location and model
training terms are governed by the operator's Google agreement, not by this repository.

The application sends the Gemini API key only as the authentication header. It records normalized
provider/model/latency/token metadata, not the key. Static analysis remains available with AI off.

## Storage controls

Privacy-preserving defaults are:

```dotenv
MAINTAINERFLOW_ANALYSIS_STORE_DIFF=false
MAINTAINERFLOW_REPOSITORY_STORE_SOURCE_CODE=false
MAINTAINERFLOW_ISSUE_STORE_BODY=false
MAINTAINERFLOW_INTELLIGENCE_RETENTION_DAYS=30
```

The CP4 retention value applies to repository indexes, historical evidence and issue analyses.
Expired rows require the worker maintenance/recovery path to run. PR analysis, delivery, audit and
outbox tables do not yet have a configurable automatic retention window; operators must define a
documented database retention policy for them.

Even with raw body/source storage disabled, derived evidence can contain paths, contributor logins,
URLs or short source/issue excerpts. Database backups inherit the same sensitivity and may outlive
live-row deletion.

## Access, export and deletion

There is no end-user privacy API or administrative web UI in the current release. A self-hosting
operator should authenticate a request against the GitHub repository owner, then:

1. Identify the internal repository ID from its GitHub repository ID.
2. Export required rows from `repositories`, `deliveries`, `analysis_snapshots`, `analyses`,
   `evidence`, `audit_events`, `repository_indexes`, `historical_evidence`, `issue_analyses`, and
   release tables using a restricted PostgreSQL account.
3. Use the intelligence repository deletion methods for CP4 cache/issue data. For a full purge,
   execute a reviewed transaction in dependency order and confirm row counts before commit.
4. Remove or expire corresponding backups according to the operator's backup policy.
5. Record the administrative action outside the deleted dataset.

Do not improvise a broad `DELETE` against production. Take a backup, dry-run selectors, respect
foreign keys and test restore/deletion on a copy first. Uninstalling the GitHub App stops future
access but does not itself delete self-hosted database/backups.

## Logs and support

Application code should log identifiers and failure classes, not secrets or complete payloads.
Reverse proxies, container runtimes and managed databases may add their own logs; configure their
retention separately. Before sharing a diagnostic bundle, remove `.env`, PEM material, tokens,
database URLs, webhook bodies, private source, diffs, issue text and contributor personal data.

No public hosted MaintainerFlow service or telemetry endpoint is claimed by this repository. If a
hosted edition is introduced, it requires a separate privacy notice, subprocessors list, deletion
SLA and data-location statement.
