/**
 * Copyright 2026 Volstrata.com
 *
 * MCP `tools/call`: run a tool, read its structured result, then run one that is
 * above the anonymous floor and report the refusal properly. Raw JSON-RPC over
 * `fetch` — no MCP SDK, nothing installed.
 * Docs: https://volstrata.com/mcp
 *
 * Run:  node mcp/call_a_tool.mjs [TICKER]
 *       npm run mcp:call
 *
 * Four requests: the two-step handshake, then two tool calls — `gex.levels`
 * (free) and `gex.snapshot` (Edge).
 *
 * There are two different failure channels here, and mixing them up is the
 * usual MCP bug:
 *
 *   the JSON-RPC `error` member   the call was refused — bad method, bad
 *                                 params, or -32001 access denied
 *   `result.isError: true`        the call ran and the tool itself reported a
 *                                 problem, described in the text content
 *
 * The HTTP status is 200 in both cases.
 */

import {
  BASE,
  VolstrataApiError,
  hasApiKey,
  headers,
  heading,
  show,
  summarize,
  withBackoff,
} from "../lib/volstrata.mjs";

const MCP_URL = `${BASE}/api/v1/mcp`;
const ticker = (process.argv[2] ?? "SPX").toUpperCase();
const PROTOCOL_VERSION = "2025-06-18";

/**
 * A JSON-RPC `error` member, as an exception.
 *
 *   -32700 parse error        -32603 internal error
 *   -32600 invalid request    -32001 access denied  (plan floor)
 *   -32601 method not found   -32002 resource not found
 *   -32602 invalid params
 *
 * A -32001 carries `data: {current_tier, required_plan, required_plan_name,
 * tool}` — `required_plan_name` is the one to show a person.
 */
class McpRpcError extends Error {
  constructor(error) {
    super(`JSON-RPC ${error?.code ?? "?"}: ${error?.message ?? "no message"}`);
    this.name = "McpRpcError";
    this.code = error?.code ?? null;
    this.data = error?.data ?? {};
  }

  get isAccessDenied() {
    return this.code === -32001;
  }

  get requiredPlanName() {
    return this.data?.required_plan_name ?? null;
  }
}

let nextId = 1;

async function rpc(method, params, { notify = false } = {}) {
  const message = { jsonrpc: "2.0", method };
  if (params !== undefined) message.params = params;
  if (!notify) message.id = nextId++;

  // The transport is retried; the MCP layer's own answer is not. A 429 or a 5xx
  // means the message never reached MCP, so sending it again is safe — and at
  // the anonymous ceiling of 10 requests a minute, a handshake plus a tools/call
  // meets that ceiling easily. An `error` inside a 200 is the server's
  // considered reply and is surfaced immediately instead.
  return withBackoff(async () => {
    const res = await fetch(MCP_URL, {
      method: "POST",
      headers: headers({ "Content-Type": "application/json" }),
      body: JSON.stringify(message),
      signal: AbortSignal.timeout(30_000),
    });

    // Only a transport failure lands here; everything the MCP layer decides is a
    // 200 with `result` or `error`. Raising it as a VolstrataApiError is what
    // lets withBackoff above see a 429 as retryable and honour `Retry-After`.
    if (!res.ok) throw await VolstrataApiError.fromResponse(res, MCP_URL);

    if (notify) return null;

    const envelope = await res.json();
    if (envelope.error) throw new McpRpcError(envelope.error);
    return envelope.result ?? {};
  });
}

heading("MCP — tools/call");
show("endpoint", MCP_URL);
show("ticker", ticker);
show("api key", hasApiKey ? "detected in VOLSTRATA_API_KEY" : "none — anonymous");

try {
  // -------------------------------------------------------------------------
  // Handshake
  // -------------------------------------------------------------------------
  const init = await rpc("initialize", {
    protocolVersion: PROTOCOL_VERSION,
    capabilities: {},
    clientInfo: { name: "volstrata-examples", version: "1.0" },
  });
  await rpc("notifications/initialized", {}, { notify: true });

  heading("Handshake");
  show("protocol", init.protocolVersion);
  show("server", `${init.serverInfo?.title ?? "(no title)"} ${init.serverInfo?.version ?? ""}`.trim());

  // -------------------------------------------------------------------------
  // A free tool
  // -------------------------------------------------------------------------
  //
  // `tools/call` takes the tool name and an `arguments` object matching the
  // tool's inputSchema — which is the same parameter set the REST capability
  // takes, because the tools are projected from that catalog one to one.
  heading("gex.levels");

  const result = await rpc("tools/call", {
    name: "gex.levels",
    arguments: { ticker },
  });

  show("isError", result.isError);
  show("content types", (result.content ?? []).map((part) => part.type).join(", ") || "(none)");

  // Two representations of the same answer come back:
  //
  //   content[]           display form — a text part holding pretty-printed JSON
  //   structuredContent   the parsed object, which is what code should read
  //
  // Read `structuredContent`. Parsing the text part works and is wasted effort.
  const payload = result.structuredContent ?? {};
  show("structured keys", Object.keys(payload).sort().join(", ") || "(none)");
  show("ticker", payload.ticker);
  show("spot", payload.spot);
  show("updated", payload.updated);

  const levels = payload.levels ?? {};
  show("level names", Object.keys(levels).sort().slice(0, 10).join(", "));
  for (const key of ["cw", "pw", "zg", "mp"]) {
    if (key in levels) show(`  ${key}`, levels[key] ?? "null");
  }

  const text = result.content?.find((part) => part.type === "text")?.text ?? "";
  show("text part", `${text.length} characters of pretty-printed JSON (the same data)`);

  // -------------------------------------------------------------------------
  // A gated tool
  // -------------------------------------------------------------------------
  //
  // `gex.snapshot` needs the Edge plan. For a caller below the floor it is both
  // hidden from tools/list and refused by tools/call — belt and braces, so an
  // agent that cached an old tool list still gets a clean, machine-readable
  // refusal rather than confusing output.
  heading("gex.snapshot — above the anonymous floor");

  try {
    const gated = await rpc("tools/call", {
      name: "gex.snapshot",
      arguments: { ticker },
    });
    show("isError", gated.isError);
    show("structured keys", Object.keys(gated.structuredContent ?? {}).sort().join(", ") || "(none)");
    show("note", "your plan includes this tool");
  } catch (error) {
    if (error instanceof McpRpcError && error.isAccessDenied) {
      // This is the shape to render in an agent UI: the required plan by name,
      // and the tool that wanted it. No stack trace, no retry.
      show("code", `${error.code} (access denied)`);
      show("tool", error.data.tool ?? "gex.snapshot");
      show("required plan", error.requiredPlanName ?? "(not reported)");
      show("current tier", error.data.current_tier ?? "(not reported)");
      show("message", error.message);
      console.log("\n  A refusal is an answer. Retrying it changes nothing —");
      console.log("  the fix is a plan that includes the tool: https://volstrata.com/api-keys");
    } else {
      throw error;
    }
  }

  // -------------------------------------------------------------------------
  // The dispatcher
  // -------------------------------------------------------------------------
  //
  // Loading 177 tool definitions into an agent's context is often the wrong
  // trade. Two meta-tools exist for that: `catalog.search` finds a capability by
  // keyword, domain or plan tier, and `capability.call` invokes any of them by
  // name — running exactly the same plan check:
  //
  //   tools/call { name: "capability.call",
  //                arguments: { name: "gex.levels", arguments: { ticker: "SPX" } } }
  //
  // `?toolset=lean` on the endpoint URL does the same job from the other
  // direction — see mcp/list_tools.mjs.
  heading("Related");
  console.log("  Tool list            node mcp/list_tools.mjs");
  console.log("  Connect a client     https://volstrata.com/mcp");
  console.log("  Capability catalog   https://volstrata.com/docs/api-catalog");
} catch (error) {
  heading("The call did not succeed");
  if (error instanceof McpRpcError) {
    console.log(`  ${error.message}`);
    show("data", summarize(error.data, { depth: 1, maxKeys: 6 }));
  } else if (error instanceof VolstrataApiError) {
    console.log(error.describe());
  } else {
    console.log(`  ${error?.message ?? error}`);
  }
  console.log("\n  Connect page: https://volstrata.com/mcp");
  process.exitCode = 1;
}
