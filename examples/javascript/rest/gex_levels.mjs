/**
 * Copyright 2026 Volstrata.com
 *
 * The `gex.*` domain: named price levels, the strike ladder, summary metrics,
 * the gamma flip, max pain — plus one capability behind the Edge floor so you
 * can see what a refusal looks like without one.
 * Catalog: https://volstrata.com/docs/api-catalog
 *
 * Run:  node rest/gex_levels.mjs [TICKER]
 *       npm run gex
 *
 * Seven requests: six Free capabilities and one gated one. All of them share the
 * same query shape — `?ticker=` — and all of them return an object with `ok`
 * alongside the payload. Field names differ per capability, so this file prints
 * what came back rather than asserting a shape; that is also the quickest way to
 * explore a capability you have not used before.
 *
 * A refused row prints its reason and the run continues. Nothing here crashes
 * because you do not have a plan.
 */

import {
  apiFetch,
  apiGet,
  banner,
  callCapability,
  heading,
  keysOf,
  report,
  show,
  showRateLimit,
  summarize,
} from "../lib/volstrata.mjs";

const ticker = (process.argv[2] ?? "SPX").toUpperCase();

banner(`gex.* — ${ticker}`);
show("ticker", `${ticker} (pass another as the first argument)`);

const results = [];

// ---------------------------------------------------------------------------
// gex.levels — the named levels, and the one capability to start with
// ---------------------------------------------------------------------------

results.push(
  await callCapability("gex.levels", async () => {
    const { res, data } = await apiFetch("/api/v1/gex/levels", { ticker });

    show("spot", data.spot);
    show("updated", data.updated);
    show("ts", data.ts);

    // `levels` is a flat map of named levels. Any value can be null when that
    // level is not defined for the session in progress, so read defensively.
    // Each name is defined in the public glossary — this file does not restate
    // what any of them mean: https://volstrata.com/docs/api-catalog
    const levels = data.levels ?? {};
    show("level names", keysOf(levels, 30));
    for (const key of ["cw", "pw", "zg", "mp", "emHigh", "emLow"]) {
      if (key in levels) show(`  ${key}`, levels[key] ?? "null");
    }

    showRateLimit(res);
    return data;
  }, { note: "named levels for the current session" }),
);

// ---------------------------------------------------------------------------
// gex.bars — the per-strike ladder behind those levels
// ---------------------------------------------------------------------------

results.push(
  await callCapability("gex.bars", async () => {
    const data = await apiGet("/api/v1/gex/bars", { ticker });

    show("keys", keysOf(data));

    // The ladder itself sits under `bars`. Whether a payload's rows arrive as an
    // array or as an object keyed by something differs per capability, so look
    // before you index — which is also why every example here prints the shape
    // it actually got rather than the shape it expected.
    const bars = data.bars;
    if (Array.isArray(bars)) {
      show("rows", bars.length);
      show("first row", summarize(bars[0], { depth: 1, maxKeys: 8 }));
    } else if (bars && typeof bars === "object") {
      show("bars keys", keysOf(bars, 12));
      show("bars", summarize(bars, { depth: 2, maxKeys: 6, maxItems: 2 }));
    }
    show("spot", data.spot);
    return data;
  }, { note: "per-strike ladder" }),
);

// ---------------------------------------------------------------------------
// gex.metrics — the scalar summary of the same session
// ---------------------------------------------------------------------------

results.push(
  await callCapability("gex.metrics", async () => {
    const data = await apiGet("/api/v1/gex/metrics", { ticker });
    show("keys", keysOf(data));
    show("payload", summarize(data, { depth: 2, maxKeys: 12 }));
    return data;
  }, { note: "summary metrics" }),
);

// ---------------------------------------------------------------------------
// gex.gamma_flip and gex.maxpain — two single-number capabilities
// ---------------------------------------------------------------------------

results.push(
  await callCapability("gex.gamma_flip", async () => {
    const data = await apiGet("/api/v1/gex/gamma_flip", { ticker });
    show("payload", summarize(data, { depth: 2, maxKeys: 12 }));
    return data;
  }),
);

results.push(
  await callCapability("gex.maxpain", async () => {
    const data = await apiGet("/api/v1/gex/maxpain", { ticker });
    show("payload", summarize(data, { depth: 2, maxKeys: 12 }));
    return data;
  }),
);

// ---------------------------------------------------------------------------
// gex.named_levels — the levels again, in a form built for plotting
// ---------------------------------------------------------------------------

results.push(
  await callCapability("gex.named_levels", async () => {
    const data = await apiGet("/api/v1/gex/named_levels", { ticker });
    show("keys", keysOf(data));

    const [rowsKey, rows] = Object.entries(data).find(([, v]) => Array.isArray(v)) ?? [];
    if (rows) {
      show("rows key", rowsKey);
      show("rows", rows.length);
      for (const row of rows.slice(0, 4)) {
        console.log(`      ${summarize(row, { depth: 1, maxKeys: 6 })}`);
      }
    } else {
      show("payload", summarize(data, { depth: 2, maxKeys: 12 }));
    }
    return data;
  }, { note: "levels as a list, ready to draw" }),
);

// ---------------------------------------------------------------------------
// gex.snapshot — Edge. The interesting row for a reader with no key.
// ---------------------------------------------------------------------------
//
// Everything above is Free. This one sits behind the Edge floor, so without a
// credential it answers 401 `auth_required`, and with a credential below the
// floor it answers with `required_plan_name: "Edge"` in the problem document.
// `callCapability` prints whichever came back and the run carries on — which is
// the behaviour to copy: a plan floor is a documented answer, not an outage.

results.push(
  await callCapability("gex.snapshot", async () => {
    const data = await apiGet("/api/v1/gex/snapshot", { ticker, window: "today", view: "net" });
    show("keys", keysOf(data, 16));
    show("payload", summarize(data, { depth: 1, maxKeys: 10 }));
    return data;
  }, { note: "Edge plan — expected to refuse without one" }),
);

report(results);

heading("Related");
console.log("  Capability catalog   https://volstrata.com/docs/api-catalog");
console.log("  Error envelope       https://volstrata.com/docs/api-errors");
console.log("  Next domain          node rest/greeks.mjs");
