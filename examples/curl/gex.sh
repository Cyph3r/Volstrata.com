#!/usr/bin/env sh
# Copyright 2026 Volstrata.com - https://volstrata.com
#
# The `gex` domain: six Free capabilities that answer with the current gamma
# picture for one ticker, plus one Edge-floor capability shown refusing.
# Docs: https://volstrata.com/docs/api-catalog
#
# Run it:
#     sh examples/curl/gex.sh [TICKER]      # default SPX
#
# Requests: 7.

set -eu

VS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$VS_DIR/_common.sh"

TICKER="${1:-SPX}"
Q="ticker=$TICKER"

vs_title "gex domain - $TICKER"
vs_auth_status

vs_note ''
vs_note 'Every capability below is GET /api/v1/gex/<name> and every one of them'
vs_note 'takes ?ticker=. The six Free ones answer with no credential; the last'
vs_note 'one sits at the Edge floor and is included precisely so you can see'
vs_note 'what a refusal looks like next to the calls that work.'
vs_note ''
vs_note 'What the individual level keys and metrics mean is documented in the'
vs_note 'public glossary and in GET /api/v1/docs/metrics - see research_and_docs.sh.'
vs_note 'This file teaches the request and response shape only.'

# ---------------------------------------------------------------------------
# 1. gex.levels - the named levels map. The one to reach for first.
# ---------------------------------------------------------------------------
vs_call 'gex.levels - named price levels' \
  '/api/v1/gex/levels' "$Q" \
  '"    ok=\(.ok)  spot=\(.spot)  updated=\(.updated)",
   "    levels: \(.levels | keys | join(", "))"'

vs_note ''
vs_note 'Values in "levels" are prices in the quote currency of the ticker. Some'
vs_note 'keys carry a two-element [high, low] band rather than a single number,'
vs_note 'and any key can be null when there is nothing to report - so read'
vs_note 'defensively rather than assuming every key is a float.'

# ---------------------------------------------------------------------------
# 2. gex.named_levels - the same idea, as an addressable list.
# ---------------------------------------------------------------------------
vs_call 'gex.named_levels - levels as labelled rows' \
  '/api/v1/gex/named_levels' "$Q" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 3. gex.metrics - the scalar summary of the same frame.
# ---------------------------------------------------------------------------
vs_call 'gex.metrics - bulk scalar metrics for the latest frame' \
  '/api/v1/gex/metrics' "$Q" \
  "$VS_SUM"

vs_note ''
vs_note 'Fields that name a basis (for example a `*_basis` alongside a derived'
vs_note 'label) tell you which definition produced the value in the same body.'
vs_note 'Carry that basis with the value whenever you compare across endpoints.'

# ---------------------------------------------------------------------------
# 4. gex.gamma_flip
# ---------------------------------------------------------------------------
vs_call 'gex.gamma_flip - the flip level for this ticker' \
  '/api/v1/gex/gamma_flip' "$Q" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 5. gex.maxpain
# ---------------------------------------------------------------------------
vs_call 'gex.maxpain - max-pain strike' \
  '/api/v1/gex/maxpain' "$Q" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 6. gex.bars - a per-strike series. The largest body in this file, so it is
#    summarised rather than printed whole.
# ---------------------------------------------------------------------------
vs_call 'gex.bars - per-strike series' \
  '/api/v1/gex/bars' "$Q" \
  "$VS_SUM"

vs_note ''
vs_note 'To see one row of that series rather than the outline:'
vs_note ''
vs_note '  curl -sS -H "User-Agent: volstrata-examples/1.0" \'
vs_note "    \"$BASE/api/v1/gex/bars?ticker=$TICKER\" | jq '.bars[0] // .'"

# ---------------------------------------------------------------------------
# 7. gex.snapshot - Edge floor. Expected to refuse for an anonymous caller and
#    for any key below Edge. The script keeps going either way.
# ---------------------------------------------------------------------------
vs_call 'gex.snapshot - Edge floor, the composite read' \
  '/api/v1/gex/snapshot' "$Q" \
  "$VS_SUM"

vs_note ''
vs_note 'gex.snapshot takes more than a ticker: window=, view=, greek=, at= and'
vs_note 'format= all have documented defaults, so ?ticker= alone is a valid call.'
vs_note 'Its defaults are listed with every other parameter in the catalog and in'
vs_note 'the public OpenAPI document at https://volstrata.com/api/openapi.json'

vs_title 'The rest of the domain'
vs_note 'gex is the largest domain on the API: 16 capabilities, of which the six'
vs_note 'called above are Free and the other ten sit at the Edge floor. The'
vs_note 'catalog lists all of them with their parameters and plan floors:'
vs_note ''
vs_note "  curl -sS '$BASE/api/v1/meta/capabilities?domain=gex&limit=25'"
vs_note ''
vs_note 'meta.capabilities is itself Free, so discovery never costs you a plan.'

vs_title 'Related'
vs_note 'greeks.sh    the greek surfaces behind these numbers'
vs_note 'levels.sh    the day/week level sets and the TradingView export'
vs_note 'Catalog:     https://volstrata.com/docs/api-catalog'

vs_footer
exit 0
