/**
 * Copyright 2026 Volstrata.com
 *
 * The smallest useful call: one Free capability, no key, no install, no setup.
 * Docs: https://volstrata.com/docs/api-examples
 *
 * Run:  node quickstart.mjs [TICKER]
 *       npm run quickstart
 *
 * Requires Node 18 or newer — that is where global `fetch` arrives. Nothing is
 * installed: this folder has no runtime dependencies, and `gex.levels` answers
 * an anonymous caller, so there is nothing to set up before running it.
 *
 * One request is made.
 */

import { BASE, VolstrataApiError, apiFetch, hasApiKey, heading, show, showRateLimit } from "./lib/volstrata.mjs";

const ticker = (process.argv[2] ?? "SPX").toUpperCase();

heading("VolStrata quickstart");
show("base url", BASE);
show("capability", `gex.levels  →  GET /api/v1/gex/levels?ticker=${ticker}`);
show("api key", hasApiKey ? "detected in VOLSTRATA_API_KEY" : "none — this call does not need one");

try {
  // `apiFetch` returns both the Response and the decoded body, because the
  // headers are worth reading too — see the rate-limit line printed below.
  //
  // The HTTP status is checked before the body is touched. That ordering is the
  // one habit to copy from this file: a refusal has a completely different body
  // shape, so branching on a field like `ok` would read a field that is not
  // there. Status first, always.
  const { res, data } = await apiFetch("/api/v1/gex/levels", { ticker });

  heading("Response");
  show("ok", data.ok); // true on success — a confirmation, not the success test
  show("ticker", data.ticker);
  show("spot", data.spot); // last price the levels were computed against
  show("updated", data.updated); // human-readable, exchange-local
  show("ts", data.ts); // the same instant as a unix timestamp

  // `levels` is a flat map of named price levels. Keys are stable, but any one
  // of them can be null when that level is not defined for the current session,
  // so read them defensively instead of indexing straight in. What each name
  // means is in the glossary: https://volstrata.com/docs/api-catalog
  const levels = data.levels ?? {};
  heading("A few named levels");
  for (const key of ["cw", "pw", "zg", "mp", "emHigh", "emLow", "hvl"]) {
    if (key in levels) show(key, levels[key] ?? "null (not defined right now)");
  }
  show("keys returned", Object.keys(levels).length);

  heading("Budget");
  showRateLimit(res); // every response carries these, success or failure

  heading("Next");
  console.log("  node auth_and_errors.mjs   keys, RFC 9457 errors, plan floors");
  console.log("  node pagination.mjs        cursor paging over the capability catalog");
  console.log("  node rest/gex_levels.mjs   the gex.* domain, end to end");
  if (!hasApiKey) {
    console.log("\n  Everything above ran anonymously. A key unlocks the capabilities");
    console.log("  above the Free floor: https://volstrata.com/api-keys");
  }
} catch (error) {
  // A Free capability failing usually means the network, not the API. Print what
  // is actually known rather than guessing.
  heading("The call did not succeed");
  if (error instanceof VolstrataApiError) {
    console.log(error.describe("  "));
    if (!error.isApiResponse) {
      console.log("\n  A non-JSON refusal never reached the API. Check the User-Agent");
      console.log("  header and any proxy between you and volstrata.com.");
    }
  } else {
    console.log(`  ${error?.message ?? error}`);
  }
  console.log("\n  Errors reference: https://volstrata.com/docs/api-errors");
  process.exitCode = 1;
}
