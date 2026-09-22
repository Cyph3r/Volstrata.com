# Python examples

Runnable examples for the VolStrata API at <https://volstrata.com>, REST and MCP,
using `requests` and the standard library. Python 3.9 or newer.

There is no VolStrata package to install and nothing here imports one. The API is
plain HTTP and JSON; a session, a header and a status check is the whole client.

## Run the quickstart

```sh
python -m pip install -r requirements.txt
python quickstart.py
```

That is the complete setup. No key, no `.env`, no account — `quickstart.py` calls
a capability that answers an anonymous caller and prints real, current output.

## Use a key when you need one

```sh
export VOLSTRATA_API_KEY=...        # macOS / Linux
$env:VOLSTRATA_API_KEY = "..."      # Windows PowerShell
```

Every file picks it up automatically and sends it as `Authorization: Bearer <key>`.
Nothing here reads a file, writes a file, or contains a credential. Issue and
revoke keys at <https://volstrata.com/api-keys>.

Two environment variables are read, and no others:

| Variable | Required | Meaning |
|---|---|---|
| `VOLSTRATA_API_KEY` | no | Sent as a bearer token when set. Some capabilities need one; many do not. |
| `VOLSTRATA_API_BASE` | no | Defaults to `https://api.volstrata.com`. Set it only to point at a proxy of your own. |

## The files

Start at the top and work down.

| File | What it is |
|---|---|
| [`quickstart.py`](quickstart.py) | One call, zero setup. Start here. |
| [`volstrata_helpers.py`](volstrata_helpers.py) | The shared module every other file imports: session, GET/POST, RFC 9457 errors, retry with backoff, cursor pagination, MCP JSON-RPC. Read it once and you have read this repository's Python. |
| [`auth_and_errors.py`](auth_and_errors.py) | Authentication, every kind of refusal, and the rate-limit headers. |
| [`pagination.py`](pagination.py) | A cursor-paged collection, read to completion under a bound. |
| [`discover_capabilities.py`](discover_capabilities.py) | The published surface, read at runtime two ways, plus what your own credential unlocks. |
| [`rest/`](rest/) | One commented, runnable file per domain group. |
| [`mcp/`](mcp/) | JSON-RPC 2.0 against the MCP endpoint — see [`mcp/README.md`](mcp/README.md). |

### `rest/`

Eight files, deliberately not one per endpoint — 180 near-identical stubs would be
worse documentation than a handful of files worth reading. Each exercises several
representative capabilities of one domain group, with real error handling.

```sh
python rest/gex_levels.py
```

| File | Domain group |
|---|---|
| [`rest/gex_levels.py`](rest/gex_levels.py) | `gex.*` — the named levels map, per-strike series, scalar metrics, and one gated capability |
| [`rest/greeks.py`](rest/greeks.py) | `greeks.*`, `vol.*` — per-strike gamma and implied vol, plus two plan floors |
| [`rest/valuation.py`](rest/valuation.py) | `valuation.*`, `fundamentals.*` — a screen, a company, and the first POST |
| [`rest/market.py`](rest/market.py) | `market.*` — quotes, candles, seasonality, index membership |
| [`rest/levels.py`](rest/levels.py) | `levels.*` — the daily and weekly products, and one capability in four formats |
| [`rest/research_and_docs.py`](rest/research_and_docs.py) | `research.*`, `docs.*`, `symbol.*` — resolve, check coverage, query, define |
| [`rest/calendar_news_social.py`](rest/calendar_news_social.py) | `calendar.*`, `news.*`, `insider.*`, `social.*` — the cursor-paged collections |
| [`rest/accuracy_and_stats.py`](rest/accuracy_and_stats.py) | `accuracy.*`, `gammapin.*`, `dealergamma.*`, `stats.*`, `status.*` — the self-scoring half |

## What every file does the same way

**An explicit `User-Agent`.** Not politeness — a requirement. Some default agent
strings are refused at the CDN before the request reaches the API, and that
refusal is plain text, not JSON. If you ever get a non-JSON error body, check
this first. `volstrata_helpers.session()` sets one.

**HTTP status first, body second.** A body that happens to contain `ok` proves
nothing, and not every successful response even carries `ok`. The status is the
source of truth, so `get()` checks it before it parses anything.

**Refusals are parsed, not dumped.** Every refusal is an RFC 9457
`application/problem+json` document: `{ok, type, title, status, detail, instance,
code, request_id}`, plus `feature`, `required_plan`, `required_plan_name` and
`current_plan` when a plan floor is the reason. `VolstrataError` carries those
fields, and `attempt()` prints one readable line and carries on.

**A gated call is an expected outcome, not a crash.** Every example that touches a
capability above the lowest floor catches the refusal, names the plan that would
clear it, and exits 0. Run any file with no key and it completes.

**Bounded, sequential requests.** These run against live production under a
per-minute ceiling that is shared per owner, not per key. There is no concurrency,
no polling and no unbounded loop anywhere in this folder; every pagination loop
carries a page bound, and `request_with_backoff()` honours `Retry-After`, retries
only 429 and 5xx, and stops after four attempts.

## Plan floors, and what "free" means

`Free` is the lowest published plan floor — it is not a synonym for anonymous.
Much of the surface answers with no credential at all; some capabilities at the
Free floor still want an authenticated principal and answer `401 auth_required`
until they get one. Rather than keeping a list, ask:

```sh
python discover_capabilities.py
```

It prints what your credential unlocks now, from `GET /api/v1/meta/access`.

## Copy this into your own project

`volstrata_helpers.py` is written to be lifted. Take the whole file, or take the
four ideas in it: set a User-Agent, check the status before the body, parse the
problem document, and bound your retries.

## Related

- <https://volstrata.com/docs/api-overview> — the API, in prose
- <https://volstrata.com/docs/api-auth> — credentials and how to present them
- <https://volstrata.com/docs/api-errors> — the refusal envelope
- <https://volstrata.com/docs/api-rate-limits> — ceilings and headers
- <https://volstrata.com/docs/api-catalog> — every published capability
- <https://volstrata.com/mcp> — the MCP connect page
- [`../curl/`](../curl/) — the same calls in a shell
- [`../../docs/reference/REST_ENDPOINTS.md`](../../docs/reference/REST_ENDPOINTS.md) — the generated surface reference

## Terms and disclaimer

The MIT licence covers the code and documentation in this repository only. Access to
the VolStrata API and any use of what it returns is governed by the Terms of Service
at <https://volstrata.com/legal/terms>. Nothing here, and nothing the API returns, is
investment, financial or trading advice; published accuracy scores are the project's
own automated grading of its own prior output and are not indicative of future
results. See <https://volstrata.com/legal/disclaimer>.

---

Copyright 2026 Volstrata.com — <https://volstrata.com>
