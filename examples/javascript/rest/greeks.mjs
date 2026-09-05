/**
 * Copyright 2026 Volstrata.com
 *
 * The `greeks.*` and `vol.*` domains: one Free capability and two that sit above
 * the Free floor, so this file is also the shortest demonstration of how a
 * mixed-tier script should behave.
 * Catalog: https://volstrata.com/docs/api-catalog
 *
 * Run:  node rest/greeks.mjs [TICKER]
 *       npm run greeks
 *
 * Three requests:
 *
 *   greeks.gamma    Free   — always runs
 *   greeks.charm    Pro    — refuses without the plan, and says so
 *   vol.surface     Pro    — same
 *
 * Two of three rows refusing is the expected, successful outcome of running this
 * with no key. The exit code is 0 either way: the script's job is to report what
 * the API said, and "you need the Pro plan for this" is something the API said.
 */

import {
  apiFetch,
  apiGet,
  banner,
  callCapability,
  hasApiKey,
  heading,
  keysOf,
  report,
  show,
  showRateLimit,
  summarize,
} from "../lib/volstrata.mjs";

const ticker = (process.argv[2] ?? "SPX").toUpperCase();

banner(`greeks.* and vol.* — ${ticker}`);
show("ticker", `${ticker} (pass another as the first argument)`);

const results = [];

// ---------------------------------------------------------------------------
// greeks.gamma — Free
// ---------------------------------------------------------------------------
//
// The one row here that runs for everybody. Field names are not restated in this
// comment on purpose: read them off the response, or look the metric up in the
// glossary. `docs.metric` (see rest/research_and_docs.mjs) returns the
// definition of any metric name over the API itself.

results.push(
  await callCapability("greeks.gamma", async () => {
    const { res, data } = await apiFetch("/api/v1/greeks/gamma", { ticker });

    show("keys", keysOf(data));

    // Most of these payloads are either a ladder (one row per strike) or a small
    // map of scalars. Find whichever this is instead of assuming.
    const [rowsKey, rows] = Object.entries(data).find(([, v]) => Array.isArray(v)) ?? [];
    if (rows) {
      show("rows key", rowsKey);
      show("rows", rows.length);
      show("first row", summarize(rows[0], { depth: 1, maxKeys: 8 }));
    } else {
      show("payload", summarize(data, { depth: 2, maxKeys: 12 }));
    }

    showRateLimit(res);
    return data;
  }, { note: "Free — the higher-order greeks below are not" }),
);

// ---------------------------------------------------------------------------
// greeks.charm — Pro
// ---------------------------------------------------------------------------
//
// `window` and `at` are the two parameters worth knowing across this domain:
// `window` selects the session ("today" is the default) and `at` selects the
// point in it ("latest" by default). Both are passed explicitly here because
// being explicit is the habit worth having in your own code.

results.push(
  await callCapability("greeks.charm", async () => {
    const data = await apiGet("/api/v1/greeks/charm", { ticker, window: "today", at: "latest" });
    show("keys", keysOf(data));
    show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    return data;
  }, { note: "Pro plan" }),
);

// ---------------------------------------------------------------------------
// vol.surface — Pro
// ---------------------------------------------------------------------------
//
// `expiry` narrows the surface to a single expiry when you pass one; leaving it
// off returns what the capability considers the default view. `lib/volstrata.mjs`
// drops parameters whose value is undefined, so an unset option simply does not
// appear on the query string.

results.push(
  await callCapability("vol.surface", async () => {
    const data = await apiGet("/api/v1/vol/surface", { ticker, window: "today", expiry: undefined });
    show("keys", keysOf(data));
    show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    return data;
  }, { note: "Pro plan" }),
);

report(results);

heading("How a refusal should read");
if (hasApiKey) {
  console.log("  A key is set. Rows that still refused above are a plan floor, not a");
  console.log("  credential problem — the problem document names the plan required.");
} else {
  console.log("  With no key, the two Pro rows above answered 401 auth_required.");
  console.log("  With a key below the floor they answer with required_plan_name set");
  console.log("  instead, which is the field to show a human.");
}

heading("Related");
console.log("  Capability catalog   https://volstrata.com/docs/api-catalog");
console.log("  Authentication       https://volstrata.com/docs/api-auth");
console.log("  Next domain          node rest/valuation.mjs");
