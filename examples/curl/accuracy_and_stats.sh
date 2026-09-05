#!/usr/bin/env sh
# Copyright 2026 Volstrata.com - https://volstrata.com
#
# The published scorecards and statistics: six Free capabilities, plus one
# Pro-floor forecast read shown refusing cleanly.
# Docs: https://volstrata.com/docs/api-examples
#
# Run it:
#     sh examples/curl/accuracy_and_stats.sh [TICKER]      # default SPX
#
# Requests: 7.

set -eu

VS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$VS_DIR/_common.sh"

TICKER="${1:-SPX}"

vs_title "accuracy and statistics - $TICKER"
vs_auth_status

vs_note ''
vs_note 'This group publishes results, not methods. The examples here show you'
vs_note 'how to read the numbers out; what any of them measures is documented on'
vs_note 'the site and in the metric glossary (see research_and_docs.sh), and'
vs_note 'nothing in this repo tries to explain how one is produced.'

# ---------------------------------------------------------------------------
# 1. accuracy.scoreboard - the headline scorecard. `ticker` is optional: leave
#    it off for every covered symbol, pass it for one.
# ---------------------------------------------------------------------------
vs_call "accuracy.scoreboard - $TICKER" \
  '/api/v1/accuracy/scoreboard' "ticker=$TICKER" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 2. accuracy.did_it_hold - per-session outcomes. `sessions` is how many
#    sessions back to include (30 by default).
# ---------------------------------------------------------------------------
vs_call 'accuracy.did_it_hold - the last 10 sessions' \
  '/api/v1/accuracy/did_it_hold' "ticker=$TICKER&sessions=10" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 3. accuracy.pin_contest
# ---------------------------------------------------------------------------
vs_call "accuracy.pin_contest - $TICKER" \
  '/api/v1/accuracy/pin_contest' "ticker=$TICKER" \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 4. stats.pin_reconciliation - no parameters at all.
# ---------------------------------------------------------------------------
vs_call 'stats.pin_reconciliation - published reconciliation stats' \
  '/api/v1/stats/pin_reconciliation' '' \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 5. stats.greeks.wall_migration - one of seven stats.greeks.* capabilities.
#
# Note the naming rule, which holds across the whole API: the dotted capability
# name is the path with dots turned into slashes, under /api/v1. So
# `stats.greeks.wall_migration` is GET /api/v1/stats/greeks/wall_migration, and
# it is also the operationId in the OpenAPI document and the tool name over MCP.
# One identifier, three surfaces.
# ---------------------------------------------------------------------------
vs_call 'stats.greeks.wall_migration' \
  '/api/v1/stats/greeks/wall_migration' '' \
  "$VS_SUM"

vs_note ''
vs_note 'The other six, all Free and all parameterless:'
vs_note ''
vs_note '  stats.greeks.charm_close_tightness   stats.greeks.oi_vs_volume_wall'
vs_note '  stats.greeks.open_iv_skew_range      stats.greeks.vanna_flip_expansion'
vs_note '  stats.greeks.zg_distance_range       stats.greeks.dex_vex_direction'
vs_note ''
vs_note 'Two Free capabilities from the accuracy domain are also left out of the'
vs_note 'run above, for the same rate-limit reason: accuracy.tape (no required'
vs_note 'parameters) and accuracy.pin_leaderboard (?ticker=).'

# ---------------------------------------------------------------------------
# 6. forecast.backtest - Free, no parameters.
# ---------------------------------------------------------------------------
vs_call 'forecast.backtest - published backtest results' \
  '/api/v1/forecast/backtest' '' \
  "$VS_SUM"

# ---------------------------------------------------------------------------
# 7. forecast.cone - Pro floor. Included so the refusal is visible next to the
#    calls that work; the script exits 0 either way.
# ---------------------------------------------------------------------------
vs_call 'forecast.cone - Pro floor, expected to refuse for most readers' \
  '/api/v1/forecast/cone' "ticker=$TICKER&window=today" \
  "$VS_SUM"

vs_title 'Reading a scorecard in a shell pipeline'
vs_note 'Every capability here takes ?format=json (the default) and answers the'
vs_note 'standard envelope, so one jq filter per field is all it takes:'
vs_note ''
vs_note "  curl -sS -H 'User-Agent: my-app/1.0' \\"
vs_note "    '$BASE/api/v1/accuracy/scoreboard?ticker=$TICKER' \\"
vs_note "    | jq -r '.ok'"
vs_note ''
vs_note 'Check the HTTP status first and .ok second: the status is authoritative'
vs_note 'and .ok is the envelope agreeing with it.'

vs_title 'Related'
vs_note 'greeks.sh    the greek reads these statistics are published alongside'
vs_note 'Examples:    https://volstrata.com/docs/api-examples'

vs_footer
exit 0
