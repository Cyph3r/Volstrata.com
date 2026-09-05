# JavaScript / Node examples

Runnable examples for the [VolStrata](https://volstrata.com) REST API and MCP endpoint,
in plain ESM for Node 18+. Native `fetch`, **zero runtime dependencies**, nothing to
install.

```bash
cd examples/javascript
node quickstart.mjs
```

That prints live data. There is no `npm install` step and no account needed: 67 of the
180 published operations sit at the Free floor, most of those answer with no credential,
and the quickstart calls one that does.

## Requirements

| | |
|---|---|
| Node | 18 or newer — that is where global `fetch` and `AbortSignal.timeout` arrive |
| Dependencies | none. `package.json` declares an empty `dependencies` and exists only for `npm run` and `"type": "module"` |
| Credential | optional. Set `VOLSTRATA_API_KEY` for capabilities above the Free floor |

There is no VolStrata npm package to install. [`lib/volstrata.mjs`](lib/volstrata.mjs) is
the entire client: one file, mostly comments, meant to be read in one sitting and copied
into your own project.

## Files

| File | What it shows | Requests |
|---|---|---:|
| [`quickstart.mjs`](quickstart.mjs) | One Free call, a few fields printed, the rate-limit budget. Start here. | 1 |
| [`auth_and_errors.mjs`](auth_and_errors.mjs) | Anonymous vs authenticated, the RFC 9457 problem document, a plan floor, a 404, the rate-limit headers. Exits 0 in every branch. | 3–4 |
| [`pagination.mjs`](pagination.mjs) | The shared `?limit=&cursor=` model walked to completion with an async generator and a page bound. | ~7 |
| [`lib/volstrata.mjs`](lib/volstrata.mjs) | The shared module every example imports: headers, errors, retry, pagination, printing. | — |

### REST, by domain group

Each file stands alone, takes an optional ticker as its first argument, and exercises a
handful of related capabilities with real error handling.

Plan floors quoted below are the ones the published catalog declares. What *your* caller
can reach is what [`GET /api/v1/meta/access`](https://volstrata.com/docs/api-catalog)
reports: an anonymous call to anything out of reach returns `401 auth_required` rather
than data, and these files print that and carry on rather than stopping.

| File | Domains | Requests |
|---|---|---:|
| [`rest/gex_levels.mjs`](rest/gex_levels.mjs) | `gex.levels`, `gex.bars`, `gex.metrics`, `gex.gamma_flip`, `gex.maxpain`, `gex.named_levels`, and `gex.snapshot` (Edge) | 7 |
| [`rest/greeks.mjs`](rest/greeks.mjs) | `greeks.gamma` (Free); `greeks.charm` and `vol.surface` (Pro) | 3 |
| [`rest/valuation.mjs`](rest/valuation.mjs) | `valuation.universe`, `valuation.company`, `fundamentals.company`; `valuation.value` (Pro, POST) | 4 |
| [`rest/market.mjs`](rest/market.mjs) | `market.status`, `.overview`, `.rotations`, `.snapshot`, `.candles`, `.seasonality`, `.etf_constituents` | 7 |
| [`rest/levels.mjs`](rest/levels.mjs) | `levels.day`, `.week`, `.day_report`, `.week_report`, `.detail`, `.tradingview` | 6 |
| [`rest/research_and_docs.mjs`](rest/research_and_docs.mjs) | `research.*`, `docs.metrics`, `docs.metric`, `symbol.search`, `symbol.resolve` | 8 |
| [`rest/calendar_news_social.mjs`](rest/calendar_news_social.mjs) | `calendar.*`, `news.feed`, `insider.filings`, `social.*` | 8 |
| [`rest/accuracy_and_stats.mjs`](rest/accuracy_and_stats.mjs) | `accuracy.*`, `gammapin.today`, `dealergamma.*`, a `stats.greeks.*` row, `status.overview` | 9 |

### MCP

| File | What it shows |
|---|---|
| [`mcp/list_tools.mjs`](mcp/list_tools.mjs) | The JSON-RPC handshake and `tools/list` over raw `fetch` |
| [`mcp/call_a_tool.mjs`](mcp/call_a_tool.mjs) | `tools/call`, `structuredContent`, and a clean `-32001` refusal |

See [`mcp/README.md`](mcp/README.md) for the endpoint's ground rules — the most important
being that it always answers HTTP 200, so `res.ok` is not the success test.

## npm scripts

`package.json` maps one script per example, so either form works:

```bash
node rest/market.mjs SPY      # direct — takes arguments
npm run market                # via npm
```

| Script | Runs |
|---|---|
| `npm run quickstart` | `quickstart.mjs` |
| `npm run auth` | `auth_and_errors.mjs` |
| `npm run pagination` | `pagination.mjs` |
| `npm run gex` · `greeks` · `valuation` · `market` · `levels` · `research` · `calendar` · `accuracy` | the matching `rest/*.mjs` |
| `npm run mcp:tools` · `npm run mcp:call` | the two `mcp/*.mjs` files |

## Environment

Two variables are read, and nothing else.

| Variable | Meaning |
|---|---|
| `VOLSTRATA_API_KEY` | Optional. Sent as `Authorization: Bearer <key>` when present. Never write a key into source — see [`../../.env.example`](../../.env.example) |
| `VOLSTRATA_BASE_URL` | Optional. Defaults to `https://volstrata.com`, the canonical host |

```bash
export VOLSTRATA_API_KEY="gex_key_v1_XXXXXXXX"     # macOS / Linux
$env:VOLSTRATA_API_KEY = "gex_key_v1_XXXXXXXX"     # Windows PowerShell
```

That placeholder is deliberately fake. Get a real one at
[volstrata.com/api-keys](https://volstrata.com/api-keys).

## Conventions these files follow

- **An explicit `User-Agent` on every request.** A CDN sits in front of the API and
  refuses some default agents before the request reaches it; that refusal is not JSON and
  is not an API error, however much it looks like one. `lib/volstrata.mjs` sets one.
- **Status first, body second.** `res.ok` is checked before anything is parsed. A refusal
  has a completely different body shape, so branching on a field like `ok` reads a field
  that is not there. The exception is MCP, which answers 200 for everything — there the
  JSON-RPC `error` member is the test.
- **Refusals are answers.** A capability above your plan floor prints the plan it needs
  and the run continues. Nothing here crashes because you do not have a key.
- **Bounded requests.** No unbounded loops, no polling, no concurrency. Every pagination
  loop has a page bound, and `withBackoff` retries only 429 and 5xx, honouring
  `Retry-After`, at most four attempts.

### About the rate limit

These run against live production. The budget is per **owner**, not per key, so a second
key does not raise the ceiling; anonymous callers get the smallest one. Running several
of the longer files back to back can meet it — when that happens the examples read
`Retry-After` and wait rather than failing, so the run is slow, not broken. To be
gentler, raise `PACE_MS` in [`lib/volstrata.mjs`](lib/volstrata.mjs): it is the pause
between calls inside one file.

## Where to look things up

- [API overview](https://volstrata.com/docs/api-overview) — the surface, in prose.
- [Authentication](https://volstrata.com/docs/api-auth) and [API keys](https://volstrata.com/docs/api-keys).
- [Errors](https://volstrata.com/docs/api-errors) — the problem+json envelope and its codes.
- [Rate limits](https://volstrata.com/docs/api-rate-limits).
- [Capability catalog](https://volstrata.com/docs/api-catalog) — every published capability and its plan floor.
- [`docs/reference/`](../../docs/reference/) in this repository — the generated, exhaustive endpoint and tool listings.

## Terms and disclaimer

The MIT licence covers the code and documentation in this repository only. Access to
the VolStrata API and any use of what it returns is governed by the Terms of Service
at <https://volstrata.com/legal/terms>. Nothing here, and nothing the API returns, is
investment, financial or trading advice; published accuracy scores are the project's
own automated grading of its own prior output and are not indicative of future
results. See <https://volstrata.com/legal/disclaimer>.

---

Copyright 2026 Volstrata.com - https://volstrata.com
