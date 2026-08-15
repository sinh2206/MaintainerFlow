# Three-minute MVP demo runbook

The repository cannot truthfully contain a finished live-demo video until a human records a real
GitHub App installation. This runbook fixes the scope, timing, narration and evidence so the final
video can be recorded in one take without exposing credentials.

## What the video must prove

Show one contributor-facing flow end to end:

```text
Open PR -> signed webhook -> queued analysis -> non-blocking GitHub Check
        -> risk + evidence + suggested tests -> maintainer decision
```

Release preview and benchmark are supporting proof, not substitutes for the live GitHub Check.

## Prepare before recording

1. Create the public demo repository from [`examples/demo/repository`](../examples/demo/repository).
2. Install the GitHub App using [the least-privilege guide](github-app-setup.md).
3. Set `WORKFLOW_ENABLED=true`, `CHECK_PUBLISH_ENABLED=true`, `CHECK_MODE=shadow`; keep AI off for
   a deterministic take unless provider behavior is the subject of the demo.
4. Start Compose and confirm `/health`, `/ready`, all five services and migration
   `0005_release_assistant` before opening the recorder.
5. Prepare a branch that changes `src/demo_calculator.py` without changing its test. Leave the
   GitHub “Create pull request” page ready, but do not submit it yet.
6. Increase terminal/browser font size, hide bookmarks/notifications, close `.env`, logs and GitHub
   App settings, and use a fresh delivery ID/PR head SHA.

Never show the webhook secret, PEM, Gemini key, installation token, database URL/password, raw
private payload, browser password manager or terminal history containing credentials.

## Exact 3:00 shot list

| Time | Screen | Action and narration |
| --- | --- | --- |
| `0:00–0:12` | Repository README/title | “MaintainerFlow turns a pull request into evidence-backed, non-blocking review guidance while keeping the maintainer in control.” |
| `0:12–0:27` | Terminal | Run `docker compose ps`, then show `/health` and `/ready`. Say: “The API, database, queue, worker and recovery process run in one self-hosted stack.” |
| `0:27–0:47` | GitHub PR diff | Show the prepared source change and absence of a matching test; click **Create pull request**. Say: “The contributor opens an ordinary PR; there is no special command or repository write by the model.” |
| `0:47–1:05` | PR Checks tab | Refresh until the MaintainerFlow Check changes from queued/in-progress to completed. Say: “A signed webhook is stored idempotently, analyzed by the worker and published through a transactional outbox.” |
| `1:05–1:35` | Completed Check details | Point to risk, evidence, changed path, suggested tests and review focus. Say: “This source-only change is flagged with provenance and a focused test suggestion. Shadow mode stays neutral and never blocks or merges.” |
| `1:35–1:52` | Terminal/read-only SQL | Show the latest delivery/analysis/outbox rows with the bounded README queries. Say: “PostgreSQL is the system of record; retries reuse identities instead of creating duplicate Checks.” Do not display report bodies or secrets. |
| `1:52–2:15` | Terminal + release notes | Run `maintainerflow release --input examples/demo/release-input.json`; show categories, contributor deduplication and the breaking candidate. Say: “Release Assistant produces a deterministic draft, but publishing is deliberately unavailable until a human reviews it.” |
| `2:15–2:38` | Benchmark Markdown/report | Show `benchmarks/reports/pr-risk-v2.0.0.md`. Say: “The versioned 60-case synthetic benchmark compares Static, offline AI proxy, Hybrid and History strategies; results are reproducible and clearly limited.” |
| `2:38–2:52` | Architecture Mermaid diagram | Show [the component diagram](architecture.md#component-diagram). Summarize: “Untrusted input crosses typed boundaries; optional AI has no tools; GitHub writes sit behind policy and outbox.” |
| `2:52–3:00` | README status/limitations | “The code, tests and local demo are reproducible. Public beta, independent fresh-user evidence and real historical evaluation remain explicit next gates.” |

If the live Check takes longer than 18 seconds, pause the recording and start a new take; do not cut
from one PR/head SHA to a different result without stating it. A single continuous take is stronger
evidence than a heavily edited video.

## Commands kept ready in a separate terminal

```powershell
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready

uv run maintainerflow release `
  --input examples/demo/release-input.json `
  --output demo-notes.md
Get-Content demo-notes.md
```

Use the read-only SQL queries already in [README](../README.md#6-verify-the-real-workflow). Do not
run destructive database commands during a demo.

## Evidence to publish with the video

After recording, add the public video URL to README and record:

- recording date and duration (`<= 3:00`);
- MaintainerFlow commit/tag and demo-repository URL/PR number;
- GitHub App mode and granted permissions, without IDs/secrets;
- whether AI was disabled or the exact provider/model version;
- known edits/cuts and limitations;
- one screenshot of the completed Check as a fallback accessibility artifact.

Captions are required. Keep terminal narration readable without audio and provide a short transcript
or link to one. Verify the public link in a signed-out/incognito browser before treating this gate as
complete.
