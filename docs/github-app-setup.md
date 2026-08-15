# GitHub App setup

Create a dedicated GitHub App for each environment. Start in `shadow` mode on a disposable test
repository, then grant only the capability you need.

## 1. Prepare a public HTTPS endpoint

GitHub must reach:

```text
https://YOUR_HOST/webhooks/github
```

Terminate TLS at a reverse proxy/load balancer and forward the original request body unchanged to
the API container on port 8000. Do not expose PostgreSQL or Redis. `/health` reports process health;
`/ready` verifies database connectivity.

## 2. Register the App

In GitHub, open **Settings -> Developer settings -> GitHub Apps -> New GitHub App**:

1. Choose a unique name and homepage URL.
2. Set **Webhook URL** to the endpoint above and activate webhooks.
3. Generate a random webhook secret of at least 16 characters and store the same value as
   `MAINTAINERFLOW_GITHUB_WEBHOOK_SECRET`.
4. Disable user authorization/callback features; MaintainerFlow uses installation authentication.
5. Set repository permissions and events from the matrix below.
6. Create the App, note its numeric App ID, generate a private key, and store the complete PEM.

## 3. Minimum permissions

GitHub grants Metadata read implicitly. Do not grant organization/account permissions.

| Capability | Contents | Pull requests | Checks | Issues | Webhook events |
| --- | --- | --- | --- | --- | --- |
| PR analysis, shadow only | Read | Read | None | None | Pull request |
| Publish PR suggestion | Read | Read | Write | None | Pull request, Check run |
| Issue triage | Read | Read | None | Read | Issues |
| PR + repository intelligence | Read | Read | None or Write | None | Pull request |
| All current runtime features | Read | Read | Write | Read | Pull request, Issues, Check run |

The installation-token implementation always narrows tokens to Contents read and Pull requests
read, then conditionally requests Checks write/Issues read. Do not grant Contents write, Pull
requests write, Issues write, Administration, Actions, Workflows, Members or Secrets permissions.

Subscribe only to:

- **Pull request**: the current parser processes `opened` and `synchronize`; other actions are
  acknowledged as ignored.
- **Issues**: the current parser processes `opened` only, and only when issue triage is enabled.
- **Check run**: optional feedback buttons process `requested_action` for MaintainerFlow checks.

## 4. Configure the deployment

Encode PEM newlines as literal `\n` inside a quoted `.env` value, or inject the multiline secret
through your deployment platform:

```dotenv
MAINTAINERFLOW_GITHUB_APP_ID=123456
MAINTAINERFLOW_GITHUB_WEBHOOK_SECRET=replace-with-a-long-random-secret
MAINTAINERFLOW_GITHUB_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
MAINTAINERFLOW_WORKFLOW_ENABLED=true

# Safe initial rollout
MAINTAINERFLOW_CHECK_PUBLISH_ENABLED=false
MAINTAINERFLOW_CHECK_MODE=shadow
MAINTAINERFLOW_ISSUE_TRIAGE_ENABLED=false
MAINTAINERFLOW_REPOSITORY_INTELLIGENCE_ENABLED=false
```

Run `uv run maintainerflow config-check` in the same environment without printing secret values.
Restart API/worker/recovery after configuration changes.

## 5. Install and verify

Install the App on **Only select repositories** and choose a test repository. Confirm:

1. `GET /health` and `/ready` succeed.
2. GitHub App **Advanced -> Recent Deliveries** shows a `2xx` response for a newly opened PR.
3. API logs show an accepted delivery; a repeated delivery is reported as duplicate.
4. In shadow mode no Check Run is created.
5. After enabling `CHECK_PUBLISH`, a new/synchronized PR creates a non-blocking MaintainerFlow Check.
6. If issue triage is enabled, a new issue creates an audit suggestion but no label/comment/change.

If GitHub returns `401`, check App ID/private-key pairing and host clock. For `403`, inspect the
`X-Accepted-GitHub-Permissions` response header and compare it to the matrix. For missing events,
check subscription, installation repository selection and webhook delivery details. A bad webhook
signature normally means GitHub and the deployment do not share the exact secret or a proxy changed
the raw body.

Permission changes require each installation owner to approve the new grant before it becomes
available. See [Security](security.md) before widening access.
