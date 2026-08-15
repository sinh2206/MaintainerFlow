# MaintainerFlow demo scaffold

This directory is a reproducible scaffold, not a claim that a public demo repository or hosted
MaintainerFlow URL already exists.

For a submission-quality recording, follow the exact
[three-minute MVP video runbook](../../docs/demo-video.md).

## Offline demo (no GitHub, Docker or API key)

From the MaintainerFlow repository root:

```powershell
uv sync --frozen --extra dev
uv run maintainerflow analyze --input examples/demo/pr-fixture.json
uv run maintainerflow release --input examples/demo/release-input.json --output demo-notes.md
Get-Content demo-notes.md
```

Expected properties:

- PR analysis returns versioned JSON with deterministic risk, evidence and suggested tests.
- Release notes group all three PRs, retain their links, list human contributors once and flag PR
  #3 as a breaking-change candidate requiring maintainer confirmation.
- Running either command again produces the same deterministic output.
- Neither command calls GitHub or publishes a release. Do not add `--ai` unless provider data
  processing is intentionally being tested.

`OWNER` URLs in `release-input.json` are placeholders. Replace them only after creating a real demo
repository.

## Create an external public demo repository

This is a maintainer/operator action and is not performed automatically by this scaffold:

1. Create an empty public repository, for example `OWNER/maintainerflow-demo`, with an OSS license.
2. Copy the contents of `repository/` into it and make the first commit.
3. Deploy MaintainerFlow from a reviewed semantic release using [self-hosting](../../docs/self-hosting.md).
4. Create/install a least-privilege GitHub App using [GitHub App setup](../../docs/github-app-setup.md),
   selecting only the demo repository.
5. Keep `CHECK_MODE=shadow` first. Open a PR that changes `src/demo_calculator.py`, verify audit/no
   write, then enable suggestion publishing and synchronize the PR.
6. Open the sample issue from `repository/DEMO_ISSUE.md` with issue triage enabled; verify a stored
   suggestion/audit but no automatic label, assignment, comment or close.
7. Publish the demo URL in the main README only after the complete walkthrough works from a fresh
   account and contains no credentials/private content.

The demo repository should pin the MaintainerFlow version it exercised and document the exact date,
commit, enabled flags and known limitations. Delete test App credentials when the demo is retired.
