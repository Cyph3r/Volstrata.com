"""Copyright 2026 Volstrata.com

The `gex` domain: named price levels, per-strike bars and scalar metrics.
Docs: https://volstrata.com/docs/api-catalog

    python rest/gex_levels.py

Seven capabilities, six of which answer without a key:

    gex.levels        GET /api/v1/gex/levels        the named levels map
    gex.named_levels  GET /api/v1/gex/named_levels  the same levels, labelled
    gex.metrics       GET /api/v1/gex/metrics       scalars in one response
    gex.gamma_flip    GET /api/v1/gex/gamma_flip    one level plus the regime
    gex.maxpain       GET /api/v1/gex/maxpain       one level plus the distance
    gex.bars          GET /api/v1/gex/bars          per-strike series
    gex.snapshot      GET /api/v1/gex/snapshot      above the lowest floor

Every one of them takes `ticker` (default SPX) and `format` (default json), and
every one returns `spot`, `ts` and `updated` so you can tell what moment you are
looking at. This file explains what the fields are, not how they are produced --
for the definitions, read GET /api/v1/docs/metric?metric=<name> or the glossary
linked from the catalog page above.

Seven sequential requests. No concurrency, no polling.
"""

import os
import sys

# Make `python rest/gex_levels.py` work from any working directory by putting
# the examples/python folder (the parent of this one) on the import path.
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

TICKER = "SPX"


def named_levels() -> None:
    """gex.levels returns a flat map of level keys; gex.named_levels labels them.

    The short keys (cw, pw, zg, mp, emHigh, emLow, hvl, ...) are stable
    identifiers meant for code. The labelled form is the same numbers keyed by
    display name, which is what you want for a chart legend or a message. Pick
    one and stay with it.

    Any level can be null when it is not defined for the current session, so
    read with .get() and handle None rather than indexing straight in.
    """
    heading("gex.levels -- the levels map")
    data = get("/gex/levels", ticker=TICKER)
    row("ticker", data.get("ticker"))
    row("spot", data.get("spot"))
    row("updated", data.get("updated"))
    levels = data.get("levels") or {}
    for key in ("cw", "pw", "zg", "mp", "emHigh", "emLow", "hvl"):
        if key in levels:
            row(key, levels[key])
    row("keys in map", len(levels))
    print("  Some entries are a two-element pair rather than a single number")
    print("  (cwLine, pwLine, and each value under `orb`, which is keyed by an")
    print("  interval in minutes). Those keys are pairs, not scalars.")

    heading("gex.named_levels -- the same numbers, labelled")
    labelled = get("/gex/named_levels", ticker=TICKER)
    named = labelled.get("named_levels") or {}
    for label in sorted(named):
        row(label, named[label])
    print("  Same response also carries the short-key `levels` map, so one call")
    print("  can feed both a chart and a human-readable summary.")


def scalars() -> None:
    """gex.metrics is the one-call version: the scalars, without the series.

    Reach for this when you want a row in a table rather than a chart. Names are
    snake_case here (call_wall, put_wall, em_high) where the levels map uses
    short camelCase keys -- the same quantity, two response shapes, because the
    two capabilities serve different consumers.

    `net_gex_bn` is a magnitude in billions; `net_gex` may be null when the raw
    figure is not carried on the response. `regime_basis` names which test
    produced `regime`, so log it alongside the value: two capabilities can
    report a different basis for the same instant, and the field tells you why.
    """
    heading("gex.metrics -- scalars in one response")
    data = get("/gex/metrics", ticker=TICKER)
    for field in ("call_wall", "put_wall", "zg", "mp", "em_high", "em_low",
                  "net_gex_bn", "net_dex", "atm_iv_today", "skew_today",
                  "regime", "regime_basis"):
        if field in data:
            row(field, data[field])


def single_level_calls() -> None:
    """Two capabilities that answer one question each.

    Small, cheap responses are worth using: a bot that only needs max pain
    should not fetch and discard a whole strike series to get it.
    """
    heading("gex.gamma_flip")
    flip = get("/gex/gamma_flip", ticker=TICKER)
    row("gamma_flip", flip.get("gamma_flip"))
    row("spot", flip.get("spot"))
    row("regime", flip.get("regime"))
    row("regime_basis", flip.get("regime_basis"))

    heading("gex.maxpain")
    pain = get("/gex/maxpain", ticker=TICKER)
    row("max_pain", pain.get("max_pain"))
    row("spot", pain.get("spot"))
    row("updated", pain.get("updated"))


def strike_series() -> None:
    """gex.bars is the per-strike view: several parallel series, one shape.

    Each series is a list of two-element pairs, ordered VALUE FIRST and strike
    second, already sorted by strike:

        "bars": {"oi": [[<value>, <strike>], ...], "vol": [...], ...}

    Check that order in your own reader before you plot anything -- a chart with
    the axes swapped still renders, it is just wrong. The keys are the
    weighting: open interest, volume, and the long/short split of each. Plot
    one, or difference two; the response gives you the numbers, not a chart.

    This response also embeds the same `levels` map as gex.levels, so a chart
    can draw bars and level lines from a single request.
    """
    heading("gex.bars -- per-strike series")
    data = get("/gex/bars", ticker=TICKER)
    bars = data.get("bars") or {}
    row("series available", ", ".join(sorted(bars)))
    row("regime", data.get("regime"))
    row("regime_basis", data.get("regime_basis"))
    oi = bars.get("oi") or []
    row("oi points", len(oi))
    if oi:
        strikes = [pair[1] for pair in oi if isinstance(pair, list) and len(pair) > 1]
        if strikes:
            row("strike range", "{0} .. {1}".format(min(strikes), max(strikes)))
        print("  First three [value, strike] pairs:")
        show(oi[:3])


def gated_snapshot() -> None:
    """gex.snapshot is the composite view, and it sits above the lowest floor.

    The catalog lists its floor as the Edge plan (`x-plan-tier-name` in the
    spec, `tier_name` in meta.capabilities). Anonymously you get 401
    auth_required; with a credential below the floor you get a 402 whose body
    names the plan in `required_plan_name`.

    attempt() prints whichever refusal arrived and returns None, so this file
    still finishes cleanly for a reader who is not entitled to it. That is the
    pattern to copy: check, report, carry on -- do not retry, because the answer
    will not change.
    """
    heading("gex.snapshot -- the gated path")
    data = attempt("gex.snapshot", get, "/gex/snapshot", ticker=TICKER)
    if data is None:
        print("  Plan floors and what clears them: https://volstrata.com/api-keys")
        return
    row("ok", data.get("ok"))
    row("top-level keys", ", ".join(sorted(data)[:12]))


def main() -> int:
    print("VolStrata: the gex domain -- https://volstrata.com")
    key_banner()
    exit_code = run_examples((
        ("named levels", named_levels),
        ("scalars", scalars),
        ("single-level calls", single_level_calls),
        ("strike series", strike_series),
        ("gated snapshot", gated_snapshot),
    ))
    heading("Next")
    print("  rest/levels.py       the daily and weekly level products")
    print("  rest/greeks.py       the greeks behind these levels")
    print("  Catalog: https://volstrata.com/docs/api-catalog")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
