#!/usr/bin/env sh
# Copyright 2026 Volstrata.com - https://volstrata.com
#
# Company valuation and fundamentals: three Free GETs, then the two Pro-floor
# POST capabilities, which are also the example of how to send a JSON body.
# Docs: https://volstrata.com/docs/api-overview
#
# Run it:
#     sh examples/curl/valuation.sh [TICKER]      # default AAPL
#
# Requests: 5.

set -eu

VS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$VS_DIR/_common.sh"

# An equity, not an index - this domain is about companies.
TICKER="${1:-AAPL}"

vs_title "valuation and fundamentals - $TICKER"
vs_auth_status

vs_note ''
vs_note '173 of the 180 published operations are GET. This domain holds two of'
vs_note 'the seven POSTs, which is why it is the file that shows how to send a'
vs_note 'JSON request body.'
vs_note ''
vs_note 'What you get back depends on what you are carrying:'
vs_note ''
vs_note '  valuation.universe, valuation.company   Free floor, but these ask for'
vs_note '                                          a credential - a key on any'
vs_note '                                          plan is enough'
vs_note '  fundamentals.company                    Free floor, answers anonymously'
vs_note '  valuation.value, valuation.screen       Pro floor'
vs_note ''
vs_note 'The two checks happen in that order, which is why a Pro-floor call made'
vs_note 'with no credential at all answers 401 auth_required rather than a plan'
vs_note 'refusal: there was nothing to check a plan against yet.'

# ---------------------------------------------------------------------------
# 1. valuation.universe - Free. The screening surface: limit/offset paging
#    (not cursor paging - this one predates the cursor model and is explicit
#    about it in the catalog), plus optional sector, model, verdict and
#    min_market_cap filters.
# ---------------------------------------------------------------------------
vs_call 'valuation.universe - the covered universe, 5 rows' \
  '/api/v1/valuation/universe' 'limit=5&offset=0' \
  "$VS_SUM"

vs_note ''
vs_note 'Narrow it with the documented filters, for example:'
vs_note ''
vs_note "  $BASE/api/v1/valuation/universe?limit=25&sector=Technology"
vs_note ''
vs_note 'Note the paging here is limit/offset, while cursor-paged collections'
vs_note 'use ?limit=&cursor= - pagination.sh covers that model. Which one an'
vs_note 'operation uses is in its parameter list in the catalog.'

# ---------------------------------------------------------------------------
# 2. valuation.company - Free. One company.
# ---------------------------------------------------------------------------
vs_call "valuation.company - $TICKER" \
  '/api/v1/valuation/company' "ticker=$TICKER" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 3. fundamentals.company - Free. The reported financials the valuation
#    capabilities are quoted alongside.
# ---------------------------------------------------------------------------
vs_call "fundamentals.company - $TICKER" \
  '/api/v1/fundamentals/company' "ticker=$TICKER" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 4. valuation.value - Pro floor, POST with a JSON body.
#
# The bare command, so the shape is copy-pasteable on its own:
#
#   curl -sS --fail-with-body \
#     -X POST \
#     -H "User-Agent: volstrata-examples/1.0 (+https://volstrata.com)" \
#     -H "Authorization: Bearer $VOLSTRATA_API_KEY" \
#     -H 'Content-Type: application/json' \
#     -d '{"ticker":"AAPL"}' \
#     "https://api.volstrata.com/api/v1/valuation/value"
#
# Content-Type: application/json is required - the body is parsed as JSON, not
# as a form. `overrides` is an optional documented parameter and is left out
# here; the defaults are the point of the example.
# ---------------------------------------------------------------------------
vs_call_post 'valuation.value - Pro floor, POST' \
  '/api/v1/valuation/value' \
  "{\"ticker\":\"$TICKER\"}" \
  '' \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 5. valuation.screen - Pro floor, POST. `symbols` is the one required member
#    of the body; everything else has a default.
# ---------------------------------------------------------------------------
vs_call_post 'valuation.screen - Pro floor, POST with a required member' \
  '/api/v1/valuation/screen' \
  "{\"symbols\":\"$TICKER,MSFT\",\"limit\":\"5\"}" \
  '' \
  "$VS_SUM"

vs_title 'The seven POST capabilities'
vs_note 'Everything else on the API is a GET. The POSTs, with their plan floor:'
vs_note ''
vs_note '  valuation.value      Pro     this file'
vs_note '  valuation.screen     Pro     this file'
vs_note '  voloi.combined       Edge    volume and open interest in one call'
vs_note '  render.card          Edge    server-rendered image'
vs_note '  render.chart         Edge    server-rendered image'
vs_note '  render.animation     Desk    server-rendered animation'
vs_note '  meta.mcp             Free    the MCP JSON-RPC transport - see mcp.sh'
vs_note ''
vs_note 'They all take a JSON body and all answer the same envelopes and the same'
vs_note 'RFC 9457 refusals as the GETs.'
vs_note ''
vs_note 'Overview: https://volstrata.com/docs/api-overview'

vs_footer
exit 0
