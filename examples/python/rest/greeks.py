"""Copyright 2026 Volstrata.com

The `greeks` and `vol` domains, and what a plan floor looks like from a client.
Docs: https://volstrata.com/docs/api-catalog
      https://volstrata.com/docs/api-auth

    python rest/greeks.py

Four capabilities, two open and two gated on purpose:

    greeks.gamma   GET /api/v1/greeks/gamma    per-strike gamma exposure
    vol.iv         GET /api/v1/vol/iv          at-the-money implied vol
    greeks.charm   GET /api/v1/greeks/charm    above the lowest floor
    vol.surface    GET /api/v1/vol/surface     above the lowest floor

The open two also carry the two shared blocks worth understanding once, because
they appear across the surface:

    freshness  {as_of, age_seconds, live, stale, stale_after_seconds}
    delivery   {mode: "live"|"delayed", delay_seconds, reason}

`delivery.reason` is "plan_tier" when the delay is a function of your plan and
"source_delay" when it is not, so a client can tell "upgrade to fix this" from
"nobody has it faster". `delay_seconds` is 0 when the body really is realtime and
null when it is delayed by an amount the server cannot state -- never coerce null
to 0, and branch on None explicitly.

Four sequential requests. Two of them are expected to be refused.
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

TICKER = "SPX"


def gamma_by_strike() -> None:
    """greeks.gamma returns the per-strike series plus the scalars around it.

    Shape:

        {"greek": "gamma",
         "strikes": [<strike>, <strike>, ...],   the strike axis
         "bars": [[<value>, <strike>], ...],     value first, strike second
         "window": [<low>, <high>],              the strike window covered
         "net_bn": <number>,                     magnitude in billions
         "peak_pos_strike": ..., "peak_neg_strike": ...,
         "regime": "...", "regime_basis": "...",
         "spot": ..., "ts": ..., "updated": "...",
         "freshness": {...}, "delivery": {...}}

    `strikes` and `bars` are two views of the same axis: use `bars` when you want
    a value and its strike together, `strikes` when you only need the axis. Mind
    the order inside a bar -- the value comes first and the strike second, which
    is the opposite of what most people assume on sight.
    """
    heading("greeks.gamma -- per-strike gamma exposure")
    data = get("/greeks/gamma", ticker=TICKER)
    row("greek", data.get("greek"))
    row("spot", data.get("spot"))
    row("net_bn", data.get("net_bn"))
    row("peak_pos_strike", data.get("peak_pos_strike"))
    row("peak_neg_strike", data.get("peak_neg_strike"))
    row("regime", data.get("regime"))
    row("regime_basis", data.get("regime_basis"))
    row("window", data.get("window"))
    bars = data.get("bars") or []
    row("bars", "{0} [value, strike] pairs".format(len(bars)))
    if bars:
        show(bars[:3])
    strikes = data.get("strikes") or []
    if strikes:
        row("strike axis", "{0} points, {1} .. {2}".format(
            len(strikes), strikes[0], strikes[-1]))
    row("freshness", describe_freshness(data))
    print("  A `delivery.mode` of 'delayed' with reason 'plan_tier' means the")
    print("  same call on a higher plan returns a fresher frame, not more fields.")


def implied_vol() -> None:
    """vol.iv is the compact implied-volatility read.

        {"atm_iv_today": <fraction>, "atm_iv_weekly": <fraction>,
         "iv_axis": [<low>, <high>],
         "surface": {"has_weekly": true, "smile0_points": <n>, "smile1_points": <n>},
         "spot": ..., "ts": ..., "updated": "...",
         "freshness": {...}, "delivery": {...}}

    Values are decimal fractions, not percentages: 0.14 is 14%. `surface` is a
    description of what the fuller surface capability would return for this
    moment -- point counts and whether a weekly smile exists -- not the surface
    itself.
    """
    heading("vol.iv -- at-the-money implied volatility")
    data = get("/vol/iv", ticker=TICKER)
    row("atm_iv_today", data.get("atm_iv_today"))
    row("atm_iv_weekly", data.get("atm_iv_weekly"))
    row("iv_axis", data.get("iv_axis"))
    row("surface", data.get("surface"))
    row("freshness", describe_freshness(data))


def gated_charm() -> None:
    """greeks.charm sits above the lowest floor. Catch, report, continue.

    The `greeks` domain publishes eleven capabilities and gamma is the one at
    the Free floor; the higher-order greeks sit above it. Discover which is
    which at runtime rather than hard-coding a list:

        GET /api/v1/meta/access   -> {"unlocked": [...], "locked": [...]}
        each locked row carries min_tier / min_tier_name

    discover_capabilities.py prints exactly that.
    """
    heading("greeks.charm -- gated")
    data = attempt("greeks.charm", get, "/greeks/charm", ticker=TICKER)
    if data is None:
        print("  Expected without the plan. The refusal names what would clear it.")
        return
    row("keys", ", ".join(sorted(data)[:12]))
    row("freshness", describe_freshness(data))


def gated_surface() -> None:
    """vol.surface is the full surface, and also above the lowest floor.

    Note the parameters it declares (ticker, window, expiry, format): a gated
    capability is fully described in the public spec even when your plan cannot
    call it, so you can build against it before you buy it.
    """
    heading("vol.surface -- gated")
    data = attempt("vol.surface", get, "/vol/surface", ticker=TICKER)
    if data is None:
        print("  Its parameters are still public: GET /api/openapi.json documents")
        print("  every operation regardless of your plan.")
        return
    row("keys", ", ".join(sorted(data)[:12]))


def main() -> int:
    print("VolStrata: greeks and vol -- https://volstrata.com")
    key_banner()
    exit_code = run_examples((
        ("gamma by strike", gamma_by_strike),
        ("implied vol", implied_vol),
        ("charm (gated)", gated_charm),
        ("surface (gated)", gated_surface),
    ))
    heading("Next")
    print("  rest/gex_levels.py   the levels these greeks sit behind")
    print("  auth_and_errors.py   the refusal envelope in full")
    print("  Plans and keys: https://volstrata.com/api-keys")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
