"""Copyright 2026 Volstrata.com

The `calendar`, `news`, `insider` and `social` domains: the list-shaped,
cursor-paged half of the surface.
Docs: https://volstrata.com/docs/api-catalog
      https://volstrata.com/docs/api-keys

    python rest/calendar_news_social.py

Eight capabilities, all GET, all collections:

    calendar.combined    GET /api/v1/calendar/combined    scheduled events, merged
    calendar.events      GET /api/v1/calendar/events      macro events
    calendar.corporate   GET /api/v1/calendar/corporate   company events
    news.feed            GET /api/v1/news/feed            headlines
    insider.filings      GET /api/v1/insider/filings      filed transactions
    social.sentiment     GET /api/v1/social/sentiment     per-ticker readings
    social.tallies       GET /api/v1/social/tallies       aggregate counts
    social.influencers   GET /api/v1/social/influencers   account-level rollup

Every one of them is at the Free floor in the catalog AND wants an authenticated
principal, so with no VOLSTRATA_API_KEY set each call answers

    401 {"code": "auth_required", ...}

and this file prints that and moves on. Any accepted credential clears it -- the
refusal is about having a principal, not about a plan. If you want to know which
capabilities your own credential can run, ask: GET /api/v1/meta/access, which
discover_capabilities.py prints.

Six of the eight share the cursor contract (`limit`, `cursor`, `next_cursor`)
with the rest of the paged surface, so once you can call one you can call those
with the same loop -- see pagination.py. `social.tallies` and
`social.influencers` are aggregates and take sample-size parameters instead of a
cursor, which is a good reason to read an operation's declared parameters in the
spec rather than assuming the family behaves alike.

Eight sequential requests, one page each.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from volstrata_helpers import (  # noqa: E402  (import after the path fix, on purpose)
    attempt,
    get,
    heading,
    key_banner,
    row,
    run_examples,
    show,
)

# One page each. These run against live production and the point is the shape,
# not the volume.
PAGE_SIZE = 5


def _collection(payload):
    """Find the list in a paged response without hard-coding its key.

    Every paged envelope carries {ok, next_cursor, ...} plus exactly one
    collection, named for the thing it holds (events, items, filings, rows...).
    In your own code, look the name up once in the spec and use it directly;
    this generic version exists so one function can summarise eight endpoints.
    """
    best_key, best_rows = None, None
    for key, value in payload.items():
        if isinstance(value, list) and (best_rows is None or len(value) > len(best_rows)):
            best_key, best_rows = key, value
    return best_key, (best_rows or [])


ANSWERED = []


def _one_page(label: str, path: str, **params) -> None:
    """Fetch one page of a collection and summarise it, or report the refusal."""
    heading(label)
    payload = attempt(label, get, path, **params)
    if payload is None:
        return
    ANSWERED.append(label)
    key, rows = _collection(payload)
    row("collection", key)
    row("rows on this page", len(rows))
    row("next_cursor", payload.get("next_cursor") or "null (last page)")
    for counter in ("total", "count", "limit"):
        if counter in payload:
            row(counter, payload[counter])
    if rows:
        print("  First row:")
        show(rows[0], max_items=4, max_chars=700)


def calendars() -> None:
    """Three calendars, one shape.

    calendar.combined merges the other two, and takes `range` (7d, 30d, ...),
    `types`, `ticker`, `limit` and `cursor`. calendar.events adds
    `importance_min` and `region`; calendar.corporate is company-scoped and
    defaults to a 30-day range.

    Prefer `combined` unless you specifically need one kind: one request, one
    cursor, one merged ordering.
    """
    _one_page("calendar.combined", "/calendar/combined", range="7d", limit=PAGE_SIZE)
    _one_page("calendar.events", "/calendar/events", range="7d", limit=PAGE_SIZE)
    _one_page("calendar.corporate", "/calendar/corporate", range="30d", limit=PAGE_SIZE)


def news_and_filings() -> None:
    """news.feed and insider.filings: two collections, same cursor contract.

    news.feed takes an optional `ticker` -- omit it for everything, pass it to
    narrow. insider.filings takes `ticker` and `form` (default "4").

    Both are ordered newest first, so a client that polls should remember the
    newest item it has seen and stop reading when it reaches it, rather than
    re-reading a page every time. And poll on a timer you chose, not in a loop:
    rate limits are per owner and shared across every key you own.
    """
    _one_page("news.feed", "/news/feed", limit=PAGE_SIZE)
    _one_page("insider.filings", "/insider/filings", form="4", limit=PAGE_SIZE)


def social() -> None:
    """Three views of the same social data set, at three levels of aggregation.

    social.sentiment is per ticker and cursor-paged (`ticker`, `limit`,
    `cursor`). social.tallies is an aggregate (`top`, `min_posts`).
    social.influencers rolls up by account over a window (`hours`, `min`).

    `min_posts` and `min` are sample-size floors: raise them and thin rows drop
    out. A rate computed over three posts is not a rate, and the parameters are
    there so you can say what you consider enough.
    """
    _one_page("social.sentiment", "/social/sentiment", limit=PAGE_SIZE)
    _one_page("social.tallies", "/social/tallies", top=PAGE_SIZE)
    _one_page("social.influencers", "/social/influencers", hours=48)


def main() -> int:
    print("VolStrata: calendar, news and social -- https://volstrata.com")
    key_banner()
    exit_code = run_examples((
        ("calendars", calendars),
        ("news and filings", news_and_filings),
        ("social", social),
    ))
    if not ANSWERED:
        # Nothing answered, so the reader has seen eight refusals and no shape.
        # Here is the shape, written out by hand -- illustrative values, not a
        # captured response.
        heading("What a page looks like when it answers")
        print("""  {
    "ok": true,
    "next_cursor": "<opaque string, or null on the last page>",
    "limit": 5,
    "total": 128,
    "events": [
      {"id": "<opaque>", "ts": 1700000000, "ticker": "EXMPL",
       "title": "<one line>", "importance": 2, "kind": "<type>"}
    ]
  }""")
        print("  The keys that matter to your loop are `next_cursor` and the one")
        print("  collection. Everything else is domain detail. pagination.py runs")
        print("  the identical loop against a collection that needs no credential.")

    heading("Next")
    print("  pagination.py               the cursor loop, in full")
    print("  discover_capabilities.py    what your credential unlocks")
    print("  Keys: https://volstrata.com/api-keys")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
