#!/usr/bin/env sh
# Copyright 2026 Volstrata.com - https://volstrata.com
#
# The two ways to present an API key, what an anonymous call can and cannot
# reach, and what each kind of refusal looks like on the wire.
# Docs: https://volstrata.com/docs/api-errors and https://volstrata.com/docs/api-auth
#
# Run it:
#     sh examples/curl/auth_and_errors.sh
#
# Requests: 4 without a key, 5 with one. Every branch exits 0 - a refusal that
# was demonstrated on purpose is a successful run of this script.

set -eu

VS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$VS_DIR/_common.sh"

vs_title '1. Where the credential goes'
vs_auth_status

vs_note ''
vs_note 'Preferred - an Authorization header:'
vs_note ''
vs_note '  curl -sS \'
vs_note '    -H "User-Agent: volstrata-examples/1.0 (+https://volstrata.com)" \'
vs_note '    -H "Authorization: Bearer $VOLSTRATA_API_KEY" \'
vs_note '    "https://volstrata.com/api/v1/gex/snapshot?ticker=SPX"'
vs_note ''
vs_note 'Also accepted - the key on the query string:'
vs_note ''
vs_note '  curl -sS \'
vs_note '    -H "User-Agent: volstrata-examples/1.0 (+https://volstrata.com)" \'
vs_note '    "https://volstrata.com/api/v1/gex/snapshot?ticker=SPX&api_key=$VOLSTRATA_API_KEY"'
vs_note ''
vs_note 'Use the header. A query string is written to shell history, proxy and'
vs_note 'server access logs, browser history and any error report that quotes a'
vs_note 'URL - so the query form leaks the key into places you do not control'
vs_note 'and cannot clean up. It exists for callers that genuinely cannot set a'
vs_note 'header (a spreadsheet formula, a webhook field, a chart URL).'
vs_note ''
vs_note 'A key is `gex_key_v1_` followed by 43 url-safe base64 characters. Legacy'
vs_note '`sig_key_v1_` keys are accepted permanently. Personal access tokens'
vs_note '(`sig_pat_v1_`) and service accounts (`sig_svc_v1_`) are accepted too and'
vs_note 'resolve to the same plan machinery; this repo teaches the API key.'
vs_note ''
vs_note 'Rate limits are enforced per owner, not per key: minting a second key'
vs_note 'does not raise your ceiling. https://volstrata.com/docs/api-rate-limits'
vs_note ''
vs_note 'Never write a key into a file. Export it:'
vs_note '  export VOLSTRATA_API_KEY=YOUR_API_KEY     # https://volstrata.com/api-keys'

# ---------------------------------------------------------------------------

vs_title '2. An anonymous call that works'

# 67 of the 180 published operations sit at the Free plan floor, and many of
# those - gex.levels among them - answer a caller with no credential at all.
# You are running this one right now with whatever you have (or have not)
# exported.
vs_call 'gex.levels - Free floor, no credential needed' \
  '/api/v1/gex/levels' 'ticker=SPX' \
  '"    ok=\(.ok)  ticker=\(.ticker)  level keys: \(.levels | keys | join(", "))"'

# meta.access answers "what can this caller reach?" for whatever credential was
# presented - useful as a one-call check that a key is wired up correctly.
vs_note ''
vs_note 'GET /api/v1/meta/access reports the plan the current caller resolves to.'
vs_note 'Run it after exporting a key to confirm the key is actually being sent.'
vs_note ''
vs_note 'One distinction worth having straight before you plan a client around'
vs_note 'the catalog: a Free PLAN FLOOR is not the same promise as "no'
vs_note 'credential needed". Most Free-floor capabilities answer anonymously,'
vs_note 'but some data endpoints ask for any valid key even at that floor. Those'
vs_note 'answer 401 auth_required with a detail that says so and names the'
vs_note 'credential prefixes it accepts, rather than a plan refusal. Read the'
vs_note '`code` and the `detail`; do not infer entitlement from the tier alone.'

# ---------------------------------------------------------------------------

vs_title '3. The same shape of call, above the Free floor'

# gex.snapshot sits at the Edge floor. Anonymously it answers 401 auth_required;
# with a valid key on a plan below Edge it answers a plan refusal instead. Both
# are RFC 9457 problem documents, and both are printed in full below.
vs_call 'gex.snapshot - Edge floor, expected to refuse for most readers' \
  '/api/v1/gex/snapshot' 'ticker=SPX'

vs_note ''
vs_note 'Reading that body, member by member:'
vs_note ''
vs_note '  type               a stable URL identifying the error class'
vs_note '  title / detail     human-readable; detail is the specific one'
vs_note '  status             repeats the HTTP status'
vs_note '  code / error       the machine-readable slug to branch on'
vs_note '  instance           the path that was refused'
vs_note '  request_id         quote this if you need to ask about a request'
vs_note '  ok                 false - refusals keep the envelope flag'
vs_note ''
vs_note 'A plan refusal adds four more:'
vs_note ''
vs_note '  feature            the capability that was gated'
vs_note '  required_plan      the plan slug the caller would need'
vs_note '  required_plan_name the customer-facing name - show this one to a human'
vs_note '  current_plan       what the caller resolves to today'
vs_note ''
vs_note 'Branch on `code`, never on the wording of `detail`.'

# ---------------------------------------------------------------------------

vs_title '4. A path that does not exist'

vs_call 'a made-up path - expect 404 route_not_found' \
  '/api/v1/gex/no_such_capability' ''

vs_note ''
vs_note 'route_not_found means no capability is published at that path - a typo,'
vs_note 'or a name you invented. It is not the same as `not_found`, which means'
vs_note 'the path is right and the resource simply is not there right now.'
vs_note 'GET /api/v1/meta/capabilities is the authoritative list of live paths.'

# ---------------------------------------------------------------------------

vs_title '5. Rate-limit headers'

vs_note 'Every response carries two header families. The modern pair:'
vs_note ''
vs_note '  ratelimit: limit=<n>, remaining=<n>, reset=<seconds>'
vs_note '  ratelimit-policy: "<bucket>";q=<quota>;w=<window seconds>'
vs_note ''
vs_note 'and the legacy set, which carries the same information field by field:'
vs_note ''
vs_note '  x-ratelimit-limit / -remaining / -reset / -bucket / -enforced-by'
vs_note ''
vs_note 'More than one policy can apply to a single request. ratelimit-policy'
vs_note 'lists each one with its quota and window, and x-ratelimit-enforced-by'
vs_note 'names the one that is actually doing the enforcing - which is the'
vs_note 'number to pace yourself against. Here they are, live:'
vs_note ''

# vs_headers runs `curl -D - -o /dev/null`: response headers to stdout, body
# thrown away. It is redirected to a file rather than piped straight into grep
# so that it runs in this shell and its request is counted; the grep keeps the
# families worth looking at, and `|| true` means a proxy that strips one of them
# does not abort the script.
vs_headers '/api/v1/gex/levels' 'ticker=SPX' >"$VS_TMP/hdrs" || true

grep -i -E '^(ratelimit|ratelimit-policy|x-ratelimit-[a-z-]+|retry-after|x-gex-api-version):' \
  "$VS_TMP/hdrs" | sed 's/^/    /' || true

vs_note ''
vs_note 'remaining is what is left in the current window; reset is seconds until'
vs_note 'it refills. On a 429 the response also carries Retry-After - wait that'
vs_note 'long, do not retry immediately, and do not retry a 4xx that is not a 429.'

# ---------------------------------------------------------------------------

vs_title '6. The query-string form, actually used'

if [ -n "${VOLSTRATA_API_KEY:-}" ]; then
  # The key is interpolated into the URL, and the URL is never printed. Only
  # the status comes back out.
  vs_q_rc=0
  vs_q_code="$(
    curl -sS -o /dev/null -w '%{http_code}' \
      -H "User-Agent: $VS_UA" \
      "$BASE/api/v1/meta/access?api_key=$VOLSTRATA_API_KEY"
  )" || vs_q_rc=$?
  VS_REQUEST_COUNT=$((VS_REQUEST_COUNT + 1))
  if [ "$vs_q_rc" -eq 0 ]; then
    vs_note "GET /api/v1/meta/access?api_key=<redacted>  ->  HTTP $vs_q_code"
    vs_note 'Accepted, exactly like the header form. The URL is not printed'
    vs_note 'here, and this script never echoes any part of the key.'
  else
    vs_note 'The request could not be completed; see the stderr line above.'
  fi
else
  vs_note 'Skipped - VOLSTRATA_API_KEY is not set, and this repo will not invent'
  vs_note 'a key to demonstrate with. Export one and re-run to see this branch:'
  vs_note ''
  vs_note '  export VOLSTRATA_API_KEY=YOUR_API_KEY'
  vs_note '  sh examples/curl/auth_and_errors.sh'
fi

vs_title 'Summary'
vs_note 'Free capability, no key            -> 200'
vs_note 'Gated capability, no key           -> 401 auth_required'
vs_note 'Gated capability, key below floor  -> plan refusal naming required_plan_name'
vs_note 'Unknown path                       -> 404 route_not_found'
vs_note 'Too many requests                  -> 429 with Retry-After'
vs_note ''
vs_note 'All five are application/problem+json apart from the 200. A refusal that'
vs_note 'is NOT JSON never reached the API - that is the CDN edge rejecting the'
vs_note 'request, and the usual cause is a missing User-Agent header.'
vs_note ''
vs_note 'Errors: https://volstrata.com/docs/api-errors'
vs_note 'Auth:   https://volstrata.com/docs/api-auth'

vs_footer
exit 0
