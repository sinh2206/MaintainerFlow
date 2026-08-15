# Security model

MaintainerFlow processes attacker-controlled webhooks, pull requests, diffs, repository files and
issue text. Treat every suggestion as untrusted advice and keep human review in the release/merge
path.

## Assets and trust boundaries

Protected assets are the GitHub App private key, webhook secret, installation tokens, optional
Gemini key, repository content, PostgreSQL records and the ability to create Check Runs. The main
boundaries are GitHub -> public webhook, worker -> GitHub/Gemini, application -> PostgreSQL/Redis,
and tag workflow -> GitHub Release.

| Threat | Current control | Residual risk / operator action |
| --- | --- | --- |
| Forged or replayed webhook | Raw-body HMAC-SHA256 verification; unique delivery ID | GitHub can legitimately redeliver. Rotate a disclosed webhook secret. |
| Duplicate/concurrent work | Database uniqueness, leases, content snapshots and outbox keys | External requests are at-least-once; monitor dead letters. |
| Prompt injection | Repository text is data; typed AI schema; static fallback; no AI tool execution | A model can still produce misleading analysis. Keep AI optional and review output. |
| Malicious paths/Markdown | Relative-path validation, escaping, length limits and secret-pattern redaction before Checks | Redaction patterns cannot recognize every credential format. Rotate any exposed secret. |
| Repository code execution | Diff/parser and Python `ast` analysis only; repository code is not imported or run | E2E/benchmark fixtures are project-owned; do not execute contributed fixtures outside CI isolation. |
| Credential exfiltration | Pydantic secret values, short-lived installation tokens, minimal permissions, no secret logging by design | Protect host/process memory and CI logs; use a secret manager in production. |
| Dependency/supply-chain compromise | Frozen `uv.lock`; dependency, secret and CodeQL scanning; CP5 release/security actions pinned to commit SHAs | Review lock changes and scanner alerts; pin container digests for hardened deployments. |
| Unauthorized GitHub write | Checks-only permission; policy defaults to shadow; transactional outbox | Enabling `CHECK_PUBLISH` grants a real write path. Test on a dedicated repository first. |
| Unreviewed release | Semantic tag/version check and full gate before privileged publish job | A maintainer can still tag unsafe reviewed code; protect tags/environments. |

## Permission and mode policy

Use the matrix in [GitHub App setup](github-app-setup.md). MaintainerFlow does not need Contents
write, Pull requests write, Issues write, Administration, Actions or organization permissions.
`Checks: write` is required only for Check Run publishing. Issue triage is suggestion-only even when
`Issues: read` is granted.

Production should start with:

```dotenv
MAINTAINERFLOW_AI_ENABLED=false
MAINTAINERFLOW_CHECK_MODE=shadow
MAINTAINERFLOW_CHECK_PUBLISH_ENABLED=false
MAINTAINERFLOW_ANALYSIS_STORE_DIFF=false
MAINTAINERFLOW_REPOSITORY_STORE_SOURCE_CODE=false
MAINTAINERFLOW_ISSUE_STORE_BODY=false
```

Enable one capability at a time. Changing GitHub App permissions requires installation owners to
approve the new grant.

## Prompt and output handling

AI is used only for optional PR semantic signals. The provider request contains PR title/body,
changed file names, a bounded diff excerpt, and static evidence/risk. It does not receive the GitHub
App private key, installation token, webhook secret, database URL or Redis URL from application
code. Issue triage and release classification are deterministic in the current implementation.

The model has no tools and cannot publish. Its response is schema validated; failures degrade to
static analysis. Before output reaches GitHub Checks, text is control-character filtered, bounded,
Markdown escaped where appropriate, and known token prefixes are redacted. These controls reduce
risk but do not make untrusted content truthful.

## Secret lifecycle

- Generate independent random values for webhook signing and database credentials.
- Store the GitHub App PEM and Gemini key in a deployment secret manager; `.env` is for local use.
- Never paste real payloads or keys into issues, fixtures, benchmark reports or support logs.
- Rotate the private key/webhook secret after suspected exposure. Revoke the Gemini key at its
  provider. Installation tokens are short-lived but should still be treated as secrets.
- Restrict PostgreSQL/Redis to the private network and use encrypted connections when external.
- Preserve release checksums and verify downloaded assets before installation.

## Operational response

Monitor repeated signature failures, abnormal webhook volume, delivery leases, failed-safe
deliveries, outbox retries/dead letters, GitHub rate limits, provider errors and unexpected changes
to App permissions. The current project exposes health/readiness and structured application logs;
it does not include a hosted alerting stack.

For a vulnerability, follow [SECURITY.md](../SECURITY.md). Do not open a public issue with exploit
details, credentials or private repository content.
