"""Copyright 2026 Volstrata.com

Authentication, refusals and rate limits -- the three things a client has to get
right before anything else matters.

Docs: https://volstrata.com/docs/api-auth
      https://volstrata.com/docs/api-errors

    python auth_and_errors.py

Runs identically with or without a key, and exits 0 either way. Five things
happen, in order:

  1. an anonymous call to a capability that answers without a credential
  2. an authenticated call, when VOLSTRATA_API_KEY is set        (or skipped)
  3. a call to a capability above your floor       (refused, caught, explained)
  4. a call to a path that does not exist                 (404, caught)
  5. the rate-limit headers, read off a real response

A refusal is data, not a crash. That is the whole lesson of this file.
"""

import sys

from volstrata_helpers import (
    VolstrataError,
    call,
    get,
    have_key,
    heading,
    rate_limit,
    row,
    run_examples,
    show,
)


def anonymous_call() -> None:
    """Much of the published surface answers with no credential at all.

    Nothing is sent here but a User-Agent -- which is not optional. Some default
    agent strings are refused at the CDN before the API ever sees the request,
    and that refusal is plain text, not problem+json. If you get a non-JSON
    error body, check your User-Agent first.
    """
    heading("1. Anonymous call -- no credential sent")
    data = get("/gex/levels", ticker="SPX")
    row("ok", data.get("ok"))
    row("ticker", data.get("ticker"))
    row("spot", data.get("spot"))
    print("  That is the whole setup: one GET, no account.")


def authenticated_call() -> None:
    """A key is presented as `Authorization: Bearer <key>`.

    The alternative is `?api_key=<key>` on the query string, accepted everywhere
    the header is. Prefer the header: query strings leak into access logs,
    proxies and browser history.

    A key is issued once and shown in full once, at creation; the service keeps
    only a hash. Personal access tokens and service-account tokens are accepted
    by the same header -- the 401 body in step 3 names the prefixes it takes.

    Issue and revoke keys at https://volstrata.com/api-keys
    Guidance: https://volstrata.com/docs/api-keys
    """
    heading("2. Authenticated call")
    if not have_key():
        print("  Skipped: VOLSTRATA_API_KEY is not set.")
        print("  Export it and re-run to see this branch:")
        print("    export VOLSTRATA_API_KEY=...        # macOS / Linux")
        print("    $env:VOLSTRATA_API_KEY = \"...\"      # Windows PowerShell")
        return

    # meta.access reports what the *calling credential* is entitled to, which
    # makes it the fastest way to confirm a key is being read correctly.
    access = get("/meta/access")
    row("ok", access.get("ok"))
    for field in ("caller_tier", "unlocked_count", "locked_count", "total",
                  "key_rate_per_min", "limit_cap"):
        if field in access:
            row(field, access[field])
    print("  caller_tier is 'anon' when no credential arrived. If you set a key")
    print("  and still see 'anon', the header is not reaching the API -- check")
    print("  that before anything else.")


def gated_call() -> None:
    """A capability above your floor is refused with a body that says so.

    Two distinct refusals live here, and telling them apart matters:

      401 `auth_required` -- no usable credential was presented at all. The
          `detail` names the credential families the API accepts.
      402 with `required_plan_name` -- the credential is valid, the plan is not
          high enough. The body adds `feature`, `required_plan`,
          `required_plan_name` and `current_plan`.

    gex.snapshot sits above the lowest floor, so anonymously you get the first
    and with a key below its floor you get the second. This prints whichever one
    you actually received.
    """
    heading("3. A capability above the anonymous floor -- gex.snapshot")
    try:
        data = get("/gex/snapshot", ticker="SPX")
    except VolstrataError as exc:
        row("status", exc.status)
        row("code", exc.code)
        row("title", exc.title)
        row("detail", exc.detail)
        if exc.needs_plan:
            row("required_plan_name", exc.required_plan_name)
            row("current_plan", exc.current_plan)
            print("  -> Nothing about the request was wrong. The account is below")
            print("     the plan floor, and the body names the plan that clears it.")
        else:
            print("  -> No usable credential was presented. Set VOLSTRATA_API_KEY and")
            print("     re-run; with a key below the floor this becomes a 402 that")
            print("     names the plan you would need.")
        print("  Handle this branch in your own client, and do not retry it: the")
        print("  answer will not change and the attempt still costs rate budget.")
        return
    row("ok", data.get("ok"))
    print("  Your plan includes this one, so it returned normally.")


def bad_path() -> None:
    """A path that does not exist answers with the same problem+json envelope.

    `route_not_found` means the URL is wrong. Plain `not_found` means the route
    was right and the resource is not available just now -- a distinction worth
    honouring in your error handling, because only one of them is a bug in your
    code. Every published path is listed by GET /api/v1/meta/capabilities.
    """
    heading("4. A path that does not exist")
    try:
        get("/gex/not_a_real_capability")
    except VolstrataError as exc:
        row("status", exc.status)
        row("code", exc.code)
        row("title", exc.title)
        row("detail", exc.detail)
        row("request_id", "present" if exc.request_id else "absent")
        print("  Every refusal carries a request_id. Quote it in a support request")
        print("  and the call can be traced.")
        return
    print("  Unexpected: that path answered successfully.")


def rate_limit_headers() -> None:
    """Rate limits are per owner, not per key.

    Minting a second key does not raise your ceiling; the budget belongs to the
    account and scales with the plan. Two header families are sent on every
    response -- the modern combined `ratelimit` header plus `ratelimit-policy`,
    and the older `x-ratelimit-*` set. `ratelimit-policy` lists each policy in
    play and marks which one is enforced, and `x-ratelimit-bucket` names the
    bucket you are counted in.

    On a 429 the body is `rate_limited` and `Retry-After` says how many seconds
    to wait. volstrata_helpers.request_with_backoff() honours it, retries only
    429 and 5xx, and gives up after four attempts.

    Reference: https://volstrata.com/docs/api-rate-limits
    """
    heading("5. Rate-limit headers")
    response = call("/gex/maxpain", params={"ticker": "SPX"})
    show(rate_limit(response))
    print("  Read `remaining` and slow down before you are told to. Everything in")
    print("  this repo is sequential for the same reason.")


def main() -> int:
    print("VolStrata: auth, errors and rate limits -- https://volstrata.com")
    exit_code = run_examples((
        ("anonymous call", anonymous_call),
        ("authenticated call", authenticated_call),
        ("gated call", gated_call),
        ("bad path", bad_path),
        ("rate-limit headers", rate_limit_headers),
    ))

    heading("Done")
    print("  Every branch above finished cleanly, including the two failures.")
    print("  Error reference: https://volstrata.com/docs/api-errors")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
