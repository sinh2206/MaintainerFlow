# Manual evaluation evidence

This is a frozen five-case manual review of real MaintainerFlow CLI output, captured on
2026-08-13 from project version `1.0.0` with Python `3.12.10`. Expectations were assigned from the
fixture intent, then compared with the static analyzer output. No Gemini/provider request was made.

The complete machine-readable expectations, input SHA-256 values and recorded output objects are in
[`evaluation/manual-v1.json`](../evaluation/manual-v1.json). A regression test re-runs every CLI
command and requires byte-equivalent parsed JSON fields, so the evidence cannot silently drift.

## Result summary

| Case | Manual expectation | Actual output | Key actual evidence | Result |
| --- | --- | --- | --- | --- |
| Docs-only README | `complete`, LOW, no missing-test warning | `complete`, LOW `1.0`, confidence `0.95` | none | PASS |
| Source plus regression test | `complete`, LOW, core change, no missing-test warning | `complete`, LOW `2.2`, confidence `0.95` | `core_change` | PASS |
| Source without tests | `complete`, MEDIUM, missing-test warning | `complete`, MEDIUM `4.5`, confidence `0.95` | `core_change`, `missing_tests`; focused unit-test suggestion | PASS |
| Authentication without tests | `complete`, HIGH, security and missing-test warnings | `complete`, HIGH `8.5`, confidence `0.95` | `authentication_change`, `missing_tests`; auth negative-path suggestion | PASS |
| Malformed diff | `partial`, fail safely with explicit limitation | `partial`, LOW `0.5`, confidence `0.75` | `Malformed diff: no file header found.` | PASS |

All five manually assigned expectations matched the recorded output. This is functional evidence,
not a statistical accuracy claim: the fixtures are project-owned synthetic cases and the reviewer
is not independent from the project.

## Reproduce one case manually

```powershell
uv sync --frozen --extra dev
uv run maintainerflow analyze `
  --input benchmarks/datasets/pr-risk/fixtures/05-authentication.json
```

Expected fields:

```json
{
  "status": "complete",
  "risk": {"score": 8.5, "level": "high", "confidence": 0.95},
  "evidence": [
    {"kind": "authentication_change", "path": "src/auth.py"},
    {"kind": "missing_tests", "path": "src/auth.py"}
  ],
  "provider_metadata": null
}
```

The CLI prints more fields than the excerpt; the complete recorded object is kept in the evidence
JSON. Re-run the full frozen set with:

```powershell
uv run pytest tests/e2e/test_manual_eval_evidence.py -m e2e
```

If a deliberate rules/schema change modifies output, review every case again, increment the manual
evidence schema/version, keep old evidence for release provenance, and document the change in the
changelog. Do not overwrite results merely to make a failing expectation pass.
