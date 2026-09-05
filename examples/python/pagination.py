"""Copyright 2026 Volstrata.com

Cursor pagination, done once, correctly.
Docs: https://volstrata.com/docs/api-base-url

    python pagination.py

One collection is paged to completion under a page bound. The endpoint used here
is the capability catalog itself (GET /api/v1/meta/capabilities), because it is
public, it is genuinely long, and paging it prints something you will want to
read anyway.

The contract, shared by every paged capability:

    GET /api/v1/<domain>/<name>?limit=25
        -> {"ok": true, "next_cursor": "<opaque>", ..., "<collection>": [...]}

    GET /api/v1/<domain>/<name>?limit=25&cursor=<opaque>
        -> the next page

    ... until "next_cursor": null

Three rules that are easy to get wrong:

  * A cursor is opaque. Pass the exact string back; never parse one, never build
    one, never assume it encodes an offset.
  * `next_cursor: null` is the only end-of-collection signal. An empty page is
    not a reliable one.
  * `limit` is a request, not a promise. The server clamps it to its own cap and
    the page you get back is whatever it decided to send.

17 of the published operations declare a cursor parameter. The rest return
everything they have in one response.
"""

import sys

from volstrata_helpers import (
    VolstrataError,
    heading,
    key_banner,
    paginate,
    row,
    show,
)

# Bound every loop that talks to a live API. 175 rows at 25 a page is 7
# requests; 12 leaves headroom if the catalog grows, and still guarantees this
# program stops.
MAX_PAGES = 12

PAGE_SIZE = 25


def main() -> int:
    print("VolStrata pagination -- https://volstrata.com")
    key_banner()

    heading("Paging GET /api/v1/meta/capabilities?limit={0}".format(PAGE_SIZE))

    rows = []
    pages = 0
    pending_cursor = None

    try:
        # paginate() is the generator in volstrata_helpers: it issues one GET per
        # page, follows next_cursor, and stops at the bound or at a null cursor.
        for page in paginate("/meta/capabilities", max_pages=MAX_PAGES, limit=PAGE_SIZE):
            pages += 1
            batch = page.get("capabilities") or []
            rows.extend(batch)
            pending_cursor = page.get("next_cursor")

            # The paged envelope is {ok, next_cursor, limit, total, <collection>}.
            # Not every capability populates all of the counters -- this one
            # reports `count` -- so read them defensively and rely on
            # next_cursor, which is always there.
            print("  page {0:>2}  rows={1:<3} next_cursor={2}".format(
                pages,
                len(batch),
                "null (last page)" if not pending_cursor else repr(pending_cursor),
            ))
            for counter in ("limit", "total", "count"):
                if counter in page and pages == 1:
                    row("  envelope " + counter, page[counter])
    except VolstrataError as exc:
        # A 400 `invalid_cursor` is what you get for a hand-edited cursor.
        print("  Paging stopped: {0}".format(exc))
        return 0

    heading("Result")
    row("pages fetched", pages)
    row("rows collected", len(rows))
    row("stopped because", "next_cursor was null" if not pending_cursor
        else "the {0}-page bound was reached".format(MAX_PAGES))
    if pending_cursor:
        print("  There is more to read. Resume from the cursor above rather than")
        print("  starting over -- that is what cursors are for.")

    # The catalog rows are the same shape the MCP tool list is projected from:
    # a dotted capability name, its HTTP method and path, its parameters, and
    # the plan floor as both a slug and a customer-facing name.
    if rows:
        heading("One row, in full")
        show(rows[0])

        heading("First few capabilities")
        for item in rows[:8]:
            print("  {0:<28} {1:<5} {2:<34} {3}".format(
                item.get("name", "?"),
                item.get("method", "?"),
                item.get("path", "?"),
                item.get("tier_name", "?"),
            ))

    print("\n  Same pattern, other collections: market.candles, news.feed,")
    print("  calendar.events, insider.filings, social.sentiment.")
    print("  Reference: https://volstrata.com/docs/api-base-url")
    return 0


if __name__ == "__main__":
    sys.exit(main())
