#!/usr/bin/env sh
# Copyright 2026 Volstrata.com - https://volstrata.com
#
# The smallest possible VolStrata API call: one GET, no credential, real data.
# Docs: https://volstrata.com/docs/api-examples
#
# Run it:
#     sh examples/curl/quickstart.sh
#
# Requests: 1.

set -eu

VS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$VS_DIR/_common.sh"

vs_title 'Quickstart - gex.levels for SPX, no API key required'
vs_auth_status

# gex.levels sits at the Free plan floor and answers with no credential at all.
# The equivalent bare command, with nothing else in the way, is:
#
#   curl -sS \
#     -H "User-Agent: volstrata-examples/1.0 (+https://volstrata.com)" \
#     "https://volstrata.com/api/v1/gex/levels?ticker=SPX"
#
# The User-Agent header is the only part that is easy to leave out and still
# regret; see the note at the top of _common.sh for why.

vs_call 'gex.levels - named price levels for one ticker' \
  '/api/v1/gex/levels' 'ticker=SPX'

vs_title 'What you just saw'
vs_note 'The response is a SuccessEnvelope: an "ok" flag plus the payload. Here'
vs_note 'that payload is "levels" (a map of named level keys to prices) along'
vs_note 'with "ticker", "spot", "ts" and "updated".'
vs_note ''
vs_note 'Field meanings live in the public glossary, not in this repo - these'
vs_note 'examples teach the request and response shape only.'
vs_note ''
vs_note 'Next:'
vs_note '  sh examples/curl/auth_and_errors.sh   how auth and refusals work'
vs_note '  sh examples/curl/pagination.sh        cursor paging'
vs_note '  sh examples/curl/gex.sh               the rest of the gex domain'
vs_note ''
vs_note 'Full endpoint catalog: https://volstrata.com/docs/api-catalog'

vs_footer
exit 0
