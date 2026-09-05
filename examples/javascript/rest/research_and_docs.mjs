/**
 * Copyright 2026 Volstrata.com
 *
 * The `research.*`, `docs.*` and `symbol.*` domains — the self-describing half
 * of the API. What is covered, which metrics exist, what each metric means, and
 * how to turn a name a human typed into a symbol the API accepts. All Free.
 * Catalog: https://volstrata.com/docs/api-catalog
 *
 * Run:  node rest/research_and_docs.mjs [TICKER]
 *       npm run research
 *
 * Eight requests. Two of them are chained on purpose: `docs.metrics` lists the
 * metric names and `docs.metric` is then asked about the first one, which is the
 * pattern to copy — discover, then ask, rather than hard-coding a list that will
 * drift out of date.
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

banner(`research.*, docs.* and symbol.* — ${ticker}`);
show("ticker", `${ticker} (pass another as the first argument)`);

const results = [];

/** Pull a list of names out of a payload without assuming the key or the shape. */
function namesFrom(data, limit = 12) {
  const [, rows] = Object.entries(data ?? {}).find(([, v]) => Array.isArray(v)) ?? [];
  if (!rows) return [];
  return rows
    .slice(0, limit)
    .map((row) => (typeof row === "string" ? row : row?.metric ?? row?.name ?? row?.id ?? row?.key))
    .filter((name) => typeof name === "string");
}

// ---------------------------------------------------------------------------
// research.metrics — which metrics the research surface can return
// ---------------------------------------------------------------------------

results.push(
  await callCapability("research.metrics", async () => {
    const { res, data } = await apiFetch("/api/v1/research/metrics");
    show("keys", keysOf(data));

    // The response is a vocabulary: several lists, each one the accepted values
    // for a parameter of `research.query` below. Print every list rather than
    // picking one, because which list matters depends on what you are asking.
    for (const [key, value] of Object.entries(data)) {
      if (Array.isArray(value)) show(key, summarize(value, { depth: 1, maxItems: 8 }));
    }

    showRateLimit(res);
    return data;
  }, { note: "the accepted values for the query parameters below" }),
);

// ---------------------------------------------------------------------------
// research.query — one shape, many views
// ---------------------------------------------------------------------------
//
// This is the widest-parameter capability in the file, and the parameters are
// worth knowing because several other capabilities borrow the same names:
//
//   metric        which metric to return
//   view          ladder | smile | term | levels_term | parity | surface
//   weight        oi | vol | both
//   contracts     all | calls | puts        moneyness  all | atm | ntm | itm | otm
//   expiry_class  all | w | m | q           strikes / start_dte / end_dte
//
// Every one of them has a default, so start small — as below — and add
// parameters only when you know why.

results.push(
  await callCapability("research.query", async () => {
    const data = await apiGet("/api/v1/research/query", {
      ticker,
      metric: "gex",
      view: "ladder",
      strikes: 5,
    });
    show("keys", keysOf(data));
    const [rowsKey, rows] = Object.entries(data).find(([, v]) => Array.isArray(v)) ?? [];
    if (rows) {
      show("rows key", rowsKey);
      show("rows", rows.length);
      show("first row", summarize(rows[0], { depth: 1, maxKeys: 8 }));
    } else {
      show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    }
    return data;
  }, { note: "view=ladder, strikes=5" }),
);

// ---------------------------------------------------------------------------
// research.coverage and research.universe — what exists, and for what
// ---------------------------------------------------------------------------
//
// `coverage` answers "what can I ask for about this symbol"; `universe` answers
// "which symbols are there at all". Both accept an `at` timestamp to ask the
// same question about a past moment, and both can return CSV via `format=csv` —
// which, like every non-JSON format, needs `res.text()` rather than a JSON
// parse.

results.push(
  await callCapability("research.coverage", async () => {
    const data = await apiGet("/api/v1/research/coverage", { ticker });
    show("keys", keysOf(data, 20));
    show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    return data;
  }),
);

results.push(
  await callCapability("research.universe", async () => {
    const data = await apiGet("/api/v1/research/universe");
    show("keys", keysOf(data));
    const names = namesFrom(data, 10);
    if (names.length) show("first symbols", names.join(", "));
    else show("payload", summarize(data, { depth: 1, maxKeys: 8 }));
    return data;
  }),
);

// ---------------------------------------------------------------------------
// docs.metrics then docs.metric — the glossary, over the API
// ---------------------------------------------------------------------------
//
// `docs.metric` is where a metric's definition lives. When a field name in some
// other response is unfamiliar, this is the capability to ask rather than
// guessing from the name — and it is Free, so an agent can look a term up for
// itself mid-conversation.

let firstMetric = null;

results.push(
  await callCapability("docs.metrics", async () => {
    const data = await apiGet("/api/v1/docs/metrics");
    show("keys", keysOf(data));
    const names = namesFrom(data, 16);
    firstMetric = names[0] ?? null;
    if (names.length) show("documented", names.join(", "));
    show("count", names.length ? `${names.length} shown` : "(no list found in this shape)");
    return data;
  }, { note: "the index" }),
);

results.push(
  await callCapability("docs.metric", async () => {
    // `metric` is required — this is the one capability in the file that has no
    // usable default, which is exactly why the call above ran first.
    const metric = firstMetric ?? "gex";
    const data = await apiGet("/api/v1/docs/metric", { metric });
    show("metric", metric);
    show("keys", keysOf(data));
    for (const [key, value] of Object.entries(data)) {
      if (typeof value === "string" && value.length > 30) {
        show(key, `${value.slice(0, 200)}${value.length > 200 ? "…" : ""}`);
      }
    }
    return data;
  }, { note: "definition of the first metric listed above" }),
);

// ---------------------------------------------------------------------------
// symbol.search and symbol.resolve — free text in, a usable symbol out
// ---------------------------------------------------------------------------
//
// Search is for a human typing; resolve is for a string your own system already
// holds and needs normalised. Call one of these before you send a user-supplied
// symbol into a data capability, and a typo becomes an empty search result
// instead of a confusing 404.

results.push(
  await callCapability("symbol.search", async () => {
    const data = await apiGet("/api/v1/symbol/search", { q: "apple", limit: 5 });
    show("query", '"apple"');
    show("keys", keysOf(data));
    const [rowsKey, rows] = Object.entries(data).find(([, v]) => Array.isArray(v)) ?? [];
    if (rows) {
      show("rows key", rowsKey);
      show("matches", rows.length);
      for (const row of rows.slice(0, 5)) console.log(`      ${summarize(row, { depth: 1, maxKeys: 6 })}`);
    } else {
      show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    }
    return data;
  }, { note: "q=apple" }),
);

results.push(
  await callCapability("symbol.resolve", async () => {
    const data = await apiGet("/api/v1/symbol/resolve", { symbol: ticker });
    show("input", ticker);
    show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    return data;
  }),
);

report(results);

heading("Related");
console.log("  Capability catalog   https://volstrata.com/docs/api-catalog");
console.log("  API overview         https://volstrata.com/docs/api-overview");
console.log("  Next domain          node rest/calendar_news_social.mjs");
