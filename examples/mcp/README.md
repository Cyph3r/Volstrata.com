# examples/mcp

Client configuration templates and ready-to-POST JSON-RPC bodies for the VolStrata MCP
endpoint.

- Endpoint: `POST https://api.volstrata.com/api/v1/mcp`
- Protocol reference: [`docs/MCP.md`](../../docs/MCP.md)
- Client setup and its caveats: [`docs/MCP_CLIENTS.md`](../../docs/MCP_CLIENTS.md)
- Product site: <https://volstrata.com>

---

## What is here

| File | What it is |
|---|---|
| `claude_desktop_config.json` | Server entry in the `mcpServers` form |
| `mcp.json.example` | The same entry, as a generic project-level `mcp.json` |
| `vscode_mcp.json` | The same entry, for an editor-level config file |
| `requests/initialize.json` | `initialize` — protocol handshake |
| `requests/tools_list.json` | `tools/list` — enumerate available tools |
| `requests/tools_call.json` | `tools/call` — invoke `gex.levels` for `SPX` |
| `requests/resources_list.json` | `resources/list` — enumerate resources |
| `requests/prompts_list.json` | `prompts/list` — enumerate prompts |

All three config files carry the same server entry with `Bearer YOUR_API_KEY`. Replace
that literal with a key from <https://volstrata.com/api-keys>, or delete the `headers`
object to run anonymously against the Free tool set.

The config file **location** and the top-level **key name** differ between MCP clients and
between versions of the same client — these files are templates for the content of the
server entry, not a claim about where your client stores its config. See
[`docs/MCP_CLIENTS.md`](../../docs/MCP_CLIENTS.md) before pasting one anywhere.

---

## Running the request bodies

Every file in `requests/` is a complete JSON-RPC 2.0 request. POST one as-is:

```bash
curl -sS https://api.volstrata.com/api/v1/mcp \
  -H "Content-Type: application/json" \
  -H "User-Agent: volstrata-examples/1.0" \
  --data @requests/tools_list.json
```

With a key, so gated tools appear:

```bash
curl -sS https://api.volstrata.com/api/v1/mcp \
  -H "Content-Type: application/json" \
  -H "User-Agent: volstrata-examples/1.0" \
  -H "Authorization: Bearer $VOLSTRATA_API_KEY" \
  --data @requests/tools_list.json
```

A smaller tool projection, via the `toolset` selector:

```bash
curl -sS "https://api.volstrata.com/api/v1/mcp?toolset=lean" \
  -H "Content-Type: application/json" \
  -H "User-Agent: volstrata-examples/1.0" \
  --data @requests/tools_list.json
```

Pretty-print with `jq` if you have it: append `| jq .`.

### Two things that will bite you

**Always set an explicit `User-Agent`.** The edge in front of the API refuses some default
agent strings — the Python standard library's `Python-urllib/*` gets a plain-text `403`
that never reaches the API. If a response is not JSON, the request was stopped before the
endpoint saw it.

**Every response is HTTP 200, including failures.** Errors ride in the JSON-RPC `error`
member. A script that only checks the exit status or the status code will treat a plan
refusal as a success. Check for `error` before reading `result`.

`requests/tools_call.json` calls `gex.levels`, a Free capability, so it returns real data
with no key. To see the refusal path instead, change `params.name` to `gex.snapshot` (an
Edge capability) and run it anonymously — the response is a `-32001` error whose message
names the required plan.

---

## The `_comment` field

JSON has no comment syntax, so each file here carries a `_comment` string holding the
copyright and a link. It is annotation only: the config files ignore unknown keys, and the
request bodies are still valid JSON-RPC with it present. If a strict client or validator
objects to it, delete that one line — nothing else depends on it.

---

## Related

- [`docs/MCP.md`](../../docs/MCP.md) — methods, tool shape, error codes, resources, prompts
- [`docs/MCP_CLIENTS.md`](../../docs/MCP_CLIENTS.md) — client configuration
- [`examples/curl/mcp.sh`](../curl/mcp.sh) — the same calls as a shell script
- [`examples/python/mcp/`](../python/mcp/) — the same calls from Python
- <https://volstrata.com/mcp> — the connect page

## Terms and disclaimer

The MIT licence covers the code and documentation in this repository only. Access to
the VolStrata API and any use of what it returns is governed by the Terms of Service
at <https://volstrata.com/legal/terms>. Nothing here, and nothing the API returns, is
investment, financial or trading advice; published accuracy scores are the project's
own automated grading of its own prior output and are not indicative of future
results. See <https://volstrata.com/legal/disclaimer>.

---

Copyright 2026 Volstrata.com - https://volstrata.com
