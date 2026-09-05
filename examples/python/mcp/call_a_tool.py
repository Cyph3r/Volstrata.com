"""Copyright 2026 Volstrata.com

Calling a tool over MCP, and what a refusal looks like when you do.
Docs: https://volstrata.com/mcp

    python mcp/call_a_tool.py

Two calls, on purpose:

    tools/call gex.levels    {"ticker": "SPX"}   -> a result
    tools/call gex.snapshot  {"ticker": "SPX"}   -> error -32001

The second one is the interesting half. A tool above your plan floor is hidden
from tools/list AND refused by tools/call, and the refusal is a JSON-RPC error
rather than an HTTP status:

    {"jsonrpc": "2.0", "id": <n>,
     "error": {"code": -32001,
               "message": "'<tool>' requires the <Plan> plan.",
               "data": {"current_tier": "...", "required_plan": "...",
                        "required_plan_name": "...", "tool": "<tool>"}}}

`required_plan_name` is the customer-facing name, and it is the string to put in
front of a user. An agent that reads this can say what is missing instead of
retrying a call that will never succeed.

Four sequential requests.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from volstrata_helpers import (  # noqa: E402  (import after the path fix, on purpose)
    McpError,
    VolstrataError,
    heading,
    key_banner,
    mcp_initialize,
    mcp_session,
    mcp_structured,
    row,
    rpc,
    show,
)

TICKER = "SPX"


def call_tool(sess, name, arguments):
    """One tools/call. Returns the result dict, or None after reporting an error.

    Both failure channels are handled here, because a client has to handle both:

      McpError        the protocol said no (a plan floor, an unknown tool, a bad
                      argument). HTTP was 200.
      VolstrataError  the request did not reach the protocol layer (rate limit,
                      or a refusal in front of the API).
    """
    try:
        return rpc(sess, "tools/call", {"name": name, "arguments": arguments})
    except McpError as exc:
        print("  {0} refused: {1}".format(name, exc))
        if exc.access_denied:
            row("  code", exc.code)
            row("  required_plan_name", exc.required_plan_name)
            row("  current_tier", exc.current_tier)
            row("  tool", exc.tool)
            print("  -> Tell the user what plan clears it. Do not retry: the answer")
            print("     will not change, and the attempt still costs rate budget.")
        return None
    except VolstrataError as exc:
        print("  {0} could not be sent: {1}".format(name, exc))
        return None


def main() -> int:
    print("VolStrata MCP: calling a tool -- https://volstrata.com/mcp")
    key_banner()

    sess = mcp_session()

    heading("Handshake")
    try:
        info = mcp_initialize(sess)
    except (VolstrataError, McpError) as exc:
        print("  Handshake failed: {0}".format(exc))
        return 0
    row("protocol", info.get("protocolVersion"))
    row("server", (info.get("serverInfo") or {}).get("title"))

    # ---------------------------------------------------------------
    # A tool that answers.
    # ---------------------------------------------------------------
    heading("tools/call gex.levels")
    print('  params: {"name": "gex.levels", "arguments": {"ticker": "%s"}}' % TICKER)
    result = call_tool(sess, "gex.levels", {"ticker": TICKER})
    if result is not None:
        # A tools/call result has three parts:
        #
        #   content            [{type: "text", text: "<pretty JSON>"}] -- what a
        #                      model reads
        #   structuredContent  the same payload as real JSON -- what your code
        #                      should read
        #   isError            false on success
        #
        # They are the same data twice, deliberately: one for the LLM, one for
        # the program. Never parse the text block when structuredContent exists.
        row("isError", result.get("isError"))
        blocks = result.get("content") or []
        row("content blocks", "{0} ({1})".format(
            len(blocks), ", ".join(b.get("type", "?") for b in blocks)))

        payload = mcp_structured(result)
        if isinstance(payload, dict):
            row("ticker", payload.get("ticker"))
            row("spot", payload.get("spot"))
            row("updated", payload.get("updated"))
            levels = payload.get("levels") or {}
            row("levels returned", len(levels))
            for key in ("cw", "pw", "zg", "mp"):
                if key in levels:
                    row("  " + key, levels[key])
            print("  Identical to GET /api/v1/gex/levels?ticker={0} -- same".format(TICKER))
            print("  capability, same gate, different transport.")

    # ---------------------------------------------------------------
    # A tool that refuses.
    # ---------------------------------------------------------------
    heading("tools/call gex.snapshot -- above the floor")
    print('  params: {"name": "gex.snapshot", "arguments": {"ticker": "%s"}}' % TICKER)
    gated = call_tool(sess, "gex.snapshot", {"ticker": TICKER})
    if gated is not None:
        row("isError", gated.get("isError"))
        payload = mcp_structured(gated)
        if isinstance(payload, dict):
            show(payload, max_items=4, max_chars=800)
        print("  Your credential clears this one's floor.")

    # ---------------------------------------------------------------
    # The other error codes, without provoking them.
    # ---------------------------------------------------------------
    heading("The error codes worth handling")
    for code, meaning in (
        ("-32700", "parse error -- the body was not valid JSON"),
        ("-32600", "invalid request -- not a well-formed JSON-RPC envelope"),
        ("-32601", "method not found -- e.g. a method this server does not answer"),
        ("-32602", "invalid params -- a required argument is missing or wrong"),
        ("-32603", "internal error -- retry with backoff, quote the request id"),
        ("-32001", "access denied -- a plan floor, with data.required_plan_name"),
        ("-32002", "resource not found -- an unknown resources/read URI"),
    ):
        print("  {0:<8} {1}".format(code, meaning))
    print("  A rate limit is different: it stops the request before the protocol")
    print("  layer, so it arrives as an HTTP status with a problem+json body and a")
    print("  Retry-After header. Handle both shapes.")

    heading("Next")
    print("  mcp/agent_loop_meta_tools.py  reach the whole catalog with 3 tools")
    print("  ../rest/gex_levels.py         the same capability over REST")
    print("  Protocol reference: https://volstrata.com/mcp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
