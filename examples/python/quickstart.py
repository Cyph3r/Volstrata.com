"""Copyright 2026 Volstrata.com

The shortest thing that works: one unauthenticated call to the VolStrata API.
Docs: https://volstrata.com/docs/api-examples

    python -m pip install requests
    python quickstart.py

No API key. No .env file. No account. `gex.levels` answers an anonymous caller,
so this runs the moment you have `requests` installed.

When you do have a key, export it and every example in this folder picks it up:

    export VOLSTRATA_API_KEY=...        # macOS / Linux
    $env:VOLSTRATA_API_KEY = "..."      # Windows PowerShell
"""

import sys

from volstrata_helpers import (
    API,
    VolstrataError,
    get,
    have_key,
    heading,
    row,
)


def main() -> int:
    print("VolStrata quickstart -- https://volstrata.com")
    print("Base: {0}".format(API))

    # GET /api/v1/gex/levels?ticker=SPX
    #
    # `ticker` defaults to SPX, so passing it is optional here. It is passed
    # explicitly because that is the habit you want in your own code.
    try:
        data = get("/gex/levels", ticker="SPX")
    except VolstrataError as exc:
        # Anything 4xx/5xx arrives as an RFC 9457 problem document, already
        # parsed. auth_and_errors.py walks through each kind.
        print("\nThe call was refused: {0}".format(exc))
        return 1

    # A successful response carries `ok: true` alongside the payload. Do not use
    # it as your success test: the HTTP status is the source of truth, and
    # volstrata_helpers.get() has already checked it before returning.
    heading("gex.levels")
    row("ok", data.get("ok"))
    row("ticker", data.get("ticker"))
    row("spot", data.get("spot"))
    row("updated", data.get("updated"))       # human-readable, exchange-local
    row("ts", data.get("ts"))                 # the same instant, unix seconds

    # `levels` is a flat map of named price levels. Every key is defined in the
    # public glossary; GET /api/v1/docs/metrics lists them, and
    # https://volstrata.com/docs/api-catalog documents the capability itself.
    # A key can be null when that level is not defined for the current session,
    # so read defensively rather than indexing straight in.
    levels = data.get("levels") or {}
    heading("A few named levels")
    for key in ("cw", "pw", "zg", "mp", "emHigh", "emLow"):
        if key in levels:
            row(key, levels[key])
    row("keys returned", len(levels))

    heading("Your setup")
    if have_key():
        print("  VOLSTRATA_API_KEY is set -- the call above was authenticated.")
        print("  Try auth_and_errors.py next to see what a key changes.")
    else:
        print("  No VOLSTRATA_API_KEY set. The call above ran anonymously.")
        print("  Issue a key at https://volstrata.com/api-keys when you want the")
        print("  capabilities behind a plan floor.")

    print("\nNext: python discover_capabilities.py   (what else is published)")
    print("      python auth_and_errors.py         (keys, errors, rate limits)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
