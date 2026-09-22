# Docs

Guides for the VolStrata public API at https://volstrata.com. Read them in this order the
first time; after that, use the table as an index.

| Page | What it covers |
|---|---|
| [`QUICKSTART.md`](QUICKSTART.md) | First call in under a minute, with no account and no key. Base URL, the required `User-Agent`, and what a successful response looks like. |
| [`AUTHENTICATION.md`](AUTHENTICATION.md) | How to present an API key — `Authorization: Bearer` or the query form — key handling, plan floors, and why rate limits are per owner rather than per key. |
| [`REST_API.md`](REST_API.md) | The REST surface as a whole: path shape, capability naming, shared response envelopes, and how to discover what your credential can reach at runtime. |
| [`ERRORS.md`](ERRORS.md) | The RFC 9457 `application/problem+json` envelope, the common refusal codes, the non-JSON edge 403 trap, and a retry-with-backoff pattern. |
| [`RATE_LIMITS.md`](RATE_LIMITS.md) | The per-minute ceiling by plan, the `ratelimit` and `x-ratelimit-*` response headers, and how to back off correctly on `Retry-After`. |
| [`PAGINATION.md`](PAGINATION.md) | The shared `limit` / `cursor` parameters, the `next_cursor` field, opaque-cursor rules, and how to write a bounded paging loop. |
| [`FRESHNESS_AND_DELIVERY.md`](FRESHNESS_AND_DELIVERY.md) | The `Freshness` and `Delivery` blocks — `as_of`, `age_seconds`, `live`, `stale`, and the `live` vs `delayed` delivery mode with its `delay_seconds` and `reason`. |
| [`MCP.md`](MCP.md) | The MCP endpoint: JSON-RPC 2.0 over `POST /api/v1/mcp`, protocol negotiation, the methods answered, tools, resources, prompts, and the toolset selector. |
| [`MCP_CLIENTS.md`](MCP_CLIENTS.md) | Connecting a real MCP client: the configuration block, where the key goes, and what an anonymous client sees versus an authenticated one. |
| [`reference/`](reference/) | Generated, exhaustive reference — the full endpoint table, the MCP tool list, and the public OpenAPI document as served, with its `servers` array pointed at the canonical API host. Never hand-edited; see [`../CONTRIBUTING.md`](../CONTRIBUTING.md). |

Runnable code for everything described here lives in [`../examples/`](../examples/).

## Terms and disclaimer

The MIT licence covers the code and documentation in this repository only. Access to
the VolStrata API and any use of what it returns is governed by the Terms of Service
at <https://volstrata.com/legal/terms>. Nothing here, and nothing the API returns, is
investment, financial or trading advice; published accuracy scores are the project's
own automated grading of its own prior output and are not indicative of future
results. See <https://volstrata.com/legal/disclaimer>.

---

Copyright 2026 Volstrata.com - https://volstrata.com
