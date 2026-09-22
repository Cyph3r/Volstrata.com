# Examples

Runnable examples for the VolStrata public API at https://volstrata.com. Each directory
stands on its own: start with its `README.md`, run the quickstart, then read the domain
files.

Every quickstart calls a Free capability and needs no API key. Set `VOLSTRATA_API_KEY`
only when you reach an example that says it needs one — see [`../.env.example`](../.env.example).

| Directory | What it covers | Priority |
|---|---|---|
| [`curl/`](curl/) | Shell scripts, one per domain group, using nothing but `curl`. The reference implementation the other languages are checked against. | 2 |
| [`python/`](python/) | Python examples using `requests` only: quickstart, authentication and RFC 9457 error handling, and one commented file per domain group. | 1 |
| [`javascript/`](javascript/) | Node 18+ examples using the runtime's native `fetch`, with no runtime dependencies. | 3 |
| [`mcp/`](mcp/) | Raw JSON-RPC 2.0 against `POST https://api.volstrata.com/api/v1/mcp` — `initialize`, `tools/list`, `tools/call` — plus a drop-in client configuration block. | 4 |

Priority is the order these were built and the order to read them in. Python is first
because it is the largest audience for this API; curl is the foundation every other
language mirrors, so if two examples ever disagree, the curl one is correct.

## Conventions every example follows

- An explicit `User-Agent` header. Some default agents are refused at the CDN edge before
  the request reaches the API, returning a plain-text 403 that is not JSON.
- Credentials read from the environment (`VOLSTRATA_API_KEY`, `VOLSTRATA_API_BASE`),
  never hardcoded.
- Real error handling: refusals arrive as `application/problem+json` and are parsed, not
  dumped. A call to a gated capability degrades with a message naming the required plan.
- Bounded request counts. The anonymous ceiling is 10 requests per minute and these run
  against live production, so there are no unbounded loops and no polling.

## Another language?

Go, Ruby, PHP, Rust and everything else are open. Open an issue or send a pull request —
[`CONTRIBUTING.md`](../CONTRIBUTING.md) has the layout to follow. Work from
[`../docs/reference/REST_ENDPOINTS.md`](../docs/reference/REST_ENDPOINTS.md): it is the
authoritative surface, generated from the public OpenAPI document, listing every
capability with its method, path and plan floor, so you do not need a maintainer to have
written your language first.

## Terms and disclaimer

The MIT licence covers the code and documentation in this repository only. Access to
the VolStrata API and any use of what it returns is governed by the Terms of Service
at <https://volstrata.com/legal/terms>. Nothing here, and nothing the API returns, is
investment, financial or trading advice; published accuracy scores are the project's
own automated grading of its own prior output and are not indicative of future
results. See <https://volstrata.com/legal/disclaimer>.

---

Copyright 2026 Volstrata.com - https://volstrata.com
