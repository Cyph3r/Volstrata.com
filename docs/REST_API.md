# The REST API — how the surface is organised

A narrative map of the VolStrata REST API: how operations are named, how plan floors are
published, and how to discover the whole surface at runtime instead of hard-coding it.
API home: <https://volstrata.com>

The exhaustive, generated operation table lives in
[`reference/REST_ENDPOINTS.md`](./reference/REST_ENDPOINTS.md). This page does not repeat it.

---

## The shape of it

| | |
|---|---|
| Published operations | **180**, each at its own unique path |
| HTTP methods | **173 GET**, **7 POST** |
| Domains (OpenAPI tags) | **56** |
| Operations at the Free plan floor | **67** |
| Base path | `/api/v1` |
| Contract version, on every response | `x-gex-api-version: 2026-09-01` |

Read operations are GET with query parameters. The seven POST operations take a JSON body
because their input is a document rather than a handful of scalars: `voloi.combined`,
`render.card` and `render.chart` at the Edge floor, `render.animation` at Desk,
`valuation.value` and `valuation.screen` at Pro, and `meta.mcp` — the MCP transport itself,
which is free and is documented in [MCP.md](./MCP.md). Every operation's method and floor is
in the generated reference; this page does not list them.

---

## Capability naming — one name, three places

Every operation has a single dotted **capability name** of the form `domain.name`, and that
name is the same string in all three places you will meet it:

```
capability name    gex.levels
OpenAPI operationId gex.levels
URL path            https://volstrata.com/api/v1/gex/levels
```

The rule is mechanical: **the dots become slashes** under `/api/v1`. So `market.status` is
`GET /api/v1/market/status`, and `valuation.screen` is `POST /api/v1/valuation/screen`. A few
names carry a third segment; they follow the same rule, and the generated reference carries
the exact path for every operation if you would rather look it up than derive it.

This matters more than a naming convention usually does, because the same dotted name is also
the tool name over MCP. One identifier addresses the same capability whether you reach it by
URL or by JSON-RPC, which means a script and an agent can be documented, logged and debugged
against a single vocabulary.

---

## Domains

The 56 domains are the OpenAPI `tags` array, and they are how the surface is grouped
everywhere — in the spec, in the generated reference, and in the example files. The largest:

| Domain | Operations |
|---|---:|
| `gex` | 16 |
| `valuation` | 15 |
| `greeks` | 11 |
| `market` | 8 |
| `crypto` | 8 |
| `stats` | 8 |
| `levels` | 7 |
| `vol` | 6 |
| `accuracy` | 6 |
| `ai` | 5 |
| `social` | 5 |

The remaining domains are smaller — several hold a single operation. Read the full list from
the spec's `tags` array rather than from any prose, including this page's.

---

## How plan floors are published

Every operation carries its plan floor in the OpenAPI document as three extension fields:

| Field | What it is | Use it for |
|---|---|---|
| `x-plan-tier` | The internal tier **slug** (`free`, `edge`, `pro`, `ultra`, `desk`) | Grouping, sorting, machine comparison — but see the warning below |
| `x-plan-tier-name` | The **customer-facing plan name** (`Free`, `Edge`, `Pro`, `Ultra`, `Desk`) | Anything a human reads |
| `x-policy-key` | The identifier of the gate the operation sits behind | Correlating operations that are gated together |

> **Render the name, not the slug.** `x-plan-tier-name` is the string the product calls the
> plan, and it is the one that is safe to print in an error message, a README, or a UI.
> Slugs are internal identifiers: they have been renamed before, and a hard-coded slug
> comparison is a bug waiting for the next rename. If you must branch in code, branch on the
> presence of a floor and show the name; do not build a slug ordering of your own.

`x-policy-key` is descriptive metadata that ships in the public spec. It tells you which
operations share a gate. It is not a setting, and there is nothing on your side to configure
with it.

Across the 180 operations the floors distribute as **Free 67 · Edge 37 · Pro 59 · Ultra 8 ·
Desk 9**. A caller below an operation's floor gets a `402` naming the plan required — see
[ERRORS.md](./ERRORS.md).

---

## Runtime discovery — do not hard-code the catalog

Two public, free, unauthenticated sources describe the whole surface. Prefer either of them
to a list you maintain by hand.

### `GET /api/v1/meta/capabilities`

The machine-readable capability listing. It is cursor-paged (see
[PAGINATION.md](./PAGINATION.md)), and each row describes one operation:

```jsonc
// Illustrative row shape.
{
  "name": "gex.levels",
  "method": "GET",
  "path": "/api/v1/gex/levels",
  "params": ["…"],
  "policy_key": "…",
  "tier": "free",
  "tier_name": "Free"
}
```

`tier` and `tier_name` are the same slug-and-name pair as the spec's `x-plan-tier` /
`x-plan-tier-name`, and the same rule applies: display `tier_name`.

Read the envelope's `total` for the row count rather than assuming one — the catalog grows.

### `GET /api/v1/meta/access`

Reports what the *calling credential* can reach. Anonymous callers get the anonymous answer,
so it is also useful as a "is my key being seen correctly?" check when a 402 surprises you.

### `GET https://volstrata.com/api/openapi.json`

The full OpenAPI 3.1 document, public and unauthenticated. Its `info.version` is the same
dated contract version the `x-gex-api-version` header reports, `info["x-base"]` is `/api/v1`,
and `servers[0].url` is `https://volstrata.com`. It is the source the generated reference in
this repo is built from, and the right input if you want to generate a client of your own.

A checked-in copy lives under [`reference/`](./reference/), regenerated and diffed by CI so it
cannot silently drift from the live document.

---

## Contracts that are the same everywhere

Four response contracts are uniform across the whole surface. Learn each once rather than
per-endpoint:

| Contract | What it looks like | Where |
|---|---|---|
| Success envelope | `{ "ok": true, … }` — payload fields alongside `ok` | this page |
| Paged envelope | adds `next_cursor`, `limit`, `total` | [PAGINATION.md](./PAGINATION.md) |
| Freshness / delivery | additive `freshness` and `delivery` blocks | [FRESHNESS_AND_DELIVERY.md](./FRESHNESS_AND_DELIVERY.md) |
| Refusals | RFC 9457 `application/problem+json` | [ERRORS.md](./ERRORS.md) |

Rate-limit headers ride on every response, success or refusal
([RATE_LIMITS.md](./RATE_LIMITS.md)).

Fields describe *what* a value is — its name, type and units. What a metric means is defined
in the public glossary on the site; how it is produced is not part of the API contract and is
not documented in this repo.

---

## Where to go next

- Every operation, with method, path and plan floor:
  [`reference/REST_ENDPOINTS.md`](./reference/REST_ENDPOINTS.md)
- A first call in three steps: [QUICKSTART.md](./QUICKSTART.md)
- Credentials and plan floors: [AUTHENTICATION.md](./AUTHENTICATION.md)
- The same capabilities as agent tools: [MCP.md](./MCP.md)

---

## Related

- [API catalog](https://volstrata.com/docs/api-catalog) — the browsable operation catalog, grouped by domain.
- [Base URL and versioning](https://volstrata.com/docs/api-base-url) — the host, the base path, and how the dated contract version moves.

---

Copyright 2026 Volstrata.com - https://volstrata.com
