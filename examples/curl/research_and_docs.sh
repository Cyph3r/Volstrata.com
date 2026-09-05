#!/usr/bin/env sh
# Copyright 2026 Volstrata.com - https://volstrata.com
#
# Discovery: the metric glossary, what is covered, and the research query
# surface - including reading one response to build the next request.
# Docs: https://volstrata.com/docs/api-catalog
#
# Run it:
#     sh examples/curl/research_and_docs.sh [TICKER]      # default SPX
#
# Requests: 6.

set -eu

VS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$VS_DIR/_common.sh"

TICKER="${1:-SPX}"

vs_title "research and docs - $TICKER"
vs_auth_status

vs_note ''
vs_note 'These capabilities answer "what exists, what does it mean, and what is'
vs_note 'covered" - the calls to reach for before hard-coding a field name or a'
vs_note 'ticker list into a client.'

# ---------------------------------------------------------------------------
# 1. docs.metrics - the glossary index: every documented metric, with a title
#    and a one-line description.
# ---------------------------------------------------------------------------
vs_call 'docs.metrics - the metric glossary index' \
  '/api/v1/docs/metrics' '' \
  '"    count=\(.count)",
   "    metrics: \(.docs | map(.metric) | join(", "))"'

# The body of the call above is still on disk, so the next request can be built
# from it rather than from a name typed into this file.
METRIC="gamma_flip"
if [ "$VS_JQ" = "1" ]; then
  DISCOVERED="$(jq -r '.docs[0].metric // empty' "$VS_TMP/out" 2>/dev/null || printf '')"
  if [ -n "$DISCOVERED" ]; then
    METRIC="$DISCOVERED"
  fi
fi

# ---------------------------------------------------------------------------
# 2. docs.metric - one entry from that index. `metric` is required, and its
#    accepted values are exactly the slugs listed above - which is why this
#    call is built from the previous response.
# ---------------------------------------------------------------------------
vs_call "docs.metric - the entry for '$METRIC'" \
  '/api/v1/docs/metric' "metric=$METRIC" \
  ''

vs_note ''
vs_note 'Discover, then call. Hard-coding an enum value that the API publishes'
vs_note 'is how a client breaks quietly when the list grows; reading it costs'
vs_note 'one request. The same applies to tickers, level kinds and formats.'

# ---------------------------------------------------------------------------
# 3. research.metrics - the metrics the research surface can return.
# ---------------------------------------------------------------------------
vs_call 'research.metrics - available research metrics' \
  '/api/v1/research/metrics' '' \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 4. research.coverage - what is covered for one ticker.
# ---------------------------------------------------------------------------
vs_call "research.coverage - coverage for $TICKER" \
  '/api/v1/research/coverage' "ticker=$TICKER" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 5. research.universe - the covered universe. Also available as CSV with
#    ?format=csv, which is the shape a spreadsheet wants.
# ---------------------------------------------------------------------------
vs_call 'research.universe - the covered universe' \
  '/api/v1/research/universe' '' \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 6. research.query - the parameterised read. This one has the longest
#    parameter list on the API and every parameter has a documented default, so
#    a minimal call is valid and a precise one is possible:
#
#      view          ladder | smile | term | levels_term | parity | surface
#      weight        oi | vol | both
#      contracts     all | calls | puts
#      moneyness     all | atm | ntm | itm | otm
#      expiry_class  all | w | m | q
#      strikes, start_dte, end_dte, combine_exp, net, format
# ---------------------------------------------------------------------------
vs_call 'research.query - a 5-strike ladder' \
  '/api/v1/research/query' "ticker=$TICKER&view=ladder&strikes=5" \
  "$VS_SUM"

vs_note ''
vs_note 'Every enum above is published in the OpenAPI document, so a client can'
vs_note 'validate a request before sending it:'
vs_note ''
vs_note "  curl -sS 'https://volstrata.com/api/openapi.json' \\"
vs_note "    | jq '.paths[\"/api/v1/research/query\"].get.parameters'"
vs_note ''
vs_note 'That document is public, unauthenticated, and the same file this repo'
vs_note 'checks in under docs/reference/openapi.json.'

vs_title 'Related'
vs_note 'pagination.sh   meta.capabilities, the runtime catalog'
vs_note 'mcp.sh          the same glossary, reachable as an MCP resource'
vs_note 'Catalog:        https://volstrata.com/docs/api-catalog'

vs_footer
exit 0
