#!/usr/bin/env sh
# Copyright 2026 Volstrata.com - https://volstrata.com
#
# Greek and volatility reads: four Free capabilities, then two above the Free
# floor shown degrading into a clear, named refusal instead of a crash.
# Docs: https://volstrata.com/docs/api-keys
#
# Run it:
#     sh examples/curl/greeks.sh [TICKER]      # default SPX
#
# Requests: 6.

set -eu

VS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$VS_DIR/_common.sh"

TICKER="${1:-SPX}"

# Several capabilities in this group take a `window` parameter with a documented
# default of "today". It is spelled out here because it is the parameter most
# worth knowing about in this domain.
WINDOW="today"
Q="ticker=$TICKER&window=$WINDOW"

vs_title "greeks and volatility - $TICKER"
vs_auth_status

vs_note ''
vs_note 'Free in this file:   greeks.gamma, vol.iv, voloi.oi, voloi.volume'
vs_note 'Pro floor:           greeks.charm, vol.surface'
vs_note ''
vs_note 'The two Pro calls are here on purpose, and what they answer depends on'
vs_note 'what you are carrying:'
vs_note ''
vs_note '  no credential      401 auth_required - nothing to check the plan on'
vs_note '  key below Pro      a plan refusal naming required_plan_name'
vs_note '  key on Pro or up   the data'
vs_note ''
vs_note 'This script prints whichever it gets, explains it, and carries on. The'
vs_note 'run still ends successfully - that is how a gated call should behave in'
vs_note 'your own code too.'

# ---------------------------------------------------------------------------
# 1. greeks.gamma - Free.
# ---------------------------------------------------------------------------
vs_call 'greeks.gamma - gamma by strike' \
  '/api/v1/greeks/gamma' "ticker=$TICKER" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 2. vol.iv - Free. Implied-vol read for the same window.
# ---------------------------------------------------------------------------
vs_call 'vol.iv - implied volatility' \
  '/api/v1/vol/iv' "$Q" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 3. voloi.oi - Free. Open interest by strike.
# ---------------------------------------------------------------------------
vs_call 'voloi.oi - open interest' \
  '/api/v1/voloi/oi' "$Q" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 4. voloi.volume - Free. Traded volume by strike, same shape as voloi.oi, so
#    the two can be read side by side without reshaping either.
# ---------------------------------------------------------------------------
vs_call 'voloi.volume - traded volume' \
  '/api/v1/voloi/volume' "$Q" \
  "$VS_SUM"

vs_note ''
vs_note 'voloi.oi and voloi.volume answer in the same shape for the same window,'
vs_note 'which is what makes them comparable in one pass. There is a POST'
vs_note 'capability (voloi.combined, Edge floor) that returns both in one call;'
vs_note 'see valuation.sh for the POST-with-a-JSON-body pattern.'

# ---------------------------------------------------------------------------
# 5. greeks.charm - Pro floor.
# ---------------------------------------------------------------------------
vs_call 'greeks.charm - Pro floor, expected to refuse for most readers' \
  '/api/v1/greeks/charm' "$Q&at=latest" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 6. vol.surface - Pro floor. `expiry` is optional; omitted here.
# ---------------------------------------------------------------------------
vs_call 'vol.surface - Pro floor, expected to refuse for most readers' \
  '/api/v1/vol/surface' "$Q" \
  "$VS_SUM"

vs_title 'Handling a gated capability in your own script'
vs_note 'The pattern this file uses, reduced to its essentials:'
vs_note ''
vs_note '  rc=0'
vs_note '  body=$(curl -sS --fail-with-body \'
vs_note '           -H "User-Agent: my-app/1.0" \'
vs_note '           -H "Authorization: Bearer $VOLSTRATA_API_KEY" \'
vs_note '           "$BASE/api/v1/greeks/charm?ticker=SPX") || rc=$?'
vs_note '  if [ "$rc" -ne 0 ]; then'
vs_note '    printf "%s" "$body" | jq -r ".required_plan_name // .detail"'
vs_note '  fi'
vs_note ''
vs_note '--fail-with-body is the flag that matters: curl exits non-zero on a 4xx'
vs_note 'and still hands you the problem document, so you can report what the'
vs_note 'refusal actually said instead of an exit code.'
vs_note ''
vs_note 'Plans and keys: https://volstrata.com/docs/api-keys'

vs_title 'The rest of these domains'
vs_note 'greeks holds 11 capabilities. greeks.gamma is the Free one; greeks.dex,'
vs_note 'greeks.vex, greeks.tex and greeks.rho are at the Edge floor,'
vs_note 'greeks.charm at Pro, and greeks.color, .speed, .vomma, .zomma and'
vs_note '.ultima at Ultra.'
vs_note ''
vs_note 'vol holds 6: vol.iv (Free), vol.skew and vol.smile (Edge), vol.surface,'
vs_note 'vol.garch and vol.regime (Pro). voloi holds 3: oi and volume (Free) and'
vs_note 'combined (Edge, POST).'
vs_note ''
vs_note 'Every one of them takes ?ticker=. The ones that read a particular frame'
vs_note 'also take ?window= and ?at=, exactly as used above, so moving up a plan'
vs_note 'changes which names you can call rather than how you call them. Plan'
vs_note 'floors are published for every capability:'
vs_note ''
vs_note "  curl -sS '$BASE/api/v1/meta/capabilities?domain=greeks&limit=25'"

vs_title 'Related'
vs_note 'gex.sh                  the gamma frame these surfaces sit behind'
vs_note 'accuracy_and_stats.sh   the published greek statistics'

vs_footer
exit 0
