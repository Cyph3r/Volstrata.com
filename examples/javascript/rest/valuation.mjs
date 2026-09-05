/**
 * Copyright 2026 Volstrata.com
 *
 * The `valuation.*` and `fundamentals.*` domains: a screened universe, one
 * company's valuation record, its fundamentals, and the one POST capability in
 * this file — which needs the Pro plan.
 * Catalog: https://volstrata.com/docs/api-catalog
 *
 * Run:  node rest/valuation.mjs [TICKER]
 *       npm run valuation
 *
 * Four requests. Unlike the index-oriented domains, these take an equity ticker,
 * so the default here is AAPL rather than SPX.
 *
 *   valuation.universe    GET   needs a credential
 *   valuation.company     GET   needs a credential
 *   fundamentals.company  GET   answers anonymously
 *   valuation.value       POST  needs the Pro plan — the shape of a POST call
 *
 * Worth knowing before you run this with no key: the `valuation.*` rows answer
 * 401 `auth_required` to an anonymous caller, so three of the four rows below
 * refuse. That is the point of running it — a credential gets you past a 401,
 * and whether the data then comes back is a separate question your plan
 * answers. `GET /api/v1/meta/access` reports what your own credential reaches.
 */

import {
  apiGet,
  apiPost,
  banner,
  callCapability,
  heading,
  keysOf,
  report,
  show,
  summarize,
} from "../lib/volstrata.mjs";

const ticker = (process.argv[2] ?? "AAPL").toUpperCase();

banner(`valuation.* — ${ticker}`);
show("ticker", `${ticker} (pass another as the first argument)`);

const results = [];

// ---------------------------------------------------------------------------
// valuation.universe — what is covered at all
// ---------------------------------------------------------------------------
//
// Start here rather than guessing whether a symbol is covered. The listing takes
// `limit` and `offset` (this one is offset-paged, not cursor-paged — the shared
// cursor model in pagination.mjs applies to the 17 operations that declare a
// `cursor` parameter, and this is not one of them), plus optional `sector`,
// `model`, `verdict` and `min_market_cap` filters.

results.push(
  await callCapability("valuation.universe", async () => {
    const data = await apiGet("/api/v1/valuation/universe", { limit: 5, offset: 0 });

    show("keys", keysOf(data));
    const [rowsKey, rows] = Object.entries(data).find(([, v]) => Array.isArray(v)) ?? [];
    if (rows) {
      show("rows key", rowsKey);
      show("rows returned", rows.length);
      for (const row of rows.slice(0, 3)) {
        console.log(`      ${summarize(row, { depth: 1, maxKeys: 7 })}`);
      }
    } else {
      show("payload", summarize(data, { depth: 2, maxKeys: 12 }));
    }
    return data;
  }, { note: "limit=5 — keep exploratory calls small" }),
);

// ---------------------------------------------------------------------------
// valuation.company — one company's record
// ---------------------------------------------------------------------------
//
// The response fields are the outputs of a valuation model. This repo documents
// their names and units and links the glossary for what each one means; how any
// of them is produced is not something these examples describe.

results.push(
  await callCapability("valuation.company", async () => {
    const data = await apiGet("/api/v1/valuation/company", { ticker });
    show("keys", keysOf(data, 20));
    show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    return data;
  }),
);

// ---------------------------------------------------------------------------
// fundamentals.company — the reported figures behind it
// ---------------------------------------------------------------------------

results.push(
  await callCapability("fundamentals.company", async () => {
    const data = await apiGet("/api/v1/fundamentals/company", { ticker });
    show("keys", keysOf(data, 20));
    show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    return data;
  }),
);

// ---------------------------------------------------------------------------
// valuation.value — POST, Pro
// ---------------------------------------------------------------------------
//
// 7 of the 180 published operations are POST; the other 173 are GET. A POST
// capability takes a JSON body:
//
//   fetch(url, {
//     method: "POST",
//     headers: { "Content-Type": "application/json", ... },
//     body: JSON.stringify({ ticker: "AAPL" }),
//   })
//
// which is what `apiPost` below does. Everything else is identical to a GET:
// the same Authorization header, the same problem+json refusal, the same
// rate-limit headers. Without the Pro plan this row refuses and the run
// continues.

results.push(
  await callCapability("valuation.value", async () => {
    const data = await apiPost("/api/v1/valuation/value", { ticker });
    show("keys", keysOf(data, 20));
    show("payload", summarize(data, { depth: 2, maxKeys: 10 }));
    return data;
  }, { note: "Pro plan — POST with a JSON body" }),
);

report(results);

heading("Related");
console.log("  Capability catalog   https://volstrata.com/docs/api-catalog");
console.log("  Plans and auth       https://volstrata.com/docs/api-auth");
console.log("  Next domain          node rest/market.mjs");
