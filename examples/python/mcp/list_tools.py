"""Copyright 2026 Volstrata.com

The MCP handshake, and what your credential can see.
Docs: https://volstrata.com/mcp

    python mcp/list_tools.py

Three messages, in the order every MCP client sends them:

    1. initialize                  negotiate a protocol revision
    2. notifications/initialized   a notification: no id, no reply
    3. tools/list                  what this caller may call

All three are POSTs to https://volstrata.com/api/v1/mcp carrying a JSON-RPC 2.0
envelope. There is no SDK involved and none is needed -- this is `requests` and
a dict.

Tools are projected from the same capability catalog the REST API publishes, so
a tool name IS the dotted capability name (`gex.levels`), and its `_meta` block
carries the HTTP method and path the tool stands for. An anonymous caller sees
67 tools: three server-native meta-tools plus the capability tools that need no
credential. A key raises that to whatever the plan behind it unlocks.

Four sequential requests (the fourth demonstrates the toolset selector).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from volstrata_helpers import (  # noqa: E402  (import after the path fix, on purpose)
    MCP_PROTOCOL_VERSION,
    MCP_URL,
    McpError,
    VolstrataError,
    heading,
    key_banner,
    mcp_initialize,
    mcp_session,
    row,
    rpc,
    show,
)

SHOW_FIRST = 12


def main() -> int:
    print("VolStrata MCP: handshake and tool list -- https://volstrata.com/mcp")
    key_banner()
    row("endpoint", MCP_URL)

    sess = mcp_session()

    # ---------------------------------------------------------------
    # 1 + 2. The handshake.
    # ---------------------------------------------------------------
    heading("initialize")
    try:
        result = mcp_initialize(sess)
    except (VolstrataError, McpError) as exc:
        print("  Handshake failed: {0}".format(exc))
        return 0

    # The client proposes a revision and the server answers with one it
    # supports. Read what came back rather than assuming you got what you
    # asked for -- that is the whole point of negotiating.
    row("requested", MCP_PROTOCOL_VERSION)
    row("negotiated", result.get("protocolVersion"))

    server = result.get("serverInfo") or {}
    row("server title", server.get("title"))
    row("server version", server.get("version"))

    capabilities = result.get("capabilities") or {}
    row("capabilities", ", ".join(sorted(capabilities)))
    print("  tools.listChanged means the list can change under you -- re-read it")
    print("  after a plan change rather than caching it for the process lifetime.")

    instructions = result.get("instructions") or ""
    if instructions:
        row("instructions", "{0} characters".format(len(instructions)))
        print("  `instructions` is written for a model, not a person: an MCP client")
        print("  passes it to the LLM as context about how to use this server.")

    # A notification carries no id and gets no response body. mcp_initialize()
    # has already sent notifications/initialized; a server may refuse ordinary
    # calls until it arrives.
    print("\n  notifications/initialized sent (no id, no reply -- that is correct).")

    # ---------------------------------------------------------------
    # 3. tools/list
    # ---------------------------------------------------------------
    heading("tools/list")
    try:
        listing = rpc(sess, "tools/list", {}) or {}
    except (VolstrataError, McpError) as exc:
        print("  tools/list failed: {0}".format(exc))
        return 0

    tools = listing.get("tools") or []
    row("tools visible", len(tools))
    if listing.get("nextCursor"):
        row("nextCursor", "present -- the list itself is pageable")

    meta_tools = [t for t in tools if not (t.get("_meta") or {}).get("path")]
    row("meta-tools", ", ".join(sorted(t.get("name", "?") for t in meta_tools)))
    print("  Those three are server-native rather than a projection of one HTTP")
    print("  route, which is why they carry no _meta.path. See")
    print("  agent_loop_meta_tools.py for why they matter.")

    print("\n  First {0} tools:".format(SHOW_FIRST))
    for tool in tools[:SHOW_FIRST]:
        meta = tool.get("_meta") or {}
        print("    {0:<26} {1:<5} {2:<32} {3}".format(
            tool.get("name", "?"),
            meta.get("method", "-"),
            meta.get("path", "-"),
            meta.get("tier_name", "-"),
        ))

    # The tool object is the whole contract: a client can build a form, a
    # validator and a permissions prompt from it without asking anyone.
    if tools:
        example = next((t for t in tools if (t.get("_meta") or {}).get("path")), tools[0])
        heading("One tool object, in full")
        show(example, max_items=6, max_chars=1800)
        print("  name/title/description  what it is, for a human and for a model")
        print("  inputSchema             JSON Schema, with defaults and enums")
        print("  outputSchema            the shape of structuredContent")
        print("  annotations             readOnlyHint, idempotentHint, ...")
        print("  _meta                   method, path, policy_key, tier, tier_name")

    heading("Trimming the list")
    print("  Registering every tool costs a model context it could spend thinking.")
    print("  Two ways to send less:")
    print("    ?toolset=lean         the meta-tools plus a small core")
    print("    ?toolset=gex,levels   only those domains")
    print("  The same selector is accepted as a `toolset` member of params.")

    try:
        lean = rpc(sess, "tools/list", {}, url=MCP_URL + "?toolset=lean") or {}
    except (VolstrataError, McpError) as exc:
        print("  (lean listing unavailable: {0})".format(exc))
        return 0

    lean_tools = lean.get("tools") or []
    row("lean tools", len(lean_tools))
    print("  " + ", ".join(t.get("name", "?") for t in lean_tools))

    heading("Next")
    print("  mcp/call_a_tool.py            run one, and hit a plan floor")
    print("  mcp/agent_loop_meta_tools.py  the agent pattern")
    print("  Protocol reference: https://volstrata.com/mcp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
