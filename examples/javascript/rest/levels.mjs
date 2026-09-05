/**
 * Copyright 2026 Volstrata.com
 *
 * The `levels.*` domain: the day and week level sets, their report forms, the
 * detail behind a single level, and the TradingView export.
 * Catalog: https://volstrata.com/docs/api-catalog
 *
 * Run:  node rest/levels.mjs [TICKER]
 *       npm run levels
 *
 * Six requests. The last one is the only capability in this folder that can
 * return something other than JSON, which is worth seeing once — see the note
 * on `format` further down.
 *
 * Two answers you may get here that are not failures:
 *
 *   404 `not_found`        the route is right and there is simply nothing to
 *                          return for this symbol at this moment. Read `detail`
 *                          — it says why — and try another symbol or later.
 *   404 `route_not_found`  the path itself is not published. A different thing
 *                          entirely, and no key or plan fixes it.
 *
 * The tally at the bottom counts them separately for exactly that reason.
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

banner(`levels.* — ${ticker}`);
show("ticker", `${ticker} (pass another as the first argument)`);

const results = [];

/** Print a level set without asserting which names are in it. */
function showLevelSet(data) {
  show("keys", keysOf(data));
  const levels = data.levels ?? data;
  if (levels && typeof levels === "object" && !Array.isArray(levels)) {
    const named = Object.entries(levels).filter(([, v]) => typeof v === "number");
    show("numeric levels", named.length);
    for (const [name, value] of named.slice(0, 8)) show(`  ${name}`, value);
  }
}

// ---------------------------------------------------------------------------
// levels.day and levels.week — the same shape over two horizons
// ---------------------------------------------------------------------------
//
// Names that appear in both are the same names `gex.levels` returns; the
// glossary defines each one, and this file does not repeat those definitions:
// https://volstrata.com/docs/api-catalog

results.push(
  await callCapability("levels.day", async () => {
    const { res, data } = await apiFetch("/api/v1/levels/day", { ticker });
    showLevelSet(data);
    showRateLimit(res);
    return data;
  }, { note: "the current session" }),
);

results.push(
  await callCapability("levels.week", async () => {
    const data = await apiGet("/api/v1/levels/week", { ticker });
    showLevelSet(data);
    return data;
  }, { note: "the current week" }),
);

// ---------------------------------------------------------------------------
// levels.day_report and levels.week_report — the same data, written out
// ---------------------------------------------------------------------------
//
// The report forms return prose or a structured summary rather than bare
// numbers, which is what you want when the destination is a Slack message or an
// LLM prompt rather than a chart.

results.push(
  await callCapability("levels.day_report", async () => {
    const data = await apiGet("/api/v1/levels/day_report", { ticker });
    show("keys", keysOf(data));
    for (const [key, value] of Object.entries(data)) {
      if (typeof value === "string" && value.length > 40) {
        show(key, `${value.slice(0, 160)}${value.length > 160 ? "…" : ""}`);
      }
    }
    return data;
  }),
);

results.push(
  await callCapability("levels.week_report", async () => {
    const data = await apiGet("/api/v1/levels/week_report", { ticker });
    show("keys", keysOf(data));
    show("payload", summarize(data, { depth: 1, maxKeys: 8, maxString: 140 }));
    return data;
  }),
);

// ---------------------------------------------------------------------------
// levels.detail — one level, in depth
// ---------------------------------------------------------------------------
//
// `kind` names the level you want detail on ("cw" here). `days` and `strikes`
// widen the history and the strike span when you pass them; left off, the
// capability picks its own defaults, which is what the omitted parameters below
// demonstrate.

results.push(
  await callCapability("levels.detail", async () => {
    const data = await apiGet("/api/v1/levels/detail", { ticker, kind: "cw" });
    show("keys", keysOf(data, 20));
    show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    return data;
  }, { note: "kind=cw" }),
);

// ---------------------------------------------------------------------------
// levels.tradingview — the export, and the one `format` you have to think about
// ---------------------------------------------------------------------------
//
// Most capabilities take `format=json` and that is the end of it. This one also
// accepts `txt`, `pine` and `csv`, and those return text/plain, not JSON — so
// the JSON helpers in lib/volstrata.mjs are the wrong tool for them:
//
//   const res = await fetch(buildUrl("/api/v1/levels/tradingview",
//                                    { ticker, format: "pine" }),
//                           { headers: headers() });
//   const script = await res.text();     // read text, not JSON
//
// The call below stays with JSON so the rest of this file's printing applies.

results.push(
  await callCapability("levels.tradingview", async () => {
    const data = await apiGet("/api/v1/levels/tradingview", { ticker, format: "json" });
    show("keys", keysOf(data, 20));
    show("payload", summarize(data, { depth: 2, maxKeys: 10, maxString: 100 }));
    return data;
  }, { note: "format=json — txt, pine and csv return text/plain" }),
);

report(results);

heading("Related");
console.log("  Capability catalog   https://volstrata.com/docs/api-catalog");
console.log("  Base URL and format  https://volstrata.com/docs/api-base-url");
console.log("  Next domain          node rest/research_and_docs.mjs");
