# Security policy

## Reporting a vulnerability

Report privately. Do not open a public issue, a pull request or a discussion for a
suspected vulnerability in the VolStrata API, this repository, or the examples in it.

Use the contact link published on https://volstrata.com and send the report by email.
Include what you observed, the endpoint or file involved, and the steps to reproduce it.
A proof of concept helps; a live exploit against production does not — keep the
reproduction to the smallest number of requests that demonstrates the issue.

You will get an acknowledgement that the report was received. Please give the team a
reasonable window to investigate and ship a fix before disclosing anything publicly.

## Never paste a key

Never put an API key, personal access token, service-account credential, session cookie
or `Authorization` header value into an issue, a pull request, a code comment, a log
excerpt or a screenshot. Redact them before you paste anything.

When you need to show a credential in text, use an obviously fake placeholder:
`YOUR_API_KEY` or `gex_key_v1_XXXXXXXX`.

## If a key is exposed

Rotate first, clean up second. A key that has appeared anywhere public should be treated
as compromised even if it was removed seconds later — rewriting history does not undo a
disclosure.

1. Revoke the exposed key and mint a replacement at https://volstrata.com/api-keys.
2. Update whatever was using it — your environment, your `.env` file, your CI secrets.
3. Then remove the value from the branch or issue.

Keys are stored as a hash and shown in plaintext only once, at creation, so a lost key is
replaced rather than recovered. Rate limits apply per owner, not per key, so minting a
replacement does not change your ceiling.

## Scope

This policy covers the public API at https://volstrata.com and the contents of this
repository. Please do not run load tests, scanners or automated fuzzing against the
production API — the anonymous ceiling is 10 requests per minute and the examples here
are written to stay well inside it.

---

Copyright 2026 Volstrata.com - https://volstrata.com
