"""Copyright 2026 Volstrata.com

Read the published surface at runtime instead of hard-coding it.
Docs: https://volstrata.com/docs/api-catalog

    python discover_capabilities.py

Nothing in this file contains a list of endpoints. It asks the API what exists,
two different ways, and prints the answer:

  1. GET /api/openapi.json          the machine-readable spec: every operation,
                                    its parameters, and its plan floor.
  2. GET /api/v1/meta/capabilities  the same catalog as a cursor-paged JSON
                                    collection, easier to consume in a loop.

Then it asks a third question that only the API can answer:

  3. GET /api/v1/meta/access        what *your* credential unlocks right now.

Both discovery endpoints are public and need no key, which is what makes
generated clients, dynamic tool registries and drift checks possible. If you
write a wrapper around this API, generate it from (1) rather than typing it out.

Five requests, sequential, no key required.
"""

import sys
from collections import Counter

from volstrata_helpers import (
    VolstrataError,
    get,
    heading,
    key_banner,
    paginate,
    row,
)

# Bound the paged read. This file only needs a taste of the collection --
# pagination.py is the one that pages a collection to completion.
CATALOG_PAGES = 3
PAGE_SIZE = 25


def read_the_spec() -> None:
    """The OpenAPI 3.1 document is public, unauthenticated and always current.

    It is the source every other view of the surface is derived from, so it is
    the right thing to point a code generator, a linter or a CI drift check at.
    Each operation carries three extensions worth knowing:

        x-plan-tier        the plan floor as a slug   ("free", "edge", "pro")
        x-plan-tier-name   the same floor, named      ("Free", "Edge", "Pro")
        x-policy-key       the entitlement this operation is gated on

    Show `x-plan-tier-name` to humans. Slugs can be renamed; the displayed name
    is what your users will recognise from the pricing page.
    """
    heading("1. The spec -- GET /api/openapi.json")
    spec = get("/api/openapi.json")

    info = spec.get("info") or {}
    servers = spec.get("servers") or [{}]
    # Read named fields rather than dumping `info`: a spec document carries
    # build metadata that is of no use to a client.
    row("title", info.get("title"))
    row("version", info.get("version"))
    row("base path", info.get("x-base"))
    row("catalog fingerprint", info.get("x-catalog-fingerprint"))
    row("server", servers[0].get("url"))
    print("  The fingerprint changes only when the catalog changes, which makes it")
    print("  a cheap way to detect drift without diffing the whole document.")

    methods = Counter()
    tiers = Counter()
    domains = Counter()
    free_floor_ops = []
    operations = 0

    for path, item in (spec.get("paths") or {}).items():
        for method, op in item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            operations += 1
            methods[method.upper()] += 1
            tiers[op.get("x-plan-tier-name") or "unknown"] += 1
            # A capability is named domain.name, and that dotted name is also
            # the operationId, the MCP tool name, and /api/v1/<domain>/<name>.
            for tag in op.get("tags") or ["untagged"]:
                domains[tag] += 1
            if op.get("x-plan-tier") == "free":
                free_floor_ops.append(op.get("operationId") or path)

    heading("What is published")
    row("operations", operations)
    row("by method", ", ".join("{0} {1}".format(n, m) for m, n in methods.most_common()))
    row("domains", len(domains))

    heading("Operations by plan floor")
    for name, count in tiers.most_common():
        row(name, count)
    print("  Free is the lowest published floor. It is not the same thing as")
    print("  anonymous: some Free capabilities still want an authenticated")
    print("  principal, and they answer 401 auth_required until they get one.")
    print("  Step 3 below is how you find out which, for your own credential.")

    heading("Largest domains")
    for name, count in domains.most_common(8):
        row(name, count)

    print("\n  {0} operations sit at the Free floor. The first few:".format(
        len(free_floor_ops)))
    print("  " + ", ".join(sorted(free_floor_ops)[:10]))


def read_the_catalog() -> None:
    """The same facts, as a paged collection you can loop over.

    Each row is {name, method, path, params, policy_key, tier, tier_name}. This
    is the endpoint to poll (occasionally) if you keep your own registry of what
    is callable -- it needs no spec parser and no key.
    """
    heading("2. The catalog -- GET /api/v1/meta/capabilities")
    seen = 0
    published = None
    pending = None
    for page in paginate("/meta/capabilities", max_pages=CATALOG_PAGES, limit=PAGE_SIZE):
        batch = page.get("capabilities") or []
        seen += len(batch)
        published = page.get("count", published)
        pending = page.get("next_cursor")
        if seen <= PAGE_SIZE:
            for item in batch[:5]:
                print("  {0:<26} {1:<5} {2:<32} {3}".format(
                    item.get("name", "?"),
                    item.get("method", "?"),
                    item.get("path", "?"),
                    item.get("tier_name", "?"),
                ))
    row("rows read", seen)
    row("published rows", published)
    print("  This count and the spec's operation count above are two views taken")
    print("  from the same catalog and need not be identical. Pick the one that")
    print("  matches what you are building -- the spec to generate a client, the")
    print("  catalog to keep a live registry -- and do not average them.")
    if pending:
        print("  Stopped at the {0}-page bound, not at the end of the collection.".format(
            CATALOG_PAGES))
        print("  pagination.py pages the same endpoint to completion.")

    # Filtering is a client-side loop over the rows -- there is no special
    # endpoint for "the free ones", and there does not need to be.
    print("\n  Filtering, in your own code:")
    print("    free = [c for c in rows if c['tier'] == 'free']")
    print("    gex  = [c for c in rows if c['name'].startswith('gex.')]")


def read_your_access() -> None:
    """What the credential in play can actually run, right now.

    meta.access answers for the caller, so run it anonymously and the `unlocked`
    list is the set of capabilities that need no key. Run it with a key and the
    same list grows to match the plan behind it. Each `locked` row names the
    floor that would clear it (`min_tier_name`).
    """
    heading("3. Your access -- GET /api/v1/meta/access")
    access = get("/meta/access")
    row("caller_tier", access.get("caller_tier"))
    row("unlocked", access.get("unlocked_count"))
    row("locked", access.get("locked_count"))
    row("total", access.get("total"))
    row("requests per minute", access.get("key_rate_per_min"))

    unlocked = access.get("unlocked") or []
    locked = access.get("locked") or []

    if unlocked:
        names = sorted(item.get("name", "?") for item in unlocked)
        print("\n  Callable with the credential you are using now ({0}):".format(len(names)))
        print("  " + ", ".join(names[:12]) + (", ..." if len(names) > 12 else ""))
        print("  Run this file with no VOLSTRATA_API_KEY set and that list is")
        print("  exactly the no-key surface. The authoritative test is still the")
        print("  response itself: catalogue entitlement and a per-endpoint")
        print("  credential requirement are two different checks.")

    if locked:
        by_floor = Counter(item.get("min_tier_name") or "?" for item in locked)
        print("\n  Behind a floor:")
        for name, count in by_floor.most_common():
            row("  " + name, count)
        example = locked[0]
        print("  e.g. {0} ({1}) needs {2}.".format(
            example.get("name"), example.get("path"), example.get("min_tier_name")))

    print("\n  Keys: https://volstrata.com/api-keys")


def main() -> int:
    print("VolStrata capability discovery -- https://volstrata.com")
    key_banner()
    for label, step in (
        ("spec", read_the_spec),
        ("catalog", read_the_catalog),
        ("access", read_your_access),
    ):
        try:
            step()
        except VolstrataError as exc:
            print("  ({0} could not be read: {1})".format(label, exc))

    heading("The point")
    print("  Nothing above was hard-coded. A capability added tomorrow shows up in")
    print("  all three views without this file changing, which is why the examples")
    print("  in rest/ read like documentation rather than a maintained inventory.")
    print("  Catalog page: https://volstrata.com/docs/api-catalog")
    return 0


if __name__ == "__main__":
    sys.exit(main())
