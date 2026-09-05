/**
 * Copyright 2026 Volstrata.com
 *
 * The `accuracy.*`, `gammapin.*`, `dealergamma.*`, `stats.*` and `status.*`
 * domains — the published track record and the service's own status. All Free.
 * Catalog: https://volstrata.com/docs/api-catalog
 *
 * Run:  node rest/accuracy_and_stats.mjs [TICKER]
 *       npm run accuracy
 *
 * Nine sequential requests, the longest run in this folder. Two runs back to
 * back will meet the anonymous rate-limit ceiling; `withBackoff` reads
 * `Retry-After` and waits rather than failing, so the second run is slow, not
 * broken. Raise `PACE_MS` in lib/volstrata.mjs to widen the gap between calls.
 *
 * These capabilities report outcomes. What each field means is in the public
 * glossary at https://volstrata.com/docs/api-catalog; how any of the numbers is
 * produced is not something this file describes. The job here is to show you how
 * to fetch them and what shape they arrive in.
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

banner(`accuracy.*, dealergamma.*, stats.* and status.* — ${ticker}`);
show("ticker", `${ticker} (pass another as the first argument)`);

const results = [];

/** Break a string onto lines of at most `width` characters, losing nothing. */
function wrap(text, width) {
  const lines = [];
  let current = "";
  for (const word of text.split(/\s+/).filter(Boolean)) {
    if (current && current.length + 1 + word.length > width) {
      lines.push(current);
      current = word;
    } else {
      current = current ? `${current} ${word}` : word;
    }
  }
  if (current) lines.push(current);
  return lines;
}

/** Print a table-shaped payload: the rows key, the count, and a few rows. */
function showTable(data, sampleCount = 3) {
  show("keys", keysOf(data, 16));
  const [rowsKey, rows] = Object.entries(data).find(([, v]) => Array.isArray(v)) ?? [];
  if (rows) {
    show("rows key", rowsKey);
    show("rows", rows.length);
    for (const row of rows.slice(0, sampleCount)) {
      console.log(`      ${summarize(row, { depth: 1, maxKeys: 7, maxString: 80 })}`);
    }
  } else {
    show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
  }
}

// ---------------------------------------------------------------------------
// accuracy.scoreboard — the summary, optionally for one symbol
// ---------------------------------------------------------------------------

results.push(
  await callCapability("accuracy.scoreboard", async () => {
    const { res, data } = await apiFetch("/api/v1/accuracy/scoreboard", { ticker });
    showTable(data);
    showRateLimit(res);
    return data;
  }, { note: `ticker=${ticker} — omit it for every symbol` }),
);

// ---------------------------------------------------------------------------
// accuracy.tape — the running record behind the scoreboard
// ---------------------------------------------------------------------------

results.push(
  await callCapability("accuracy.tape", async () => {
    const data = await apiGet("/api/v1/accuracy/tape");
    showTable(data);
    return data;
  }),
);

// ---------------------------------------------------------------------------
// accuracy.pin_contest and accuracy.pin_leaderboard
// ---------------------------------------------------------------------------
//
// The current contest and the standing it feeds. Both take a `ticker`.

results.push(
  await callCapability("accuracy.pin_contest", async () => {
    const data = await apiGet("/api/v1/accuracy/pin_contest", { ticker });
    showTable(data);
    // The response carries a display-ready `disclaimer`. Render it IN FULL if
    // you surface any of this to a user — a risk disclaimer cut off
    // mid-sentence is worse than one you never showed. Wrap it; never slice it.
    if (data?.disclaimer) {
      console.log("      disclaimer:");
      for (const line of wrap(String(data.disclaimer), 72)) console.log(`        ${line}`);
    }
    return data;
  }),
);

results.push(
  await callCapability("accuracy.pin_leaderboard", async () => {
    const data = await apiGet("/api/v1/accuracy/pin_leaderboard", { ticker });
    showTable(data, 5);
    return data;
  }),
);

// ---------------------------------------------------------------------------
// gammapin.today — today's entry
// ---------------------------------------------------------------------------
//
// `date` asks for a specific day; left off, you get the current one. A date with
// no data is a normal answer, not an error, so read the payload rather than
// assuming a row is there.

results.push(
  await callCapability("gammapin.today", async () => {
    const data = await apiGet("/api/v1/gammapin/today", { ticker });
    show("keys", keysOf(data, 16));
    show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    return data;
  }, { note: "add date=YYYY-MM-DD for a specific session" }),
);

// ---------------------------------------------------------------------------
// dealergamma.history and dealergamma.tickers
// ---------------------------------------------------------------------------
//
// `days` bounds the history — 120 is the default and 30 is plenty for a look.
// Ask `dealergamma.tickers` which symbols carry this series before requesting
// one that does not.

results.push(
  await callCapability("dealergamma.history", async () => {
    const data = await apiGet("/api/v1/dealergamma/history", { ticker, days: 30 });
    showTable(data, 2);
    return data;
  }, { note: "days=30" }),
);

results.push(
  await callCapability("dealergamma.tickers", async () => {
    const data = await apiGet("/api/v1/dealergamma/tickers");
    show("keys", keysOf(data));
    const [, rows] = Object.entries(data).find(([, v]) => Array.isArray(v)) ?? [];
    if (rows) {
      show("symbols", rows.length);
      // Rows may be bare strings or small objects depending on the capability —
      // depth 2 renders both without assuming either.
      show("first", summarize(rows.slice(0, 6), { depth: 2, maxItems: 6, maxKeys: 4 }));
    } else {
      show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    }
    return data;
  }, { note: "which symbols this series covers" }),
);

// ---------------------------------------------------------------------------
// stats.greeks.dex_vex_direction — one row from the stats.greeks.* family
// ---------------------------------------------------------------------------
//
// Seven `stats.greeks.*` capabilities publish the same kind of aggregate over
// different measurements, and they all take no parameters at all. The path is
// the dotted name with slashes, as everywhere else:
//
//   stats.greeks.dex_vex_direction  →  /api/v1/stats/greeks/dex_vex_direction
//
// Run `node pagination.mjs` — or read the generated reference under
// `docs/reference/` in this repository — for the full list, rather than typing
// the other six from memory.

results.push(
  await callCapability("stats.greeks.dex_vex_direction", async () => {
    const data = await apiGet("/api/v1/stats/greeks/dex_vex_direction");
    showTable(data, 2);
    return data;
  }, { note: "no parameters" }),
);

// ---------------------------------------------------------------------------
// status.overview — is the service healthy
// ---------------------------------------------------------------------------
//
// The capability to call before concluding that something on your side is
// broken. It is Free and needs no key, so it also works as the first check in a
// monitoring script.

results.push(
  await callCapability("status.overview", async () => {
    const data = await apiGet("/api/v1/status/overview");
    show("keys", keysOf(data, 16));
    show("payload", summarize(data, { depth: 2, maxKeys: 12 }));
    return data;
  }),
);

report(results);

heading("Related");
console.log("  Capability catalog   https://volstrata.com/docs/api-catalog");
console.log("  Rate limits          https://volstrata.com/docs/api-rate-limits");
console.log("  MCP                  node mcp/list_tools.mjs");
