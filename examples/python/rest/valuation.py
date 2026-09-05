"""Copyright 2026 Volstrata.com

The `valuation` and `fundamentals` domains, and the first POST in this repo.
Docs: https://volstrata.com/docs/api-catalog
      https://volstrata.com/docs/api-auth

    python rest/valuation.py

Four capabilities:

    fundamentals.company  GET  /api/v1/fundamentals/company  reported figures
    valuation.universe    GET  /api/v1/valuation/universe    a screen, paged by offset
    valuation.company     GET  /api/v1/valuation/company     one company
    valuation.value       POST /api/v1/valuation/value       above the lowest floor

Two things this file is here to teach:

  * A capability whose catalog floor is Free can still require an authenticated
    principal. When that is the case the refusal is a 401 `auth_required` rather
    than a 403 naming a plan -- any accepted credential clears it. Check
    GET /api/v1/meta/access for what your own credential unlocks.
  * `valuation.universe` pages with `limit` and `offset`, not with a cursor.
    Most of the surface is cursor-paged; this one is not, and reading the
    parameters in the spec rather than assuming is the habit that catches it.

Four sequential requests. Some will be refused unless you have a key.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from volstrata_helpers import (  # noqa: E402  (import after the path fix, on purpose)
    attempt,
    get,
    heading,
    key_banner,
    post,
    row,
    run_examples,
    show,
)

TICKER = "AAPL"


def reported_fundamentals() -> None:
    """fundamentals.company returns the reported line items, plus their history.

    Shape:

        {"ok": true,
         "entity_name": "...", "cik": "...", "currency": "USD",
         "fiscal_year": <year>, "period_end": "YYYY-MM-DD", "as_of": <unix>,
         "latest":  {"revenue": <n>, "net_income": <n>, "eps_diluted": <n>, ...},
         "history": {"revenue": [{"fy": <year>, "end": "YYYY-MM-DD", "val": <n>}, ...],
                      ...}}

    `latest` and `history` share their keys, so one loop can render a value and
    its trend. Amounts are in `currency` units as reported; per-share figures are
    per share. Nothing here is derived or adjusted -- it is what was filed.
    """
    heading("fundamentals.company -- reported figures")
    data = get("/fundamentals/company", ticker=TICKER)
    row("entity_name", data.get("entity_name"))
    row("cik", data.get("cik"))
    row("currency", data.get("currency"))
    row("fiscal_year", data.get("fiscal_year"))
    row("period_end", data.get("period_end"))

    latest = data.get("latest") or {}
    row("line items", len(latest))
    for field in ("revenue", "net_income", "eps_diluted", "total_assets", "cash"):
        if field in latest:
            row(field, latest[field])

    history = data.get("history") or {}
    revenue = history.get("revenue") or []
    if revenue:
        # Each point is {"fy": <year>, "end": "YYYY-MM-DD", "val": <n>}. Sort by
        # `end` yourself if order matters to you rather than trusting the order
        # a list happens to arrive in.
        print("  history.revenue, first rows as returned:")
        for point in revenue[:4]:
            print("    fy {0}  ending {1}".format(point.get("fy"), point.get("end")))


def screen_the_universe() -> None:
    """valuation.universe is a screen: many companies, a few fields each.

    Parameters: limit, offset, sector, model, verdict, min_market_cap, format.
    Page it by advancing `offset` -- and note the ceiling on `limit` is the
    server's to choose, so read how many rows you actually got rather than
    assuming you got `limit` of them.
    """
    heading("valuation.universe -- a screen")
    data = attempt("valuation.universe", get, "/valuation/universe", limit=5, offset=0)
    if data is None:
        print("  Set VOLSTRATA_API_KEY and re-run to see this one.")
        return
    rows = None
    for key in ("universe", "rows", "companies", "results"):
        if isinstance(data.get(key), list):
            rows = data[key]
            row("collection key", key)
            break
    row("rows returned", len(rows) if rows is not None else "n/a")
    if rows:
        show(rows[0])
    else:
        # Not every response names its collection the same way; when in doubt,
        # print the keys and read them once rather than guessing forever.
        row("top-level keys", ", ".join(sorted(data)[:14]))


def one_company() -> None:
    """valuation.company is the single-name view of the same data set."""
    heading("valuation.company -- one company")
    data = attempt("valuation.company", get, "/valuation/company", ticker=TICKER)
    if data is None:
        print("  Same credential requirement as the screen above.")
        return
    row("ticker", data.get("ticker"))
    row("top-level keys", ", ".join(sorted(data)[:14]))
    show(data, max_items=3, max_chars=900)


def gated_post() -> None:
    """valuation.value is a POST, and it is above the lowest floor.

    Seven of the 180 published operations take POST; the rest are GET. The body
    is plain JSON, and `requests` will set Content-Type for you when you pass
    `json=`:

        POST /api/v1/valuation/value
        Content-Type: application/json

        {"ticker": "AAPL", "format": "json"}

    The `overrides` parameter is documented in the spec for callers who want to
    supply their own assumptions. The refusal below names the plan that clears
    the floor; nothing about the request shape is wrong.
    """
    heading("valuation.value -- gated POST")
    body = {"ticker": TICKER, "format": "json"}
    print("  body: {0}".format(body))
    data = attempt("valuation.value", post, "/valuation/value", body)
    if data is None:
        print("  Expected without the plan. Pricing and keys:")
        print("  https://volstrata.com/api-keys")
        return
    row("ok", data.get("ok"))
    row("top-level keys", ", ".join(sorted(data)[:14]))


def main() -> int:
    print("VolStrata: valuation and fundamentals -- https://volstrata.com")
    key_banner()
    exit_code = run_examples((
        ("fundamentals", reported_fundamentals),
        ("universe", screen_the_universe),
        ("company", one_company),
        ("valuation.value", gated_post),
    ))
    heading("Next")
    print("  discover_capabilities.py   what your credential unlocks")
    print("  rest/research_and_docs.py  the research query surface")
    print("  Catalog: https://volstrata.com/docs/api-catalog")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
