/**
 * Copyright 2026 Volstrata.com
 *
 * Cursor pagination, walked to completion against the capability catalog.
 * Docs: https://volstrata.com/docs/api-base-url
 *
 * Run:  node pagination.mjs [PAGE_SIZE]
 *       npm run pagination
 *
 * Pages `GET /api/v1/meta/capabilities?limit=25` — a Free, unauthenticated
 * capability that lists every published operation — until `next_cursor` comes
 * back null.
 *
 * One page is one request, so a full walk at limit=25 is around seven requests.
 * The loop is bounded by MAX_PAGES below: an unbounded cursor loop against a
 * live API is how a rate-limit budget disappears in a single run.
 */

import { VolstrataApiError, heading, paginate, show, summarize } from "./lib/volstrata.mjs";

/** Rows per page. Small on purpose here, so the walk actually has several pages. */
const LIMIT = Number(process.argv[2] ?? 25);

/** Hard stop. Reaching it means "stopped early", not "reached the end". */
const MAX_PAGES = 12;

heading("Cursor pagination — meta.capabilities");
show("path", "/api/v1/meta/capabilities");
show("page size", LIMIT);
show("page bound", MAX_PAGES);

/**
 * The paged envelope is uniform across the surface:
 *
 *   {"ok": true, "next_cursor": "<opaque>" | null, "limit": 25, "total": 175,
 *    "<rows>": [ … ]}
 *
 * `next_cursor` is the entire termination condition — null means this was the
 * last page. `total` is the matching row count across all pages, which is handy
 * for a progress line but is not a substitute for the null check.
 *
 * The rows themselves sit under the operation's own key, which differs per
 * operation, so this file finds the array rather than assuming a name. Printing
 * one page before writing the loop is the fastest way to learn the key you need.
 */
function rowsOf(page) {
  for (const [key, value] of Object.entries(page)) {
    if (Array.isArray(value)) return { key, rows: value };
  }
  return { key: null, rows: [] };
}

const rows = [];
let collectionKey = null;
let envelope = null;
let stoppedEarly = false;
let pages = 0;

try {
  // `paginate` is an async generator: it issues one request per iteration and
  // stops when `next_cursor` is null or the bound is reached. Cursors are opaque
  // — pass the string straight back, never parse, edit or construct one.
  for await (const { page, data, nextCursor } of paginate(
    "/api/v1/meta/capabilities",
    { limit: LIMIT },
    { maxPages: MAX_PAGES, pauseMs: 300 },
  )) {
    const found = rowsOf(data);
    collectionKey ??= found.key;
    envelope ??= data;
    rows.push(...found.rows);
    pages = page;

    console.log(
      `  page ${String(page).padStart(2)}  ` +
        `rows ${String(found.rows.length).padStart(3)}  ` +
        `running total ${String(rows.length).padStart(4)}  ` +
        `next_cursor ${nextCursor === null ? "null (last page)" : "present"}`,
    );

    // The bound, made visible: if the last page still had a cursor, there is
    // more data and this run simply chose not to ask for it.
    if (page === MAX_PAGES && nextCursor !== null) stoppedEarly = true;
  }
} catch (error) {
  heading("The walk stopped on an error");
  if (error instanceof VolstrataApiError) {
    console.log(error.describe("  "));
  } else {
    console.log(`  ${error?.message ?? error}`);
  }
  console.log("\n  Errors reference: https://volstrata.com/docs/api-errors");
  process.exitCode = 1;
}

if (envelope) {
  heading("Envelope fields (from the first page)");
  show("ok", envelope.ok);
  show("limit applied", envelope.limit ?? "(not reported)"); // read it; your requested size may be capped
  show("total", envelope.total ?? "(not reported)");
  show("rows key", collectionKey ?? "(none found)");
  if (envelope.limit === undefined || envelope.total === undefined) {
    console.log("  (not every paged capability reports limit and total — `next_cursor`");
    console.log("   is the only field the loop actually needs)");
  }

  heading("Result");
  show("pages fetched", pages);
  show("rows collected", rows.length);
  show("complete", stoppedEarly ? `no — stopped at the ${MAX_PAGES}-page bound` : "yes — next_cursor was null");

  if (rows.length > 0) {
    // Each capability row describes one operation: {name, method, path, params,
    // policy_key, tier, tier_name}. Display `tier_name` ("Free", "Edge") to a
    // human and branch on `tier` in software.
    heading("First rows");
    for (const row of rows.slice(0, 5)) {
      console.log(`  ${summarize(row, { depth: 1, maxKeys: 6 })}`);
    }

    const byTier = new Map();
    for (const row of rows) {
      const tier = row?.tier_name ?? row?.tier ?? "(unknown)";
      byTier.set(tier, (byTier.get(tier) ?? 0) + 1);
    }
    heading("Rows by plan floor");
    for (const [tier, count] of [...byTier].sort((a, b) => b[1] - a[1])) {
      show(tier, count);
    }
  }

  console.log("\n  This listing is the reason not to hard-code a capability list:");
  console.log("  it is free, unauthenticated, and always current.");
}
