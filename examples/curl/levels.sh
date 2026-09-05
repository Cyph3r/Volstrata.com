#!/usr/bin/env sh
# Copyright 2026 Volstrata.com - https://volstrata.com
#
# The `levels` domain: day and week level sets, their report forms, per-level
# detail, and the TradingView export - which is also this repo's one non-JSON
# response.
# Docs: https://volstrata.com/docs/api-catalog
#
# Run it:
#     sh examples/curl/levels.sh [TICKER]      # default SPX
#
# Requests: 6.

set -eu

VS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$VS_DIR/_common.sh"

TICKER="${1:-SPX}"
Q="ticker=$TICKER"

vs_title "levels domain - $TICKER"
vs_auth_status

vs_note ''
vs_note 'Six of the seven capabilities in this domain are Free, and all six are'
vs_note 'called below. The seventh, levels.air_pockets, sits at the Pro floor and'
vs_note 'is not called here - greeks.sh and accuracy_and_stats.sh already show'
vs_note 'what a refusal above your plan looks like.'

# ---------------------------------------------------------------------------
# 1. levels.day
# ---------------------------------------------------------------------------
vs_call 'levels.day - the day level set' \
  '/api/v1/levels/day' "$Q" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 2. levels.week
# ---------------------------------------------------------------------------
vs_call 'levels.week - the week level set' \
  '/api/v1/levels/week' "$Q" \
  "$VS_SUM"

vs_note ''
vs_note 'Same shape, different horizon. A client that renders one can render the'
vs_note 'other without a second code path.'
vs_note ''
vs_note 'If one of these answers 404 with code "not_found" and a detail saying'
vs_note 'the set is withheld, the path is correct and the data simply is not'
vs_note 'being served at that moment - try again later. That is a different'
vs_note 'condition from "route_not_found", which means no such capability'
vs_note 'exists. Branch on `code`, not on the status alone.'

# ---------------------------------------------------------------------------
# 3. levels.detail - one named level, expanded. `kind` selects which; the level
#    keys returned by gex.levels are the values it accepts, and it defaults to
#    "cw". `days` and `strikes` narrow what comes back.
# ---------------------------------------------------------------------------
vs_call 'levels.detail - one named level, expanded' \
  '/api/v1/levels/detail' "$Q&kind=cw" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 4. levels.day_report - the same day set as prose-ready fields, for a client
#    that wants to render a written summary rather than a chart.
# ---------------------------------------------------------------------------
vs_call 'levels.day_report - the day set in report form' \
  '/api/v1/levels/day_report' "$Q" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 5. levels.week_report
# ---------------------------------------------------------------------------
vs_call 'levels.week_report - the week set in report form' \
  '/api/v1/levels/week_report' "$Q" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 6. levels.tradingview - the export. `format` is an enum: json, txt, pine, csv.
#
# This is the one capability in this repo whose response is not JSON, so it is
# also the one that proves the point made in auth_and_errors.sh: a non-JSON body
# is not automatically an error. Check the status code, then the Content-Type -
# in that order, always.
# ---------------------------------------------------------------------------
vs_call 'levels.tradingview - format=pine, a text/plain body' \
  '/api/v1/levels/tradingview' "$Q&format=pine" \
  ''

vs_note ''
vs_note 'The same capability in the other three formats:'
vs_note ''
vs_note "  $BASE/api/v1/levels/tradingview?ticker=$TICKER&format=json"
vs_note "  $BASE/api/v1/levels/tradingview?ticker=$TICKER&format=csv"
vs_note "  $BASE/api/v1/levels/tradingview?ticker=$TICKER&format=txt"
vs_note ''
vs_note 'To save the Pine output straight to a file:'
vs_note ''
vs_note "  curl -sS -H 'User-Agent: my-app/1.0' \\"
vs_note "    '$BASE/api/v1/levels/tradingview?ticker=$TICKER&format=pine' \\"
vs_note "    -o ${TICKER}_levels.pine"
vs_note ''
vs_note 'Do not pipe a text/plain body into jq and do not assume a body is JSON'
vs_note 'because the status was 200. Several capabilities take a format= enum;'
vs_note 'the accepted values for each are in the catalog and in the public'
vs_note 'OpenAPI document.'

vs_title 'Related'
vs_note 'gex.sh       the levels map these sets are built from'
vs_note 'Catalog:     https://volstrata.com/docs/api-catalog'

vs_footer
exit 0
