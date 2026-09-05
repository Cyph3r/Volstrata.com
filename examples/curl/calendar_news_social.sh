#!/usr/bin/env sh
# Copyright 2026 Volstrata.com - https://volstrata.com
#
# The event feeds: calendar, news, social and insider filings - cursor-paged,
# published at the Free plan floor, and credential-gated: a key on any plan is
# enough, but these particular endpoints do want one.
# Docs: https://volstrata.com/docs/api-base-url
#
# Run it:
#     export VOLSTRATA_API_KEY=YOUR_API_KEY    # https://volstrata.com/api-keys
#     sh examples/curl/calendar_news_social.sh [TICKER]      # default SPX
#
# Requests: 7 with a key. Without one it stops after 2, because seven identical
# refusals teach nothing and spend your rate limit.

set -eu

VS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$VS_DIR/_common.sh"

TICKER="${1:-SPX}"

# Every feed below is paged. Small pages keep the output readable; the model is
# identical at limit=5 and limit=500.
LIMIT=5

vs_title "calendar, news and social - $TICKER"
vs_auth_status

vs_note ''
vs_note 'These are the cursor-paged collections. Each answers the PagedEnvelope:'
vs_note 'ok, the rows, and next_cursor - null on the last page. pagination.sh'
vs_note 'walks the loop; this file shows the feeds themselves.'
vs_note ''
vs_note 'Several also accept ?version= for a pinned response shape. Leave it off'
vs_note 'unless you have been told to send it.'

# These endpoints are published at the Free plan floor and are also among the
# ones that want a credential of some kind - any valid key will do. Without one,
# this script demonstrates the refusal twice and then stops calling, which is
# both kinder to your rate limit and more honest than seven identical 401s.
if [ -n "${VOLSTRATA_API_KEY:-}" ]; then
  FULL=1
else
  FULL=0
  vs_note ''
  vs_note 'No VOLSTRATA_API_KEY is set. These feeds ask for a credential even at'
  vs_note 'the Free floor, so the first two calls below will show you the 401 and'
  vs_note 'the rest will be skipped rather than repeated. Get a key at'
  vs_note 'https://volstrata.com/api-keys and re-run to see rows.'
fi

DEMOED=0

# feed_call <label> <path> <query> - vs_call, plus the skip rule above.
feed_call() {
  if [ "$FULL" = "0" ] && [ "$DEMOED" -ge 2 ]; then
    printf '\n--- %s\n' "$1"
    printf '    skipped: no VOLSTRATA_API_KEY, and the calls above already\n'
    printf '    showed what these feeds answer without one.\n'
    return 0
  fi
  DEMOED=$((DEMOED + 1))
  vs_call "$1" "$2" "$3" "$VS_SUM"

  # If a call came back 2xx with no credential in play, there is nothing to
  # demonstrate and no reason to stop early: run the rest.
  case "$VS_HTTP_CODE" in
    2*) FULL=1 ;;
  esac
}

# ---------------------------------------------------------------------------
# 1. calendar.combined - every calendar type in one feed. `range` is a window
#    ("7d" is the documented default), `types` filters, `ticker` narrows.
# ---------------------------------------------------------------------------
feed_call 'calendar.combined - all event types, next 7 days' \
  '/api/v1/calendar/combined' "range=7d&types=all&limit=$LIMIT"

# ---------------------------------------------------------------------------
# 2. calendar.events - scheduled events, with an importance floor.
#    importance_min= filters out the small stuff; region= narrows by region.
# ---------------------------------------------------------------------------
feed_call 'calendar.events - scheduled events' \
  '/api/v1/calendar/events' "range=7d&importance_min=0&limit=$LIMIT"

# ---------------------------------------------------------------------------
# 3. calendar.corporate - company events, over a wider default window.
# ---------------------------------------------------------------------------
feed_call 'calendar.corporate - corporate events, next 30 days' \
  '/api/v1/calendar/corporate' "range=30d&limit=$LIMIT"

vs_note ''
vs_note 'Add ?ticker= to any of the three to narrow to one symbol. Without it'
vs_note 'you get the whole feed for the window, which is usually what a calendar'
vs_note 'view wants.'

# ---------------------------------------------------------------------------
# 4. news.feed - headlines, optionally for one ticker.
# ---------------------------------------------------------------------------
feed_call "news.feed - headlines for $TICKER" \
  '/api/v1/news/feed' "ticker=$TICKER&limit=$LIMIT"

# ---------------------------------------------------------------------------
# 5. social.sentiment - the sentiment feed, same paging contract.
# ---------------------------------------------------------------------------
feed_call "social.sentiment - sentiment rows for $TICKER" \
  '/api/v1/social/sentiment' "ticker=$TICKER&limit=$LIMIT"

# ---------------------------------------------------------------------------
# 6. social.tallies - aggregate counts rather than individual rows. `top` caps
#    the list, `min_posts` sets the floor for inclusion.
# ---------------------------------------------------------------------------
feed_call 'social.tallies - the top talked-about symbols' \
  '/api/v1/social/tallies' 'top=10&min_posts=3'

# ---------------------------------------------------------------------------
# 7. insider.filings - filings, filtered by form type. form=4 is the default.
# ---------------------------------------------------------------------------
feed_call 'insider.filings - recent form 4 filings' \
  '/api/v1/insider/filings' "form=4&limit=$LIMIT"

vs_note ''
vs_note 'Add ?ticker= to narrow. Every row is a filing as filed - this API'
vs_note 'reports the record, it does not interpret it.'

vs_title 'Also at the Free floor in these domains'
vs_note 'social.influencers  ?hours=48&min=2'
vs_note ''
vs_note 'Left out of the run only to keep this script inside one minute of the'
vs_note 'anonymous ceiling.'

vs_title 'Paging these feeds'
vs_note 'Ask for what you will use. A feed at limit=500 is one request and a'
vs_note 'large body; limit=5 is a small body but five times the requests to see'
vs_note 'the same 25 rows. The ceiling is on requests, not bytes.'
vs_note ''
vs_note 'Pagination and base URL: https://volstrata.com/docs/api-base-url'

vs_footer
exit 0
