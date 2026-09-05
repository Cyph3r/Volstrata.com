"""Copyright 2026 Volstrata.com

The `research`, `docs` and `symbol` domains: the query surface, the glossary,
and how to turn a user's typing into a ticker the API will accept.
Docs: https://volstrata.com/docs/api-catalog
      https://volstrata.com/docs/api-examples

    python rest/research_and_docs.py

Eight capabilities:

    symbol.search      GET /api/v1/symbol/search      free-text -> candidates
    symbol.resolve     GET /api/v1/symbol/resolve     one string -> one symbol
    research.coverage  GET /api/v1/research/coverage  is this symbol served?
    research.universe  GET /api/v1/research/universe  what is served at all
    research.metrics   GET /api/v1/research/metrics   what you may ask for
    research.query     GET /api/v1/research/query     the query itself
    docs.metrics       GET /api/v1/docs/metrics       the glossary index
    docs.metric        GET /api/v1/docs/metric        one definition

The order above is the order a well-behaved client does things in: resolve the
symbol, check it is covered, check what your plan lets you ask for, then ask.
Each of those is a real capability rather than a guess your code has to make.

Eight sequential requests.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from volstrata_helpers import (  # noqa: E402  (import after the path fix, on purpose)
    attempt,
    describe_freshness,
    get,
    heading,
    key_banner,
    row,
    run_examples,
)


def resolve_a_symbol() -> None:
    """symbol.search is for a search box; symbol.resolve is for one known string.

    search  -> {"ok": true, "count": <n>, "query": "...",
                "symbols": [{"symbol": "...", "name": "...",
                             "assetClass": "stock|etf|index|future",
                             "dataTicker": "...", "candleSymbol": "...",
                             "tracked": true}, ...]}

    resolve -> {"ok": true, "known": true, "query": "...", "symbol": {...}}

    Note the three identifiers on every row. `symbol` is the canonical name and
    is what other capabilities want; `dataTicker` and `candleSymbol` are the
    forms used elsewhere in a response. Resolve once, keep the canonical form,
    and stop passing whatever the user typed to every endpoint.

    `known: false` from resolve is a clean answer, not an error -- the string
    did not match anything. Handle it as a normal branch.
    """
    heading("symbol.search -- free text to candidates")
    found = get("/symbol/search", q="app", limit=5)
    row("query", found.get("query"))
    row("count", found.get("count"))
    for item in (found.get("symbols") or [])[:5]:
        print("  {0:<8} {1:<32} {2:<8} tracked={3}".format(
            item.get("symbol", "?"),
            (item.get("name") or "")[:32],
            str(item.get("assetClass")),
            item.get("tracked"),
        ))

    heading("symbol.resolve -- one string to one symbol")
    resolved = get("/symbol/resolve", symbol="spy")
    row("known", resolved.get("known"))
    symbol = resolved.get("symbol") or {}
    row("symbol", symbol.get("symbol"))
    row("name", symbol.get("name"))
    row("assetClass", symbol.get("assetClass"))
    row("tracked", symbol.get("tracked"))


def check_coverage() -> None:
    """research.coverage answers "will this symbol return anything?" before you ask.

        {"ok": true, "symbol": "...", "display_name": "...",
         "asset_class": "index", "data_class": "us_index_option",
         "known": true, "tracked": true, "servable": true,
         "coverage": "full", "status": "covered_stale",
         "age_seconds": <n>, "last_updated_text": "4 min ago",
         "history_days": <n>, "expiry_windows": <n>,
         "delayed": false, "delay_minutes": null, "entitled": true,
         "headline": "...", "detail": "...", "remedy": {"kind": "none"},
         "freshness": {...}}

    `headline`, `detail` and `remedy` are written for display: when a symbol is
    not servable, show those instead of composing your own apology. `entitled`
    is about your plan, `servable` is about the data -- a symbol can be one
    without the other, and the two failures need different messages.

    research.universe is the same question asked across everything at once.
    """
    heading("research.coverage -- one symbol")
    data = get("/research/coverage", ticker="SPX")
    for field in ("symbol", "display_name", "asset_class", "data_class",
                  "known", "tracked", "servable", "entitled",
                  "coverage", "status", "last_updated_text",
                  "history_days", "expiry_windows", "delayed"):
        if field in data:
            row(field, data[field])
    row("headline", data.get("headline"))
    row("freshness", describe_freshness(data))

    heading("research.universe -- everything at once")
    universe = get("/research/universe")
    for field in ("registry", "tracked", "servable", "thin", "breadth"):
        if field in universe:
            row(field, universe[field])
    by_class = universe.get("servable_by_class") or {}
    for name in sorted(by_class):
        row("  " + name, by_class[name])
    symbols = universe.get("symbols") or []
    row("rows returned", len(symbols))


def what_you_may_ask() -> None:
    """research.metrics describes the query surface *for your plan*.

    It returns the metric list grouped into layers, plus the axes a query
    accepts (views, weights, contracts, moneyness, expiry classes) and an
    `access` block saying which of those your plan can actually use:

        "access": {"views":   {"ladder": {"entitled": true,
                                          "min_plan": "free",
                                          "min_plan_name": "Free"}, ...},
                   "weights": {...}, "export": {...}, "combine_exp": {...}}

    Read this once at start-up and you can grey out the options a user cannot
    pick, instead of letting them submit a query that will be refused.
    """
    heading("research.metrics -- what this caller may ask for")
    data = get("/research/metrics")
    caller = data.get("caller") or {}
    row("plan", caller.get("plan_name") or caller.get("plan"))
    row("views", ", ".join(data.get("views") or []))
    row("weights", ", ".join(
        item.get("id", "?") for item in (data.get("weights") or [])
        if isinstance(item, dict)))
    row("contracts", ", ".join(data.get("contracts") or []))
    row("moneyness", ", ".join(data.get("moneyness") or []))

    access = data.get("access") or {}
    views = access.get("views") or {}
    if views:
        allowed = sorted(k for k, v in views.items() if isinstance(v, dict) and v.get("entitled"))
        blocked = sorted(
            "{0} (needs {1})".format(k, v.get("min_plan_name"))
            for k, v in views.items() if isinstance(v, dict) and not v.get("entitled"))
        row("views you can use", ", ".join(allowed) or "none")
        row("views behind a floor", ", ".join(blocked) or "none")

    layers = data.get("layers") or []
    row("metric layers", len(layers))
    for layer in layers[:3]:
        names = [m.get("id") for m in (layer.get("metrics") or [])][:6]
        print("    {0:<18} {1}".format(layer.get("layer", "?"), ", ".join(str(n) for n in names)))


def run_a_query() -> None:
    """research.query is the parameterised read: one metric, one view, one window.

    Parameters worth knowing: metric, view (ladder, smile, term, levels_term,
    parity, surface), weight (oi, vol, both), strikes, start_dte, end_dte,
    expiry_class, contracts, moneyness, net, combine_exp, format (json or csv).

    Two parts of the response deserve your attention:

      query  -- the parameters the server actually used, echoed back. Log this,
                not what you sent: they can differ.
      meta   -- what the chain looked like (expiry count, dte range) plus an
                `entitlement` block. `expiry_clamped: true` means your window
                was narrowed to what your plan allows, and `end_dte_allowed`
                says where the edge is. A response can be a success and still
                not be the question you asked.
    """
    heading("research.query -- ladder view")
    data = get("/research/query", ticker="SPX", metric="gex", view="ladder", strikes=5)
    row("metric", "{0} ({1})".format(data.get("metric"), data.get("metric_label")))
    row("units", data.get("units"))
    row("view", data.get("view"))
    row("spot", data.get("spot"))

    echoed = data.get("query") or {}
    row("echoed query", ", ".join(
        "{0}={1}".format(k, echoed[k]) for k in sorted(echoed))[:150])

    meta = data.get("meta") or {}
    row("expiry_count", meta.get("expiry_count"))
    row("chain dte range", "{0} .. {1}".format(
        meta.get("chain_dte_min"), meta.get("chain_dte_max")))
    entitlement = meta.get("entitlement") or {}
    row("expiry_clamped", entitlement.get("expiry_clamped"))
    row("end_dte_allowed", entitlement.get("end_dte_allowed"))

    ladder = data.get("ladder") or {}
    row("ladder blocks", ", ".join(sorted(ladder)))
    levels = ladder.get("levels") or {}
    if levels:
        row("levels in view", ", ".join(
            "{0}={1}".format(k, levels[k]) for k in sorted(levels))[:150])
    row("freshness", describe_freshness(data))


def the_glossary() -> None:
    """docs.metrics and docs.metric are the definitions, served as data.

    docs.metrics -> {"ok": true, "count": <n>,
                     "docs": [{"metric": "call_wall",
                               "title": "Call Wall (CW)",
                               "short": "..."}, ...]}

    docs.metric?metric=<id> -> the same row plus `body`, the full write-up in
    Markdown.

    This is the honest way to label a number in your own UI: pull the title and
    the short definition from the API instead of writing your own and letting it
    drift. It is also what the MCP meta-tool docs.search reads.
    """
    heading("docs.metrics -- the glossary index")
    index = get("/docs/metrics")
    row("count", index.get("count"))
    for item in (index.get("docs") or [])[:6]:
        print("  {0:<20} {1}".format(
            item.get("metric", "?"), (item.get("title") or "")[:44]))

    heading("docs.metric -- one definition")
    metric = (index.get("docs") or [{}])[0].get("metric") or "gex"
    detail = attempt("docs.metric", get, "/docs/metric", metric=metric)
    if detail is None:
        return
    row("metric", detail.get("metric"))
    row("title", detail.get("title"))
    row("short", (detail.get("short") or "")[:120])
    body = detail.get("body") or ""
    row("body", "{0} characters of Markdown".format(len(body)))
    for line in body.splitlines()[:4]:
        print("    {0}".format(line[:100]))


def main() -> int:
    print("VolStrata: research, docs and symbols -- https://volstrata.com")
    key_banner()
    exit_code = run_examples((
        ("symbols", resolve_a_symbol),
        ("coverage", check_coverage),
        ("query surface", what_you_may_ask),
        ("query", run_a_query),
        ("glossary", the_glossary),
    ))
    heading("Next")
    print("  rest/gex_levels.py         the metrics this query surface exposes")
    print("  mcp/agent_loop_meta_tools.py  the same discovery, for an agent")
    print("  Catalog: https://volstrata.com/docs/api-catalog")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
