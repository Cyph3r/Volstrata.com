/**
 * Copyright 2026 Volstrata.com
 *
 * The `market.*` domain: session status, the cross-market overview, sector
 * rotation, a multi-symbol snapshot, candles, seasonality and ETF constituents.
 * Catalog: https://volstrata.com/docs/api-catalog
 *
 * Run:  node rest/market.mjs [TICKER]
 *       npm run market
 *
 * Seven sequential requests — enough to reach the anonymous rate-limit ceiling
 * if you run it twice in quick succession. That is not a defect to work around:
 * `withBackoff` reads `Retry-After` and waits. Raise `PACE_MS` in
 * lib/volstrata.mjs to widen the gap between calls.
 *
 * Which of these answer without a credential depends on the caller: an
 * anonymous call to a capability out of reach returns 401 `auth_required`
 * instead of data. Both outcomes are printed and the run continues.
 * `GET /api/v1/meta/access` reports what your own credential reaches — ask it
 * rather than trusting a list in a comment, which is exactly the kind of thing
 * that goes stale.
 *
 * This file also shows the two shared response blocks — `freshness` and
 * `delivery` — that appear on the reads that have them.
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

banner(`market.* — ${ticker}`);
show("ticker", `${ticker} (pass another as the first argument)`);

/**
 * Render the two shared blocks when a response carries them.
 *
 *   freshness  {as_of, age_seconds, live, stale, stale_after_seconds}
 *   delivery   {mode: "live" | "delayed", delay_seconds, reason}
 *
 * `delay_seconds` is `0` when the body really is realtime, and `null` when it is
 * delayed by an amount the server cannot state. The two are not interchangeable:
 * never coerce `null` to `0` (`delay ?? 0`, `delay || 0`), because that turns
 * "delayed by an unknown amount" into "not delayed at all". `reason` is
 * "plan_tier", "source_delay" or null: the first means a higher plan removes the
 * delay, the second means it does not.
 */
function showSharedBlocks(data) {
  const { freshness, delivery } = data ?? {};
  if (freshness && typeof freshness === "object") {
    show("freshness", `as_of=${freshness.as_of} age=${freshness.age_seconds}s stale=${freshness.stale}`);
  }
  if (delivery && typeof delivery === "object") {
    const seconds = delivery.delay_seconds;
    let delay;
    if (seconds === null || seconds === undefined) {
      // NOT the same as 0. The server is saying "delayed, magnitude unknown".
      delay = "delay not stated";
    } else if (seconds === 0) {
      delay = "+0s (realtime)";
    } else {
      delay = `+${seconds}s (${delivery.reason ?? "no reason given"})`;
    }
    show("delivery", `${delivery.mode} — ${delay}`);
  }
}

const results = [];

// ---------------------------------------------------------------------------
// market.status — is the session open, and how fresh is the data
// ---------------------------------------------------------------------------

results.push(
  await callCapability("market.status", async () => {
    const { res, data } = await apiFetch("/api/v1/market/status", {
      tickers: ticker,
      fresh_within_sec: 900, // what "fresh" should mean for this call
    });
    show("keys", keysOf(data));
    show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    showSharedBlocks(data);
    showRateLimit(res);
    return data;
  }, { note: "session state and freshness" }),
);

// ---------------------------------------------------------------------------
// market.overview — the cross-market read in one call
// ---------------------------------------------------------------------------

results.push(
  await callCapability("market.overview", async () => {
    const data = await apiGet("/api/v1/market/overview");
    show("keys", keysOf(data, 20));
    show("payload", summarize(data, { depth: 2, maxKeys: 8 }));
    showSharedBlocks(data);
    return data;
  }),
);

// ---------------------------------------------------------------------------
// market.rotations — sector rotation over a timeframe
// ---------------------------------------------------------------------------

results.push(
  await callCapability("market.rotations", async () => {
    const data = await apiGet("/api/v1/market/rotations", { tf: "1d" });
    show("keys", keysOf(data));
    const [rowsKey, rows] = Object.entries(data).find(([, v]) => Array.isArray(v)) ?? [];
    if (rows) {
      show("rows key", rowsKey);
      show("rows", rows.length);
      for (const row of rows.slice(0, 4)) console.log(`      ${summarize(row, { depth: 1, maxKeys: 6 })}`);
    } else {
      show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    }
    return data;
  }, { note: "tf=1d" }),
);

// ---------------------------------------------------------------------------
// market.snapshot — several symbols at once
// ---------------------------------------------------------------------------
//
// `tickers` takes a comma-separated list, or the keyword "core" for the default
// set. One request for many symbols beats one request per symbol — that is the
// difference between staying inside a rate-limit budget and not.

results.push(
  await callCapability("market.snapshot", async () => {
    const data = await apiGet("/api/v1/market/snapshot", { tickers: "core" });
    show("keys", keysOf(data, 20));
    show("payload", summarize(data, { depth: 2, maxKeys: 8 }));
    return data;
  }, { note: 'tickers="core"' }),
);

// ---------------------------------------------------------------------------
// market.candles — OHLC bars, cursor-paged
// ---------------------------------------------------------------------------
//
// One of the operations that declares a `cursor` parameter, so the paging model
// in pagination.mjs applies here too. `from` and `to` bound the range; `limit`
// is kept small here because an example should not pull a year of 1-minute bars
// to prove that it can.

results.push(
  await callCapability("market.candles", async () => {
    const data = await apiGet("/api/v1/market/candles", { ticker, tf: "1d", limit: 5 });
    show("keys", keysOf(data));
    show("next_cursor", data.next_cursor === null ? "null (last page)" : (data.next_cursor ? "present" : "(not reported)"));
    const [rowsKey, rows] = Object.entries(data).find(([, v]) => Array.isArray(v)) ?? [];
    if (rows) {
      show("rows key", rowsKey);
      show("bars", rows.length);
      show("first bar", summarize(rows[0], { depth: 1, maxKeys: 8 }));
      show("last bar", summarize(rows.at(-1), { depth: 1, maxKeys: 8 }));
    } else {
      show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    }
    return data;
  }, { note: "tf=1d, limit=5" }),
);

// ---------------------------------------------------------------------------
// market.seasonality — the calendar-shaped view
// ---------------------------------------------------------------------------

results.push(
  await callCapability("market.seasonality", async () => {
    const data = await apiGet("/api/v1/market/seasonality");
    show("keys", keysOf(data, 20));
    show("payload", summarize(data, { depth: 2, maxKeys: 8 }));
    return data;
  }),
);

// ---------------------------------------------------------------------------
// market.etf_constituents — what is inside an ETF
// ---------------------------------------------------------------------------

results.push(
  await callCapability("market.etf_constituents", async () => {
    const data = await apiGet("/api/v1/market/etf_constituents", { ticker: "SPY" });
    show("keys", keysOf(data));
    const [rowsKey, rows] = Object.entries(data).find(([, v]) => Array.isArray(v)) ?? [];
    if (rows) {
      show("rows key", rowsKey);
      show("constituents", rows.length);
      show("first", summarize(rows[0], { depth: 1, maxKeys: 6 }));
    } else {
      show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    }
    return data;
  }, { note: "ticker=SPY" }),
);

report(results);

heading("Related");
console.log("  Capability catalog   https://volstrata.com/docs/api-catalog");
console.log("  Rate limits          https://volstrata.com/docs/api-rate-limits");
console.log("  Next domain          node rest/levels.mjs");
