<!-- Copyright 2026 Volstrata.com - https://volstrata.com -->

# curl examples

Shell scripts that call the VolStrata public API at <https://volstrata.com> with nothing
but `curl`. They are the ground truth the Python and JavaScript examples are checked
against: same capabilities, same order, same behaviour. Where two examples disagree, the
one in this directory is correct.

Start here:

```sh
sh examples/curl/quickstart.sh
```

That makes one request, needs no account and no API key, and prints live data.

## Requirements

| | |
|---|---|
| `sh` | POSIX shell. macOS, Linux, WSL, and Git Bash on Windows all work. No bash-only syntax is used. |
| `curl` | Any version. `--fail-with-body` (curl 7.76+) is used when present and worked around when not. |
| `jq` | **Optional.** Every script runs without it and prints raw response bodies instead of formatted summaries. Install it from <https://jqlang.github.io/jq/> for nicer output. |

Run the scripts from the repository root, as shown above, or from anywhere — each one
resolves its own directory to find `_common.sh`.

## Environment variables

These two are the only environment variables this repository reads. Both are optional.

| Variable | Default | What it does |
|---|---|---|
| `VOLSTRATA_API_KEY` | unset | When set, every request carries `Authorization: Bearer <key>`. When unset, requests go out anonymously — a fully supported mode: 67 of the 180 published operations sit at the Free plan floor and most of those answer without any credential. |
| `VOLSTRATA_API_BASE` | `https://api.volstrata.com` | The host to call. Override only if you have been told to. |

```sh
export VOLSTRATA_API_KEY=YOUR_API_KEY    # https://volstrata.com/api-keys
sh examples/curl/gex.sh
```

Never write a key into a file in this repository. Nothing here reads a key from disk, and
no script prints any part of one.

## The scripts

| Script | What it teaches | Requests |
|---|---|---:|
| [`quickstart.sh`](quickstart.sh) | One Free call, no key, real output. | 1 |
| [`auth_and_errors.sh`](auth_and_errors.sh) | Both ways to present a key, an anonymous call succeeding, a gated one refusing, a 404, and the rate-limit headers. | 4–5 |
| [`pagination.sh`](pagination.sh) | The shared `?limit=`/`?cursor=` model, following `next_cursor` in a bounded loop. | 1–4 |
| [`gex.sh`](gex.sh) | The `gex` domain: levels, named levels, metrics, gamma flip, max pain, bars, and one Edge-floor call refusing. | 7 |
| [`greeks.sh`](greeks.sh) | Gamma, implied vol, open interest and volume; then two Pro-floor calls degrading cleanly. | 6 |
| [`valuation.sh`](valuation.sh) | Universe, company and fundamentals reads, plus the two Pro-floor `POST` capabilities — the JSON-body pattern. | 5 |
| [`market.sh`](market.sh) | Session status, overview, snapshot, candles, rotations and the two symbol lookups; the freshness and delivery contracts. | 7 |
| [`levels.sh`](levels.sh) | Day and week level sets, their report forms, per-level detail, and the TradingView export — the one non-JSON response. | 6 |
| [`research_and_docs.sh`](research_and_docs.sh) | The metric glossary, coverage, the universe and the parameterised research query; reading one response to build the next request. | 6 |
| [`calendar_news_social.sh`](calendar_news_social.sh) | The cursor-paged event feeds: calendar, news, social and insider filings. These ask for a credential — any key will do — so without one the script demonstrates the refusal twice and stops. | 2–7 |
| [`accuracy_and_stats.sh`](accuracy_and_stats.sh) | The published scorecards and statistics, plus a Pro-floor forecast read refusing. | 7 |
| [`mcp.sh`](mcp.sh) | The MCP endpoint over raw JSON-RPC 2.0: `initialize`, `tools/list`, `tools/call`, and a gated tool returning `-32001`. | 6 |
| [`_common.sh`](_common.sh) | Sourced by all of the above: base URL, the mandatory `User-Agent`, optional bearer auth, output helpers. Not run directly. | — |

Each of the eight domain scripts takes an optional ticker as its first argument,
defaulting to `SPX` (`valuation.sh` defaults to `AAPL`, since that domain is about
companies):

```sh
sh examples/curl/gex.sh SPY
```

## Rate limits, and why the request counts are in that table

These scripts call live production. The ceiling is **10 requests per minute for an
anonymous caller**, enforced per owner rather than per key, so:

- run one script at a time rather than piping several together;
- if you get a `429`, read the `ratelimit` header, wait for the reset, and try again;
- nothing here loops without a bound, polls, or issues requests in parallel.

Each script prints how many requests it spent when it finishes.

## What a refusal means when you run these anonymously

Running the whole set without a key is expected to produce some refusals, and they are
not all the same thing:

| You see | It means |
|---|---|
| `401 auth_required` | No credential was presented. Either the capability sits above the Free floor, or it is a data endpoint that asks for any valid key even at the Free floor. The `detail` says which. |
| `402`/`403` with `required_plan_name` | The credential was accepted; the plan floor was not met. |
| `404 route_not_found` | Nothing is published at that path — a typo or an invented name. |
| `404 not_found` | The path is right and the data is not being served at that moment. Try later. |
| `429` | Rate limited. Read `ratelimit` and `Retry-After`, wait, retry. |

A Free plan floor is a statement about plans, not a promise that no credential is needed.
Read the `code` member; do not infer entitlement from the tier alone.

## Conventions every script follows

- **An explicit `User-Agent` on every request.** This is not politeness. The CDN in front
  of the API refuses some well-known default agents at the edge, with a plain-text body,
  before the API ever sees the request — so a non-JSON refusal means the request never
  arrived. Every real API refusal is `application/problem+json`.
- **`curl -sS --fail-with-body`.** A 4xx exits non-zero *and* still gives you the problem
  document, so a script can report what the refusal actually said.
- **Status first, body second.** A body is only worth reading once the status is known.
- **Gated calls are included on purpose.** Several scripts call a capability above the
  Free floor, print the refusal, explain it and carry on. Every script exits `0`; a
  demonstrated refusal is a successful run.

## Related

- [Examples index](../README.md) — the Python and JavaScript sets.
- [API examples](https://volstrata.com/docs/api-examples) — the same ground, in prose.
- [Capability catalog](https://volstrata.com/docs/api-catalog) — every published
  capability and its plan floor.
- [Errors](https://volstrata.com/docs/api-errors) — the RFC 9457 envelope in full.

## Terms and disclaimer

The MIT licence covers the code and documentation in this repository only. Access to
the VolStrata API and any use of what it returns is governed by the Terms of Service
at <https://volstrata.com/legal/terms>. Nothing here, and nothing the API returns, is
investment, financial or trading advice; published accuracy scores are the project's
own automated grading of its own prior output and are not indicative of future
results. See <https://volstrata.com/legal/disclaimer>.

---

Copyright 2026 Volstrata.com - https://volstrata.com
