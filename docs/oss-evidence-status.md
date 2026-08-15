# OSS evidence status

Snapshot date: **2026-08-13**. “Ready” means the artifact exists in this repository and has been
locally verified; it does not imply an external reviewer has accepted it.

| Requested evidence | Status | Repository evidence / remaining gate |
| --- | --- | --- |
| Three-minute MVP demo video | **Pending external recording** | Demo repository scaffold and exact [3:00 recording runbook](demo-video.md) are ready. A human must create/install the public GitHub App demo and record the real Check flow. |
| Architecture diagram | **Ready** | [Mermaid component and PR sequence diagrams](architecture.md#component-diagram) plus detailed boundaries/sequences. |
| At least 10 merged PRs | **Not met: 0/10** | The public [merged-PR view](https://github.com/sinh2206/MaintainerFlow/pulls?q=is%3Apr+is%3Amerged) showed zero on the snapshot date. Only real reviewed/merged changes count. |
| README setup/env/sample queries | **Ready** | End-to-end installation, consolidated environment reference, operating modes, read-only PostgreSQL queries, release/benchmark commands and troubleshooting are in [README](../README.md). |
| At least five manual eval cases with actual output | **Ready: 5/5** | [Manual evidence report](evaluation-evidence.md), full [machine-readable recorded outputs](../evaluation/manual-v1.json), input hashes and replay test. |

## Build 10 meaningful merged PRs

Do not create empty/rename-only PRs to inflate the number. The current CP5 work naturally separates
into reviewable boundaries:

1. Release domain schemas/classification/breaking renderer plus unit tests.
2. Release persistence model and migration.
3. GitHub release/compare pagination and rate-budget tests.
4. Release orchestration service and CP1–CP5 compatibility contract.
5. Release CLI plus deterministic export E2E.
6. Versioned PR-risk strategies/dataset/report and reproducibility tests.
7. Fresh-install, migration round-trip, smoke and concurrency gates.
8. Architecture/security/privacy/self-hosting/community documentation.
9. CI, release and security workflows with pinned actions.
10. Demo scaffold, video runbook, README configuration and manual-eval evidence.

Merge them sequentially only when each diff is independently coherent and CI passes. If splitting
the current dirty worktree, make a recoverable backup first. For each PR cycle, stage only one
boundary, stash the remainder with `--keep-index --include-untracked`, commit/push the staged subset,
open and merge the PR, update `main`, then restore the remainder. Inspect `git status` and the stash
before every pop; never discard the only copy of uncommitted work.

GitHub CLI is currently installed locally but unauthenticated. Authenticate without pasting a token
into terminal history:

```powershell
gh auth login
gh auth status
gh pr list --repo sinh2206/MaintainerFlow --state merged --limit 100
```

For every PR, require a descriptive title/body, linked issue or acceptance criterion, focused tests,
green CI and a review. Capture the final merged-PR page URL in the application evidence instead of
screenshots alone.
