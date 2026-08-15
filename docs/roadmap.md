# Roadmap after v1.0

This roadmap is directional, not a promise of dates or hosted availability. Security, privacy,
determinism and operator control take priority over feature count.

## Near term

- Validate fresh-user setup with independent maintainers and publish only anonymized findings.
- Expand PR/issue datasets with licensed, provenance-tracked examples from multiple project types.
- Add JavaScript/TypeScript language analyzers through the existing analyzer protocol.
- Expose administrative retention/export operations with authorization and auditable dry runs.
- Add OpenTelemetry-compatible metrics/traces for leases, outbox, provider use and latency.

## Later candidates

- Pluggable duplicate retrieval (BM25/embeddings) with hard-negative and privacy evaluation.
- Configurable release taxonomy and additional deterministic release-note renderers.
- Optional reviewed GitHub Release publisher as a separate least-privilege component.
- Policy packs for monorepos and repository-owned configuration with signed/trusted boundaries.
- PostgreSQL/Redis high-availability deployment examples and Kubernetes manifests after load tests.

## Evidence required before promotion

A candidate moves into a release only with an owner, threat/privacy review, migration/rollback plan,
tests, versioned benchmark evidence and documentation. Hosted service, auto-label/close/merge,
blocking Checks and code-writing automation are explicitly out of scope until separate consent,
permissions and abuse controls exist.
