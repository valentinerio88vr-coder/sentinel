# Security Policy

## Reporting a vulnerability

**Please do not open a public issue.** Use GitHub's private vulnerability reporting on this
repository, or contact the maintainer directly.

Include: what you did, what happened, and what you expected. A proof of concept helps enormously.

### What counts as critical

- Reading another account's monitored data (cross-tenant leak)
- Bypassing the consent requirement during enrolment
- Defeating the server-side kill switch (pause / revoke)
- Recovering a device token or session token from the database or logs
- Any way to make the Android agent collect data while showing no notification

### Response

Best effort, typically within a week. This is a self-hosted project maintained by volunteers — there
is no SLA, and no bug bounty.

## Supported versions

Only the latest `main` is supported. If you are running an older commit, upgrade before reporting.

## Security posture — what you should know before deploying

Sentinel is a **reference implementation**, not a hardened product. Read
[`MISSING-FEATURES.md`](MISSING-FEATURES.md) §3 before trusting it with real data. In particular:

| Known limitation | Status |
|---|---|
| No TLS termination included | You must put it behind Caddy/nginx. Tokens travel in headers. |
| No login rate limiting | Add at the reverse proxy until §3.2 lands. |
| No password reset | Back up `data/secret.key` and record your password. |
| Session tokens valid until expiry (12h) | No revocation until §3.6 lands. |
| SQLite, single writer | Do not expose to the public internet. |
| Push notifications unimplemented | Alerts require an open browser tab. An SOS may not reach you. |

The last row is the one that matters for a safety product. Treat v2.0.0 as a working prototype and
verify alerts reach you before relying on them.
