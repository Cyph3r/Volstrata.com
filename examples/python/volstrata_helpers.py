"""Copyright 2026 Volstrata.com

Shared helpers for the VolStrata API examples.
Docs: https://volstrata.com/docs/api-overview

Every other example in this folder imports this module. It is deliberately small
and depends on nothing but `requests` and the standard library, so you can read
it end to end in a few minutes and copy the parts you want into your own project.

What it gives you:

  session()               a configured requests.Session (User-Agent + optional key)
  get(path, **params)     one GET, status checked first, parsed JSON returned
  post(path, body)        one POST with a JSON body
  paginate(path, ...)     a bounded generator over a cursor-paged collection
  VolstrataError          the RFC 9457 problem+json body, as an exception
  request_with_backoff()  retry on 429/5xx only, honouring Retry-After
  attempt(label, fn, ...) run a call that may be refused, and never crash
  run_examples(steps)     run a list of steps in order and always exit 0
  show(obj)               a compact pretty-printer for terminal output
  mcp_session() / rpc()   raw JSON-RPC 2.0 against the MCP endpoint
  mcp_initialize(sess)    the MCP handshake, in one call
  mcp_structured(result)  the machine-readable half of a tools/call result

Two environment variables are read, and nothing else:

  VOLSTRATA_API_KEY   optional. When present it is sent as `Authorization: Bearer
                      <key>`. Many capabilities answer without it.
  VOLSTRATA_API_BASE  optional. Defaults to the canonical API host,
                      https://api.volstrata.com

Never put a key in source. Export it in your shell instead:

  export VOLSTRATA_API_KEY=...        # macOS / Linux
  $env:VOLSTRATA_API_KEY = "..."      # Windows PowerShell

Key management: https://volstrata.com/docs/api-keys
"""

from __future__ import annotations

import json
import os
import random
import time
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple

import requests

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# The canonical API host. VOLSTRATA_API_BASE exists so you can point the examples
# at a proxy of your own; it is not something you normally need to set. The older
# VOLSTRATA_BASE_URL is still read as a fallback.
BASE = (
    os.environ.get("VOLSTRATA_API_BASE")
    or os.environ.get("VOLSTRATA_BASE_URL")
    or "https://api.volstrata.com"
).rstrip("/")

# Optional. Running with no key at all is a supported mode, not a degraded one:
# a large part of the published surface answers an anonymous caller.
API_KEY = os.environ.get("VOLSTRATA_API_KEY")

# Every capability path hangs off /api/v1. There is no other live base path.
API = BASE + "/api/v1"

# The MCP transport is one POST endpoint under the same base path.
MCP_URL = API + "/mcp"

# A real, identifying User-Agent is MANDATORY, not politeness. The CDN in front
# of the API refuses some default agents (the Python standard library's
# `Python-urllib/*` among them) with a plain-text 403 that the API never sees.
# If you ever get a non-JSON refusal, this is almost always why.
USER_AGENT = "volstrata-examples/1.0 (+https://volstrata.com)"

DEFAULT_TIMEOUT = 30  # seconds


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class VolstrataError(Exception):
    """A refused request.

    The API answers every refusal with RFC 9457 `application/problem+json`:

        {
          "ok": false,
          "type": "<origin>/errors/<code>",
          "title": "Authentication required",
          "status": 401,
          "detail": "...",
          "instance": "/api/v1/...",
          "code": "auth_required",
          "request_id": "<opaque id>"
        }

    A plan refusal carries four extra keys: `feature`, `required_plan`,
    `required_plan_name` and `current_plan`. `required_plan_name` is the
    customer-facing name ("Edge", "Pro") and is the one to show a human.

    Reference: https://volstrata.com/docs/api-errors
    """

    def __init__(
        self,
        status: int,
        body: Any = None,
        raw_text: str = "",
        url: str = "",
    ) -> None:
        self.status = status
        self.url = url
        self.raw_text = raw_text
        # True when the body really was a JSON object, i.e. this came from the
        # API rather than from something in front of it (see USER_AGENT above).
        self.from_api = isinstance(body, dict)
        body = body if isinstance(body, dict) else {}
        self.body: Dict[str, Any] = body
        self.code = body.get("code") or body.get("error")
        self.title = body.get("title")
        self.detail = body.get("detail")
        self.request_id = body.get("request_id")
        self.required_plan_name = body.get("required_plan_name")
        self.current_plan = body.get("current_plan")
        self.feature = body.get("feature")
        super().__init__(str(self))

    @property
    def needs_plan(self) -> bool:
        """True when this refusal is a plan floor rather than a mistake."""
        return bool(self.required_plan_name)

    @property
    def needs_credential(self) -> bool:
        """True when no usable credential was presented (HTTP 401)."""
        return self.status == 401 or self.code == "auth_required"

    def __str__(self) -> str:
        if not self.from_api and self.status < 400:
            return (
                "HTTP {0} with a body that was not a JSON object. Every capability "
                "returns an object at the top level; check the `format` parameter "
                "if you asked for csv, pine or txt.".format(self.status)
            )
        if not self.from_api:
            snippet = " ".join(self.raw_text.split())[:120]
            return (
                "HTTP {status} with a non-JSON body: this response did not come from "
                "the API. A request refused at the CDN edge never reaches it, and the "
                "usual cause is a missing or default User-Agent header. "
                "Body starts: {snippet!r}".format(status=self.status, snippet=snippet)
            )
        parts = ["HTTP {0}".format(self.status)]
        if self.code:
            parts.append(self.code)
        head = " ".join(parts)
        if self.needs_plan:
            tail = "{0} requires the {1} plan".format(
                self.feature or "this capability", self.required_plan_name
            )
            if self.current_plan:
                tail += " (you are on {0})".format(self.current_plan)
        else:
            tail = self.detail or self.title or "request refused"
        line = "{0}: {1}".format(head, tail)
        if self.request_id:
            line += " [request_id={0}]".format(self.request_id)
        return line


class McpError(Exception):
    """A JSON-RPC `error` member returned by the MCP endpoint.

    Once a request is past the rate limiter the MCP endpoint answers HTTP 200
    for everything, so protocol-level failures arrive in `error`, never as a
    4xx. Codes:

        -32700 parse error          -32603 internal error
        -32600 invalid request      -32001 access denied (plan floor)
        -32601 method not found     -32002 resource not found
        -32602 invalid params

    A -32001 carries `data`: {current_tier, required_plan, required_plan_name, tool}.

    Reference: https://volstrata.com/mcp
    """

    def __init__(self, error: Dict[str, Any]) -> None:
        self.code = error.get("code")
        self.message = error.get("message") or "MCP error"
        self.data: Dict[str, Any] = error.get("data") or {}
        self.required_plan_name = self.data.get("required_plan_name")
        self.current_tier = self.data.get("current_tier")
        self.tool = self.data.get("tool")
        super().__init__(str(self))

    @property
    def access_denied(self) -> bool:
        return self.code == -32001

    def __str__(self) -> str:
        line = "JSON-RPC {0}: {1}".format(self.code, self.message)
        if self.required_plan_name:
            line += " (needs the {0} plan".format(self.required_plan_name)
            if self.current_tier:
                line += "; you are on {0}".format(self.current_tier)
            line += ")"
        return line


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


def have_key() -> bool:
    """True when VOLSTRATA_API_KEY was set in the environment."""
    return bool(API_KEY)


def session() -> requests.Session:
    """Build a Session with the headers every call to the API should carry.

    The Authorization header is set only when a key is present. The alternative
    presentation, `?api_key=<key>` on the query string, is accepted everywhere
    the header is; prefer the header, because query strings end up in access
    logs, proxies and browser history.
    """
    sess = requests.Session()
    sess.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
    )
    if API_KEY:
        sess.headers["Authorization"] = "Bearer " + API_KEY
    return sess


_DEFAULT_SESSION = None  # type: Optional[requests.Session]


def default_session() -> requests.Session:
    """A lazily-created module-level Session, reused by get() and post()."""
    global _DEFAULT_SESSION
    if _DEFAULT_SESSION is None:
        _DEFAULT_SESSION = session()
    return _DEFAULT_SESSION


# Only these deserve a second attempt. A 400 or a 402 will be refused again just
# as fast, and retrying a plan refusal only burns rate-limit budget.
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

MAX_ATTEMPTS = 4  # hard cap, including the first try


def _retry_after_seconds(response: requests.Response) -> Optional[float]:
    """Parse Retry-After (delta-seconds form). Returns None when absent or odd."""
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(raw.strip()))
    except ValueError:
        return None


def request_with_backoff(
    method: str,
    url: str,
    sess: Optional[requests.Session] = None,
    max_attempts: int = MAX_ATTEMPTS,
    **kwargs: Any
) -> requests.Response:
    """Perform one request, retrying only 429 and 5xx, and return the Response.

    On a 429 the server sends `Retry-After` in seconds; that always wins.
    Otherwise back off exponentially with a little jitter, so a fleet of clients
    does not retry in lockstep. Four attempts total is the ceiling: past that you
    are not recovering from a blip, you are adding load.

    Rate limits are per owner, not per key, so minting a second key does not
    raise the ceiling. Reference: https://volstrata.com/docs/api-rate-limits
    """
    sess = sess or default_session()
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    attempts = max(1, min(int(max_attempts), MAX_ATTEMPTS))
    last = None  # type: Optional[requests.Response]

    for attempt_no in range(1, attempts + 1):
        last = sess.request(method, url, **kwargs)
        if last.status_code not in RETRY_STATUSES or attempt_no == attempts:
            return last
        wait = _retry_after_seconds(last)
        if wait is None:
            # 0.5s, 1s, 2s ... plus up to 250ms of jitter.
            wait = (2 ** (attempt_no - 1)) * 0.5 + random.uniform(0, 0.25)
        wait = min(wait, 30.0)
        print("  (HTTP {0}; waiting {1:.0f}s before retry {2} of {3})".format(
            last.status_code, wait, attempt_no + 1, attempts))
        time.sleep(wait)

    return last  # unreachable in practice; keeps type checkers happy


def _parse_or_none(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def raise_for_problem(response: requests.Response) -> None:
    """Check the HTTP status FIRST, and only then look at the body.

    This ordering matters. A body that happens to contain `ok` proves nothing:
    a refusal in front of the API can return any shape at all, including none.
    Status code first, every time.
    """
    if response.status_code < 400:
        return
    raise VolstrataError(
        status=response.status_code,
        body=_parse_or_none(response),
        raw_text=response.text or "",
        url=response.url,
    )


def url_for(path: str) -> str:
    """Resolve a capability path to an absolute URL.

    `path` may be a bare capability path ("/gex/levels"), a full API path
    ("/api/v1/gex/levels") or an absolute URL.
    """
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if path.startswith("/api/"):
        return BASE + path
    return API + "/" + path.lstrip("/")


def call(
    path: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
    sess: Optional[requests.Session] = None,
) -> requests.Response:
    """Low-level entry point: returns the checked Response, headers and all."""
    clean = dict((k, v) for k, v in (params or {}).items() if v is not None)
    kwargs = {"params": clean}  # type: Dict[str, Any]
    if body is not None:
        kwargs["json"] = body
    response = request_with_backoff(method, url_for(path), sess=sess, **kwargs)
    raise_for_problem(response)
    return response


def get(path: str, **params: Any) -> Dict[str, Any]:
    """GET one capability and return the parsed JSON body.

    Raises VolstrataError on any 4xx/5xx, including plan refusals.

        levels = get("/gex/levels", ticker="SPX")
    """
    response = call(path, "GET", params=params)
    data = _parse_or_none(response)
    if not isinstance(data, dict):
        raise VolstrataError(response.status_code, None, response.text or "", url=response.url)
    return data


def post(path: str, body: Optional[Dict[str, Any]] = None, **params: Any) -> Dict[str, Any]:
    """POST a JSON body to one capability and return the parsed JSON body.

    Only 7 of the 180 published operations take POST; the rest are GET.
    """
    response = call(path, "POST", params=params, body=body or {})
    data = _parse_or_none(response)
    if not isinstance(data, dict):
        raise VolstrataError(response.status_code, None, response.text or "", url=response.url)
    return data


def rate_limit(response: requests.Response) -> Dict[str, Any]:
    """Pull the rate-limit headers off a Response.

    Two families are sent on every response: the modern combined
    `ratelimit: limit=..., remaining=..., reset=...` alongside `ratelimit-policy`,
    and the legacy `x-ratelimit-*` set. `ratelimit-policy` names each policy in
    play and says which one is enforced, so read it before you tune anything.
    """
    h = response.headers
    return {
        "ratelimit": h.get("ratelimit"),
        "ratelimit-policy": h.get("ratelimit-policy"),
        "x-ratelimit-limit": h.get("x-ratelimit-limit"),
        "x-ratelimit-remaining": h.get("x-ratelimit-remaining"),
        "x-ratelimit-reset": h.get("x-ratelimit-reset"),
        "x-ratelimit-bucket": h.get("x-ratelimit-bucket"),
    }


# --------------------------------------------------------------------------
# Pagination
# --------------------------------------------------------------------------

# A safety rail. These examples run against live production under a modest
# per-minute ceiling, so no loop here is allowed to be unbounded.
DEFAULT_MAX_PAGES = 10


def paginate(
    path: str,
    max_pages: int = DEFAULT_MAX_PAGES,
    **params: Any
) -> Iterator[Dict[str, Any]]:
    """Yield successive pages of a cursor-paged collection.

    Paged responses share one field, and it is the only one this loop needs:

        {"ok": true, "next_cursor": "<opaque>" | null, "<collection>": [...]}

    Follow `next_cursor` until it comes back null. Cursors are opaque: pass the
    string straight back as `?cursor=`, never parse or construct one. 17 of the
    published operations declare a cursor parameter.

    Row counters are per-operation rather than part of the shared contract: an
    operation may report a page size, a total, both or neither, and the names
    vary (`meta.capabilities` reports `count`). Read them with .get() and never
    terminate on one.

    Reference: https://volstrata.com/docs/api-base-url
    """
    cursor = params.pop("cursor", None)  # type: Optional[str]
    for _ in range(max(1, int(max_pages))):
        page = get(path, cursor=cursor, **params)
        yield page
        cursor = page.get("next_cursor")
        if not cursor:
            return


def collect(
    path: str,
    key: str,
    max_pages: int = DEFAULT_MAX_PAGES,
    **params: Any
) -> Tuple[List[Any], Optional[str]]:
    """Page through a collection and return (rows, cursor_still_pending).

    A non-None second element means the page bound stopped you early, not that
    the collection ended.
    """
    rows = []  # type: List[Any]
    pending = None  # type: Optional[str]
    for page in paginate(path, max_pages=max_pages, **params):
        rows.extend(page.get(key) or [])
        pending = page.get("next_cursor")
    return rows, pending


# --------------------------------------------------------------------------
# Output helpers -- terminal readability only, nothing API-specific
# --------------------------------------------------------------------------


def heading(text: str) -> None:
    """Print a section header."""
    print("\n" + text)
    print("-" * min(len(text), 72))


def _trim(obj: Any, max_items: int, depth: int = 0) -> Any:
    if isinstance(obj, dict):
        if depth >= 4:
            return "{{...{0} keys...}}".format(len(obj))
        return dict((k, _trim(v, max_items, depth + 1)) for k, v in obj.items())
    if isinstance(obj, list):
        if depth >= 4:
            return "[...{0} items...]".format(len(obj))
        head = [_trim(v, max_items, depth + 1) for v in obj[:max_items]]
        if len(obj) > max_items:
            head.append("... {0} more".format(len(obj) - max_items))
        return head
    if isinstance(obj, str) and len(obj) > 160:
        return obj[:157] + "..."
    return obj


def show(obj: Any, max_items: int = 5, max_chars: int = 1600) -> None:
    """Pretty-print a response compactly: long lists and long strings are cut.

    Use this while exploring. In real code, read the fields you need by name.
    """
    text = json.dumps(_trim(obj, max_items), indent=2, sort_keys=False, default=str)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n  ... output truncated ..."
    print(text)


def row(label: str, value: Any, width: int = 26) -> None:
    """Print one aligned label/value line."""
    print("  {0:<{1}} {2}".format(label + ":", width, value))


def describe_freshness(payload: Dict[str, Any]) -> str:
    """Summarise the shared Freshness / Delivery blocks when a response has them.

    Freshness: {as_of, age_seconds, live, stale, stale_after_seconds}
    Delivery:  {mode: "live"|"delayed", delay_seconds, reason}

    `delay_seconds` is `0` when the body really is realtime, and `null` when it
    is delayed by an amount the server cannot state. The two are not
    interchangeable: never coerce `null` to `0`, because that turns "delayed by
    an unknown amount" into "not delayed at all". Branch on `None` explicitly.
    `reason` is "plan_tier", "source_delay" or null.

    One practical note about timestamps anywhere on this surface: check the
    magnitude before you convert. A ten-digit number is unix seconds and a
    thirteen-digit one is milliseconds, and both turn up. Dividing by the wrong
    thousand puts you in 1970 or in the year 58000, which at least fails loudly.
    """
    bits = []
    fresh = payload.get("freshness")
    if isinstance(fresh, dict):
        bits.append(
            "as_of={0} age={1}s stale={2}".format(
                fresh.get("as_of"), fresh.get("age_seconds"), fresh.get("stale")
            )
        )
    delivery = payload.get("delivery")
    if isinstance(delivery, dict):
        delay = delivery.get("delay_seconds")
        if delay is None:
            # NOT the same as 0. The server is saying "delayed, magnitude
            # unknown" -- render that, never "no delay".
            detail = " (delay not stated)"
        elif delay == 0:
            detail = " (+0s, realtime)"
        else:
            detail = " (+{0}s, {1})".format(delay, delivery.get("reason"))
        bits.append("delivery={0}{1}".format(delivery.get("mode"), detail))
    return " | ".join(bits) if bits else "(no freshness block on this response)"


def attempt(label: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Optional[Any]:
    """Run a call that some readers will not be entitled to, and never crash.

    Returns the result, or None after printing a one-line explanation. This is
    how every gated example in this repo degrades: a reader without the plan
    still gets a complete, successful run and a clear statement of what is
    missing.
    """
    try:
        return fn(*args, **kwargs)
    except VolstrataError as exc:
        if exc.needs_plan:
            # 402 with a plan floor: the credential is fine, the plan is not.
            print("  {0}: not included in your plan -- needs {1}.".format(
                label, exc.required_plan_name))
        elif exc.needs_credential:
            # 401: no usable credential was presented. Any accepted credential
            # gets you past this one; whether data comes back then depends on
            # the plan behind it.
            print("  {0}: needs a credential -- set VOLSTRATA_API_KEY and re-run.".format(
                label))
        elif exc.code == "not_found":
            # 404 `not_found` (as opposed to `route_not_found`) means the route
            # is right and there is simply nothing to return at the moment.
            print("  {0}: nothing to return right now -- {1}".format(
                label, exc.detail or "not found"))
        else:
            print("  {0}: {1}".format(label, exc))
        return None
    except McpError as exc:
        print("  {0}: {1}".format(label, exc))
        return None
    except requests.RequestException as exc:
        print("  {0}: network error -- {1}".format(label, exc.__class__.__name__))
        return None


def run_examples(steps: Iterable[Tuple[str, Callable[[], Any]]]) -> int:
    """Run a list of (label, function) steps in order and always exit 0.

    Sequential on purpose: these examples talk to live production, so there is
    no concurrency anywhere in this repo.
    """
    for label, step in steps:
        try:
            step()
        except VolstrataError as exc:
            # A refused call is a legitimate outcome for an example. Report it
            # and keep going, so the rest of the file still teaches something.
            print("  ({0} could not complete: {1})".format(label, exc))
        except requests.RequestException as exc:
            print("  ({0} could not complete: network error, {1})".format(
                label, exc.__class__.__name__))
    return 0


def key_banner() -> None:
    """One line telling the reader which mode they are running in."""
    if have_key():
        print("VOLSTRATA_API_KEY detected -- calls are authenticated.")
    else:
        print("No VOLSTRATA_API_KEY set -- running anonymously.")


# --------------------------------------------------------------------------
# MCP -- raw JSON-RPC 2.0, no SDK
# --------------------------------------------------------------------------

# The protocol revision this repo asks for. The server negotiates and echoes a
# supported revision back in the initialize result, so read what you got rather
# than assuming you got what you asked for.
MCP_PROTOCOL_VERSION = "2025-06-18"

MCP_CLIENT_INFO = {"name": "volstrata-examples", "version": "1.0"}


def mcp_session() -> requests.Session:
    """A Session configured for the MCP endpoint (same auth as the REST API)."""
    sess = session()
    sess.headers["Content-Type"] = "application/json"
    return sess


_RPC_ID = [0]


def rpc(
    sess: requests.Session,
    method: str,
    params: Optional[Dict[str, Any]] = None,
    notify: bool = False,
    url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Send one JSON-RPC 2.0 message to the MCP endpoint.

    Two failure channels, and a client has to handle both:

      * transport -- a request stopped before the protocol layer (rate limiting,
        for instance) answers with an HTTP status and a problem+json body, so
        the status is checked first and raises VolstrataError.
      * protocol  -- everything else answers HTTP 200 with a JSON-RPC envelope,
        and a failure rides in its `error` member, which raises McpError.

    `notify=True` sends a notification: no `id`, and no response body to read.
    That is what `notifications/initialized` is.
    """
    payload = {"jsonrpc": "2.0", "method": method}  # type: Dict[str, Any]
    if params is not None:
        payload["params"] = params
    if not notify:
        _RPC_ID[0] += 1
        payload["id"] = _RPC_ID[0]

    response = request_with_backoff("POST", url or MCP_URL, sess=sess, json=payload)
    raise_for_problem(response)
    if notify:
        return None

    envelope = _parse_or_none(response)
    if not isinstance(envelope, dict):
        raise VolstrataError(
            response.status_code, None, response.text or "", url=response.url
        )
    if envelope.get("error"):
        raise McpError(envelope["error"])
    result = envelope.get("result")
    return result if isinstance(result, dict) else {}


def mcp_initialize(
    sess: requests.Session,
    url: Optional[str] = None,
    protocol_version: str = MCP_PROTOCOL_VERSION,
) -> Dict[str, Any]:
    """Run the MCP handshake: initialize, then the initialized notification.

    Returns the initialize result: {protocolVersion, capabilities, serverInfo,
    instructions}. A client must send `notifications/initialized` before issuing
    normal calls.
    """
    result = rpc(
        sess,
        "initialize",
        {
            "protocolVersion": protocol_version,
            "capabilities": {},
            "clientInfo": MCP_CLIENT_INFO,
        },
        url=url,
    ) or {}
    rpc(sess, "notifications/initialized", {}, notify=True, url=url)
    return result


def mcp_structured(result: Dict[str, Any]) -> Any:
    """Pull the machine-readable half out of a tools/call result.

    A tools/call result is:

        {"content": [{"type": "text", "text": "<pretty JSON>"}],
         "isError": false,
         "structuredContent": {...}}

    `content` is for a model to read; `structuredContent` is the same payload as
    real JSON, and is what your code should use.
    """
    if result.get("structuredContent") is not None:
        return result["structuredContent"]
    for block in result.get("content") or []:
        if block.get("type") == "text":
            try:
                return json.loads(block.get("text") or "")
            except ValueError:
                return block.get("text")
    return None
