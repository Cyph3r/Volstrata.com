#!/usr/bin/env sh
# Copyright 2026 Volstrata.com - https://volstrata.com
#
# The MCP endpoint over raw JSON-RPC 2.0 and nothing else: handshake, tool
# listing, a Free tool call, and a gated one refusing.
# Docs: https://volstrata.com/mcp
#
# Run it:
#     sh examples/curl/mcp.sh
#
# Requests: 6.
#
# There is one MCP endpoint and it is POST https://api.volstrata.com/api/v1/mcp.
# It is the transport an MCP client speaks; this script is what that client
# does, written out in curl so you can watch it happen.

set -eu

VS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
. "$VS_DIR/_common.sh"

MCP_PATH='/api/v1/mcp'

# ---------------------------------------------------------------------------
# mcp_call <label> <json-body> [jq-filter] [query] [raw-ok]
#
# One JSON-RPC message. Anything the endpoint can parse comes back 2xx - 200
# with an envelope for a request, 204 with no body for a notification - so the
# status line tells you almost nothing. The failure signal is the `error` member
# of the envelope, and this helper checks for it explicitly before reading
# anything else.
#
# raw-ok=0 suppresses the without-jq raw dump for responses this script would
# rather summarise than print whole.
# ---------------------------------------------------------------------------
mcp_call() {
  m_label="$1"
  m_body="$2"
  m_filter="${3:-}"
  m_query="${4:-}"
  m_raw="${5:-1}"

  printf '\n--- %s\n' "$m_label"
  printf '    POST %s\n' "$(vs_url "$MCP_PATH" "$m_query")"

  m_rc=0
  vs_post "$MCP_PATH" "$m_body" "$m_query" >"$VS_TMP/rpc" || m_rc=$?
  printf '    HTTP %s\n' "$VS_HTTP_CODE"

  if [ "$m_rc" -ne 0 ]; then
    # A non-200 means the request was stopped before the JSON-RPC layer saw
    # it - bad path, rate limit, or an edge refusal.
    vs_show "$VS_TMP/rpc"
    vs_explain "$VS_HTTP_CODE"
    return 0
  fi

  if [ ! -s "$VS_TMP/rpc" ]; then
    # Correct, not a failure: a notification carries no id, so there is
    # nothing for the server to answer with.
    vs_note 'empty body - expected for a notification.'
    return 0
  fi

  if [ "$VS_JQ" = "0" ]; then
    if [ "$m_raw" = "1" ]; then
      vs_show_head "$VS_TMP/rpc" 600
    else
      vs_note 'A JSON-RPC envelope came back. jq is not installed, so this'
      vs_note 'script does not parse it here; the members worth reading are'
      vs_note 'named in the notes around this call.'
    fi
    return 0
  fi

  # The failure signal, checked before anything else is read.
  if jq -e 'has("error") and (.error != null)' "$VS_TMP/rpc" >/dev/null 2>&1; then
    printf '    JSON-RPC error:\n'
    jq -r '"      code=\(.error.code)  \(.error.message)"' "$VS_TMP/rpc" 2>/dev/null || true
    jq -e '.error.data' "$VS_TMP/rpc" >/dev/null 2>&1 && \
      jq -r '"      data: \(.error.data | tojson)"' "$VS_TMP/rpc" 2>/dev/null || true
    return 0
  fi

  if [ -n "$m_filter" ]; then
    vs_pick "$VS_TMP/rpc" "$m_filter"
  else
    vs_show "$VS_TMP/rpc"
  fi
  return 0
}

vs_title 'MCP over raw JSON-RPC 2.0'
vs_auth_status

vs_note ''
vs_note "endpoint: $BASE$MCP_PATH  (POST only)"
vs_note ''
vs_note 'Three things to know before reading the calls below:'
vs_note ''
vs_note '  1. Every message that expects an answer comes back HTTP 200 with a'
vs_note '     well-formed JSON-RPC envelope - including the failures, which ride'
vs_note '     in the `error` member rather than in the status code. So `curl'
vs_note '     --fail` never fires on a refused tool call, and checking the status'
vs_note '     is not enough: check for `error`. (A notification, which carries no'
vs_note '     id and expects no answer, gets 204 No Content and an empty body.)'
vs_note '  2. Tools are the public capability catalog, projected one to one:'
vs_note '     the tool name IS the dotted capability name is the OpenAPI'
vs_note '     operationId. gex.levels the REST path and gex.levels the tool are'
vs_note '     the same thing behind the same plan gate.'
vs_note '  3. Auth is the same bearer key as the REST API. Anonymous callers see'
vs_note '     and can call the Free tools only.'

# ---------------------------------------------------------------------------
# 1. initialize - the handshake. protocolVersion is negotiated: ask for one and
#    read what comes back, because the server answers with a version it
#    actually supports rather than echoing yours blindly.
#
#    Supported: 2025-11-25 (latest), 2025-06-18, 2025-03-26, 2024-11-05.
#    A client that names none gets 2024-11-05.
# ---------------------------------------------------------------------------
INIT_BODY=$(cat <<'JSON'
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "clientInfo": { "name": "volstrata-curl-examples", "version": "1.0" }
  }
}
JSON
)

mcp_call 'initialize - negotiate the protocol version' \
  "$INIT_BODY" \
  '"    protocolVersion: \(.result.protocolVersion)",
   "    server:          \(.result.serverInfo.title) \(.result.serverInfo.version)",
   "    capabilities:    \(.result.capabilities | keys | join(", "))"' \
  '' \
  '0'

vs_note ''
vs_note 'Members worth reading in that result:'
vs_note ''
vs_note '  result.protocolVersion   the version actually negotiated'
vs_note '  result.serverInfo.title  the display name of the server'
vs_note '  result.capabilities      tools, resources, prompts, completions'
vs_note ''
vs_note 'Use serverInfo.title when you need to name the server in a UI, and'
vs_note 'branch on protocolVersion rather than on what you asked for.'

# ---------------------------------------------------------------------------
# 2. notifications/initialized - a notification: no "id", and no response body
#    is expected. A conforming client sends it once, after initialize, before
#    any normal call.
# ---------------------------------------------------------------------------
INITIALIZED_BODY=$(cat <<'JSON'
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized",
  "params": {}
}
JSON
)

mcp_call 'notifications/initialized - handshake complete' \
  "$INITIALIZED_BODY" \
  "$VS_SUM" \
  '' \
  '0'

# ---------------------------------------------------------------------------
# 3. tools/list - what this caller can see. The list is scoped to the caller's
#    plan: an anonymous caller sees 67 tools (3 server-native meta-tools plus
#    the 64 Free capability tools), a fully entitled one sees 177.
# ---------------------------------------------------------------------------
LIST_BODY=$(cat <<'JSON'
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
JSON
)

mcp_call 'tools/list - the default projection' \
  "$LIST_BODY" \
  '"    tools visible to this caller: \(.result.tools | length)",
   "    first ten: \(.result.tools | map(.name) | sort | .[0:10] | join(", "))"' \
  '' \
  '1'

vs_note ''
vs_note 'Three of those are server-native meta-tools, always present:'
vs_note ''
vs_note '  catalog.search    find a capability by what it does'
vs_note '  capability.call   universal dispatcher: {name, arguments}, same gate'
vs_note '  docs.search       look up a metric definition'
vs_note ''
vs_note 'Every tool object carries name, title, description, inputSchema (with'
vs_note 'defaults and enums), outputSchema and annotations. Capability tools add'
vs_note 'a _meta block naming the method, path, policy key and plan tier behind'
vs_note 'them; the three meta-tools have no REST route, so they carry no _meta -'
vs_note 'which is how you tell the two kinds apart.'

# ---------------------------------------------------------------------------
# 4. tools/list?toolset=lean - the selector. A smaller table for a client with
#    a tight context budget, or a domain-filtered one for a focused agent.
# ---------------------------------------------------------------------------
mcp_call 'tools/list with ?toolset=lean' \
  "$LIST_BODY" \
  '"    tools: \(.result.tools | length)",
   "    names: \(.result.tools | map(.name) | sort | join(", "))"' \
  'toolset=lean' \
  '1'

vs_note ''
vs_note 'toolset= accepts:'
vs_note ''
vs_note '  (omitted)     the full projection, scoped to your plan'
vs_note '  lean          10 tools: the 3 meta-tools plus 7 orientation reads'
vs_note '  gex,levels    domain-filtered - any comma-separated domain list'
vs_note ''
vs_note 'It can also be sent inside params rather than on the query string, for'
vs_note 'clients that cannot control the URL.'

# ---------------------------------------------------------------------------
# 5. tools/call on a Free tool.
#
# The result is the MCP shape, not the REST shape:
#   {content: [{type: "text", text: "<pretty JSON>"}],
#    isError: false,
#    structuredContent: { ...the same payload, parsed... }}
#
# Read structuredContent. `content` is the human/LLM-readable rendering of the
# same thing.
# ---------------------------------------------------------------------------
CALL_BODY=$(cat <<'JSON'
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "gex.levels",
    "arguments": { "ticker": "SPX" }
  }
}
JSON
)

mcp_call 'tools/call gex.levels - Free, works anonymously' \
  "$CALL_BODY" \
  '"    isError: \(.result.isError)",
   "    content blocks: \(.result.content | length) (\(.result.content[0].type))",
   "    structuredContent keys: \(.result.structuredContent | keys | join(", "))"' \
  '' \
  '1'

# ---------------------------------------------------------------------------
# 6. tools/call on a gated tool.
#
# gex.snapshot is at the Edge floor. For a caller below it the tool is hidden
# from tools/list AND refused by tools/call - listing and calling are gated
# separately, so never assume a tool you did not see is simply missing.
#
# The refusal is JSON-RPC error -32001 with data:
#   {current_tier, required_plan, required_plan_name, tool}
# ---------------------------------------------------------------------------
GATED_BODY=$(cat <<'JSON'
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "gex.snapshot",
    "arguments": { "ticker": "SPX" }
  }
}
JSON
)

mcp_call 'tools/call gex.snapshot - Edge floor, expected to refuse' \
  "$GATED_BODY" \
  '"    isError: \(.result.isError)"' \
  '' \
  '1'

vs_note ''
vs_note 'JSON-RPC error codes you can get back:'
vs_note ''
vs_note '  -32700  parse error            -32603  internal error'
vs_note '  -32600  invalid request        -32001  access denied (plan floor)'
vs_note '  -32601  method not found       -32002  resource not found'
vs_note '  -32602  invalid params'
vs_note ''
vs_note 'Branch on the code. -32001 carries data.required_plan_name, which is the'
vs_note 'string to show a human.'

vs_title 'The rest of the surface'
vs_note 'Methods this endpoint answers, beyond the five used above:'
vs_note ''
vs_note '  ping                       resources/read'
vs_note '  resources/list             prompts/list'
vs_note '  resources/templates/list   prompts/get'
vs_note '  completion/complete'
vs_note ''
vs_note 'Five resources are published (a manifest, a glossary, level'
vs_note 'definitions, the plan table and a forecast scoreboard), two resource'
vs_note 'templates, and nine prompts. resources/list and prompts/list enumerate'
vs_note 'them; both are Free.'
vs_note ''
vs_note 'The request bodies used here are also checked in as files, one per'
vs_note 'method, if you would rather not paste a here-doc:'
vs_note ''
vs_note "  curl -sS -X POST \\"
vs_note "    -H 'Content-Type: application/json' \\"
vs_note "    -H 'User-Agent: volstrata-examples/1.0' \\"
vs_note "    --data @examples/mcp/requests/tools_list.json \\"
vs_note "    $BASE$MCP_PATH"

vs_title 'Pointing a real client at it'
vs_note 'The configuration block an MCP client wants:'
vs_note ''
vs_note '  {'
vs_note '    "mcpServers": {'
vs_note '      "volstrata": {'
vs_note "        \"url\": \"$BASE$MCP_PATH\","
vs_note '        "headers": { "Authorization": "Bearer YOUR_API_KEY" }'
vs_note '      }'
vs_note '    }'
vs_note '  }'
vs_note ''
vs_note 'Drop the headers block entirely to connect anonymously and get the Free'
vs_note 'tools. Ready-made files live in examples/mcp/.'
vs_note ''
vs_note 'Connect page: https://volstrata.com/mcp'

vs_footer
exit 0
