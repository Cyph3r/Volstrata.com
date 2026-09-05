#!/usr/bin/env sh
# Copyright 2026 Volstrata.com - https://volstrata.com
#
# The shared cursor-pagination model: ?limit= and ?cursor=, following
# next_cursor until it comes back null, with a hard bound on the loop.
# Docs: https://volstrata.com/docs/api-base-url
#
# Run it:
#     sh examples/curl/pagination.sh
#
# Requests: up to 4 (the page bound below), or 1 without jq.

set -eu

VS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$VS_DIR/_common.sh"

# meta.capabilities is the runtime catalog: every published capability with its
# method, path, parameters and plan floor. It needs no credential, it is one of
# the 17 operations that declare a cursor parameter, and it is big enough to
# actually page - which makes it the right thing to learn the model on.
PATH_CAPS='/api/v1/meta/capabilities'

# Small on purpose, so the loop runs more than once against a collection of
# ~175 rows.
LIMIT=25

# The bound. This is not defensive decoration: these scripts hit live
# production under a per-minute ceiling (10/min for an anonymous caller), so a
# paging loop gets a fixed maximum number of iterations and no exceptions. Raise
# it if you need the whole collection, and expect to pace the requests.
MAX_PAGES=4

vs_title 'Cursor pagination - meta.capabilities'
vs_auth_status

vs_note ''
vs_note 'The model, once, for every paged collection on the API:'
vs_note ''
vs_note '  1. GET the path with ?limit=N'
vs_note '  2. read "next_cursor" from the response'
vs_note '  3. null  -> that was the last page, stop'
vs_note '     string -> GET again with ?cursor=<that string>'
vs_note ''
vs_note 'Cursors are opaque. Pass the string straight back, url-encoded; never'
vs_note 'parse one, build one, or assume it encodes an offset or a timestamp.'
vs_note 'Paged responses share one envelope: "ok", "next_cursor" (null on the'
vs_note 'last page) and the collection itself, plus a count of the rows that'
vs_note 'exist in total.'

if [ "$VS_JQ" = "0" ]; then
  # Without jq there is no dependable way to read next_cursor out of a JSON
  # body in POSIX sh - a regex over raw JSON is the kind of thing that works
  # until it silently does not. So: fetch exactly one page, show it, and say
  # plainly what is missing rather than pretending to loop.
  vs_title 'jq is not installed - fetching one page only'

  vs_note 'The loop below needs jq to read "next_cursor" and url-encode it.'
  vs_note 'Install jq (https://jqlang.github.io/jq/) and re-run to see paging.'
  vs_note ''

  vs_call "page 1 of the catalog (limit=$LIMIT)" "$PATH_CAPS" "limit=$LIMIT" "$VS_SUM"

  vs_note ''
  vs_note 'That body carries a "next_cursor" member, and it is what page 2'
  vs_note 'would be requested with:'
  vs_note ''
  vs_note "  GET $BASE$PATH_CAPS?limit=$LIMIT&cursor=<next_cursor>"

  vs_footer
  exit 0
fi

# ---------------------------------------------------------------------------
# The loop. Bounded by MAX_PAGES, and it stops early the moment next_cursor
# comes back null.
# ---------------------------------------------------------------------------

vs_title "Paging with limit=$LIMIT, at most $MAX_PAGES pages"

page=0
rows=0
cursor=""
pending=""
total=""

while [ "$page" -lt "$MAX_PAGES" ]; do
  page=$((page + 1))

  # Build the query. The cursor is url-encoded with jq's @uri, because an
  # opaque token is allowed to contain characters that mean something in a
  # query string.
  query="limit=$LIMIT"
  if [ -n "$cursor" ]; then
    query="$query&cursor=$cursor"
  fi

  rc=0
  vs_get "$PATH_CAPS" "$query" >"$VS_TMP/page" || rc=$?

  if [ "$rc" -ne 0 ]; then
    printf '\n    page %s: HTTP %s - stopping.\n' "$page" "$VS_HTTP_CODE"
    vs_show "$VS_TMP/page"
    vs_explain "$VS_HTTP_CODE"
    break
  fi

  # Rows on this page, and the collection's total row count.
  got="$(jq -r '.capabilities | length' "$VS_TMP/page" 2>/dev/null || printf '0')"
  total="$(jq -r '.count // .total // "unknown"' "$VS_TMP/page" 2>/dev/null || printf 'unknown')"
  rows=$((rows + got))

  # next_cursor, url-encoded, empty string when null or absent.
  pending="$(jq -r 'if .next_cursor then (.next_cursor | @uri) else "" end' "$VS_TMP/page" 2>/dev/null || printf '')"

  if [ -n "$pending" ]; then
    shown="$(printf '%s' "$pending" | cut -c1-16)"
    cursor_note="next_cursor=$shown..."
  else
    cursor_note='next_cursor=null (last page)'
  fi

  printf '    page %s: %s rows  (running total %s of %s)  %s\n' \
    "$page" "$got" "$rows" "$total" "$cursor_note"

  # A sample row from the first page, so the shape is visible once.
  if [ "$page" -eq 1 ]; then
    printf '\n    first row of page 1:\n'
    jq -r '.capabilities[0] | "      name=\(.name)\n      method=\(.method) path=\(.path)\n      plan floor=\(.tier_name)"' \
      "$VS_TMP/page" 2>/dev/null || true
    printf '\n'
  fi

  if [ -z "$pending" ]; then
    break
  fi
  cursor="$pending"
done

vs_title 'Result'
vs_note "pages fetched: $page"
vs_note "rows collected: $rows of $total"

if [ -n "$pending" ]; then
  vs_note ''
  vs_note 'A non-null next_cursor is still outstanding: the loop stopped because'
  vs_note "it hit its own $MAX_PAGES-page bound, not because the collection ended."
  vs_note 'That distinction is worth keeping in your own client - "no more'
  vs_note 'pages" and "I stopped early" are different states.'
else
  vs_note ''
  vs_note 'next_cursor came back null, so that was the whole collection.'
fi

vs_note ''
vs_note 'The same ?limit=&cursor= model applies to every paged collection -'
vs_note 'news.feed, social.sentiment, insider.filings, market.candles and the'
vs_note 'calendar feeds among them. 17 published operations declare a cursor.'
vs_note ''
vs_note 'Base URL and versioning: https://volstrata.com/docs/api-base-url'

vs_footer
exit 0
