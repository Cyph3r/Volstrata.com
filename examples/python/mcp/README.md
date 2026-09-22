# Python MCP examples

Raw JSON-RPC 2.0 against the VolStrata MCP endpoint, using `requests` and nothing
else. No `mcp` SDK, no client library, no framework — just the wire protocol, so
these run wherever Python does and show you exactly what a client sends.

Endpoint: `POST https://api.volstrata.com/api/v1/mcp`
Connect page: <https://volstrata.com/mcp>
Protocol reference for this API: [`../../../docs/MCP.md`](../../../docs/MCP.md)
Client configuration: [`../../../docs/MCP_CLIENTS.md`](../../../docs/MCP_CLIENTS.md)

## Run them

```sh
python -m pip install -r ../requirements.txt

python mcp/list_tools.py            # handshake, then what your credential sees
python mcp/call_a_tool.py           # run one tool, then run a gated one
python mcp/agent_loop_meta_tools.py # the pattern to build an agent on
```

Each file also runs from inside this directory (`python list_tools.py`). They
import `volstrata_helpers` from the parent folder, which holds the JSON-RPC
plumbing: `mcp_session()`, `rpc()`, `mcp_initialize()` and `mcp_structured()`.

No key is required. `VOLSTRATA_API_KEY`, when set, is sent as
`Authorization: Bearer <key>` — the same credential as the REST API, and it
changes both what `tools/list` returns and what `tools/call` will run.

| File | What it demonstrates |
|---|---|
| [`list_tools.py`](list_tools.py) | `initialize` → `notifications/initialized` → `tools/list`, the negotiated protocol version, the tool object shape, and the `?toolset=` selector |
| [`call_a_tool.py`](call_a_tool.py) | `tools/call` on an open tool, reading `structuredContent`, then a gated tool and its `-32001` error |
| [`agent_loop_meta_tools.py`](agent_loop_meta_tools.py) | `catalog.search` → `capability.call` → `docs.search`: reaching the whole catalog through three tools instead of registering hundreds |

## Two things that will bite you

**Failures arrive in two different places.** Once a request is past the rate
limiter the endpoint answers HTTP 200 for everything, and a protocol failure
rides in the `error` member of the JSON-RPC envelope:

```json
{"jsonrpc": "2.0", "id": 4,
 "error": {"code": -32001,
           "message": "'<tool>' requires the <Plan> plan.",
           "data": {"current_tier": "...", "required_plan": "...",
                    "required_plan_name": "...", "tool": "<tool>"}}}
```

So `response.ok` is not a success test. Check the HTTP status *and* look for
`error` before you touch `result`. Transport-level refusals — rate limiting, for
instance — do come back as an HTTP status with an RFC 9457 problem body, which is
why `rpc()` in `volstrata_helpers` checks both.

**Set a User-Agent.** Some default agent strings are refused at the CDN before
the request reaches the API, and that refusal is plain text rather than JSON. If
you get a non-JSON body back from a JSON-RPC endpoint, this is almost always why.
`mcp_session()` sets one for you.

## A note on transports

These examples speak JSON-RPC over a single HTTP POST, which is the transport
this endpoint answers and the one a client should implement against.

## Related

- [`../../../docs/MCP.md`](../../../docs/MCP.md) — methods, tool shape, error codes, resources, prompts
- [`../../../docs/MCP_CLIENTS.md`](../../../docs/MCP_CLIENTS.md) — dropping the endpoint into an MCP client
- [`../../mcp/`](../../mcp/) — the same calls as raw JSON request bodies, for `curl`
- [`../README.md`](../README.md) — the Python examples, REST included
- <https://volstrata.com/mcp> — the connect page
- <https://volstrata.com/docs/api-auth> — the credential the header carries

## Terms and disclaimer

The MIT licence covers the code and documentation in this repository only. Access to
the VolStrata API and any use of what it returns is governed by the Terms of Service
at <https://volstrata.com/legal/terms>. Nothing here, and nothing the API returns, is
investment, financial or trading advice; published accuracy scores are the project's
own automated grading of its own prior output and are not indicative of future
results. See <https://volstrata.com/legal/disclaimer>.

---

Copyright 2026 Volstrata.com — <https://volstrata.com>
