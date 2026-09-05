# Errors — refusals, and how to read them

Every refusal from the VolStrata API is a machine-readable document in a single format.
This page describes that format, shows the refusals you will actually meet, and states the
two rules that keep a client from turning a refusal into a wrong answer.
API home: <https://volstrata.com>

> **Every body on this page is hand-written and illustrative.** The values — request ids,
> paths, plan names, timings — are placeholders chosen to show the shape. Do not match on
> them; match on the HTTP status and the documented field names.

---

## The problem document

Refusals are served as `application/problem+json` per
[RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html), with a few additive fields:

| Field | Type | Meaning |
|---|---|---|
| `type` | string | `https://volstrata.com/errors/<code>` — a stable URI identifying the error class |
| `title` | string | Short, human-readable summary of the class. Stable for a given `type` |
| `status` | number | The HTTP status code, repeated in the body |
| `detail` | string | What went wrong *with this request*. Written for a human; may change wording |
| `instance` | string | The request path the refusal applies to |
| `code` | string | The machine-readable error code — the canonical thing to branch on when you must |
| `error` | string | A short machine string carried alongside `code` for clients written against the older shape. Treat `code` as canonical |
| `request_id` | string | Identifier for this request. Log it; quote it if you contact support |
| `ok` | boolean | Always `false` on a refusal — the mirror of `ok: true` on success |

A **plan refusal** (402) adds four more:

| Field | Meaning |
|---|---|
| `feature` | The capability that was refused, by its dotted name |
| `required_plan` | The plan **slug** of the floor |
| `required_plan_name` | The **customer-facing** plan name — this is the one to display |
| `current_plan` | The plan the calling credential currently resolves to |

---

## The refusals you will meet

### 401 — no usable credential

```jsonc
// Illustrative.
{
  "ok": false,
  "type": "https://volstrata.com/errors/auth_required",
  "title": "Authentication required",
  "status": 401,
  "detail": "This capability requires a credential. Send 'Authorization: Bearer <key>' or '?api_key=<key>'. Accepted prefixes: gex_key_v1_, sig_key_v1_, sig_pat_v1_, sig_svc_v1_.",
  "instance": "/api/v1/gex/snapshot",
  "code": "auth_required",
  "error": "auth_required",
  "request_id": "00000000-0000-0000-0000-000000000000"
}
```

You sent no credential, or one the API could not resolve. Check that the environment variable
is actually set in the process that made the call, and that the header reads
`Authorization: Bearer <key>` with the single space. See
[AUTHENTICATION.md](./AUTHENTICATION.md).

### 402 — your plan sits below the operation's floor

```jsonc
// Illustrative.
{
  "ok": false,
  "type": "https://volstrata.com/errors/<error-code>",
  "title": "Plan upgrade required",
  "status": 402,
  "detail": "'gex.snapshot' requires the Edge plan.",
  "instance": "/api/v1/gex/snapshot",
  "code": "<error-code>",
  "error": "<error-code>",
  "request_id": "00000000-0000-0000-0000-000000000000",
  "feature": "gex.snapshot",
  "required_plan": "edge",
  "required_plan_name": "Edge",
  "current_plan": "free"
}
```

Your credential was accepted and understood; the answer is withheld. This is not a bug in
your request, and retrying will not help — the same request will be refused identically until
the owning account's plan changes.

`<error-code>` is written as a placeholder deliberately: branch on the **402 status**, not on
a code string copied out of a document. When you surface this to a person, print
`required_plan_name` (`Edge`), never `required_plan` (`edge`) — the slug is internal and has
been renamed before. Which operations sit behind which floor is in
[`reference/REST_ENDPOINTS.md`](./reference/REST_ENDPOINTS.md).

### 404 — that operation does not exist

```jsonc
// Illustrative.
{
  "ok": false,
  "type": "https://volstrata.com/errors/route_not_found",
  "title": "Not found",
  "status": 404,
  "detail": "No capability is published at this path.",
  "instance": "/api/v1/gex/levelz",
  "code": "route_not_found",
  "error": "route_not_found",
  "request_id": "00000000-0000-0000-0000-000000000000"
}
```

Nearly always a typo in the path or a stale operation name. Note that a gated operation you
cannot reach still exists — it answers 401 or 402, not 404. A 404 means the path itself is
not published. Confirm the name against the generated reference or the free
`GET /api/v1/meta/capabilities`.

### 429 — you are over your rate limit

```jsonc
// Illustrative.
{
  "ok": false,
  "type": "https://volstrata.com/errors/<error-code>",
  "title": "Too many requests",
  "status": 429,
  "detail": "Rate limit exceeded. Retry after the interval named in the Retry-After header.",
  "instance": "/api/v1/gex/levels",
  "code": "<error-code>",
  "error": "<error-code>",
  "request_id": "00000000-0000-0000-0000-000000000000"
}
```

The only refusal on this page that is worth retrying, and the one most likely to be
misread — see Rule 1. Honour `Retry-After`; the full policy, the headers that let you avoid
the 429 in the first place, and a retry helper are in [RATE_LIMITS.md](./RATE_LIMITS.md).

---

## Rule 1 — check the HTTP status before the body shape

```python
# Wrong. This turns every refusal into "no data".
levels = resp.json().get("levels", {})
```

That line is a bug even though it never raises. On a 429 it produces an empty result, and an
empty result is indistinguishable, downstream, from a genuine "there is nothing here". You
have not failed to get an answer — you have manufactured a **wrong** one, and it will
propagate into whatever you compute next.

Branch on the status first, every time:

```python
import requests

resp = session.get(url, params=params, timeout=30)

if resp.status_code == 200:
    payload = resp.json()
elif resp.status_code == 429:
    raise RateLimited(resp.headers.get("Retry-After"))     # retryable
elif resp.status_code in (401, 402):
    problem = parse_problem(resp)                          # a refusal, not an outage
    raise AccessDenied(problem.get("detail") or problem.get("title"))
elif 500 <= resp.status_code < 600:
    raise ServerError(resp.status_code)                    # retryable
else:
    raise ApiError(resp.status_code, parse_problem(resp))
```

The same discipline in JavaScript — `fetch` does **not** reject on a 4xx or 5xx, so
`res.ok` is the check you cannot skip:

```javascript
const res = await fetch(url, { headers });
if (!res.ok) {
  const problem = await parseProblem(res);   // may be null: see Rule 2
  throw new VolstrataApiError(res.status, problem);
}
const payload = await res.json();
```

---

## Rule 2 — a refusal that is not JSON never reached the API

Requests pass through a CDN edge before the API sees them. The edge can refuse on its own,
and when it does it answers in **`text/plain`**, not `application/problem+json`. There will be
no `code`, no `request_id`, and no problem document to parse — because no part of the API was
involved in producing it.

The specific trap: **the Python standard library's default `Python-urllib/*` User-Agent is
refused at the edge.** A first script written with `urllib.request` and no headers gets a
plain-text `403` before the API is reached, and a client that assumes every error is JSON
raises a decode error that points at the wrong layer entirely.

The fix is one line, and every example in this repo carries it:

```python
headers = {"User-Agent": "my-app/1.0 (+https://example.com)"}
```

Set an explicit `User-Agent` that names your program. Then make your parser defensive, so
that when a non-JSON refusal does arrive you can tell where it came from:

```python
def parse_problem(resp):
    """Return the problem document, or None if this refusal did not come from the API."""
    ctype = resp.headers.get("Content-Type", "")
    if "json" not in ctype:
        # Not application/problem+json -> the API never saw this request.
        # Almost always: a missing or refused User-Agent at the edge.
        return None
    try:
        return resp.json()
    except ValueError:
        return None
```

```javascript
async function parseProblem(res) {
  const ctype = res.headers.get("content-type") ?? "";
  if (!ctype.includes("json")) return null;   // edge refusal, not an API refusal
  try {
    return await res.json();
  } catch {
    return null;
  }
}
```

When `parse_problem` returns `None`, say so in your error message. "Refused before reaching
the API — check the User-Agent header" saves the next reader an hour that "Expecting value:
line 1 column 1" does not.

---

## Handling summary

| Status | Retry? | What it means |
|---|---|---|
| 401 | No | No usable credential. Fix the header or the environment variable |
| 402 | No | Below the plan floor. Display `required_plan_name` |
| 404 | No | The path is not published. Check the capability name |
| Other 4xx | **Never** | Your request is wrong. Retrying repeats the same wrong request |
| 429 | Yes | Over the rate limit. Honour `Retry-After`, back off |
| 5xx | Yes | Server-side. Back off with jitter, cap the attempts |

Log `request_id` on every refusal you keep. It is the fastest way for support to find the
request you are describing — and it is the one field in a problem document worth storing even
when you handled the error cleanly.

---

## Related

- [API error reference](https://volstrata.com/docs/api-errors) — the error envelope and code list, maintained with the API.

---

Copyright 2026 Volstrata.com - https://volstrata.com
