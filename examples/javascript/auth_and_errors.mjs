/**
 * Copyright 2026 Volstrata.com
 *
 * Authentication and the error envelope, in one runnable file.
 * Docs: https://volstrata.com/docs/api-errors
 *
 * Run:  node auth_and_errors.mjs
 *       npm run auth
 *
 * Five things happen, in order:
 *
 *   1. a Free call with no credential at all      → 200
 *   2. the same call with a key, when one is set  → 200 (skipped otherwise)
 *   3. a capability above the Free floor          → 402, naming the plan needed
 *   4. a path that does not exist                 → 404 route_not_found
 *   5. the rate-limit headers every response carries
 *
 * Every branch is handled, so this file exits 0 whether or not you have a key.
 * Three requests are made, or four with a key set.
 */

import {
  BASE,
  TIMEOUT_MS,
  USER_AGENT,
  VolstrataApiError,
  apiFetch,
  buildUrl,
  hasApiKey,
  heading,
  keysOf,
  show,
  showRateLimit,
} from "./lib/volstrata.mjs";

// ---------------------------------------------------------------------------
// 1. No credential at all
// ---------------------------------------------------------------------------
//
// 67 of the 180 published operations sit at the Free plan floor and most of
// those, `gex.levels` included, answer a caller who sends nothing at all. This
// is a supported mode, not a degraded one, so the request below does NOT go
// through the shared helper — it sends only the two headers every HTTP client
// should send, and no Authorization header even if you have a key exported.

heading("1. Anonymous — gex.levels (Free)");

let anonymousResponse = null;
try {
  const url = buildUrl("/api/v1/gex/levels", { ticker: "SPX" });
  const res = await fetch(url, {
    headers: {
      // Mandatory, not politeness. A CDN sits in front of the API and refuses
      // some default agents outright; that refusal is HTML or plain text and
      // never reaches the API, so it cannot be an API error however it looks.
      "User-Agent": USER_AGENT,
      Accept: "application/json",
    },
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });

  // Status first. Only then the body.
  if (!res.ok) throw await VolstrataApiError.fromResponse(res, url);
  const data = await res.json();

  anonymousResponse = res;
  show("status", res.status);
  show("ticker", data.ticker);
  show("spot", data.spot);
  show("levels", keysOf(data.levels, 8));
} catch (error) {
  reportError(error);
}

// ---------------------------------------------------------------------------
// 2. With a key
// ---------------------------------------------------------------------------
//
// One header carries it:
//
//     Authorization: Bearer <your key>
//
// The API also accepts `?api_key=<your key>` on the query string, which is
// occasionally the only option (a spreadsheet, a chart tool). Prefer the header:
// query strings end up in shell history, proxy logs and referrer headers.
//
// Keys look like `gex_key_v1_` followed by 43 url-safe base64 characters. The
// older `sig_key_v1_` prefix is still accepted. Two other credential families —
// personal access tokens (`sig_pat_v1_`) and service accounts (`sig_svc_v1_`) —
// are accepted on the same header; this repo teaches API keys.
//
// Never put any of them in source. `lib/volstrata.mjs` reads VOLSTRATA_API_KEY
// from the environment and attaches the header only when it is present.

heading("2. Authenticated — same capability, with a key");

if (!hasApiKey) {
  console.log("  VOLSTRATA_API_KEY is not set, so this step is skipped.");
  console.log("  Nothing above needed it. Get one at https://volstrata.com/api-keys,");
  console.log("  then:");
  console.log('    export VOLSTRATA_API_KEY="gex_key_v1_XXXXXXXX"      # macOS / Linux');
  console.log('    $env:VOLSTRATA_API_KEY = "gex_key_v1_XXXXXXXX"      # Windows PowerShell');
} else {
  try {
    const { res, data } = await apiFetch("/api/v1/gex/levels", { ticker: "SPX" });
    show("status", res.status);
    show("ticker", data.ticker);
    show("auth", "sent as Authorization: Bearer …");
    // A key raises the ceiling and unlocks capabilities; the response shape of
    // a Free capability is the same either way.
    showRateLimit(res);
  } catch (error) {
    reportError(error);
  }
}

// ---------------------------------------------------------------------------
// 3. A capability above your plan floor
// ---------------------------------------------------------------------------
//
// `gex.snapshot` requires the Edge plan, so this step refuses — in one of two
// different ways, and telling them apart is the point of this section.
//
// With no credential you get 401 `auth_required`, and the detail names the
// credential families the API accepts:
//
//     {"ok": false, "status": 401, "code": "auth_required",
//      "type": "<origin>/errors/auth_required",
//      "title": "Authentication required", "detail": "…",
//      "instance": "/api/v1/gex/snapshot", "request_id": "…"}
//
// With a valid credential whose plan sits below the floor, the credential is
// fine and the plan is not, so the problem document carries four extra fields:
//
//     "feature": "gex.snapshot", "required_plan": "edge",
//     "required_plan_name": "Edge", "current_plan": "…"
//
// Show `required_plan_name` to a human ("Edge") and branch on `required_plan`
// or `code` in software. Never retry either refusal: it will be refused again
// just as fast, and the attempt still counts against your rate limit.

heading("3. Gated — gex.snapshot (Edge)");

try {
  const { data } = await apiFetch("/api/v1/gex/snapshot", { ticker: "SPX" });
  show("status", 200);
  show("keys", keysOf(data, 12));
  show("note", "your plan includes this capability");
} catch (error) {
  if (error instanceof VolstrataApiError && error.isPlanRefusal) {
    // Authenticated, but below the floor.
    show("status", error.status);
    show("refused", `needs the ${error.requiredPlanName} plan`);
    show("code", error.code);
    show("current plan", error.currentPlan ?? "(unknown)");
    show("request_id", error.requestId ?? "(none)");
    console.log("\n  Plans: https://volstrata.com/docs/api-auth");
  } else if (error instanceof VolstrataApiError && error.isAuthRequired) {
    // No credential at all — the usual outcome when running this file with no
    // key. A key gets you past this; whether the data then comes back depends
    // on the plan behind it.
    show("status", error.status);
    show("code", error.code);
    show("detail", error.detail ?? "(none)");
    show("request_id", error.requestId ?? "(none)");
    console.log("\n  Set VOLSTRATA_API_KEY and run again to see the plan-floor form");
    console.log("  of this refusal: https://volstrata.com/docs/api-auth");
  } else {
    reportError(error);
  }
}

// ---------------------------------------------------------------------------
// 4. A path that does not exist
// ---------------------------------------------------------------------------
//
// Worth seeing once so you can tell it apart from a plan refusal: a wrong path
// is 404 `route_not_found`, and no key or plan will ever fix it. Capability
// names are dotted (`gex.levels`) and the path is the same name with slashes
// (`/api/v1/gex/levels`) — the two are always in step.

heading("4. Wrong path — 404 route_not_found");

try {
  await apiFetch("/api/v1/gex/no-such-capability");
  show("status", "200 — unexpected; that path is not published");
} catch (error) {
  if (error instanceof VolstrataApiError && error.isApiResponse) {
    show("status", error.status);
    show("code", error.code);
    show("title", error.title);
    show("detail", error.detail ?? "(none)");
    show("instance", error.instance ?? "(none)");
  } else {
    reportError(error);
  }
}

// ---------------------------------------------------------------------------
// 5. Rate limits
// ---------------------------------------------------------------------------
//
// Every response carries both header families: the modern combined
// `ratelimit: limit=…, remaining=…, reset=…` with `ratelimit-policy`, and the
// legacy `x-ratelimit-limit` / `-remaining` / `-reset`. Read whichever suits
// your stack — they describe the same budget.
//
// The budget is per OWNER, not per key: minting a second key does not raise the
// ceiling. Anonymous callers get the smallest one and it rises with the plan —
// read `remaining` and `reset` off the response rather than hard-coding a
// number. On a 429, `Retry-After` says how long to wait; honour it instead of
// inventing a delay. `withBackoff()` in lib/volstrata.mjs does exactly that.

heading("5. Rate-limit headers");

if (anonymousResponse) {
  showRateLimit(anonymousResponse);
} else {
  console.log("  (no response captured above)");
}
console.log("\n  Reference: https://volstrata.com/docs/api-rate-limits");

heading("Done");
console.log(`  base url   ${BASE}`);
console.log(`  api key    ${hasApiKey ? "detected" : "not set — every step above still ran"}`);
console.log("  exit code  0 in every branch: a refusal is an answer, not a crash.");

/** Print any failure without ever failing the run. */
function reportError(error) {
  if (error instanceof VolstrataApiError) {
    console.log(error.describe("  "));
    if (!error.isApiResponse) {
      console.log("  This response did not come from the API — see the note in step 1.");
    }
  } else {
    console.log(`  request failed: ${error?.message ?? error}`);
  }
}
