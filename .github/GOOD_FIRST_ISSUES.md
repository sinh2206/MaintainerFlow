# Good first contribution tasks

This is a ready-to-file backlog, not a claim that corresponding public GitHub issues already exist.
Maintainers should create one issue per task, link this specification and mentor scope explicitly.
All tasks preserve safe defaults and require the standard quality gate.

## 1. Add TOML/YAML paths to dependency-config suggestions

Extend deterministic test/review suggestions for changes to `pyproject.toml`, `compose.yaml` and
GitHub workflow files without parsing untrusted templates. Acceptance: table-driven unit tests cover
add/rename/delete and mixed-case paths; no risk-score change; docs name the new evidence.

## 2. Detect generated Python files before AST analysis

Add conservative markers (for example a leading “generated; do not edit” comment) and skip AST
symbols/imports for marked files. Acceptance: no execution/import, false-positive fixture included,
limitation names each skipped path, repository-cache identity/version changes.

## 3. Add Vietnamese issue-classifier fixtures

Contribute licensed synthetic examples for all five categories with difficult negatives. Acceptance:
manifest source/license/fixed split updated, at least 20 cases, no production/private issue text,
benchmark report shows per-class counts and does not reduce the locked English test result.

## 4. Document a Caddy TLS reverse-proxy example

Add an opt-in self-hosting snippet that exposes only webhook/health routes and preserves the raw
signed body. Acceptance: configuration validates, no hard-coded domain/credential, forwarded scheme
and request-size/rate-limit behavior explained, existing Compose defaults unchanged.

## 5. Add machine-readable benchmark report validation

Create a JSON Schema for committed reports and validate required manifest version, commit,
environment, strategy, sample count, metrics and limitations. Acceptance: valid report passes;
missing/unknown/wrong-type fields fail; schema never permits secret/raw-source payload fields.

## 6. Add Markdown link/path fuzz cases to release notes

Expand release renderer tests with Unicode, brackets, angle brackets, newlines and deceptive URL
inputs. Acceptance: deterministic snapshot, only validated HTTP(S) URLs become links, no raw HTML,
no duplicate PR/contributor and no behavior relaxation.

## 7. Add an audit-event operator query cookbook

Document read-only PostgreSQL queries for delivery, analysis, issue triage, feedback and dead-letter
investigation. Acceptance: queries use explicit filters/limits, contain no deletion, work on the
current schema and warn that derived evidence may be private.

When filing one of these, add `good first issue`, one domain label, expected files, acceptance tests
and a maintainer contact. Do not bundle multiple tasks into one PR.
