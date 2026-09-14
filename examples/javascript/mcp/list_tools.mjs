/**
 * Copyright 2026 Volstrata.com
 *
 * MCP over raw JSON-RPC 2.0: handshake, then list the tools your credential can
 * see. No MCP SDK, no npm install — one `fetch` and a JSON body.
 * Docs: https://volstrata.com/mcp
 *
 * Run:  node mcp/list_tools.mjs [TOOLSET]
 *       npm run mcp:tools
 *
 * Three requests to POST /api/v1/mcp:
 *
 *   initialize                   negotiate the protocol revision
 *   notifications/initialized    the handshake's second half (no reply)
 *   tools/list                   what this caller can call
 *
 * The endpoint answers HTTP 200 for everything it can parse, so `res.ok` is NOT
 * the success test here — a failure arrives inside the JSON-RPC `error` member
 * of a 200 response. That single fact is the main thing this file teaches.
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

/** The transport is one URL. JSON-RPC over POST; there is no GET form. */
const MCP_URL = `${BASE}/api/v1/mcp`;

/**
 * Optional toolset selector, as a query string on the endpoint URL or as a
 * `toolset` member of the `tools/list` params:
 *
 *   (none)        the full projection your plan unlocks
 *   lean          the meta-tools plus a small core — 10 tools
 *   gex,levels    only the named domains
 *
 * Useful when an agent's context budget cannot hold the whole catalog.
 */
const toolset = process.argv[2] ?? null;
const url = toolset ? `${MCP_URL}?toolset=${encodeURIComponent(toolset)}` : MCP_URL;

/**
 * The protocol revision this client asks for. The server negotiates and echoes
 * back what it will actually speak, so read the reply rather than assuming you
 * got what you asked for. It supports 2025-11-25, 2025-06-18, 2025-03-26 and
 * 2024-11-05, and falls back to the oldest of those for a client that names
 * none.
 */
const PROTOCOL_VERSION = "2025-06-18";

/** A JSON-RPC `error` member, as an exception. */
class McpRpcError extends Error {
  constructor(error) {
    super(`JSON-RPC ${error?.code ?? "?"}: ${error?.message ?? "no message"}`);
    this.name = "McpRpcError";
    this.code = error?.code ?? null;
    this.data = error?.data ?? {};
  }

  /** -32001 is the access-denied code: a plan floor, not a malformed call. */
  get isAccessDenied() {
    return this.code === -32001;
  }
}

let nextId = 1;

/**
 * Send one JSON-RPC message.
 *
 * A notification (`notify: true`) carries no `id` and gets no result — the
 * server acknowledges with an empty body, so there is nothing to parse.
 */
async function rpc(method, params, { notify = false } = {}) {
  const message = { jsonrpc: "2.0", method };
  if (params !== undefined) message.params = params;
  if (!notify) message.id = nextId++;

  // The transport is retried; the MCP layer's own answer is not. A 429 or a 5xx
  // means the message never reached MCP, so sending it again is safe — and at
  // the anonymous ceiling of 10 requests a minute, a handshake plus tools/list
  // meets that ceiling easily. An `error` inside a 200 is the server's
  // considered reply and is surfaced immediately instead.
  return withBackoff(async () => {
    const res = await fetch(url, {
      method: "POST",
      // Same credential as the REST API: `Authorization: Bearer <key>`, attached
      // only when VOLSTRATA_API_KEY is set. Anonymous callers get the free tools.
      headers: headers({ "Content-Type": "application/json" }),
      body: JSON.stringify(message),
      signal: AbortSignal.timeout(30_000),
    });

    // A non-2xx here means the request never reached the MCP layer at all — a
    // wrong URL, a proxy, an edge refusal, or the rate limiter. Everything the
    // MCP layer itself decides comes back as 200 with an `error` member.
    // Raising it as a VolstrataApiError is what lets withBackoff above see a
    // 429 as retryable and honour `Retry-After`; it also parses the RFC 9457
    // problem document, so the message below is the API's own words.
    if (!res.ok) throw await VolstrataApiError.fromResponse(res, url);

    if (notify) return null;

    const envelope = await res.json();
    if (envelope.error) throw new McpRpcError(envelope.error);
    return envelope.result ?? {};
  });
}

heading("MCP — tools/list");
show("endpoint", MCP_URL);
show("toolset", toolset ?? "(default — everything your plan unlocks)");
show("api key", hasApiKey ? "detected in VOLSTRATA_API_KEY" : "none — anonymous projection");

try {
  // -------------------------------------------------------------------------
  // 1. initialize
  // -------------------------------------------------------------------------
  const init = await rpc("initialize", {
    protocolVersion: PROTOCOL_VERSION,
    capabilities: {},
    clientInfo: { name: "volstrata-examples", version: "1.0" },
  });

  heading("1. initialize");
  show("requested", PROTOCOL_VERSION);
  show("negotiated", init.protocolVersion);
  // `serverInfo.title` is the display name to show a user; `version` is the
  // dated contract version, the same one the REST API reports on every response.
  show("server", `${init.serverInfo?.title ?? "(no title)"} ${init.serverInfo?.version ?? ""}`.trim());
  show("capabilities", Object.keys(init.capabilities ?? {}).sort().join(", ") || "(none)");

  // -------------------------------------------------------------------------
  // 2. notifications/initialized
  // -------------------------------------------------------------------------
  //
  // The half of the handshake that is easy to skip and awkward to debug: a
  // client tells the server it is ready, with a message that has no `id` and
  // therefore no reply.
  await rpc("notifications/initialized", {}, { notify: true });
  heading("2. notifications/initialized");
  show("sent", "no id, no reply — that is what a notification is");

  // -------------------------------------------------------------------------
  // 3. tools/list
  // -------------------------------------------------------------------------
  const list = await rpc("tools/list", {});
  const tools = list.tools ?? [];

  heading("3. tools/list");
  show("tools visible", tools.length);

  // Three meta-tools are always present whatever your plan: one to search the
  // catalog, one universal dispatcher, one for metric definitions. The rest are
  // capability tools, projected one-to-one from the public REST catalog — the
  // tool name IS the dotted capability name, so `gex.levels` here and
  // `/api/v1/gex/levels` there are the same thing.
  const META = new Set(["catalog.search", "capability.call", "docs.search"]);
  const metaTools = tools.filter((tool) => META.has(tool.name));
  const capabilityTools = tools.filter((tool) => !META.has(tool.name));

  show("meta-tools", metaTools.map((tool) => tool.name).join(", ") || "(none)");
  show("capability tools", capabilityTools.length);

  heading("First names");
  for (const tool of tools.slice(0, 12)) {
    console.log(`  ${tool.name.padEnd(26)} ${tool.title ?? ""}`);
  }
  if (tools.length > 12) console.log(`  … and ${tools.length - 12} more`);

  // Domains, derived from the names themselves.
  const domains = new Map();
  for (const tool of capabilityTools) {
    const domain = tool.name.split(".")[0];
    domains.set(domain, (domains.get(domain) ?? 0) + 1);
  }
  heading("Busiest domains");
  for (const [domain, count] of [...domains].sort((a, b) => b[1] - a[1]).slice(0, 8)) {
    show(domain, count);
  }

  // One tool, in full-ish: every tool carries an inputSchema and an outputSchema
  // (both JSON Schema, with defaults and enums where the parameter is
  // constrained) plus `annotations` telling a client whether the call is
  // read-only, idempotent and destructive.
  const sample = tools.find((tool) => tool.name === "gex.levels") ?? tools[0];
  if (sample) {
    heading(`Anatomy of one tool — ${sample.name}`);
    show("title", sample.title ?? "(none)");
    show("description", (sample.description ?? "").slice(0, 160));
    show("input params", Object.keys(sample.inputSchema?.properties ?? {}).join(", ") || "(none)");
    show("required", (sample.inputSchema?.required ?? []).join(", ") || "(none)");
    show("annotations", summarize(sample.annotations, { depth: 1, maxKeys: 6 }));
  }

  heading("What you are seeing");
  if (hasApiKey) {
    console.log("  This projection is scoped to your plan. Tools above your floor are");
    console.log("  hidden from tools/list and refused by tools/call — both, not one.");
  } else {
    console.log("  Anonymously the endpoint publishes 67 tools: the 3 meta-tools plus");
    console.log("  the 64 free capability tools. A fully entitled caller sees 177.");
    console.log("  Set VOLSTRATA_API_KEY to see your own projection.");
  }
  console.log("\n  Next: node mcp/call_a_tool.mjs   — actually call one");
} catch (error) {
  heading("The call did not succeed");
  if (error instanceof McpRpcError) {
    console.log(`  ${error.message}`);
    if (error.isAccessDenied) show("required plan", error.data.required_plan_name ?? "(not reported)");
  } else if (error instanceof VolstrataApiError) {
    console.log(error.describe());
  } else {
    console.log(`  ${error?.message ?? error}`);
  }
  console.log("\n  Connect page: https://volstrata.com/mcp");
  process.exitCode = 1;
}
