#!/usr/bin/env sh
# Copyright 2026 Volstrata.com - https://volstrata.com
#
# Shared shell helpers for the VolStrata API curl examples: base URL, the
# mandatory User-Agent, optional bearer auth, response printing and a raw
# header dump. Every other script in this directory sources this file.
# Docs: https://volstrata.com/docs/api-overview
#
# Source it, do not execute it:
#     . "$(dirname "$0")/_common.sh"
#
# POSIX sh only - this must run under dash, ash, bash, zsh and Git Bash.
# No arrays, no [[ ]], no "local", no process substitution.

set -eu

# ---------------------------------------------------------------------------
# Configuration. These two environment variables are the only ones this repo
# reads. Nothing here is written to disk and no credential is ever printed.
# ---------------------------------------------------------------------------

# The canonical public host. Override only if you have been told to.
BASE="${VOLSTRATA_BASE_URL:-https://volstrata.com}"

# Sent on every single request, and not optional.
#
# The CDN in front of the API refuses a handful of well-known default client
# User-Agent strings at the edge, with a plain-text body, before the request
# ever reaches the API. When that happens you get a non-JSON refusal that looks
# like a broken response rather than what it is. Setting an explicit User-Agent
# avoids the whole class of problem: a non-JSON refusal means the request never
# arrived, and every real API refusal is application/problem+json.
VS_UA="volstrata-examples/1.0 (+https://volstrata.com)"

# VOLSTRATA_API_KEY is read from the environment when - and only when - it is
# set. There is no default, no literal and no file fallback anywhere in this
# repo. 67 of the 180 published operations sit at the Free plan floor and many
# of those answer with no credential at all, so every script here does
# something useful with this variable unset.
#
#     export VOLSTRATA_API_KEY=YOUR_API_KEY   # https://volstrata.com/api-keys

# ---------------------------------------------------------------------------
# Capability detection, done once.
# ---------------------------------------------------------------------------

# jq is optional. When it is missing every script still prints the raw response
# body; you just lose the pretty-printing and the one-line summaries.
if command -v jq >/dev/null 2>&1; then VS_JQ=1; else VS_JQ=0; fi

# --fail-with-body arrived in curl 7.76. It makes curl exit non-zero on a 4xx
# or 5xx while still writing the response body, which is exactly what you want
# against an API whose refusals are RFC 9457 problem documents worth reading.
# Older curl gets the body without the non-zero exit; the helpers below fall
# back to the HTTP status code, which they capture either way.
if curl --fail-with-body --version >/dev/null 2>&1; then
  VS_FAILBODY=1
else
  VS_FAILBODY=0
fi

# Scratch space for one run of one script.
VS_TMP="${TMPDIR:-/tmp}/volstrata-examples.$$"
if ! mkdir -p "$VS_TMP"; then
  printf 'error: cannot create a temporary directory under %s\n' "${TMPDIR:-/tmp}" >&2
  exit 1
fi
vs_cleanup() {
  if [ -n "${VS_TMP:-}" ] && [ -d "$VS_TMP" ]; then
    rm -rf "$VS_TMP"
  fi
}
trap vs_cleanup EXIT

# Set by vs_get / vs_post on every call.
VS_HTTP_CODE=""

# Every request any helper here makes is counted, and every script prints the
# total when it finishes. These examples run against live production under a
# published per-minute ceiling, so the count is worth keeping in view.
VS_REQUEST_COUNT=0

# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

# vs_curl_raw <curl args...>
#
# The one place a credential is ever attached. The Authorization header is
# added only when VOLSTRATA_API_KEY is a non-empty environment variable; with
# it unset the request goes out anonymously, which is a first-class supported
# mode for the free capabilities.
#
# The alternative presentation the API accepts is `?api_key=<key>` on the query
# string. The header is used here because a query string ends up in shell
# history, proxy logs and browser history; see auth_and_errors.sh.
vs_curl_raw() {
  VS_REQUEST_COUNT=$((VS_REQUEST_COUNT + 1))
  if [ -n "${VOLSTRATA_API_KEY:-}" ]; then
    curl -sS \
      -H "User-Agent: $VS_UA" \
      -H "Accept: application/json" \
      -H "Authorization: Bearer $VOLSTRATA_API_KEY" \
      "$@"
  else
    curl -sS \
      -H "User-Agent: $VS_UA" \
      -H "Accept: application/json" \
      "$@"
  fi
}

# vs_curl <curl args...> - as above, but a 4xx/5xx becomes a non-zero exit
# while the problem+json body is still delivered.
vs_curl() {
  if [ "$VS_FAILBODY" = "1" ]; then
    set -- --fail-with-body "$@"
  fi
  vs_curl_raw "$@"
}

# vs_url <path> [query] -> the absolute URL, printed.
vs_url() {
  if [ -n "${2:-}" ]; then
    printf '%s%s?%s' "$BASE" "$1" "$2"
  else
    printf '%s%s' "$BASE" "$1"
  fi
}

# vs_stderr_if_no_response
#
# curl writes one line to stderr for an HTTP failure ("returned error: 404"),
# which is redundant here because the status code is printed anyway. Keep it
# only when there was no HTTP response at all - that is the case where curl's
# own message (DNS, TLS, timeout) is the whole story.
vs_stderr_if_no_response() {
  if [ "$VS_HTTP_CODE" = "000" ] && [ -s "$VS_TMP/err" ]; then
    cat "$VS_TMP/err" >&2
  fi
}

# vs_get <path> [query]
#
# Prints the response body on stdout, sets VS_HTTP_CODE, and returns non-zero
# when the request was refused. Callers that want to keep going after a refusal
# should use vs_call, or guard with `|| rc=$?`.
vs_get() {
  vs_g_url="$(vs_url "$1" "${2:-}")"
  vs_g_rc=0
  vs_curl -w '%{http_code}' -o "$VS_TMP/body" "$vs_g_url" \
    >"$VS_TMP/code" 2>"$VS_TMP/err" || vs_g_rc=$?
  VS_HTTP_CODE="$(cat "$VS_TMP/code" 2>/dev/null || printf '000')"
  [ -n "$VS_HTTP_CODE" ] || VS_HTTP_CODE="000"
  vs_stderr_if_no_response
  if [ -f "$VS_TMP/body" ]; then cat "$VS_TMP/body"; fi
  # Older curl without --fail-with-body: derive failure from the status code.
  if [ "$vs_g_rc" -eq 0 ] && [ "$VS_FAILBODY" != "1" ]; then
    case "$VS_HTTP_CODE" in
      2*) ;;
      *) vs_g_rc=22 ;;
    esac
  fi
  return "$vs_g_rc"
}

# vs_post <path> <json-body> [query] - same contract as vs_get.
#
# 7 of the 180 published operations are POST; everything else is a GET.
vs_post() {
  vs_p_url="$(vs_url "$1" "${3:-}")"
  vs_p_rc=0
  vs_curl -X POST \
    -H 'Content-Type: application/json' \
    -d "$2" \
    -w '%{http_code}' -o "$VS_TMP/body" "$vs_p_url" \
    >"$VS_TMP/code" 2>"$VS_TMP/err" || vs_p_rc=$?
  VS_HTTP_CODE="$(cat "$VS_TMP/code" 2>/dev/null || printf '000')"
  [ -n "$VS_HTTP_CODE" ] || VS_HTTP_CODE="000"
  vs_stderr_if_no_response
  if [ -f "$VS_TMP/body" ]; then cat "$VS_TMP/body"; fi
  if [ "$vs_p_rc" -eq 0 ] && [ "$VS_FAILBODY" != "1" ]; then
    case "$VS_HTTP_CODE" in
      2*) ;;
      *) vs_p_rc=22 ;;
    esac
  fi
  return "$vs_p_rc"
}

# vs_headers <path> [query]
#
# Dumps the response headers and discards the body. Every response carries the
# modern `ratelimit` / `ratelimit-policy` pair, the legacy `x-ratelimit-*`
# headers and the API version, so this is the quickest way to see where you are
# against your ceiling.
vs_headers() {
  vs_curl_raw -D - -o /dev/null "$(vs_url "$1" "${2:-}")"
}

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

vs_title() {
  printf '\n'
  printf '===============================================================\n'
  printf '  %s\n' "$1"
  printf '===============================================================\n'
}

vs_note() {
  printf '  %s\n' "$1"
}

# vs_show <file> - pretty-print JSON with jq when it is available and the body
# really is JSON; otherwise print the body verbatim. Non-JSON response formats
# (levels.tradingview can return Pine, CSV or plain text) fall through here
# unharmed, as does any plain-text edge refusal.
vs_show() {
  if [ "$VS_JQ" = "1" ] && jq -e . "$1" >/dev/null 2>&1; then
    jq . "$1"
  else
    cat "$1"
    printf '\n'
  fi
}

# vs_show_head <file> [bytes] - the first N bytes, for bodies too large to read.
vs_show_head() {
  head -c "${2:-700}" "$1"
  printf '\n  ... (body truncated for display)\n'
}

# vs_pick <file> <jq-filter> [fallback-bytes]
#
# A one-line summary when jq is installed, a truncated raw body when it is not.
# Nothing in this repo requires jq; it only makes the output nicer. A filter
# that does not fit the body it was handed falls back to the whole document
# rather than failing the script.
vs_pick() {
  if [ "$VS_JQ" = "1" ] && jq -e . "$1" >/dev/null 2>&1; then
    if ! jq -r "$2" "$1" 2>/dev/null; then
      vs_show "$1"
    fi
  else
    head -c "${3:-500}" "$1"
    printf '\n  (install jq for a formatted summary instead of the raw body)\n'
  fi
}

# VS_SUM - a jq filter that summarises any JSON object without knowing its
# shape: scalars printed, arrays and objects reduced to a size and their key
# names. Pass it as the last argument to vs_call when you want the outline of a
# response rather than the whole thing.
VS_SUM='to_entries[] | "    \(.key): " +
  (if   (.value | type) == "array"  then "[\(.value | length) items]"
   elif (.value | type) == "object" then "{\(.value | keys | join(", "))}"
   elif (.value | type) == "null"   then "null"
   else (.value | tostring)
   end
   | if length > 140 then .[0:140] + " ..." else . end)'

# vs_explain <http-status> - plain-English reading of a refusal.
vs_explain() {
  case "$1" in
    400)
      vs_note 'HTTP 400 - a parameter was rejected. The "detail" member of the'
      vs_note 'problem document names it.'
      ;;
    401)
      vs_note 'HTTP 401 auth_required - no credential was presented. Either this'
      vs_note 'capability sits above the Free floor, or it is one of the data'
      vs_note 'endpoints that require any valid key even at the Free floor; the'
      vs_note '"detail" member says which, and names the credential prefixes'
      vs_note 'that are accepted. Export VOLSTRATA_API_KEY and run again:'
      vs_note 'https://volstrata.com/api-keys'
      ;;
    402 | 403)
      vs_note 'HTTP 402/403 - a plan refusal. The credential was accepted, the'
      vs_note 'plan floor was not met. The body carries "feature",'
      vs_note '"required_plan_name" and "current_plan" so a client can say'
      vs_note 'exactly what is missing rather than "forbidden".'
      ;;
    404)
      vs_note 'HTTP 404 - either route_not_found (nothing is published at that'
      vs_note 'path) or not_found (the path is right, the resource is not there'
      vs_note 'right now). GET /api/v1/meta/capabilities lists every live path.'
      ;;
    429)
      vs_note 'HTTP 429 - rate limited. Read Retry-After and the `ratelimit`'
      vs_note 'header, wait, then retry. Limits are per owner, not per key, so'
      vs_note 'minting another key does not raise the ceiling.'
      ;;
    5*)
      vs_note 'HTTP 5xx - server side. Retry with backoff; the "request_id" in'
      vs_note 'the body is the thing to quote if it persists.'
      ;;
    000)
      vs_note 'No HTTP response at all - DNS, TLS or connectivity. Check the'
      vs_note 'stderr line above.'
      ;;
    *)
      vs_note "HTTP $1 - see https://volstrata.com/docs/api-errors"
      ;;
  esac
}

# vs_call <label> <path> [query] [jq-filter]
#
# The workhorse. Issues one GET, prints the request line and the outcome, and
# never aborts the calling script: a refusal is printed, explained and stepped
# over, because a demonstrated refusal is a legitimate result for an example.
#
# The raw body of the most recent call is left in "$VS_TMP/out", so a script
# that needs a value out of one response to build the next request can read it
# there instead of making the call twice.
vs_call() {
  vs_c_label="$1"
  vs_c_path="$2"
  vs_c_query="${3:-}"
  vs_c_filter="${4:-}"

  printf '\n--- %s\n' "$vs_c_label"
  printf '    GET %s\n' "$(vs_url "$vs_c_path" "$vs_c_query")"

  vs_c_rc=0
  vs_get "$vs_c_path" "$vs_c_query" >"$VS_TMP/out" || vs_c_rc=$?

  if [ "$vs_c_rc" -eq 0 ]; then
    printf '    HTTP %s\n' "$VS_HTTP_CODE"
    if [ -n "$vs_c_filter" ]; then
      vs_pick "$VS_TMP/out" "$vs_c_filter"
    else
      vs_show "$VS_TMP/out"
    fi
  else
    printf '    HTTP %s - refused; the problem document below says why\n' "$VS_HTTP_CODE"
    vs_show "$VS_TMP/out"
    vs_explain "$VS_HTTP_CODE"
  fi
  return 0
}

# vs_call_post <label> <path> <json-body> [query] [jq-filter] - same contract.
vs_call_post() {
  vs_cp_label="$1"
  vs_cp_path="$2"
  vs_cp_body="$3"
  vs_cp_query="${4:-}"
  vs_cp_filter="${5:-}"

  printf '\n--- %s\n' "$vs_cp_label"
  printf '    POST %s\n' "$(vs_url "$vs_cp_path" "$vs_cp_query")"
  printf '    body %s\n' "$vs_cp_body"

  vs_cp_rc=0
  vs_post "$vs_cp_path" "$vs_cp_body" "$vs_cp_query" >"$VS_TMP/out" || vs_cp_rc=$?

  if [ "$vs_cp_rc" -eq 0 ]; then
    printf '    HTTP %s\n' "$VS_HTTP_CODE"
    if [ -n "$vs_cp_filter" ]; then
      vs_pick "$VS_TMP/out" "$vs_cp_filter"
    else
      vs_show "$VS_TMP/out"
    fi
  else
    printf '    HTTP %s - refused; the problem document below says why\n' "$VS_HTTP_CODE"
    vs_show "$VS_TMP/out"
    vs_explain "$VS_HTTP_CODE"
  fi
  return 0
}

# vs_auth_status - says whether a key is in play, without printing any part of
# it. Call this at the top of a script so the reader knows which mode they are
# looking at.
vs_auth_status() {
  if [ -n "${VOLSTRATA_API_KEY:-}" ]; then
    vs_note 'auth: VOLSTRATA_API_KEY is set - requests carry an Authorization header.'
  else
    vs_note 'auth: VOLSTRATA_API_KEY is not set - running anonymously.'
    vs_note '      Free capabilities still work; gated ones will refuse, on purpose.'
  fi
  if [ "$VS_JQ" = "0" ]; then
    vs_note 'jq:   not installed - raw response bodies will be printed instead.'
  fi
  vs_note "base: $BASE"
}

# vs_footer - the last line of every script: how many requests it just spent.
#
# The anonymous ceiling is 10 requests per minute and it is enforced per owner,
# not per key. Run one script at a time and a 429 never comes up.
vs_footer() {
  printf '\n'
  vs_note "Done. Requests made by this script: $VS_REQUEST_COUNT."
  vs_note 'Ceilings are per minute and per owner (anonymous: 10/min). Running two'
  vs_note 'of these back to back can trip a 429 - wait for the reset printed in'
  vs_note 'the `ratelimit` header rather than retrying straight away.'
}
