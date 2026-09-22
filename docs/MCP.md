# MCP — Model Context Protocol

VolStrata exposes its public API as an MCP server so an LLM agent can call the same
capabilities a REST client calls. This page documents the wire protocol. For client
configuration files see [MCP_CLIENTS.md](./MCP_CLIENTS.md); for ready-to-POST request
bodies see [`examples/mcp/`](../examples/mcp/).

Product site: <https://volstrata.com> · Connect page: <https://volstrata.com/mcp>

---

## Endpoint

```
POST https://api.volstrata.com/api/v1/mcp
Content-Type: application/json
```

- **JSON-RPC 2.0**, POST only.
- The endpoint always answers **HTTP 200** with a well-formed JSON-RPC envelope. Failures
  ride in the `error` member of that envelope — the endpoint does not emit 5xx status
  codes, so check `error`, not the HTTP status.
- `/api/v1` is the only live API surface. An older `v2` alias is retired and nothing is
  served under it, so a client pointed there gets a plain `404`, not a JSON-RPC envelope.

This endpoint is the transport the server answers on.

---

## Authentication

Same credential as the REST API: an API key presented as a bearer token.

```
Authorization: Bearer YOUR_API_KEY
```

Public (Free-tier) tools work with **no key at all**, so `initialize`, `tools/list` and a
call to a Free tool such as `gex.levels` all succeed anonymously. A key raises the set of
tools you can see and call, and raises your rate limit. Rate limits are applied per owner
rather than per key.

- Auth reference: <https://volstrata.com/docs/api-auth>
- Key management: <https://volstrata.com/api-keys>

---

## Handshake

`initialize` negotiates the protocol version.

Supported versions, newest first:

| Version | Notes |
|---|---|
| `2025-11-25` | Latest |
| `2025-06-18` | |
| `2025-03-26` | |
| `2024-11-05` | Returned when the client requests no version at all |

The server echoes back the version the client requested when that version is supported;
otherwise it offers its latest. A client that sends no `protocolVersion` receives
`2024-11-05`.

Request — [`examples/mcp/requests/initialize.json`](../examples/mcp/requests/initialize.json):

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "clientInfo": { "name": "volstrata-examples", "version": "1.0.0" }
  }
}
```

Response (abridged — `serverInfo` carries more members than are shown here):

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-11-25",
    "capabilities": {
      "tools": { "listChanged": true },
      "resources": { "listChanged": true, "subscribe": false },
      "prompts": { "listChanged": true },
      "completions": {}
    },
    "serverInfo": { "title": "VolStrata", "version": "2026-09-09" }
  }
}
```

`serverInfo.title` is `"VolStrata"` — that is the name to display in a client UI.
`serverInfo.version` (`"2026-09-09"`) matches the API version stamped on REST responses.

Resource subscriptions are not offered (`resources.subscribe` is `false`), so poll
`resources/read` rather than waiting for change notifications.

---

## Methods answered

```
initialize                 notifications/initialized   ping
tools/list                 tools/call
resources/list             resources/templates/list    resources/read
prompts/list               prompts/get
completion/complete
```

Anything else returns `-32601`.

---

## Tools

There is **one tool per public capability, and the tool name is the dotted capability
name**. The REST capability `gex.levels` — `GET /api/v1/gex/levels` — is the MCP tool
`gex.levels`, taking the same parameters. Nothing is renamed or re-shaped in between, so
the REST reference and the tool list describe the same surface.

What `tools/list` returns depends on the caller's plan:

| Caller | Tools returned |
|---|---|
| Anonymous (no key) | **67** — 3 meta-tools + 64 Free capability tools |
| Fully entitled | **177** — 3 meta-tools + 174 capability tools |

A tool above the caller's plan floor is **both hidden from `tools/list` and refused by
`tools/call`**. Hiding it is not the only enforcement; the gate runs again on every call.

### The three meta-tools

These are always present, at every tier, and are not projections of a REST capability:

| Tool | Arguments | Purpose |
|---|---|---|
| `catalog.search` | query terms | Find a capability by name or description |
| `capability.call` | `{ "name": "...", "arguments": { ... } }` | Universal dispatcher — invoke any capability by name |
| `docs.search` | query terms | Look up a metric definition |

**Prefer these three over registering the full tool list.** Handing a model 170+ tool
schemas up front consumes a large share of the context window and measurably degrades
tool selection — the model has to choose among near-identical options before it knows
what it is looking for. The `catalog.search` → `capability.call` pair gives an agent the
whole surface behind two schemas: search for the capability, then dispatch it.
`capability.call` re-runs the same plan gate as a direct call, so it is not a way around
entitlements.

### Toolset selector

Narrow the projection with a `toolset` selector, supplied either as a query string on the
endpoint URL or as a `params.toolset` member on `tools/list`:

| Selector | Result |
|---|---|
| *(none)* | Default — the full tier-scoped projection |
| `?toolset=lean` | **10 tools**: `catalog.search`, `capability.call`, `docs.search`, `market.status`, `docs.metrics`, `research.metrics`, `status.overview`, `symbol.search`, `meta.capabilities`, `meta.access` |
| `?toolset=gex,levels` | Only tools in the named domains (this pair returns 15) |

```
POST https://api.volstrata.com/api/v1/mcp?toolset=lean
```

`lean` is the recommended starting point for an agent: three meta-tools plus a handful of
cheap orientation calls, with the rest of the surface still reachable through
`capability.call`.

### Tool object shape

Every entry in `tools/list` carries:

| Field | Contents |
|---|---|
| `name` | Dotted capability name, e.g. `gex.levels` |
| `title` | Human-readable label |
| `description` | What the capability returns |
| `inputSchema` | JSON Schema for the arguments, including `default` values and `enum` members wherever a parameter is constrained |
| `outputSchema` | JSON Schema for the result |
| `annotations` | `readOnlyHint`, `idempotentHint`, `destructiveHint`, `openWorldHint`, `title` |
| `_meta` | `method`, `path`, `policy_key`, `tier`, `tier_name` — on capability tools only |

`_meta` is the one field that is not on every entry: the three meta-tools are served by the
MCP endpoint itself rather than projected from a REST route, so they carry no `_meta` at
all. Its absence is how you tell the two kinds apart.
`_meta.method` and `_meta.path` name the REST operation the tool wraps, so a tool listing
can be cross-referenced against `openapi.json` directly. `_meta.tier` is the plan slug and
`_meta.tier_name` the customer-facing plan name — show `tier_name` to a human.
`_meta.policy_key` is the same value the OpenAPI document publishes as `x-policy-key`.

### tools/call

Request — [`examples/mcp/requests/tools_call.json`](../examples/mcp/requests/tools_call.json):

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "gex.levels",
    "arguments": { "ticker": "SPX" }
  }
}
```

Result shape (values elided — the real payload is the capability's own JSON body):

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      { "type": "text", "text": "{\"ok\": true, \"ticker\": \"SPX\", \"levels\": {}}" }
    ],
    "isError": false,
    "structuredContent": { "ok": true, "ticker": "SPX", "levels": {} }
  }
}
```

`content[0].text` is the same object pretty-printed as a JSON string, for clients that
only render text. **Read `structuredContent`** when you want the parsed object — do not
re-parse the text block.

---

## Errors

Errors arrive as a JSON-RPC `error` member on an HTTP 200 response.

| Code | Meaning |
|---:|---|
| `-32700` | Parse error — the body was not valid JSON |
| `-32600` | Invalid request — not a well-formed JSON-RPC object |
| `-32601` | Method not found |
| `-32602` | Invalid params |
| `-32603` | Internal error |
| `-32001` | Access denied — the tool is above the caller's plan |
| `-32002` | Resource not found |

A plan refusal is the one an anonymous client hits most. Calling `gex.snapshot` (an Edge
capability) without a key returns:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "error": {
    "code": -32001,
    "message": "'gex.snapshot' requires the Edge plan.",
    "data": {
      "current_tier": "free",
      "required_plan": "edge",
      "required_plan_name": "Edge",
      "tool": "gex.snapshot"
    }
  }
}
```

The message names the tool and the required plan in a form that can be surfaced to a user
as-is. Handle `-32001` explicitly: it is a normal, expected outcome for a client whose key
does not reach a given tool, not a bug.

Related: <https://volstrata.com/docs/api-errors>

---

## Resources

Five resources are published:

| URI | Contents |
|---|---|
| `volstrata://manifest` | The server's own capability manifest |
| `volstrata://glossary` | Metric glossary |
| `volstrata://levels/definitions` | Definitions of the published level types |
| `volstrata://plans` | Plan tiers and what each includes |
| `volstrata://forecast/scoreboard` | Forecast scoreboard |

Two resource templates:

| Template | Notes |
|---|---|
| `volstrata://glossary/{metric}` | One glossary entry |
| `volstrata://snapshot/{ticker}` | Gated the same way as the `gex.snapshot` tool |

List them with `resources/list`, list the templates with `resources/templates/list`, and
fetch one with `resources/read`. Templates are gated on read exactly as the equivalent
tool is, so `volstrata://snapshot/{ticker}` returns a plan refusal for a caller below the
floor.

---

## Prompts

Nine prompts are published:

```
morning_gamma_brief
dealer_positioning_explainer
squeeze_scan_index_complex
valuation_deep_dive
higher_order_greek_map
flow_and_positioning_reconcile
earnings_setup
congress_and_insider_watch
explain_todays_dealer_positioning
```

`prompts/list` returns each one's declared arguments alongside its name; call
`prompts/get` with a name and arguments to retrieve the filled-in prompt. Read the
argument set off the live `prompts/list` response rather than hard-coding it, since
prompts can change independently of the API version.

---

## Connecting a client

The client-side configuration block and the caveats that come with it are in
[MCP_CLIENTS.md](./MCP_CLIENTS.md). Ready-to-POST JSON-RPC bodies, usable from curl or any
HTTP client, are in [`examples/mcp/requests/`](../examples/mcp/requests/).

The human-facing connect page is <https://volstrata.com/mcp> — that is an HTML page, not
the RPC endpoint.

---

## Related

- [MCP_CLIENTS.md](./MCP_CLIENTS.md) — client configuration files
- [`examples/mcp/`](../examples/mcp/) — request bodies and config templates
- <https://volstrata.com/docs/api-auth> — credentials and how they are presented
- <https://volstrata.com/docs/api-catalog> — the full capability catalog
- <https://volstrata.com/docs/api-rate-limits> — per-owner rate limits
- <https://volstrata.com/docs/api-errors> — the REST error envelope

Copyright 2026 Volstrata.com - https://volstrata.com
