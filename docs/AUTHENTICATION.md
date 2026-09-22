# Authentication — VolStrata REST API

How to identify yourself to the API, what a credential looks like, and where the limits
attach. API home: <https://volstrata.com>

---

## Base URL and base path

| | |
|---|---|
| Host | `https://api.volstrata.com` |
| Base path | `/api/v1` |
| A full URL | `https://api.volstrata.com/api/v1/<domain>/<name>` |
| Version header on every response | `x-gex-api-version: 2026-09-09` |

`/api/v1` is the only live API surface. The `/api/v2` base path is **retired**: nothing is
served or advertised under it, so a request to it is a plain `404` — and, because no
capability route matches, that 404 comes from the web layer as HTML rather than as an
RFC 9457 problem document. If you are reading an old snippet that uses it, change the path
segment to `v1` and nothing else — the operation names did not move.

Clients in this repo read the host from `VOLSTRATA_API_BASE` and default to
`https://api.volstrata.com`, the canonical API host. The apex `https://volstrata.com`
serves the identical API and keeps working, so an older snippet that names it is not
broken — but every example here calls the API host. For compatibility the clients still
read the older `VOLSTRATA_BASE_URL` if `VOLSTRATA_API_BASE` is unset.

---

## One mechanism, four credential families

Authentication is a single mechanism: the request presents a credential, the API resolves it
to an owner and that owner's plan tier, and the plan tier decides which operations answer.
Four families of credential feed that same machinery:

| Family | Prefix | Use it for |
|---|---|---|
| Browser session cookie | — | Signed-in use of the website. **Not applicable to scripts** — do not try to reuse a session cookie from your browser in code. |
| **API key** | `gex_key_v1_` | Scripts, notebooks, spreadsheets, servers, MCP clients. **This is the family this repo teaches.** |
| Personal access token | `sig_pat_v1_` | Named in the API's own 401 body as an accepted credential. Not covered here. |
| Service account | `sig_svc_v1_` | Named in the API's own 401 body as an accepted credential. Not covered here. |

All four resolve to the same principal-and-tier model, so everything the rest of this repo
says about plan floors, rate limits, errors and freshness applies whichever one you hold.

---

## The API key

**Format.** The prefix `gex_key_v1_` followed by 43 url-safe base64 characters.

**Legacy keys.** Keys minted under the older `sig_key_v1_` prefix are still accepted. If you
hold one it keeps working; there is nothing to migrate.

**Storage.** The API stores only a SHA-256 hash of your key. The plaintext is displayed
**exactly once**, at creation. If you lose it, no one can recover it — mint a new key and
delete the old one.

**Placeholders in this repo.** Examples show `YOUR_API_KEY` or `gex_key_v1_XXXXXXXX`. Neither
is a valid length or alphabet, so neither can be mistaken for a live credential.

### Presentation — two ways, one preferred

**Preferred — `Authorization` header:**

```bash
curl -sS \
  -A "volstrata-examples/1.0" \
  -H "Authorization: Bearer ${VOLSTRATA_API_KEY}" \
  "https://api.volstrata.com/api/v1/gex/snapshot?ticker=SPX"
```

**Alternative — `api_key` query parameter:**

```bash
curl -sS \
  -A "volstrata-examples/1.0" \
  "https://api.volstrata.com/api/v1/gex/snapshot?ticker=SPX&api_key=${VOLSTRATA_API_KEY}"
```

The query form exists for environments that cannot set a header — a spreadsheet formula, a
charting tool's URL field, a quick browser check. Understand the cost before you use it: a
URL travels into shell history, browser history, bookmarks, referrer headers, proxy logs and
crash reports, and every one of those is a place your key can be read later. Prefer the
header everywhere you control the request.

### In code

Python (`requests`), header set once on a session:

```python
import os
import requests

session = requests.Session()
session.headers.update({
    "Accept": "application/json",
    "User-Agent": "volstrata-examples/1.0",
})

api_key = os.environ.get("VOLSTRATA_API_KEY")
if api_key:
    session.headers["Authorization"] = f"Bearer {api_key}"

base = os.environ.get("VOLSTRATA_API_BASE", "https://api.volstrata.com")
resp = session.get(f"{base}/api/v1/gex/levels", params={"ticker": "SPX"}, timeout=30)
```

JavaScript (Node 18+, native `fetch`):

```javascript
const base = process.env.VOLSTRATA_API_BASE ?? "https://api.volstrata.com";
const headers = {
  Accept: "application/json",
  "User-Agent": "volstrata-examples/1.0",
};
if (process.env.VOLSTRATA_API_KEY) {
  headers.Authorization = `Bearer ${process.env.VOLSTRATA_API_KEY}`;
}

const res = await fetch(`${base}/api/v1/gex/levels?ticker=SPX`, { headers });
```

Note the shape of both: the key is read from the environment and the code still runs without
it. That is deliberate — see the next section.

---

## 67 operations sit at the Free plan floor

Of the 180 published operations, **67 sit at the Free plan floor**, and most of those answer
a caller who sends no credential at all. That is not a trial mode or a teaser; it is a
documented part of the surface, and it is why every example in this repo can be cloned and
run before you have an account.

**A Free floor is not a promise of anonymous access.** The plan floor and the credential
requirement are two separate gates. A handful of Free-floor data operations — `market.status`,
`market.overview`, `market.rotations`, `news.feed`, the `calendar.*` family, `insider.filings`,
the `social.*` family, `valuation.company`, `valuation.universe` and `alerts.signal_stats`
among them — ask for *any* valid key and answer `401 auth_required` without one. Any accepted
credential clears that gate; no upgrade is involved.

Do not maintain that list by hand. `GET /api/v1/meta/access` reports what the credential you
are actually sending can reach, which is the only answer that cannot go stale.

Write your client so the credential is optional: attach the header when the environment
variable is set, omit it when it is not, and let the API decide. An anonymous call to a gated
operation is refused cleanly with 401 and a body that tells you what was missing — a much
better failure than a crash on a `KeyError` at import time.

Which operations are free is recorded per-operation in
[`reference/REST_ENDPOINTS.md`](./reference/REST_ENDPOINTS.md), and can be read at runtime
from the free `GET /api/v1/meta/capabilities` — see [REST_API.md](./REST_API.md).

---

## When a credential is rejected

A missing or unusable credential produces `401` with an RFC 9457 problem document whose
`code` is `auth_required`. The body names the credential prefixes the API accepts, which is
where the `sig_pat_v1_` and `sig_svc_v1_` families in the table above come from — it is
telling you the full set, not implying you should have four of them.

A credential that is valid but whose owner sits below an operation's plan floor produces
`402`, with `feature`, `required_plan`, `required_plan_name` and `current_plan` added to the
problem document. Full bodies and handling code are in [ERRORS.md](./ERRORS.md).

---

## Rate limiting attaches to the owner, not the key

This is the single most misunderstood part of the model, so it is stated plainly:

> **The rate limit is per owner.** Every credential you hold draws from one bucket sized by
> your plan tier. Minting a second key does not give you a second allowance, and neither does
> a tenth. More keys buy you separation and revocability — never throughput.

Keys are still worth splitting per application, because you can revoke one without touching
the others and you can tell from usage which integration is spending the budget. Just size
your clients against one shared ceiling. The per-minute numbers by tier, the response headers
that report your remaining budget, and the retry policy are in
[RATE_LIMITS.md](./RATE_LIMITS.md).

---

## Handling keys safely

- Read the key from `VOLSTRATA_API_KEY`. Never write it into source, a notebook cell, a
  config file you commit, a screenshot, or an issue report.
- This repo ships `.env.example` only. `.env` is git-ignored and must stay that way.
- Prefer the `Authorization` header over `?api_key=` wherever you control the request.
- Mint one key per application so a leak has a blast radius of one.
- Rotate by creating the new key, deploying it, then deleting the old one — in that order,
  so nothing is offline in between.
- If a key is exposed, delete it. Because only a hash is stored, deletion is the only
  remediation there is, and it is immediate.

**Get an API key:** <https://volstrata.com/api-keys>

---

## Related

- [API authentication](https://volstrata.com/docs/api-auth) — the credential families as the API team documents them.
- [API keys](https://volstrata.com/docs/api-keys) — creating, scoping, rotating and revoking a key.

---

Copyright 2026 Volstrata.com - https://volstrata.com
