"""Copyright 2026 Volstrata.com

The `market` domain: quotes, candles, breadth and index membership.
Docs: https://volstrata.com/docs/api-catalog
      https://volstrata.com/docs/api-base-url

    python rest/market.py

Seven capabilities, all GET, all in one domain:

    market.status            GET /api/v1/market/status            per-ticker state
    market.overview          GET /api/v1/market/overview          the board
    market.rotations         GET /api/v1/market/rotations         sector movement
    market.snapshot          GET /api/v1/market/snapshot          quick quotes
    market.candles           GET /api/v1/market/candles           a price series
    market.seasonality       GET /api/v1/market/seasonality       calendar aggregates
    market.etf_constituents  GET /api/v1/market/etf_constituents  index membership

Two contract details this domain shows off:

  * Not every response carries `ok`. market.snapshot does not. Never test a
    response body for success -- the HTTP status is the source of truth, which
    is why volstrata_helpers checks it before it parses anything.
  * A `tickers` parameter takes a comma-separated list or a named set
    (market.snapshot accepts "core"), while `ticker` is singular. Read which one
    an operation declares; they are not interchangeable.

Seven sequential requests. Some may want a credential; each one that does says
so and the file keeps going.
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
    show,
)


def quotes() -> None:
    """market.snapshot: a compact quote row per ticker, plus a freshness block.

        {"tickers": [{"symbol": "$SPX", "label": "...", "last": <price>,
                      "chg": <change>, "pct": <percent>,
                      "t": <unix>, "quote_t": <unix>}, ...],
         "freshness": {"as_of": <unix>, "age_seconds": <n>, "session": "closed",
                       "market_open": false, "stale": false, ...}}

    `t` is when the row was assembled and `quote_t` is when the quote itself was
    stamped; they are not always the same number and the difference is the age
    of what you are looking at. `session` and `market_open` in the freshness
    block save you from reimplementing a market calendar to decide whether a
    stale-looking number is actually fine.
    """
    heading("market.snapshot -- quotes for a named set")
    data = get("/market/snapshot", tickers="core")
    rows = data.get("tickers") or []
    row("rows", len(rows))
    for item in rows[:6]:
        print("  {0:<8} {1:<26} last={2} chg={3} pct={4}".format(
            item.get("symbol", "?"),
            (item.get("label") or "")[:26],
            item.get("last"),
            item.get("chg"),
            item.get("pct"),
        ))
    fresh = data.get("freshness") or {}
    row("session", fresh.get("session"))
    row("market_open", fresh.get("market_open"))
    row("freshness", describe_freshness(data))


def candles() -> None:
    """market.candles returns a price series and its length.

        {"ticker": "SPX", "n": <count>, "series": [<price>, ...], "t": <unix>}

    Parameters: ticker, tf (timeframe), from, to, limit, cursor. `limit` is a
    request, not a promise -- read `n`, or len(series), rather than assuming.
    This is one of the 17 operations that declare a cursor, so a long range can
    be walked page by page with the pattern in pagination.py.
    """
    heading("market.candles -- a price series")
    data = get("/market/candles", ticker="SPX", tf="1d", limit=10)
    row("ticker", data.get("ticker"))
    row("n", data.get("n"))
    series = data.get("series") or []
    row("points returned", len(series))
    if series:
        row("first / last", "{0} / {1}".format(series[0], series[-1]))
    if data.get("next_cursor"):
        row("next_cursor", "present -- more available")


def board_and_rotations() -> None:
    """Three capabilities that describe the wider tape rather than one symbol.

    market.status takes `tickers` (comma-separated) and `fresh_within_sec`;
    market.overview takes nothing; market.rotations takes a timeframe `tf`.

    All three sit at the Free floor in the catalog and want an authenticated
    principal in practice, so anonymously you will see 401 auth_required here
    and the file will carry on. That combination -- Free floor, credential
    required -- is exactly why meta.access exists: ask, do not assume.
    """
    heading("market.status -- per-ticker state")
    status = attempt("market.status", get, "/market/status", tickers="SPX,NDX")
    if status is not None:
        show(status, max_items=3, max_chars=900)

    heading("market.overview -- the board")
    overview = attempt("market.overview", get, "/market/overview")
    if overview is not None:
        row("top-level keys", ", ".join(sorted(overview)[:14]))

    heading("market.rotations -- sector movement")
    rotations = attempt("market.rotations", get, "/market/rotations", tf="1d")
    if rotations is not None:
        row("top-level keys", ", ".join(sorted(rotations)[:14]))


def seasonality() -> None:
    """market.seasonality returns calendar aggregates, no ticker required.

        {"ok": true, "available": true,
         "seasonality": {"history_from": "YYYY-MM-DD",
                         "month_curve": [{"month": <1-12>, "avg": <n>,
                                          "median": <n>, "hit_rate": <fraction>}, ...],
                         "dow_month": [[...], ...]}}

    `dow_month` is a matrix: one row per weekday, one column per month.
    `hit_rate` is a fraction between 0 and 1. Check `available` before you read
    the block -- it can be false, in which case there is nothing under it.
    """
    heading("market.seasonality -- calendar aggregates")
    data = get("/market/seasonality")
    row("available", data.get("available"))
    block = data.get("seasonality") or {}
    row("history_from", block.get("history_from"))
    curve = block.get("month_curve") or []
    row("month_curve points", len(curve))
    for point in curve[:3]:
        print("  month {0}: avg={1} median={2} hit_rate={3}".format(
            point.get("month"), point.get("avg"),
            point.get("median"), point.get("hit_rate")))
    matrix = block.get("dow_month") or []
    if matrix and isinstance(matrix[0], list):
        row("dow_month", "{0} rows x {1} columns".format(len(matrix), len(matrix[0])))


def etf_constituents() -> None:
    """market.etf_constituents lists what an index ETF is made of.

        {"ok": true, "sym": "SPY", "name": "...",
         "constituents": [{"ticker": "...", "name": "...", "sector": "...",
                           "rank": <n>, "net_gex_bn": <n>,
                           "share_of_tracked": <fraction>, "polled": true}, ...],
         "covered_count": <n>, "not_covered_count": <n>, "universe_count": <n>,
         "etf_net_gex_bn": <n>, "stale": false, "supported": true,
         "gaps": ["...", ...]}

    Two counts worth reading before the rows: `universe_count` is the whole
    membership and `covered_count` is how much of it this response has numbers
    for. `gaps` is a list of plain-English caveats about the difference. A
    response that quietly omits what it does not know is harder to use than one
    that says so.
    """
    heading("market.etf_constituents -- index membership")
    data = get("/market/etf_constituents", ticker="SPY")
    row("sym", data.get("sym"))
    row("name", data.get("name"))
    row("universe_count", data.get("universe_count"))
    row("covered_count", data.get("covered_count"))
    row("not_covered_count", data.get("not_covered_count"))
    row("stale", data.get("stale"))
    rows = data.get("constituents") or []
    row("constituents", len(rows))
    for item in rows[:5]:
        print("  #{0:<4} {1:<6} {2:<26} sector={3}".format(
            str(item.get("rank")),
            item.get("ticker", "?"),
            (item.get("name") or "")[:26],
            item.get("sector"),
        ))
    for note in (data.get("gaps") or [])[:2]:
        print("  gap: {0}".format(note[:110]))


def main() -> int:
    print("VolStrata: the market domain -- https://volstrata.com")
    key_banner()
    exit_code = run_examples((
        ("quotes", quotes),
        ("candles", candles),
        ("board and rotations", board_and_rotations),
        ("seasonality", seasonality),
        ("etf constituents", etf_constituents),
    ))
    heading("Next")
    print("  rest/levels.py                  the daily and weekly level products")
    print("  rest/calendar_news_social.py    what is scheduled and what is said")
    print("  Catalog: https://volstrata.com/docs/api-catalog")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
