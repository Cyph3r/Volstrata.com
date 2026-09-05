"""Copyright 2026 Volstrata.com

The agent pattern: three tools instead of a hundred and seventy.
Docs: https://volstrata.com/mcp

    python mcp/agent_loop_meta_tools.py

An anonymous caller sees 67 tools; a fully entitled one sees the whole catalog
projected, which is more than a hundred and fifty. Registering all of them with
a language model is possible and usually wrong: every schema is context spent
before the model has thought about anything, and most of them are irrelevant to
any single question.

The server ships three meta-tools so you do not have to:

    catalog.search   find a capability by keyword, domain or plan floor
    capability.call  invoke any capability by name -- the same gate applies
    docs.search      look up what a metric means

Register those three, and the whole catalog is reachable in two calls: search,
then call. This file is that loop, written out step by step -- the "agent" here
is a keyword and a print statement, because the interesting part is the protocol,
not the model.

    catalog.search {"query": "max pain"}
        -> results[] with name, domain, description, input_schema,
           min_plan_name and unlocked

    capability.call {"name": "gex.maxpain", "arguments": {"ticker": "SPX"}}
        -> the capability's own payload in structuredContent

`unlocked` on a search result is the field that makes this work end to end: a
model can be told what it may run before it tries, instead of discovering a plan
floor by being refused.

Five sequential requests.
"""

import json
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

# What our "agent" was asked about.
QUESTION = "max pain"
TICKER = "SPX"


def meta_tool(sess, name, arguments):
    """Call one meta-tool and return its structuredContent, or None."""
    try:
        result = rpc(sess, "tools/call", {"name": name, "arguments": arguments})
    except McpError as exc:
        print("  {0} refused: {1}".format(name, exc))
        return None
    except VolstrataError as exc:
        print("  {0} could not be sent: {1}".format(name, exc))
        return None
    return mcp_structured(result or {})


def main() -> int:
    print("VolStrata MCP: the meta-tool agent loop -- https://volstrata.com/mcp")
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
    # Step 1 -- find a capability from a keyword.
    # ---------------------------------------------------------------
    heading('Step 1: catalog.search {{"query": "{0}"}}'.format(QUESTION))
    found = meta_tool(sess, "catalog.search", {"query": QUESTION, "limit": 5})
    if not isinstance(found, dict):
        print("  No searchable result; stopping here.")
        return 0

    results = found.get("results") or []
    row("matches", found.get("count"))
    row("returned", found.get("returned"))
    row("next_cursor", found.get("next_cursor") or "null")
    for item in results:
        print("  {0:<24} {1:<10} {2:<6} unlocked={3}".format(
            item.get("name", "?"),
            item.get("domain", "?"),
            item.get("min_plan_name", "?"),
            item.get("unlocked"),
        ))
        print("      {0}".format((item.get("description") or "")[:96]))

    # catalog.search takes domain, tier, unlocked_only, limit and cursor as
    # well, so a picker can be narrowed however you like:
    #
    #     {"query": "wall", "domain": "gex", "unlocked_only": true}
    #
    # Each result carries its own input_schema, which is what you hand a model
    # so it can fill the arguments in without a second round trip.
    runnable = [item for item in results if item.get("unlocked")]
    if not runnable:
        print("\n  Nothing in these results is unlocked for this credential.")
        print("  That is the answer an agent should give -- naming the plan from")
        print("  min_plan_name -- rather than calling and being refused.")
        return 0

    chosen = runnable[0]
    heading("The schema for {0}".format(chosen.get("name")))
    show(chosen.get("input_schema"), max_items=8, max_chars=700)

    # ---------------------------------------------------------------
    # Step 2 -- run it, without ever having registered its schema.
    # ---------------------------------------------------------------
    name = chosen.get("name")
    arguments = {}
    properties = ((chosen.get("input_schema") or {}).get("properties")) or {}
    if "ticker" in properties:
        arguments["ticker"] = TICKER

    heading('Step 2: capability.call {{"name": "{0}", "arguments": {1}}}'.format(
        name, json.dumps(arguments)))
    payload = meta_tool(sess, "capability.call", {"name": name, "arguments": arguments})
    if isinstance(payload, dict):
        show(payload, max_items=6, max_chars=900)
        print("  Same payload the REST route returns, and the same gate: the")
        print("  dispatcher re-runs the entitlement check rather than trusting the")
        print("  caller to have checked `unlocked` first.")

    # ---------------------------------------------------------------
    # Step 3 -- explain the number you just fetched.
    # ---------------------------------------------------------------
    heading('Step 3: docs.search {{"query": "{0}"}}'.format(QUESTION))
    glossary = meta_tool(sess, "docs.search", {"query": QUESTION, "limit": 3})
    if isinstance(glossary, dict):
        rows = None
        for key in ("results", "docs", "matches"):
            if isinstance(glossary.get(key), list):
                rows = glossary[key]
                break
        if rows:
            for item in rows[:3]:
                if isinstance(item, dict):
                    print("  {0:<20} {1}".format(
                        item.get("metric") or item.get("name") or "?",
                        (item.get("title") or "")[:60]))
                    if item.get("short"):
                        print("      {0}".format(item["short"][:96]))
        else:
            show(glossary, max_items=4, max_chars=700)
        print("  A model that can define its own output is a model you can check.")

    heading("Why this beats registering everything")
    print("  * Three schemas of context instead of a table of hundreds.")
    print("  * A capability added tomorrow is reachable today: catalog.search")
    print("    reads the live catalog, so nothing is pinned to your tool table.")
    print("  * The plan floor is data (min_plan_name, unlocked), so the model can")
    print("    say what is missing instead of failing at call time.")
    print("  * Need the full table anyway? tools/list still returns it, and")
    print("    ?toolset=lean or ?toolset=<domains> trims it -- see list_tools.py.")

    heading("Next")
    print("  mcp/list_tools.py    the full projection and the tool object shape")
    print("  ../discover_capabilities.py   the same discovery over REST")
    print("  Protocol reference: https://volstrata.com/mcp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
