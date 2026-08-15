## Summary

<!-- What changed, why, and what is intentionally out of scope? -->

## Verification

<!-- List exact commands and important results. Do not paste secrets/private payloads. -->

- [ ] `uv run ruff format --check .`
- [ ] `uv run ruff check .`
- [ ] `uv run mypy backend/src/maintainerflow`
- [ ] Relevant unit/integration/E2E tests
- [ ] Migration/benchmark/smoke checks when affected

## Safety and compatibility

- [ ] No new permission or external write; or the least-privilege/policy change is explained.
- [ ] No new stored/sent data; or privacy, retention, export and deletion are documented.
- [ ] Untrusted input is bounded/validated/sanitized and adversarial cases are tested.
- [ ] CP1 webhook/idempotency, CP2 analysis, CP3 policy/outbox, CP4 context/triage and CP5 release/evaluation remain compatible.
- [ ] User/operator docs and `CHANGELOG.md` are updated when behavior changes.

## Evidence

<!-- Link the issue; include before/after metric for rule/model changes and a migration plan if needed. -->
