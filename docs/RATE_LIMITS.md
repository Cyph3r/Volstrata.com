# Rate limits — the budget, the headers, and how to back off

The VolStrata API meters requests with a per-owner token bucket. This page gives the
ceilings, the headers that report your remaining budget, and a retry policy that behaves.
API home: <https://volstrata.com>

---

## The budget is per owner

One bucket per **account**, sized by plan tier. Not per key, not per process, not per
machine — every credential an owner holds, and every script those credentials run in, draws
from the same allowance.

> Minting a second API key does not give you a second budget. Extra keys are for separation
> and revocability ([AUTHENTICATION.md](./AUTHENTICATION.md)), never for throughput.

Anonymous callers are metered too. If you have not sent a credential, you are on the
anonymous ceiling.

### Ceilings, requests per minute

| Tier | Per minute |
|---|---:|
| Anonymous (no credential) | 10 |
| Free | 10 |
| Edge | 60 |
| Pro | 120 |
| Ultra | 200 |
| Desk | 300 |
| Quant | 600 |

A token bucket refills continuously rather than resetting on the minute, so a steady
2-requests-per-second stream at Pro is fine while a burst of 120 in one second is not. If you
have work to spread out, spread it out: an even cadence gets more done than a burst followed
by a wall of 429s.

**More than one policy can be in force at once, and the table above is the one to build
against.** A response can advertise a larger ceiling than your tier's, because a wider
service-wide policy is also being applied and is the one currently doing the rejecting.
`ratelimit-policy` lists every policy in play and marks each `enforced` or `observed`, and
`x-ratelimit-enforced-by` names the one that actually applies. Do not read a roomier number
off a live header and design for it: an observed policy can begin enforcing without your
code changing, and the per-tier figures above are what your plan entitles you to.

---

## Read the headers — do not guess

Every response carries rate-limit headers, on success and on refusal alike. Read them and you
will rarely see a 429 at all.

**Modern form** (structured fields):

```
ratelimit: limit=120, remaining=118, reset=41
ratelimit-policy: 120;w=60
```

- `limit` — the bucket's size for your tier.
- `remaining` — tokens left right now. This is the number to watch.
- `reset` — seconds until the window resets.
- `ratelimit-policy` — the policy in force, as size and window (here: 120 per 60 seconds).

**Legacy form**, carrying the same information under the older names, still emitted for
clients written against it:

```
x-ratelimit-limit
x-ratelimit-remaining
x-ratelimit-reset
x-ratelimit-bucket        which bucket was applied
x-ratelimit-enforced-by   which layer enforced it
```

Prefer the modern header for budget decisions. For *timing* decisions after a 429, prefer
`Retry-After` over any computation of your own — it is the server telling you directly.

Parsing the modern header:

```python
def parse_ratelimit(headers):
    """-> {'limit': int, 'remaining': int, 'reset': int} or {} if absent/unparsable."""
    raw = headers.get("ratelimit")
    if not raw:
        return {}
    out = {}
    for part in raw.split(","):
        key, _, value = part.strip().partition("=")
        try:
            out[key.strip()] = int(value.strip())
        except ValueError:
            continue
    return out
```

```javascript
function parseRateLimit(headers) {
  const raw = headers.get("ratelimit");
  if (!raw) return {};
  return Object.fromEntries(
    raw.split(",").map((part) => {
      const [k, v] = part.split("=").map((s) => s.trim());
      return [k, Number(v)];
    }).filter(([, v]) => Number.isFinite(v)),
  );
}
```

Treat missing headers as missing information, not as an infinite budget. Write the fallback
path as if `remaining` were low.

---

## Retry policy

Four rules, in order of importance:

1. **Honour `Retry-After`.** If the header is present on a 429, wait at least that long. Do
   not shorten it, and do not replace it with your own estimate.
2. **Exponential backoff with jitter** when no `Retry-After` is given. Doubling alone
   synchronises every client that failed at the same moment into a second simultaneous
   burst; jitter is what breaks that up.
3. **Cap the attempts, hard.** Three or four tries, then fail loudly and let the caller
   decide. A retry loop with no ceiling is an outage amplifier — and against a metered API,
   it is also a way to spend your entire budget on requests that were never going to succeed.
4. **Retry only 429 and 5xx.** A 400, 401, 402 or 404 is a statement about your request. The
   identical request will be refused identically, so retrying it wastes budget and delays the
   error reaching you. See [ERRORS.md](./ERRORS.md).

```python
import random
import time

import requests

RETRYABLE = {429, 500, 502, 503, 504}


def get_with_retry(session, url, params=None, *, max_attempts=4, timeout=30):
    """GET with bounded backoff. Raises on the final failure; never loops forever."""
    for attempt in range(1, max_attempts + 1):
        resp = session.get(url, params=params, timeout=timeout)

        if resp.status_code not in RETRYABLE:
            return resp                      # success, or a refusal worth surfacing now

        if attempt == max_attempts:
            resp.raise_for_status()          # out of attempts: fail loudly
            return resp

        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                delay = float(retry_after)   # server's instruction wins
            except ValueError:
                delay = 2.0 ** attempt
        else:
            delay = 2.0 ** attempt           # 2s, 4s, 8s

        delay += random.uniform(0, 1.0)      # jitter: de-synchronise concurrent clients
        time.sleep(delay)

    raise RuntimeError("unreachable")
```

The JavaScript version is the same shape:

```javascript
const RETRYABLE = new Set([429, 500, 502, 503, 504]);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function getWithRetry(url, { headers, maxAttempts = 4 } = {}) {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const res = await fetch(url, { headers });
    if (!RETRYABLE.has(res.status)) return res;
    if (attempt === maxAttempts) return res;   // caller inspects res.ok and gives up

    const retryAfter = Number(res.headers.get("retry-after"));
    const base = Number.isFinite(retryAfter) && retryAfter > 0
      ? retryAfter * 1000
      : 2 ** attempt * 1000;
    await sleep(base + Math.random() * 1000);
  }
}
```

---

## Do not poll in an unbounded loop

The most common way to burn a budget is a loop that was never meant to be a load test:

```python
while True:                       # do not do this
    r = requests.get(url)
    process(r.json())
```

At the anonymous ceiling of 10 requests per minute, that loop is over budget within a second
and stays there. Instead:

- **Bound every loop** — a fixed page cap, a fixed iteration count, a deadline. Pagination
  loops in particular must have a ceiling; see [PAGINATION.md](./PAGINATION.md).
- **Sleep on purpose.** If you want a value every 30 seconds, sleep 30 seconds. Do not spin
  and rely on 429s to pace you — a 429 costs you a request and gives you nothing.
- **Do not parallelise to go faster.** Concurrency does not raise the ceiling; it just
  reaches it sooner, from several places at once, and makes the backoff harder to reason
  about.
- **Cache what does not move.** The capability catalog, the OpenAPI document and reference
  data change on the order of days. Fetch them once per run, not once per call.
- **Check `freshness` before re-fetching.** If the payload tells you how old it is and when
  it goes stale, you can often skip the next call entirely — see
  [FRESHNESS_AND_DELIVERY.md](./FRESHNESS_AND_DELIVERY.md).
- **Keep CI honest.** Automated checks run against the live production API on the same
  ceiling as everything else. A smoke test should be a couple of requests, not a matrix.

---

## Related

- [API rate limits](https://volstrata.com/docs/api-rate-limits) — the metering model and current per-plan ceilings, maintained with the API.

---

Copyright 2026 Volstrata.com - https://volstrata.com
