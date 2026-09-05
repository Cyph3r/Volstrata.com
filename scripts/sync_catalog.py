#!/usr/bin/env python3
"""Generate the VolStrata API + MCP reference under ``docs/reference/``.

Everything this script writes is derived from two public, unauthenticated
sources on https://volstrata.com — no API key is read, sent or required:

  * ``GET  /api/openapi.json``            the OpenAPI 3.1 document (REST surface)
  * ``GET  /api/v1/meta/capabilities``    the paged runtime capability catalog
  * ``POST /api/v1/mcp``                  JSON-RPC ``tools/list``, called with no
                                          credentials, to learn which MCP tools a
                                          key-less caller can actually see

It produces exactly four files:

  * ``docs/reference/openapi.json``       byte-for-byte verbatim copy of the spec
  * ``docs/reference/REST_ENDPOINTS.md``  rendered from that spec
  * ``docs/reference/mcp-tools.json``     rendered from the capability catalog
  * ``docs/reference/MCP_TOOLS.md``       rendered from ``mcp-tools.json``

Design rules, because CI diffs the committed copies against a fresh run:

  * Determinism. Nothing that varies between two runs of the same catalog is
    ever written: no wall-clock date, no hostname, no username, no local path,
    no run id. The only version markers stamped into a generated file are
    ``info.version`` and ``info["x-catalog-fingerprint"]``, both read from the
    spec itself. Every collection this script builds is sorted, and every text
    file is written with LF line endings.
  * ``--base`` changes where bytes are *fetched from*; it never changes what is
    *written*. Public URLs printed into the generated files are derived from
    ``servers[0].url`` inside the spec, so pointing the fetcher somewhere else
    cannot leak that location into a committed artifact.
  * The CDN in front of the API refuses some default User-Agents before the
    request ever reaches the API — a plain-text body rather than the API's
    RFC 9457 JSON is the tell. The Python standard library's default
    ``Python-urllib/*`` is one of the refused ones, so every request below sets
    an explicit User-Agent.

Usage::

    python scripts/sync_catalog.py                 # regenerate from the live host
    python scripts/sync_catalog.py --check         # verify the committed copies
    python scripts/sync_catalog.py --source local:./openapi.json

Standard library only. See ``scripts/README.md``.

Copyright 2026 Volstrata.com - https://volstrata.com
"""

from __future__ import annotations

import argparse
import filecmp
import json
import pathlib
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, OrderedDict

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

#: Public host the reference is generated from. Overridable with ``--base``.
DEFAULT_BASE = "https://volstrata.com"

#: Fallback for the public URLs written into generated files, used only if the
#: spec somehow carries no ``servers`` entry. Normally taken from the spec.
CANONICAL_BASE = "https://volstrata.com"

#: urllib's default ``Python-urllib/*`` is refused at the CDN edge with a
#: plain-text body before the API sees it. Always send a real User-Agent.
USER_AGENT = "volstrata-examples-sync/1.0 (+https://volstrata.com)"

OPENAPI_PATH = "/api/openapi.json"
CAPABILITIES_PATH = "/api/v1/meta/capabilities"
MCP_PATH = "/api/v1/mcp"

#: Printed into the generated files so a reader knows how to reproduce them.
GENERATING_COMMAND = "python scripts/sync_catalog.py"

#: The MCP transport itself is published as a capability, but it is the door,
#: not a tool behind it, so it is never projected as an MCP tool.
MCP_TRANSPORT_CAPABILITY = "meta.mcp"

#: Display order for the plan-floor summary line. Counts and customer-facing
#: plan names are always read from the spec; this list only decides the order
#: they are printed in. Any plan slug not listed here is appended
#: alphabetically, so a new plan degrades to a sorted position rather than
#: disappearing.
PLAN_DISPLAY_ORDER = ("free", "edge", "pro", "ultra", "desk", "quant")

#: Same idea for HTTP methods.
METHOD_DISPLAY_ORDER = ("GET", "POST", "PUT", "PATCH", "DELETE")

HTTP_TIMEOUT_SECONDS = 60
MAX_ATTEMPTS = 3
MAX_RETRY_SLEEP_SECONDS = 65
#: Anonymous callers get a small per-minute budget; a full run is well under it,
#: but spacing requests keeps a back-to-back re-run from tripping the ceiling.
MIN_REQUEST_INTERVAL_SECONDS = 0.4
#: Every pagination loop is bounded. The catalog is a few hundred rows over
#: 25-row pages; this is a wide margin, not a target.
MAX_CATALOG_PAGES = 40

RETRYABLE_STATUS = (429, 500, 502, 503, 504)

GENERATED_FILES = (
    "openapi.json",
    "REST_ENDPOINTS.md",
    "mcp-tools.json",
    "MCP_TOOLS.md",
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
REFERENCE_DIR = REPO_ROOT / "docs" / "reference"

COPYRIGHT = "Copyright 2026 Volstrata.com - https://volstrata.com"

DO_NOT_EDIT = (
    "Generated file - do not edit by hand. "
    "Regenerate with `{cmd}`; CI fails on any difference."
).format(cmd=GENERATING_COMMAND)


class SyncError(Exception):
    """A failure a user should read as a sentence, not as a traceback."""


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

_last_request_at = [0.0]


def _throttle():
    elapsed = time.monotonic() - _last_request_at[0]
    if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
        time.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)
    _last_request_at[0] = time.monotonic()


def _retry_after_seconds(headers, attempt):
    """Honour ``Retry-After`` when present, else back off gently."""
    raw = headers.get("Retry-After") if headers else None
    if raw:
        try:
            return min(max(float(raw), 1.0), MAX_RETRY_SLEEP_SECONDS)
        except (TypeError, ValueError):
            pass
    return min(2.0 * (attempt + 1), MAX_RETRY_SLEEP_SECONDS)


def _describe_http_error(url, status, headers, payload):
    """Turn a refusal into one readable line, including the edge/UA trap."""
    content_type = (headers.get("Content-Type") or "").lower() if headers else ""
    text = ""
    if payload:
        try:
            text = payload.decode("utf-8", "replace").strip()
        except Exception:  # pragma: no cover - decoding a bytes object
            text = ""

    if "json" in content_type:
        try:
            body = json.loads(payload.decode("utf-8"))
        except Exception:
            body = None
        if isinstance(body, dict):
            bits = [str(body.get(k)) for k in ("code", "title", "detail") if body.get(k)]
            if bits:
                return "HTTP {0} from {1}: {2}".format(status, url, " - ".join(bits))
        return "HTTP {0} from {1}: {2}".format(status, url, text[:400])

    hint = ""
    if status in (403, 1010) or "error code" in text.lower():
        hint = (
            " This body is not JSON, which means the request never reached the API - "
            "it was refused at the CDN edge. That is usually a blocked User-Agent; "
            "this script sends '{ua}'.".format(ua=USER_AGENT)
        )
    return "HTTP {0} from {1}: {2}{3}".format(status, url, text[:400] or "(empty body)", hint)


def _fetch(url, method="GET", body=None):
    """Fetch a URL, returning raw bytes. Raises SyncError with a plain message."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"

    last_error = None
    for attempt in range(MAX_ATTEMPTS):
        _throttle()
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            payload = b""
            try:
                payload = exc.read()
            except Exception:  # pragma: no cover - body already consumed
                pass
            message = _describe_http_error(url, exc.code, exc.headers, payload)
            if exc.code in RETRYABLE_STATUS and attempt + 1 < MAX_ATTEMPTS:
                delay = _retry_after_seconds(exc.headers, attempt)
                print(
                    "  retrying in {0:.0f}s ({1})".format(delay, message),
                    file=sys.stderr,
                )
                time.sleep(delay)
                last_error = message
                continue
            raise SyncError(message)
        except OSError as exc:
            reason = getattr(exc, "reason", exc)
            message = "could not reach {0}: {1}".format(url, reason)
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(min(2.0 * (attempt + 1), MAX_RETRY_SLEEP_SECONDS))
                last_error = message
                continue
            raise SyncError(
                message
                + ". Check network access to the public host; this script needs no "
                "credentials, only outbound HTTPS."
            )
    raise SyncError(last_error or "request to {0} failed".format(url))


def _fetch_json(url, method="GET", body=None):
    raw = _fetch(url, method=method, body=body)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise SyncError(
            "response from {0} was not valid JSON ({1}). A non-JSON body from this "
            "API means the request was refused before it arrived - see the "
            "User-Agent note in this script's docstring.".format(url, exc)
        )


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------


def load_openapi_bytes(base, source):
    """Return the raw spec bytes, verbatim, from the live host or a local file."""
    if source and source != "live":
        if not source.startswith("local:"):
            raise SyncError(
                "--source must be 'live' or 'local:<path>' (got {0!r})".format(source)
            )
        path = pathlib.Path(source[len("local:") :]).expanduser()
        if not path.is_file():
            raise SyncError("local spec not found: {0}".format(path))
        return path.read_bytes()
    return _fetch(base + OPENAPI_PATH)


def parse_openapi(raw):
    try:
        spec = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise SyncError("spec is not valid JSON: {0}".format(exc))
    if not isinstance(spec, dict) or "paths" not in spec:
        raise SyncError("spec does not look like an OpenAPI document (no 'paths')")
    return spec


def fetch_capabilities(base):
    """Page the public capability catalog until ``next_cursor`` is null."""
    rows = []
    seen = set()
    cursor = None
    for page in range(MAX_CATALOG_PAGES):
        url = base + CAPABILITIES_PATH + "?limit=200"
        if cursor:
            url += "&cursor=" + urllib.parse.quote(str(cursor), safe="")
        payload = _fetch_json(url)
        batch = payload.get("capabilities")
        if not isinstance(batch, list):
            raise SyncError(
                "unexpected capability catalog shape from {0}: no 'capabilities' list".format(url)
            )
        for row in batch:
            name = row.get("name")
            if not name or name in seen:
                continue
            seen.add(name)
            rows.append(row)
        cursor = payload.get("next_cursor")
        if not cursor:
            return rows
        if page + 1 == MAX_CATALOG_PAGES:
            raise SyncError(
                "capability catalog did not finish paging within {0} pages; refusing to "
                "loop further against the live API".format(MAX_CATALOG_PAGES)
            )
    return rows


def fetch_anonymous_tools(base):
    """``tools/list`` with no credentials: what a key-less caller actually sees."""
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    ).encode("utf-8")
    payload = _fetch_json(base + MCP_PATH, method="POST", body=body)
    if "error" in payload and payload.get("error"):
        error = payload["error"]
        raise SyncError(
            "MCP tools/list returned a JSON-RPC error: {0} {1}".format(
                error.get("code"), error.get("message")
            )
        )
    tools = (payload.get("result") or {}).get("tools")
    if not isinstance(tools, list):
        raise SyncError("MCP tools/list response had no 'result.tools' array")
    return tools


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def public_base(spec):
    """The public host to print into generated files, read from the spec."""
    servers = spec.get("servers") or []
    if servers and isinstance(servers[0], dict):
        url = str(servers[0].get("url") or "").rstrip("/")
        if url.startswith("https://"):
            return url
    return CANONICAL_BASE


def spec_version(spec):
    return str(spec.get("info", {}).get("version") or "unknown")


def spec_fingerprint(spec):
    return str(spec.get("info", {}).get("x-catalog-fingerprint") or "unknown")


def domain_of(name):
    """``gex.levels`` -> ``gex``; ``stats.greeks.zg_distance_range`` -> ``stats``."""
    return str(name).split(".", 1)[0]


def cell(value):
    """Collapse a value onto one line and escape it for a markdown table cell."""
    text = " ".join(str(value if value is not None else "").split())
    return text.replace("|", "\\|")


def ordered_by(mapping, order):
    """Yield ``(key, value)`` in ``order`` first, then anything else sorted."""
    known = [k for k in order if k in mapping]
    rest = sorted(k for k in mapping if k not in order)
    for key in known + rest:
        yield key, mapping[key]


def write_text(path, text):
    """Write UTF-8 with LF line endings, whatever platform this runs on."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)


def dump_json(obj):
    """2-space indent, sorted keys, trailing newline."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------
# REST_ENDPOINTS.md
# --------------------------------------------------------------------------


def collect_operations(spec):
    """Flatten the spec into one sorted list of operation records."""
    methods = {m.lower() for m in METHOD_DISPLAY_ORDER} | {"head", "options", "trace"}
    operations = []
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method.lower() not in methods or not isinstance(operation, dict):
                continue
            tags = operation.get("tags") or ["(untagged)"]
            operations.append(
                {
                    "operation_id": operation.get("operationId") or path,
                    "method": method.upper(),
                    "path": path,
                    "domain": str(tags[0]),
                    "tier": str(operation.get("x-plan-tier") or ""),
                    "tier_name": str(operation.get("x-plan-tier-name") or ""),
                    "summary": operation.get("summary") or "",
                }
            )
    operations.sort(key=lambda op: (op["domain"], op["operation_id"], op["method"], op["path"]))
    return operations


def render_rest_endpoints(spec):
    operations = collect_operations(spec)
    if not operations:
        raise SyncError("spec contained no operations")

    base = public_base(spec)
    base_path = str(spec.get("info", {}).get("x-base") or "")

    # Domains come from the spec's own tag list, sorted by name; any tag used by
    # an operation but missing from that list is folded in so nothing is lost.
    tag_names = [str(t.get("name")) for t in (spec.get("tags") or []) if t.get("name")]
    used = sorted({op["domain"] for op in operations})
    domains = sorted(set(tag_names) | set(used))
    domains = [d for d in domains if any(op["domain"] == d for op in operations)]

    by_domain = OrderedDict((d, []) for d in domains)
    for operation in operations:
        by_domain[operation["domain"]].append(operation)

    method_counts = Counter(op["method"] for op in operations)
    plan_names = {}
    plan_counts = Counter()
    for operation in operations:
        slug = operation["tier"] or "unknown"
        plan_counts[slug] += 1
        plan_names.setdefault(slug, operation["tier_name"] or slug)
    free_count = sum(1 for op in operations if op["tier"] == "free")

    methods_text = ", ".join(
        "{0} {1}".format(count, method)
        for method, count in ordered_by(method_counts, METHOD_DISPLAY_ORDER)
    )
    plans_text = ", ".join(
        "{0} {1}".format(plan_names[slug], count)
        for slug, count in ordered_by(plan_counts, PLAN_DISPLAY_ORDER)
    )

    out = []
    out.append("<!-- {0} -->".format(DO_NOT_EDIT))
    out.append("")
    out.append("# VolStrata REST endpoint reference")
    out.append("")
    out.append(
        "Every operation the public VolStrata API publishes, rendered from "
        "[`{0}{1}`]({0}{1}).".format(base, OPENAPI_PATH)
    )
    out.append("")
    out.append("| | |")
    out.append("| --- | --- |")
    out.append("| Spec version (`info.version`) | `{0}` |".format(cell(spec_version(spec))))
    out.append(
        "| Catalog fingerprint (`info.x-catalog-fingerprint`) | `{0}` |".format(
            cell(spec_fingerprint(spec))
        )
    )
    out.append("| Base URL | `{0}` |".format(cell(base)))
    if base_path:
        out.append("| Base path | `{0}` |".format(cell(base_path)))
    out.append("| Generated by | `{0}` |".format(GENERATING_COMMAND))
    out.append("")
    out.append(
        "**{0} operations** across **{1} domains** - {2}. "
        "By plan floor: {3}. **{4}** operations sit at the Free plan floor.".format(
            len(operations), len(by_domain), methods_text, plans_text, free_count
        )
    )
    out.append("")
    # WHY THERE IS NO "Key required" COLUMN. There used to be one, derived from
    # `x-plan-tier == "free"`. That derivation is wrong: the plan floor and the
    # credential requirement are two different gates, and a handful of Free-floor
    # data operations still ask for any valid key and answer 401 auth_required
    # without one. The spec does not publish that second gate per-operation, so
    # this generator will not invent it - it states the floor, which is a fact it
    # can read, and points at the runtime answer for the rest.
    out.append(
        "`Plan` is the customer-facing plan floor (`x-plan-tier-name`) - the lowest plan "
        "that may call the operation. A Free floor is not a promise of anonymous access: "
        "most Free operations answer with no credential, but some data operations ask for "
        "any valid key and answer `401 auth_required` without one. "
        "`GET {0}{1}/meta/access` is the runtime answer for the credential you hold.".format(
            base, base_path or "/api/v1"
        )
    )
    out.append("")
    out.append("## Domains")
    out.append("")
    out.append(" ".join("[`{0}`](#{0})".format(domain) for domain in by_domain))
    out.append("")

    for domain, rows in by_domain.items():
        out.append("## {0}".format(domain))
        out.append("")
        out.append("_{0} operation{1}._".format(len(rows), "" if len(rows) == 1 else "s"))
        out.append("")
        out.append("| Capability | Method | Path | Plan | Summary |")
        out.append("| --- | --- | --- | --- | --- |")
        for row in rows:
            out.append(
                "| `{0}` | {1} | `{2}` | {3} | {4} |".format(
                    cell(row["operation_id"]),
                    cell(row["method"]),
                    cell(row["path"]),
                    cell(row["tier_name"] or row["tier"]),
                    cell(row["summary"]),
                )
            )
        out.append("")

    out.append("---")
    out.append("")
    out.append(
        "Narrative documentation lives at [{0}/docs/api-catalog]({0}/docs/api-catalog).".format(base)
    )
    out.append("")
    out.append(COPYRIGHT)
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# mcp-tools.json
# --------------------------------------------------------------------------


def _meta_tool_params(schema):
    """Describe a server-native tool's inputs in the catalog's own param style."""
    if not isinstance(schema, dict):
        return []
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return []
    required = set(schema.get("required") or [])
    params = []
    for name in sorted(properties):
        spec = properties[name] if isinstance(properties[name], dict) else {}
        label = name if name in required else name + "?"
        if "default" in spec:
            default = spec["default"]
            rendered = default if isinstance(default, str) else json.dumps(default)
            label += "=" + str(rendered)
        params.append(label)
    return params


def build_mcp_tools(spec, capability_rows, anonymous_tools):
    """Project the public capability catalog into the MCP tool table.

    Capability tools come from ``GET /api/v1/meta/capabilities``; the server-native
    meta-tools are whatever ``tools/list`` returns that is *not* a catalog row, so
    the set is discovered rather than hard-coded. The ``anonymous`` flag on every
    entry is what an un-credentialed ``tools/list`` actually returned.
    """
    base = public_base(spec)
    anonymous_by_name = {}
    for tool in anonymous_tools:
        name = tool.get("name")
        if name:
            anonymous_by_name[str(name)] = tool
    anonymous_names = set(anonymous_by_name)

    catalog_names = {str(row.get("name")) for row in capability_rows if row.get("name")}
    if not catalog_names:
        raise SyncError("capability catalog returned no rows")

    tools = []

    # Server-native meta-tools: present in tools/list, absent from the catalog.
    for name in sorted(anonymous_names - catalog_names):
        tool = anonymous_by_name[name]
        tools.append(
            {
                "anonymous": True,
                "description": " ".join(str(tool.get("description") or "").split()),
                "domain": domain_of(name),
                "kind": "meta",
                "method": None,
                "name": name,
                "params": _meta_tool_params(tool.get("inputSchema")),
                "path": None,
                "policy_key": None,
                # Reachable with no credentials, therefore no plan floor above Free.
                "tier": "free",
                "tier_name": "Free",
                "title": " ".join(str(tool.get("title") or name).split()),
            }
        )

    # Capability tools: every published row except the MCP transport itself.
    for row in sorted(capability_rows, key=lambda r: str(r.get("name"))):
        name = str(row.get("name"))
        if name == MCP_TRANSPORT_CAPABILITY:
            continue
        params = row.get("params")
        tools.append(
            {
                "anonymous": name in anonymous_names,
                "domain": domain_of(name),
                "kind": "capability",
                "method": str(row.get("method") or "").upper() or None,
                "name": name,
                # Source order is preserved: the catalog lists a capability's
                # parameters in a meaningful order, not an alphabetical one.
                "params": [str(p) for p in params] if isinstance(params, list) else [],
                "path": row.get("path"),
                "policy_key": row.get("policy_key"),
                "tier": row.get("tier"),
                "tier_name": row.get("tier_name"),
            }
        )

    tools.sort(key=lambda t: (0 if t["kind"] == "meta" else 1, t["name"]))

    meta_count = sum(1 for t in tools if t["kind"] == "meta")
    capability_count = len(tools) - meta_count
    anonymous_count = sum(1 for t in tools if t["anonymous"])

    return {
        "api_version": spec_version(spec),
        "catalog_fingerprint": spec_fingerprint(spec),
        "copyright": COPYRIGHT,
        "counts": {
            "anonymous": anonymous_count,
            "capability_tools": capability_count,
            "meta_tools": meta_count,
            "total": len(tools),
        },
        "endpoint": base + MCP_PATH,
        "generator": {
            "command": GENERATING_COMMAND,
            "do_not_edit": DO_NOT_EDIT,
            "sources": {
                "capabilities": base + CAPABILITIES_PATH,
                "mcp": base + MCP_PATH,
                "openapi": base + OPENAPI_PATH,
            },
        },
        "protocol": "JSON-RPC 2.0",
        "tools": tools,
    }


# --------------------------------------------------------------------------
# MCP_TOOLS.md
# --------------------------------------------------------------------------


def _tool_row(tool):
    return "| `{0}` | {1} | {2} | {3} | {4} |".format(
        cell(tool["name"]),
        cell(tool["method"]) if tool.get("method") else "-",
        "`{0}`".format(cell(tool["path"])) if tool.get("path") else "-",
        cell(tool.get("tier_name") or tool.get("tier") or ""),
        "Yes" if tool.get("anonymous") else "No",
    )


TOOL_TABLE_HEADER = (
    "| Tool | Method | Path | Plan | Anonymous |",
    "| --- | --- | --- | --- | --- |",
)


def render_mcp_tools(doc):
    tools = doc["tools"]
    counts = doc["counts"]
    endpoint = doc["endpoint"]
    base = endpoint[: -len(MCP_PATH)] if endpoint.endswith(MCP_PATH) else CANONICAL_BASE

    meta_tools = [t for t in tools if t["kind"] == "meta"]
    capability_tools = [t for t in tools if t["kind"] != "meta"]

    by_domain = OrderedDict()
    for tool in capability_tools:
        by_domain.setdefault(tool["domain"], []).append(tool)
    by_domain = OrderedDict(sorted(by_domain.items()))

    out = []
    out.append("<!-- {0} -->".format(DO_NOT_EDIT))
    out.append("")
    out.append("# VolStrata MCP tool reference")
    out.append("")
    out.append(
        "Every tool the VolStrata MCP server projects, derived from the public "
        "capability catalog and from an un-credentialed `tools/list` call."
    )
    out.append("")
    out.append("| | |")
    out.append("| --- | --- |")
    out.append("| Endpoint | `POST {0}` |".format(endpoint))
    out.append("| Protocol | `{0}` |".format(cell(doc.get("protocol", "JSON-RPC 2.0"))))
    out.append("| API version | `{0}` |".format(cell(doc["api_version"])))
    out.append("| Catalog fingerprint | `{0}` |".format(cell(doc["catalog_fingerprint"])))
    out.append("| Generated by | `{0}` |".format(GENERATING_COMMAND))
    out.append("")
    out.append(
        "**{0} meta-tools + {1} capability tools = {2} tools** for a fully entitled "
        "caller. **{3}** are reachable anonymously - a caller sending no credentials "
        "sees exactly those in `tools/list`, and `tools/call` refuses the rest with "
        "JSON-RPC error `-32001` naming the plan required.".format(
            counts["meta_tools"],
            counts["capability_tools"],
            counts["total"],
            counts["anonymous"],
        )
    )
    out.append("")
    out.append(
        "A capability tool's name is identical to its REST `operationId`, and `Path` is "
        "the REST route the tool calls on your behalf. Meta-tools are served by the MCP "
        "endpoint itself and have no REST route of their own."
    )
    out.append("")

    out.append("## Meta-tools")
    out.append("")
    out.extend(TOOL_TABLE_HEADER)
    for tool in meta_tools:
        out.append(_tool_row(tool))
    out.append("")
    for tool in meta_tools:
        out.append("- `{0}` - {1}".format(tool["name"], cell(tool.get("title") or "")))
    out.append("")

    out.append("## Capability tools by domain")
    out.append("")
    out.append(" ".join("[`{0}`](#{0})".format(domain) for domain in by_domain))
    out.append("")
    for domain, rows in by_domain.items():
        out.append("### {0}".format(domain))
        out.append("")
        out.append("_{0} tool{1}._".format(len(rows), "" if len(rows) == 1 else "s"))
        out.append("")
        out.extend(TOOL_TABLE_HEADER)
        for tool in rows:
            out.append(_tool_row(tool))
        out.append("")

    out.append("---")
    out.append("")
    out.append(
        "Connect a client with [{0}/docs/api-catalog]({0}/docs/api-catalog) and "
        "[{0}/docs/api-auth]({0}/docs/api-auth).".format(base)
    )
    out.append("")
    out.append(COPYRIGHT)
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------


def reconcile_surfaces(spec, doc):
    """Report capabilities the REST spec publishes but MCP does not project.

    The two generated references describe the same surface from two different
    live sources, and both are stamped with the same catalog fingerprint - which
    is exactly why a silent disagreement between them is worth surfacing. This
    is a REPORT, not a gate: it writes nothing, so it can never cause drift, and
    it does not fail the run, because the reconciliation belongs upstream in the
    API rather than in a repository of examples.

    Returns the sorted list of operationIds with no matching MCP tool.
    """
    operation_ids = {
        str(op.get("operationId"))
        for item in (spec.get("paths") or {}).values()
        if isinstance(item, dict)
        for op in item.values()
        if isinstance(op, dict) and op.get("operationId")
    }
    tool_names = {str(t["name"]) for t in doc.get("tools") or []}
    # The MCP transport is the door, not a tool behind it - never projected.
    return sorted(operation_ids - tool_names - {MCP_TRANSPORT_CAPABILITY})


def generate(base, source, out_dir, quiet=False):
    """Write the four generated artifacts into ``out_dir``. Returns the spec."""

    def say(message):
        if not quiet:
            print(message)

    out_dir = pathlib.Path(out_dir)

    say("1/4 fetching the OpenAPI document")
    raw_spec = load_openapi_bytes(base, source)
    spec = parse_openapi(raw_spec)
    say(
        "    info.version={0} fingerprint={1} bytes={2}".format(
            spec_version(spec), spec_fingerprint(spec), len(raw_spec)
        )
    )
    # Verbatim: no reformat, no re-serialisation, no key reordering, and no
    # header of ours - a byte-for-byte copy is the only thing CI can diff.
    write_bytes(out_dir / "openapi.json", raw_spec)

    say("2/4 rendering REST_ENDPOINTS.md")
    write_text(out_dir / "REST_ENDPOINTS.md", render_rest_endpoints(spec))

    say("3/4 paging the public capability catalog")
    capability_rows = fetch_capabilities(base)
    say("    {0} published capabilities".format(len(capability_rows)))
    say("    calling tools/list with no credentials")
    anonymous_tools = fetch_anonymous_tools(base)
    say("    {0} tools visible anonymously".format(len(anonymous_tools)))
    doc = build_mcp_tools(spec, capability_rows, anonymous_tools)
    write_text(out_dir / "mcp-tools.json", dump_json(doc))

    say("4/4 rendering MCP_TOOLS.md")
    write_text(out_dir / "MCP_TOOLS.md", render_mcp_tools(doc))

    unprojected = reconcile_surfaces(spec, doc)
    if unprojected:
        say(
            "    note: {0} operation(s) published in the spec have no MCP tool: {1}".format(
                len(unprojected), ", ".join(unprojected)
            )
        )
        say("    MCP_TOOLS.md is the authoritative tool list.")

    return spec


def compare(fresh_dir, committed_dir):
    """Return the generated filenames whose committed copy differs."""
    differences = []
    for name in GENERATED_FILES:
        fresh = pathlib.Path(fresh_dir) / name
        committed = pathlib.Path(committed_dir) / name
        if not committed.is_file():
            differences.append(name)
            continue
        if not filecmp.cmp(str(fresh), str(committed), shallow=False):
            differences.append(name)
    return differences


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Generate docs/reference/* from the public VolStrata API. Needs no API key."
        )
    )
    parser.add_argument(
        "--base",
        default=DEFAULT_BASE,
        help="host to fetch from (default: %(default)s). Only changes where bytes are "
        "read from; never changes what is written.",
    )
    parser.add_argument(
        "--source",
        default="live",
        help="'live' (default) or 'local:<path>' to read the OpenAPI document from a "
        "file you already have. The capability catalog and MCP tool list are always "
        "read from --base.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate into a temporary directory and exit non-zero if the committed "
        "docs/reference/* differs.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="write to this directory instead of docs/reference (ignored with --check).",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    base = args.base.rstrip("/")
    if not base.startswith("https://") and not base.startswith("http://"):
        print("error: --base must be an http(s) URL", file=sys.stderr)
        return 2

    try:
        if args.check:
            with tempfile.TemporaryDirectory(prefix="volstrata-sync-") as tmp:
                generate(base, args.source, tmp, quiet=True)
                differences = compare(tmp, REFERENCE_DIR)
            if differences:
                print("drift: " + ", ".join(differences), file=sys.stderr)
                print(
                    "run `{0}` and commit the result.".format(GENERATING_COMMAND),
                    file=sys.stderr,
                )
                return 1
            print("docs/reference is up to date ({0} files).".format(len(GENERATED_FILES)))
            return 0

        out_dir = pathlib.Path(args.out) if args.out else REFERENCE_DIR
        generate(base, args.source, out_dir)
        print("wrote {0} files to {1}".format(len(GENERATED_FILES), out_dir.as_posix()))
        return 0
    except SyncError as exc:
        print("error: {0}".format(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:  # pragma: no cover
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
