# Quickstart — VolStrata REST API

From nothing to a real HTTP response in three steps, no account and no API key required.
API home: <https://volstrata.com>

- **Base URL:** `https://volstrata.com`
- **Base path:** `/api/v1`
- **Auth for this page:** none — 67 of the 180 published operations sit at the Free plan
  floor and most of those, including every call on this page, answer with no credential.

---

## Step 1 — Set a User-Agent

Every request in this repo sends an explicit `User-Agent`. This is not decoration.

Requests reach a CDN edge before they reach the API. The edge refuses some default agent
strings outright — notably the Python standard library's `Python-urllib/*` — and answers
with a **plain-text** body that never came from the API at all. A client that assumes
"every refusal is JSON" will throw a JSON decode error and blame the wrong layer.

Set an agent that names your program:

```
User-Agent: my-app/1.0 (+https://example.com)
```

Full explanation of that failure mode, and how to detect it in code, is in
[ERRORS.md](./ERRORS.md).

---

## Step 2 — Call a free endpoint

`gex.levels` needs no credential. Ask it for SPX:

```bash
curl -sS \
  -A "volstrata-examples/1.0" \
  "https://volstrata.com/api/v1/gex/levels?ticker=SPX"
```

Python, standard library only — note the explicit agent:

```python
import json
import urllib.request

req = urllib.request.Request(
    "https://volstrata.com/api/v1/gex/levels?ticker=SPX",
    headers={
        "Accept": "application/json",
        "User-Agent": "volstrata-examples/1.0",  # required: see Step 1
    },
)
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.load(resp)

print(json.dumps(data, indent=2))
```

JavaScript, Node 18+ (native `fetch`, no dependencies):

```javascript
const res = await fetch(
  "https://volstrata.com/api/v1/gex/levels?ticker=SPX",
  { headers: { Accept: "application/json", "User-Agent": "volstrata-examples/1.0" } },
);
const data = await res.json();
console.log(JSON.stringify(data, null, 2));
```

In a browser, `User-Agent` is a forbidden header name and is ignored — the browser sends
its own, which the edge accepts. The header matters for scripts and servers, not tabs.

---

## Step 3 — Read `ok`, then read the payload

Successful responses are a JSON object whose first field is `ok`. The rest of the object
is the operation's own payload. For `gex.levels` the top-level keys are
`ok`, `ticker`, `spot`, `ts`, `updated`, and `levels`:

```jsonc
// Illustrative shape. Values are synthetic — print the live response to see real ones.
{
  "ok": true,
  "ticker": "SPX",
  "spot": 5000.0,
  "ts": "…",
  "updated": "…",
  "levels": { "…": "…" }
}
```

Two habits worth forming on your very first call:

1. **Check the HTTP status before you look at the body.** `ok` is only meaningful on a
   2xx response. A 429 whose body you read as "no data" is a *wrong* answer that looks
   like an empty one. See [ERRORS.md](./ERRORS.md).
2. **Dump the whole response once** (`json.dumps(data, indent=2)`) rather than guessing at
   field names. Payload keys differ per operation and the printed object is the
   authoritative answer for the ticker and moment you asked about.

Every response also carries `x-gex-api-version` (the dated API contract version) and a
set of rate-limit headers described in [RATE_LIMITS.md](./RATE_LIMITS.md).

---

## Step 4 (optional) — Add a key

Gated operations need a credential. Create one at <https://volstrata.com/api-keys>, put it
in an environment variable, and send it as a bearer token:

```bash
export VOLSTRATA_API_KEY="gex_key_v1_XXXXXXXX"   # placeholder, not a real key

curl -sS \
  -A "volstrata-examples/1.0" \
  -H "Authorization: Bearer ${VOLSTRATA_API_KEY}" \
  "https://volstrata.com/api/v1/gex/snapshot?ticker=SPX"
```

If the key is missing you get **401** (`auth_required`). If the key is valid but your plan
sits below the operation's floor you get **402**, and the body names the plan you need —
that is a refusal to answer, not a bug in your request. Both bodies, and how to branch on
them, are in [ERRORS.md](./ERRORS.md); the credential formats are in
[AUTHENTICATION.md](./AUTHENTICATION.md).

Never hard-code a key in a file you commit. This repo reads `VOLSTRATA_API_KEY` (and
optionally `VOLSTRATA_BASE_URL`) from the environment everywhere, and ships only an
`.env.example`.

---

## Where to go next

| You want | Read |
|---|---|
| Runnable shell scripts | [`../examples/curl/`](../examples/curl/) |
| Runnable Python (`requests`) | [`../examples/python/`](../examples/python/) |
| Runnable JavaScript (native `fetch`) | [`../examples/javascript/`](../examples/javascript/) |
| The full operation list | [`reference/REST_ENDPOINTS.md`](./reference/REST_ENDPOINTS.md) |
| How the surface is organised | [REST_API.md](./REST_API.md) |
| Credentials and plan floors | [AUTHENTICATION.md](./AUTHENTICATION.md) |
| Refusals and retries | [ERRORS.md](./ERRORS.md) · [RATE_LIMITS.md](./RATE_LIMITS.md) |
| Multi-page results | [PAGINATION.md](./PAGINATION.md) |
| How current the data is | [FRESHNESS_AND_DELIVERY.md](./FRESHNESS_AND_DELIVERY.md) |

One practical note before you write a loop: the anonymous ceiling is 10 requests per
minute, shared across everything you run. Bound your loops.

---

## Related

- [Three-language API examples on volstrata.com](https://volstrata.com/docs/api-examples) — the same curl / Python / JavaScript progression, maintained alongside the API itself.

---

Copyright 2026 Volstrata.com - https://volstrata.com
