"""Copyright 2026 Volstrata.com

The `levels` domain: the daily and weekly level products, and one capability
that hands you the same data in four formats.
Docs: https://volstrata.com/docs/api-catalog
      https://volstrata.com/docs/api-errors

    python rest/levels.py

Six capabilities:

    levels.day          GET /api/v1/levels/day          today's levels
    levels.week         GET /api/v1/levels/week         this week's levels
    levels.day_report   GET /api/v1/levels/day_report   the daily write-up
    levels.week_report  GET /api/v1/levels/week_report  the weekly write-up
    levels.detail       GET /api/v1/levels/detail       one level, in depth
    levels.tradingview  GET /api/v1/levels/tradingview  json | txt | pine | csv

The error lesson lives here. These capabilities can answer

    404 {"code": "not_found", "detail": "..."}

which is NOT the same as

    404 {"code": "route_not_found", ...}

`route_not_found` means you got the URL wrong -- a bug in your client that will
never fix itself. Plain `not_found` means the route is right and there is simply
nothing to return for that ticker at that moment; the same request can succeed
later. Treat them differently: alert on the first, retry later on the second.

Seven sequential requests -- the last capability is asked twice, once for JSON
and once for CSV -- and a 404 is a legitimate outcome for several of them.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from volstrata_helpers import (  # noqa: E402  (import after the path fix, on purpose)
    VolstrataError,
    attempt,
    call,
    get,
    heading,
    key_banner,
    row,
    run_examples,
    show,
)

TICKER = "SPX"


def day_and_week() -> None:
    """levels.day and levels.week: the published level sets for a session.

    Both take `ticker` and `format`. When a set is available you get an object
    of named levels; when it is not you get a 404 `not_found` with a `detail`
    that says why. attempt() prints that line and returns None, which is why
    this function has no try/except of its own.
    """
    heading("levels.day")
    day = attempt("levels.day", get, "/levels/day", ticker=TICKER)
    if day is not None:
        row("top-level keys", ", ".join(sorted(day)[:14]))
        show(day, max_items=6, max_chars=900)

    heading("levels.week")
    week = attempt("levels.week", get, "/levels/week", ticker=TICKER)
    if week is not None:
        row("top-level keys", ", ".join(sorted(week)[:14]))


def reports() -> None:
    """The *_report capabilities return the same session as prose.

    Useful when the consumer is a person or a language model rather than a
    chart: one string you can post to a channel without formatting it yourself.
    """
    heading("levels.day_report")
    day = attempt("levels.day_report", get, "/levels/day_report", ticker=TICKER)
    if day is not None:
        row("top-level keys", ", ".join(sorted(day)[:14]))
        for key in ("report", "text", "summary", "body"):
            value = day.get(key)
            if isinstance(value, str):
                print("  {0}: {1}".format(key, value[:200].replace("\n", " ")))
                break

    heading("levels.week_report")
    week = attempt("levels.week_report", get, "/levels/week_report", ticker=TICKER)
    if week is not None:
        row("top-level keys", ", ".join(sorted(week)[:14]))


def one_level_in_depth() -> None:
    """levels.detail takes a level `kind` and returns its history and context.

    Parameters: ticker, kind (cw, pw, zg, mp, ...), days, strikes, format.

    Shape:

        {"ok": true, "ticker": "...", "kind": "cw", "kind_label": "Call Wall",
         "mode": "resistance", "days": <n>,
         "current": {"level": <price>, "spot": <price>, "distance": <n>,
                     "distance_pct": <fraction>, "side": "above", "as_of_t": <unix>},
         "history": [{"day": "YYYY-MM-DD", "t": <unix>,
                      "level": <price>, "spot": <price>}, ...],
         "respect": {"sessions": <n>, "respected": <n>, "pierced": <n>,
                     "crossings": <n>, "respect_pct": <fraction>,
                     "respect_label": "<what was counted>", ...},
         "composition": {"basis": "...", "primary": <price>,
                         "strikes": [{"strike": <price>, "rank": <n>,
                                      "is_primary": true, ...}, ...]}}

    `respect_label` is the response telling you in words what its own counts
    mean; render it next to `respect_pct` rather than inventing a caption. The
    `*_reason` fields (reason, history_reason, respect_reason) are null when a
    block is complete and carry an explanation when it is not.
    """
    heading("levels.detail -- one level, in depth")
    data = attempt("levels.detail", get, "/levels/detail", ticker=TICKER, kind="cw")
    if data is None:
        return
    row("kind", "{0} ({1})".format(data.get("kind"), data.get("kind_label")))
    row("mode", data.get("mode"))
    current = data.get("current") or {}
    row("level", current.get("level"))
    row("spot", current.get("spot"))
    row("distance", current.get("distance"))
    row("distance_pct", current.get("distance_pct"))
    row("side", current.get("side"))

    respect = data.get("respect") or {}
    if respect:
        row("sessions counted", respect.get("sessions"))
        row("respect_pct", respect.get("respect_pct"))
        row("respect_label", respect.get("respect_label"))

    history = data.get("history") or []
    row("history points", len(history))
    for point in history[:3]:
        print("    {0}  level={1}  spot={2}".format(
            point.get("day"), point.get("level"), point.get("spot")))

    composition = data.get("composition") or {}
    strikes = composition.get("strikes") or []
    row("composition.basis", composition.get("basis"))
    row("strikes listed", len(strikes))


def four_formats() -> None:
    """levels.tradingview is one capability with four representations.

    `format` accepts json, txt, pine and csv. The json form is the one to code
    against -- it carries the levels as data *and* the other three as strings:

        {"ok": true, "ticker": "...", "spot": <price>, "count": <n>,
         "levels": [{"label": "Call Wall", "price": <price>}, ...],
         "text": "...", "csv": "label,price\\n...", "pine": "//@version=5\\n..."}

    Ask for a non-JSON format and the body is that text rather than an object,
    so read `response.text` instead of parsing it. That is what call() is for:
    it hands back the checked Response, headers and all, and leaves the parsing
    to you.
    """
    heading("levels.tradingview -- json | txt | pine | csv")
    data = attempt("levels.tradingview", get, "/levels/tradingview", ticker=TICKER)
    if data is not None:
        row("count", data.get("count"))
        for item in (data.get("levels") or [])[:6]:
            print("    {0:<22} {1}".format(item.get("label", "?"), item.get("price")))
        csv_text = data.get("csv") or ""
        if csv_text:
            print("  csv, first line: {0}".format(csv_text.splitlines()[0]))
        pine = data.get("pine") or ""
        if pine:
            print("  pine, first line: {0}".format(pine.splitlines()[0]))

    # The same capability, asked for a different representation. One request,
    # and nothing is parsed as JSON.
    heading("The same call, asked for csv")
    try:
        response = call("/levels/tradingview", params={"ticker": TICKER, "format": "csv"})
    except VolstrataError as exc:
        print("  csv form unavailable: {0}".format(exc))
        return
    row("content-type", response.headers.get("Content-Type"))
    first = (response.text or "").splitlines()[:3]
    for line in first:
        print("    {0}".format(line))


def main() -> int:
    print("VolStrata: the levels domain -- https://volstrata.com")
    key_banner()
    exit_code = run_examples((
        ("day and week", day_and_week),
        ("reports", reports),
        ("one level in depth", one_level_in_depth),
        ("four formats", four_formats),
    ))
    heading("Next")
    print("  rest/gex_levels.py   the intraday levels map these are built around")
    print("  auth_and_errors.py   every refusal code, one file")
    print("  Errors: https://volstrata.com/docs/api-errors")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
