# Security Policy

## Supported versions

Security fixes are made on the current release line. Pre-1.0 checkpoints are no longer supported
after `v1.0.0` is published.

| Version | Supported |
| --- | --- |
| Latest `1.x` | Yes |
| `0.4.x` and older | No after `v1.0.0` |

Until the first `v1.0.0` tag exists, report issues against the latest commit on `main` and treat it
as pre-release software.

## Report a vulnerability privately

Use the repository's [private vulnerability report](https://github.com/sinh2206/MaintainerFlow/security/advisories/new).
Do not open a public issue, discussion or pull request with exploit details, secrets, real webhook
payloads, private repository content or personal data. If private reporting is not enabled, ask the
repository owner to enable it without disclosing the vulnerability, then use the private form.

Include only what is necessary:

- affected version/commit and deployment mode;
- impact and prerequisites;
- minimal reproduction using synthetic data;
- relevant logs with secrets, URLs and private content removed;
- suggested mitigation, if known.

Expect acknowledgement within 3 business days and an initial severity/next-step assessment within
10 business days. Complex or coordinated fixes may take longer; the maintainer will provide updates.
Please allow a fix and disclosure plan before publishing details. We will credit reporters who want
credit and will not require secrecy after a coordinated disclosure date.

Immediately rotate/revoke a credential if it may have been exposed; a code fix cannot make an
already disclosed secret safe. For operational hardening and the threat model, see
[docs/security.md](docs/security.md).
