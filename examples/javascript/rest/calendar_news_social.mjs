/**
 * Copyright 2026 Volstrata.com
 *
 * The `calendar.*`, `news.*`, `insider.*` and `social.*` domains — the
 * event-shaped half of the surface. Most of these are cursor-paged, so this is
 * where the `limit` and `cursor` parameters show up most often.
 * Catalog: https://volstrata.com/docs/api-catalog
 *
 * Run:  node rest/calendar_news_social.mjs [TICKER]
 *       npm run calendar
 *
 * Eight requests, each capped with a small `limit`. Only the first page of each
 * feed is fetched: pagination.mjs is where walking a feed to the end belongs,
 * and doing it eight times over in one script would spend a rate-limit budget
 * for no teaching benefit.
 *
 * Before you run this with no key: these capabilities currently answer
 * 401 `auth_required` to an anonymous caller, so a keyless run prints eight
 * refusals and no rows. That is a complete and correct run — just not an
 * interesting one. Read `rest/gex_levels.mjs` first if you have no key yet, and
 * come back to this file once you do. Any valid key gets past a 401; what your
 * plan then reaches is what `GET /api/v1/meta/access` reports.
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

banner(`calendar.*, news.*, insider.* and social.* — ${ticker}`);
show("ticker", `${ticker} (pass another as the first argument)`);

const results = [];

/**
 * Print the first page of a feed: how many rows, whether another page exists,
 * and a couple of rows so the shape is visible.
 *
 * `next_cursor` is the only termination condition that matters. A page that
 * comes back full is not proof there is more, and a short page is not proof
 * there is not.
 */
function showFeed(data, sampleCount = 3) {
  show("keys", keysOf(data));
  if ("total" in data) show("total", data.total);
  if ("limit" in data) show("limit applied", data.limit);
  if ("next_cursor" in data) {
    show("next_cursor", data.next_cursor === null ? "null (last page)" : "present (more pages)");
  }
  const [rowsKey, rows] = Object.entries(data).find(([, v]) => Array.isArray(v)) ?? [];
  if (rows) {
    show("rows key", rowsKey);
    show("rows", rows.length);
    for (const row of rows.slice(0, sampleCount)) {
      console.log(`      ${summarize(row, { depth: 1, maxKeys: 6, maxString: 90 })}`);
    }
  } else {
    show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
  }
}

// ---------------------------------------------------------------------------
// calendar.combined — everything on the calendar, one call
// ---------------------------------------------------------------------------
//
// `range` takes a compact duration ("7d", "30d"), `types` filters the kinds of
// event, and `ticker` narrows to one symbol. Start with the combined feed and
// drop to the specific ones below when you need the extra filters they carry.

results.push(
  await callCapability("calendar.combined", async () => {
    const { res, data } = await apiFetch("/api/v1/calendar/combined", { range: "7d", limit: 5 });
    showFeed(data);
    showRateLimit(res);
    return data;
  }, { note: "range=7d, limit=5" }),
);

// ---------------------------------------------------------------------------
// calendar.events — macro events, with an importance filter
// ---------------------------------------------------------------------------

results.push(
  await callCapability("calendar.events", async () => {
    const data = await apiGet("/api/v1/calendar/events", {
      range: "7d",
      limit: 5,
      importance_min: 0, // raise this to drop the routine entries
      region: "all",
    });
    showFeed(data);
    return data;
  }, { note: "range=7d, importance_min=0" }),
);

// ---------------------------------------------------------------------------
// calendar.corporate — company events, over a longer default range
// ---------------------------------------------------------------------------

results.push(
  await callCapability("calendar.corporate", async () => {
    const data = await apiGet("/api/v1/calendar/corporate", { range: "30d", limit: 5 });
    showFeed(data);
    return data;
  }, { note: "range=30d, limit=5" }),
);

// ---------------------------------------------------------------------------
// news.feed — headlines, optionally for one symbol
// ---------------------------------------------------------------------------
//
// Leave `ticker` off for the whole feed. This repo does not name where any of
// this content originates; the fields are what the API returns.

results.push(
  await callCapability("news.feed", async () => {
    const data = await apiGet("/api/v1/news/feed", { ticker, limit: 5 });
    showFeed(data);
    return data;
  }, { note: `ticker=${ticker}, limit=5` }),
);

// ---------------------------------------------------------------------------
// insider.filings — regulatory filings
// ---------------------------------------------------------------------------
//
// `form` selects the filing type ("4" by default). Passing a `ticker` narrows
// to one issuer; leaving it off returns the general feed, which is what this
// call does so it returns rows for an index ticker too.

results.push(
  await callCapability("insider.filings", async () => {
    const data = await apiGet("/api/v1/insider/filings", { form: "4", limit: 5 });
    showFeed(data);
    return data;
  }, { note: "form=4, limit=5" }),
);

// ---------------------------------------------------------------------------
// social.sentiment, social.tallies, social.influencers
// ---------------------------------------------------------------------------
//
// Three different cuts of the same conversation: the per-post feed, the counted
// summary, and the accounts driving it. `tallies` and `influencers` take
// thresholds (`min_posts`, `min`) rather than a cursor — they are already
// aggregates.

results.push(
  await callCapability("social.sentiment", async () => {
    const data = await apiGet("/api/v1/social/sentiment", { ticker, limit: 5 });
    showFeed(data);
    return data;
  }, { note: `ticker=${ticker}, limit=5` }),
);

results.push(
  await callCapability("social.tallies", async () => {
    const data = await apiGet("/api/v1/social/tallies", { top: 10, min_posts: 3 });
    showFeed(data, 5);
    return data;
  }, { note: "top=10, min_posts=3" }),
);

results.push(
  await callCapability("social.influencers", async () => {
    const data = await apiGet("/api/v1/social/influencers", { hours: 48, min: 2 });
    showFeed(data, 5);
    return data;
  }, { note: "hours=48, min=2" }),
);

report(results);

heading("Related");
console.log("  Capability catalog   https://volstrata.com/docs/api-catalog");
console.log("  Pagination           node pagination.mjs");
console.log("  Next domain          node rest/accuracy_and_stats.mjs");
