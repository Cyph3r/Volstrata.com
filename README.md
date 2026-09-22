<a href="https://volstrata.com"><img src="assets/volstrata-logo.svg" alt="VolStrata" height="40"></a>

Runnable examples for the VolStrata public REST API and MCP endpoint, in curl, Python and JavaScript.

[![verify](https://github.com/Cyph3r/Volstrata.com/actions/workflows/verify.yml/badge.svg)](https://github.com/Cyph3r/Volstrata.com/actions/workflows/verify.yml)
[![License MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![API version 2026-09-09](https://img.shields.io/badge/API%20version-2026--09--09-e0b23a)](https://api.volstrata.com/api/openapi.json)

## 30-second quickstart

No account, no key, no install. Paste this into a terminal:

```bash
curl -sS -H 'User-Agent: volstrata-examples/1.0' 'https://api.volstrata.com/api/v1/docs/metrics'
```

The response is JSON — the glossary of every metric the analytics surface reports.
Abridged; the live call returns all 14:

```json
{
  "ok": true,
  "count": 14,
  "docs": [
    {
      "metric": "call_wall",
      "title": "Call Wall (CW)",
      "short": "Strike carrying the largest positive dealer gamma — magnetic resistance."
    },
    {
      "metric": "charm",
      "title": "Charm Exposure",
      "short": "Dealer sensitivity of delta to the passage of time (delta decay)."
    }
  ]
}
```

**Ticker-scoped market data asks for a free account.** Operations that answer *about a
symbol* — `gex.levels`, `gex.snapshot`, `levels.day` and the rest — refuse an anonymous
caller with `401 account_required` and the message "Sign in to a free account to view
SPX", even though they sit at the Free plan floor. A free account and a key from
<https://volstrata.com/api-keys> is the whole requirement. Operations that answer about
the *surface itself* — the one above, `meta.capabilities`, `status.overview` — need
nothing at all.

Always send an explicit `User-Agent`. Some default agents — including the Python
standard library's `Python-urllib/*` — are refused at the CDN edge with a plain-text
403 that never reaches the API, which looks like an API error but is not one. Every
example in this repository sets one.

## API surface

| Fact | Value |
|---|---|
| REST base URL | `https://api.volstrata.com/api/v1` |
| REST operations | 180 across 56 domains — 173 `GET`, 7 `POST` |
| Operations at the Free plan floor | 67 — surface and reference operations answer with no credential; ticker-scoped market data asks for a free account (see the quickstart note above) |
| Machine-readable spec | [`GET /api/openapi.json`](https://api.volstrata.com/api/openapi.json) — OpenAPI 3.1, public, unauthenticated |
| API version header | `x-gex-api-version: 2026-09-09` on every response |
| MCP endpoint | `POST https://api.volstrata.com/api/v1/mcp` — JSON-RPC 2.0 |
| MCP tools | 67 to an anonymous caller, 177 to a fully entitled one |

That endpoint is the MCP transport to use; it needs no client library.

## Repo map

| Path | What is in it |
|---|---|
| [`docs/`](docs/) | Hand-written guides: quickstart, authentication, errors, rate limits, pagination, freshness, MCP. |
| [`docs/reference/`](docs/reference/) | Generated reference artifacts — the exhaustive endpoint and tool surface. Never hand-edited. |
| [`examples/curl/`](examples/curl/) | Shell scripts. The ground truth every other language mirrors. |
| [`examples/python/`](examples/python/) | Python examples using `requests` only. |
| [`examples/javascript/`](examples/javascript/) | Node 18+ examples using native `fetch`, zero runtime dependencies. |
| [`examples/mcp/`](examples/mcp/) | JSON-RPC calls against the MCP endpoint, plus client configuration. |
| [`scripts/`](scripts/) | The generator that keeps `docs/reference/` in sync, and the CI drift check. |

## Get an API key

Most examples here run with no key at all. A key is needed only for capabilities above
the Free floor. [Get an API key](https://volstrata.com/api-keys), then set
`VOLSTRATA_API_KEY` in your environment — see [`.env.example`](.env.example).

## Docs

- [API overview](https://volstrata.com/docs/api-overview) — what the API covers and how it is organised.
- [Authentication](https://volstrata.com/docs/api-auth) — credential families, headers, and the per-owner rate-limit model.
- [Capability catalog](https://volstrata.com/docs/api-catalog) — every published capability and its plan floor.

## Terms and data use

The MIT licence below covers the example code and documentation **in this repository**, and
nothing else. It does not grant any right to the API or to the data the API returns.

Access to the VolStrata API, and any use of what it returns, is governed by the Terms of
Service at <https://volstrata.com/legal/terms> and the Risk Disclaimer at
<https://volstrata.com/legal/disclaimer>. Calling the API constitutes acceptance of those
terms. They set out, among other things, the limits on redistributing market data, on
storing or accumulating it, and on using it to build or train a competing product — none of
which the MIT licence on this repository speaks to.

## Disclaimer

Nothing in this repository, and nothing returned by this API, is investment, financial or
trading advice. Analytics are model-derived estimates, not statements of fact. Published
accuracy scores are the project's own automated grading of its own prior output, are not
independently audited, and are not indicative of future results. Trading involves a
substantial risk of loss. See <https://volstrata.com/legal/disclaimer>.

## Licence

MIT — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

---

Copyright 2026 Volstrata.com - https://volstrata.com
