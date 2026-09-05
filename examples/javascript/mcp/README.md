# MCP from Node

Two files, no dependencies. They speak [MCP](https://volstrata.com/mcp) to
[VolStrata](https://volstrata.com) as raw JSON-RPC 2.0 over `fetch`, which is the
lowest-common-denominator way to do it: no SDK to install, nothing to keep in step with a
protocol revision, and every byte on the wire visible in the file you are reading.

```bash
cd examples/javascript
node mcp/list_tools.mjs        # handshake + tools/list
node mcp/call_a_tool.mjs SPX   # tools/call, twice: one free tool, one gated
```

| File | What it does | Requests |
|---|---|---:|
| [`list_tools.mjs`](list_tools.mjs) | `initialize` → `notifications/initialized` → `tools/list`. Prints the count, the meta-tools, the busiest domains, and one tool's schema. | 3 |
| [`call_a_tool.mjs`](call_a_tool.mjs) | Handshake, then `tools/call` on `gex.levels`, then on `gex.snapshot` — which refuses, cleanly. | 4 |

## The endpoint

```
POST https://volstrata.com/api/v1/mcp
Content-Type: application/json
Authorization: Bearer <your key>     ← optional; anonymous callers get the free tools
```

POST only, one URL, JSON-RPC 2.0 in the body. Methods answered: `initialize`,
`notifications/initialized`, `ping`, `tools/list`, `tools/call`, `resources/list`,
`resources/templates/list`, `resources/read`, `prompts/list`, `prompts/get`,
`completion/complete`.

## Three things that catch people out

**1. HTTP 200 is not success.** The endpoint answers 200 with a well-formed JSON-RPC
envelope for everything it can parse. A failure rides in the `error` member of that 200,
so `res.ok` is the wrong test:

```js
const envelope = await res.json();
if (envelope.error) throw new McpRpcError(envelope.error);   // ← the real test
const result = envelope.result;
```

A non-2xx status means the request never reached the MCP layer at all — a wrong URL, a
proxy, an edge refusal.

**2. There are two failure channels.** The `error` member means the call was refused
(bad method, bad params, or `-32001` access denied). `result.isError: true` means the
call ran and the tool itself reported a problem, described in its text content. Handle
both.

| Code | Meaning |
|---:|---|
| `-32700` | Parse error |
| `-32600` | Invalid request |
| `-32601` | Method not found |
| `-32602` | Invalid params |
| `-32603` | Internal error |
| `-32001` | Access denied — carries `data: {current_tier, required_plan, required_plan_name, tool}` |
| `-32002` | Resource not found |

**3. The handshake has two halves.** `initialize` negotiates the protocol revision — the
server echoes back what it will actually speak, so read the reply instead of assuming
your requested version was accepted — and then the client sends
`notifications/initialized`, which has no `id` and gets no reply.

## Tools

Tool name **is** the dotted capability name, projected one to one from the public REST
catalog: `gex.levels` here is `/api/v1/gex/levels` there, with the same parameters. Each
tool carries `inputSchema` and `outputSchema` (JSON Schema, with defaults and enums where
a parameter is constrained) plus `annotations` — `readOnlyHint`, `idempotentHint`,
`destructiveHint`, `openWorldHint`.

Three meta-tools are always present whatever your plan:

| Tool | For |
|---|---|
| `catalog.search` | Find a capability by keyword, domain or plan tier without loading every tool |
| `capability.call` | Invoke any capability by name — the same plan check applies |
| `docs.search` | Look up what a metric means |

An anonymous caller sees **67** tools: those three plus the 64 free capability tools. A
fully entitled one sees 177. Tools above your floor are both hidden from `tools/list` and
refused by `tools/call`.

If the whole catalog is more than an agent's context should hold, narrow it:

```
POST https://volstrata.com/api/v1/mcp?toolset=lean          → 10 tools
POST https://volstrata.com/api/v1/mcp?toolset=gex,levels    → those domains only
```

`list_tools.mjs` takes the same selector as its first argument:

```bash
node mcp/list_tools.mjs lean
node mcp/list_tools.mjs gex,levels
```

## Beyond tools

The same endpoint serves resources (`volstrata://manifest`, `volstrata://glossary`,
`volstrata://levels/definitions`, `volstrata://plans`,
`volstrata://forecast/scoreboard`, plus two templates) and nine prompts, through
`resources/list`, `resources/read`, `prompts/list` and `prompts/get`. The `rpc()` helper
in either file already speaks them — change the method name.

## Connecting a client instead

To point an MCP client at this endpoint rather than writing your own loop:

```json
{
  "mcpServers": {
    "volstrata": {
      "url": "https://volstrata.com/api/v1/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    }
  }
}
```

Ready-made configuration files are in [`../../mcp/`](../../mcp/).

## Terms and disclaimer

The MIT licence covers the code and documentation in this repository only. Access to
the VolStrata API and any use of what it returns is governed by the Terms of Service
at <https://volstrata.com/legal/terms>. Nothing here, and nothing the API returns, is
investment, financial or trading advice; published accuracy scores are the project's
own automated grading of its own prior output and are not indicative of future
results. See <https://volstrata.com/legal/disclaimer>.

---

Copyright 2026 Volstrata.com - https://volstrata.com
