# MCP client configuration

How to point an MCP client at the VolStrata endpoint, and what to do when your client
cannot reach it. Protocol details are in [MCP.md](./MCP.md).

Product site: <https://volstrata.com> · Connect page: <https://volstrata.com/mcp>

---

## The config block

This is the server entry the site itself publishes:

```json
{
  "mcpServers": {
    "volstrata": {
      "url": "https://volstrata.com/api/v1/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

Replace `YOUR_API_KEY` with a key from <https://volstrata.com/api-keys>. Never commit a
real key — every file in this repo uses the literal string `YOUR_API_KEY`.

To use only the public capabilities, drop the `headers` object entirely. Anonymous callers
get the Free tool set (67 tools) with no credential at all, which is enough to try the
server before creating a key.

Copy-ready files carrying exactly this entry:

- [`examples/mcp/claude_desktop_config.json`](../examples/mcp/claude_desktop_config.json)
- [`examples/mcp/mcp.json.example`](../examples/mcp/mcp.json.example) — the generic project-level form
- [`examples/mcp/vscode_mcp.json`](../examples/mcp/vscode_mcp.json)

---

## Read this before you paste it anywhere

**This is a remote HTTP MCP server.** It is not a local process a client launches with a
`command` and `args`; it is a URL that answers JSON-RPC over HTTP POST.

That matters because:

1. **Support for remote HTTP servers varies by client and by version.** Some MCP clients
   only launch local subprocess servers. Some support remote servers but only through a
   local bridge or proxy. Some support them natively. There is no single answer, and the
   answer changes between releases of the same client.
2. **The config file location varies by client and operating system.** The file names in
   `examples/mcp/` follow common conventions, but they are templates for the *content* of
   a server entry — not a claim about where your client reads its config from.
3. **The top-level key name varies too.** `mcpServers` is the most widely used spelling
   and is what the site publishes; some clients read `servers` instead, and some nest the
   whole object under an application-specific key.

**So: get the file path and the key name from your own client's documentation, then paste
the inner `"volstrata": { ... }` entry into it.** This repo does not claim that any named
client is verified working against this endpoint — that is a moving target we would be
telling you wrong as often as right.

---

## The fallback that always works

If your client does not support remote HTTP MCP servers, or you cannot get its config to
take, the protocol itself is still fully reachable. It is JSON-RPC 2.0 over an ordinary
HTTP POST, so **anything that can POST JSON can drive it** — a shell script, a notebook, a
serverless function, your own agent loop.

- [`examples/mcp/requests/`](../examples/mcp/requests/) — five ready-to-POST JSON-RPC
  bodies (`initialize`, `tools/list`, `tools/call`, `resources/list`, `prompts/list`)
- [`examples/curl/mcp.sh`](../examples/curl/mcp.sh) — the same calls from a shell
- [`examples/python/mcp/`](../examples/python/mcp/) — the same calls from Python, with no
  MCP client library required

A minimal call, with no key, no client, and no dependencies:

```bash
curl -sS https://volstrata.com/api/v1/mcp \
  -H "Content-Type: application/json" \
  -H "User-Agent: volstrata-examples/1.0" \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

Always send an explicit `User-Agent`. The edge in front of the API refuses some default
agent strings — notably the Python standard library's `Python-urllib/*`, which gets a
plain-text `403` that never reaches the API at all. A non-JSON refusal means the request
was stopped before the endpoint saw it.

---

## Checking that it works

Two calls tell you everything:

1. `initialize` — a `result` containing `serverInfo.title` of `"VolStrata"` means the
   transport is fine.
2. `tools/list` — count the tools. 67 means you are anonymous; a larger number means your
   key was accepted and its plan is being applied. If you sent a key and still see 67,
   the header did not arrive — check the spelling of `Authorization` and that the value
   begins with `Bearer `.

Remember that every response is HTTP 200, including refusals. A client that only checks
the status code will report success on an error; check for the `error` member.

---

## Related

- [MCP.md](./MCP.md) — protocol, tools, resources, prompts, error codes
- [`examples/mcp/README.md`](../examples/mcp/README.md) — how to use the request bodies
- <https://volstrata.com/mcp> — the connect page
- <https://volstrata.com/docs/api-keys> — creating and storing a key

Copyright 2026 Volstrata.com - https://volstrata.com
