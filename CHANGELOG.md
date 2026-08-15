# Changelog

All notable changes are documented here. The project follows [Semantic Versioning](https://semver.org/)
and uses `vMAJOR.MINOR.PATCH` Git tags. Dates use `YYYY-MM-DD`.

## [Unreleased]

No unreleased changes yet.

## [1.0.0] - 2026-08-13

### Added

- Release Assistant for deterministic PR categorization, breaking-change candidates, contributor
  lists and human-reviewed Markdown preview/export.
- Versioned PR/issue benchmark runners with strategy comparison and environment metadata.
- One-command smoke testing, OSS architecture/security/privacy/self-hosting documentation,
  contribution templates and gated semantic-tag release/security workflows.

### Security

- Release publication is separated into a least-privilege job and requires the full quality,
  migration, smoke and benchmark gate plus artifact checksum/metadata.

## [0.4.0] - 2026-08-12

### Added

- Deterministic issue category, priority, label and lexical duplicate suggestions with evidence.
- Repository tree/Python AST intelligence, dependency graph, criticality, related tests and
  provenance-bearing history.
- Expiring repository/issue caches with privacy-preserving raw source/body defaults.

### Changed

- PR snapshot identity incorporates repository-context identity and risk/test suggestions can use
  repository criticality/history.

## [0.3.0] - 2026-08-12

### Added

- Non-blocking GitHub Check Run rendering, policy, feedback audit and transactional outbox.
- Outbox retry/dead-letter handling and idempotent Check Run reconciliation.

## [0.2.0] - 2026-08-11

### Added

- Deterministic diff parsing, static PR risk/evidence/test suggestions and content snapshots.
- Optional schema-validated Gemini analysis with static fallback.

## [0.1.0] - 2026-08-11

### Added

- FastAPI webhook ingestion with HMAC verification and minimal event envelopes.
- PostgreSQL delivery state/leases, Redis/Dramatiq worker and recovery loop.
- Docker Compose development stack, migrations, health/readiness and baseline CI.

[Unreleased]: https://github.com/sinh2206/MaintainerFlow/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/sinh2206/MaintainerFlow/compare/v0.4.0...v1.0.0
[0.4.0]: https://github.com/sinh2206/MaintainerFlow/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/sinh2206/MaintainerFlow/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/sinh2206/MaintainerFlow/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/sinh2206/MaintainerFlow/releases/tag/v0.1.0
