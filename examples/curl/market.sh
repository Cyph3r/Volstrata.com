#!/usr/bin/env sh
# Copyright 2026 Volstrata.com - https://volstrata.com
#
# Market context: session state, breadth, a multi-ticker snapshot, candles and
# the two symbol lookups - every one at the Free plan floor, and the file where
# the freshness and delivery contracts are explained.
# Docs: https://volstrata.com/docs/api-rate-limits
#
# Run it:
#     sh examples/curl/market.sh [TICKER]      # default SPX
#
# Requests: 7. That is most of an anonymous minute's allowance (10/min), so run
# this one on its own rather than immediately after another script.

set -eu

VS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$VS_DIR/_common.sh"

TICKER="${1:-SPX}"

vs_title "market context - $TICKER"
vs_auth_status

vs_note ''
vs_note 'Every capability called here is published at the Free plan floor. That'
vs_note 'is a statement about plans, not about credentials: a few of these data'
vs_note 'endpoints ask for any valid key even at the Free floor, and answer 401'
vs_note 'auth_required when there is not one. Running this script without a key'
vs_note 'shows you exactly which, on the day you run it - and the script prints'
vs_note 'and explains each refusal instead of stopping at it.'

# ---------------------------------------------------------------------------
# 1. market.status - is the session open, and how old is what you are about to
#    read. The cheapest call on the API and a sensible first call in any client.
# ---------------------------------------------------------------------------
vs_call 'market.status - session state and data age' \
  '/api/v1/market/status' "tickers=$TICKER" \
  "$VS_SUM"

vs_note ''
vs_note 'Two additive blocks appear on reads that feed a live view, and they'
vs_note 'answer different questions:'
vs_note ''
vs_note '  freshness {as_of, age_seconds, live, stale, stale_after_seconds}'
vs_note '            how old this body is. `live` is `not stale`. An unknown'
vs_note '            timestamp is reported honestly as stale, never as fresh.'
vs_note ''
vs_note '  delivery  {mode, delay_seconds, reason}'
vs_note '            WHY it is delayed, if it is. mode is "live" or "delayed";'
vs_note '            reason is "plan_tier", "source_delay" or null.'
vs_note ''
vs_note 'delay_seconds is null when the magnitude is unknown and 0 when the body'
vs_note 'really is realtime - so test for null explicitly, never for falsiness.'
vs_note 'A frame can be perfectly fresh for its lane and still be delivered'
vs_note 'delayed because of the plan the caller is on.'

# ---------------------------------------------------------------------------
# 2. market.overview - the broad picture, no parameters.
# ---------------------------------------------------------------------------
vs_call 'market.overview - broad market view' \
  '/api/v1/market/overview' '' \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 3. market.snapshot - several tickers in one call. `tickers` accepts a named
#    set ("core" is the documented default) or a comma-separated list.
# ---------------------------------------------------------------------------
vs_call 'market.snapshot - the core set in one call' \
  '/api/v1/market/snapshot' 'tickers=core' \
  "$VS_SUM"

vs_note ''
vs_note "Or name your own:  ?tickers=$TICKER,QQQ,IWM"
vs_note 'One call for several tickers is the difference between staying inside'
vs_note 'your per-minute ceiling and not.'

# ---------------------------------------------------------------------------
# 4. market.candles - a cursor-paged OHLC series. tf= is the timeframe;
#    from=/to= bound it. Kept to 5 bars here.
# ---------------------------------------------------------------------------
vs_call 'market.candles - 5 one-minute bars' \
  '/api/v1/market/candles' "ticker=$TICKER&tf=1m&limit=5" \
  "$VS_SUM"

vs_note ''
vs_note 'This one is cursor-paged: follow next_cursor exactly as pagination.sh'
vs_note 'does. Ask for a wider window with from= and to= rather than paging'
vs_note 'through thousands of bars one page at a time.'

# ---------------------------------------------------------------------------
# 5. market.rotations - relative movement across groups, over a timeframe.
# ---------------------------------------------------------------------------
vs_call 'market.rotations - group rotation over 1 day' \
  '/api/v1/market/rotations' 'tf=1d' \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 6. symbol.search - free-text lookup. `q` is required.
# ---------------------------------------------------------------------------
vs_call 'symbol.search - find a symbol by name or fragment' \
  '/api/v1/symbol/search' 'q=apple&limit=5' \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 7. symbol.resolve - turn one user-typed string into the canonical symbol the
#    rest of the API expects. `symbol` is required.
# ---------------------------------------------------------------------------
vs_call 'symbol.resolve - canonicalise one symbol' \
  '/api/v1/symbol/resolve' "symbol=$TICKER" \
  "$VS_SUM"

vs_note ''
vs_note 'Resolve once, then cache the result. Passing a symbol the API does not'
vs_note 'recognise to a data capability gets you a refusal with a "detail" that'
vs_note 'names the parameter, which is a slower way to learn the same thing.'

vs_title 'Also Free in this domain'
vs_note 'market.seasonality       ?format=json'
vs_note 'market.etf_constituents  ?ticker=SPY'
vs_note ''
vs_note 'Left out of the run above only to keep this script inside a single'
vs_note 'minute of the anonymous rate-limit ceiling. Add them when you need them:'
vs_note ''
vs_note "  curl -sS -H 'User-Agent: volstrata-examples/1.0' \\"
vs_note "    '$BASE/api/v1/market/etf_constituents?ticker=SPY'"
vs_note ''
vs_note 'Rate limits: https://volstrata.com/docs/api-rate-limits'

vs_footer
exit 0
