/**
 * Copyright 2026 Volstrata.com
 *
 * Shared helpers for every JavaScript example in this folder: URL building,
 * headers, the RFC 9457 error type, retry-with-backoff, cursor pagination,
 * rate-limit header parsing, and a couple of small printers.
 *
 * There is no VolStrata npm package. This file is the whole client: plain ESM on
 * top of the `fetch` that ships with Node 18+, mostly comments. Copy it into
 * your own project and edit it — that is what it is for.
 *
 * Docs: https://volstrata.com/docs/api-overview
 * Node: 18 or newer (global `fetch`, `AbortSignal.timeout`)
 */

// ---------------------------------------------------------------------------
// Configuration — environment only, never a literal in source
// ---------------------------------------------------------------------------

/**
 * Base URL of the API. Override with VOLSTRATA_API_BASE only if you have been
 * told to; https://api.volstrata.com is the canonical API host. The older
 * VOLSTRATA_BASE_URL is still read as a fallback.
 */
export const BASE = (
  process.env.VOLSTRATA_API_BASE ??
  process.env.VOLSTRATA_BASE_URL ??
  "https://api.volstrata.com"
).replace(/\/+$/, "");

/**
 * Optional API key. 67 of the 180 published capabilities sit at the Free floor
 * and most of those answer with no credential at all; a few Free-floor data
 * capabilities still ask for any valid key and answer 401 without one. Every
 * example in this folder runs to completion with this unset: a row the caller
 * cannot reach prints its refusal and the run carries on.
 *
 * Create one at https://volstrata.com/api-keys, then:
 *   macOS / Linux    export VOLSTRATA_API_KEY="gex_key_v1_XXXXXXXX"
 *   Windows (PS)     $env:VOLSTRATA_API_KEY = "gex_key_v1_XXXXXXXX"
 */
const rawKey = process.env.VOLSTRATA_API_KEY;
export const API_KEY = rawKey && rawKey.trim() ? rawKey.trim() : undefined;
export const hasApiKey = API_KEY !== undefined;

/**
 * A CDN sits in front of the API and refuses some default User-Agent strings
 * before the request ever reaches it — the refusal is then HTML or plain text,
 * not the JSON problem document the API would have returned. Always send an
 * explicit, identifying User-Agent.
 */
export const USER_AGENT = "volstrata-examples/1.0 (+https://volstrata.com)";

/** Default per-request timeout, milliseconds. */
export const TIMEOUT_MS = 20_000;

/**
 * Request headers. `Authorization` appears only when the environment variable is
 * set, which is what lets one code path serve both the anonymous and the
 * authenticated case.
 *
 * The query-string form (`?api_key=…`) is also accepted by the API, but a header
 * keeps the key out of shell history, proxy logs and browser referrers.
 */
export function headers(extra = {}) {
  const out = {
    "User-Agent": USER_AGENT,
    Accept: "application/json",
    ...extra,
  };
  if (API_KEY) out.Authorization = `Bearer ${API_KEY}`;
  return out;
}

// ---------------------------------------------------------------------------
// Errors — RFC 9457 application/problem+json
// ---------------------------------------------------------------------------

/**
 * Every refusal from the API is an RFC 9457 problem document:
 *
 *   {"ok": false, "type": "<origin>/errors/<code>", "title": "...",
 *    "status": 402, "detail": "...", "instance": "/api/v1/...", "code": "...",
 *    "request_id": "..."}
 *
 * Plan refusals add "required_plan", "required_plan_name" and "current_plan".
 *
 * A response whose body is NOT JSON did not come from the API — something in
 * front of it answered instead. `isApiResponse` records which case you are in so
 * you never have to guess.
 */
export class VolstrataApiError extends Error {
  constructor(message, fields = {}) {
    super(message);
    this.name = "VolstrataApiError";
    this.status = fields.status ?? 0;
    this.code = fields.code ?? null;
    this.title = fields.title ?? null;
    this.detail = fields.detail ?? null;
    this.instance = fields.instance ?? null;
    this.requestId = fields.requestId ?? null;
    this.requiredPlan = fields.requiredPlan ?? null;
    this.requiredPlanName = fields.requiredPlanName ?? null;
    this.currentPlan = fields.currentPlan ?? null;
    this.retryAfterSeconds = fields.retryAfterSeconds ?? null;
    this.url = fields.url ?? null;
    this.contentType = fields.contentType ?? null;
    this.isApiResponse = fields.isApiResponse ?? true;
    this.bodySample = fields.bodySample ?? null;
  }

  /** True for the two classes of failure that are worth trying again. */
  get isRetryable() {
    return this.status === 429 || (this.status >= 500 && this.status <= 599);
  }

  /** True when the caller is authenticated but the plan is below the floor. */
  get isPlanRefusal() {
    return this.requiredPlanName !== null || this.code === "upgrade_required";
  }

  /** True when no credential was presented at all. */
  get isAuthRequired() {
    return this.status === 401 || this.code === "auth_required";
  }

  /**
   * True for a 404 `not_found`: the route is right and the capability simply has
   * nothing to return at this moment. Distinct from `route_not_found`, which
   * means the path itself is not published and no key or plan will fix it.
   */
  get isNoData() {
    return this.status === 404 && this.code === "not_found";
  }

  /** Build the error from a non-2xx response. Reads the body exactly once. */
  static async fromResponse(res, url) {
    const contentType = res.headers.get("content-type") ?? "";
    const retryAfterSeconds = parseRetryAfter(res.headers.get("retry-after"));
    const text = await res.text().catch(() => "");

    let problem = null;
    try {
      const parsed = JSON.parse(text);
      if (parsed && typeof parsed === "object") problem = parsed;
    } catch {
      problem = null;
    }

    if (!problem) {
      // Not JSON => this response was not produced by the API. The usual cause
      // is an edge/CDN refusal in front of it (a blocked User-Agent, a WAF rule,
      // or a captive network). Say so rather than inventing an API error code.
      return new VolstrataApiError(
        `HTTP ${res.status} from ${url} did not come from the API: the body is ` +
          `${contentType || "an unknown content type"}, not application/problem+json. ` +
          "A layer in front of the API answered — check the User-Agent header, the " +
          "URL, and any proxy between you and volstrata.com.",
        {
          status: res.status,
          url: String(url),
          contentType,
          retryAfterSeconds,
          isApiResponse: false,
          bodySample: text.slice(0, 200),
          code: "non_api_response",
          title: "Response did not come from the API",
        },
      );
    }

    const title = str(problem.title) ?? `HTTP ${res.status}`;
    const detail = str(problem.detail);
    return new VolstrataApiError(`HTTP ${res.status} ${title}${detail ? ` — ${detail}` : ""}`, {
      status: Number(problem.status) || res.status,
      code: str(problem.code),
      title,
      detail,
      instance: str(problem.instance),
      requestId: str(problem.request_id),
      requiredPlan: str(problem.required_plan),
      requiredPlanName: str(problem.required_plan_name),
      currentPlan: str(problem.current_plan),
      retryAfterSeconds,
      url: String(url),
      contentType,
      isApiResponse: true,
    });
  }

  /** Multi-line, human-readable rendering used by the examples. */
  describe(indent = "  ") {
    const lines = [`${indent}HTTP ${this.status} ${this.title ?? ""}`.trimEnd()];
    if (this.code) lines.push(`${indent}code       ${this.code}`);
    if (this.detail) lines.push(`${indent}detail     ${this.detail}`);
    if (this.requiredPlanName) {
      const current = this.currentPlan ? ` (you are on ${this.currentPlan})` : "";
      lines.push(`${indent}plan       requires ${this.requiredPlanName}${current}`);
    }
    if (this.retryAfterSeconds !== null) {
      lines.push(`${indent}retry-after ${this.retryAfterSeconds}s`);
    }
    if (this.requestId) lines.push(`${indent}request_id ${this.requestId}`);
    if (!this.isApiResponse && this.bodySample) {
      lines.push(`${indent}body       ${JSON.stringify(this.bodySample)}`);
    }
    return lines.join("\n");
  }
}

function str(value) {
  return typeof value === "string" && value.length > 0 ? value : null;
}

/** `Retry-After` is either delta-seconds or an HTTP date. Handle both. */
function parseRetryAfter(value) {
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return Math.max(0, Math.round(seconds));
  const when = Date.parse(value);
  if (Number.isNaN(when)) return null;
  return Math.max(0, Math.round((when - Date.now()) / 1000));
}

// ---------------------------------------------------------------------------
// Requests
// ---------------------------------------------------------------------------

/** Build an absolute URL, dropping params whose value is undefined or null. */
export function buildUrl(path, params = {}) {
  const url = new URL(path.startsWith("/") ? path : `/${path}`, BASE);
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    url.searchParams.set(key, String(value));
  }
  return url;
}

/**
 * One GET. Returns `{ res, data }` so callers can read response headers as well
 * as the body.
 *
 * The order here is the whole point: check `res.ok` / `res.status` FIRST, then
 * parse. Never branch on `data.ok` or on the presence of a field — a refusal has
 * a completely different body shape, and a body that is not JSON at all means
 * the response never reached the API.
 */
export async function apiFetch(path, params = {}, options = {}) {
  const url = buildUrl(path, params);
  const res = await fetch(url, {
    method: options.method ?? "GET",
    headers: headers(options.headers),
    body: options.body,
    signal: AbortSignal.timeout(options.timeoutMs ?? TIMEOUT_MS),
  });

  if (!res.ok) throw await VolstrataApiError.fromResponse(res, url);

  const text = await res.text();
  try {
    return { res, data: JSON.parse(text) };
  } catch {
    throw new VolstrataApiError(
      `HTTP ${res.status} from ${url} carried a body that is not JSON ` +
        `(${res.headers.get("content-type") ?? "no content-type"}), so it did not ` +
        "come from the API.",
      {
        status: res.status,
        url: String(url),
        contentType: res.headers.get("content-type"),
        isApiResponse: false,
        bodySample: text.slice(0, 200),
        code: "non_api_response",
        title: "Response did not come from the API",
      },
    );
  }
}

/** `apiFetch` when you only want the decoded body. */
export async function apiGet(path, params = {}) {
  const { data } = await apiFetch(path, params);
  return data;
}

/** The 7 POST capabilities take a JSON body; everything else is a GET. */
export async function apiPost(path, body = {}, params = {}) {
  const { data } = await apiFetch(path, params, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return data;
}

// ---------------------------------------------------------------------------
// Retry
// ---------------------------------------------------------------------------

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Run `fn`, retrying only 429 and 5xx — the two failures that can succeed on a
 * second attempt. A 401, 402 or 404 is a decision, not a hiccup: retrying it
 * just spends your rate-limit budget.
 *
 * At most 4 attempts. `Retry-After` wins when the server sends it; otherwise the
 * delay doubles from `baseDelayMs` with jitter so that many clients recovering
 * from the same incident do not all come back in lockstep.
 */
export async function withBackoff(fn, options = {}) {
  const attempts = options.attempts ?? 4;
  const baseDelayMs = options.baseDelayMs ?? 600;
  const maxDelayMs = options.maxDelayMs ?? 8_000;
  const maxWaitMs = options.maxWaitMs ?? 65_000;
  const onRetry = options.onRetry ?? defaultOnRetry;

  for (let attempt = 1; ; attempt += 1) {
    try {
      return await fn(attempt);
    } catch (error) {
      const retryable = error instanceof VolstrataApiError && error.isRetryable;
      if (!retryable || attempt >= attempts) throw error;

      const backoff = Math.min(maxDelayMs, baseDelayMs * 2 ** (attempt - 1));
      const jitter = Math.random() * backoff;
      const serverWait = error.retryAfterSeconds !== null ? error.retryAfterSeconds * 1000 : 0;
      const waitMs = Math.max(serverWait, backoff + jitter);

      // Do not sit for minutes inside an example. If the server asks for longer
      // than we are prepared to wait, surface the error instead.
      if (waitMs > maxWaitMs) throw error;

      onRetry(error, attempt, waitMs);
      await sleep(waitMs);
    }
  }
}

function defaultOnRetry(error, attempt, waitMs) {
  const reason = error.status === 429 ? "rate limited" : `server error ${error.status}`;
  console.log(`  ... ${reason}, retrying in ${(waitMs / 1000).toFixed(1)}s (attempt ${attempt + 1})`);
}

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

/**
 * Walk a cursor-paginated capability.
 *
 * One field is uniform across the surface: `next_cursor`, which is null on the
 * last page and opaque everywhere else — never parse it, decode it or build one
 * yourself. Row counters (`limit`, `total`, `count`) are per-operation: some
 * paged capabilities report one, some the other, some neither, so read them
 * defensively and never terminate a loop on them.
 *
 * Yields `{page, data, nextCursor}`. When the final yielded page still has a
 * `nextCursor`, the loop stopped at `maxPages`, not at the end of the data.
 *
 * `maxPages` is not optional politeness: an unbounded cursor loop against a live
 * API is how you burn a rate-limit budget in one run.
 */
export async function* paginate(path, params = {}, options = {}) {
  const maxPages = options.maxPages ?? 20;
  const pauseMs = options.pauseMs ?? 250;
  let cursor;

  for (let page = 1; page <= maxPages; page += 1) {
    const query = cursor ? { ...params, cursor } : { ...params };
    const { data } = await withBackoff(() => apiFetch(path, query));

    const nextCursor = typeof data?.next_cursor === "string" && data.next_cursor.length > 0
      ? data.next_cursor
      : null;

    yield { page, data, nextCursor };

    // End of data, or a server that repeated itself — either way, stop.
    if (nextCursor === null || nextCursor === cursor) return;
    cursor = nextCursor;
    if (pauseMs) await sleep(pauseMs);
  }
}

// ---------------------------------------------------------------------------
// Rate limits
// ---------------------------------------------------------------------------

/**
 * Read the rate-limit headers off any response — success or failure, every
 * response carries them.
 *
 * Modern form:  ratelimit: limit=60, remaining=59, reset=60
 * Legacy form:  x-ratelimit-limit / -remaining / -reset
 *
 * The budget is per OWNER, not per key: minting a second key does not raise the
 * ceiling. See https://volstrata.com/docs/api-rate-limits.
 */
export function rateLimitFrom(res) {
  const out = { limit: null, remaining: null, reset: null, policy: null, raw: null };
  if (!res || !res.headers) return out;

  out.policy = res.headers.get("ratelimit-policy");
  out.raw = res.headers.get("ratelimit");

  if (out.raw) {
    for (const part of out.raw.split(",")) {
      const [name, value] = part.split("=").map((piece) => piece?.trim());
      if (name === "limit" || name === "remaining" || name === "reset") {
        const parsed = Number(value);
        if (Number.isFinite(parsed)) out[name] = parsed;
      }
    }
  }

  const legacy = {
    limit: res.headers.get("x-ratelimit-limit"),
    remaining: res.headers.get("x-ratelimit-remaining"),
    reset: res.headers.get("x-ratelimit-reset"),
  };
  for (const key of ["limit", "remaining", "reset"]) {
    if (out[key] === null && legacy[key] !== null) {
      const parsed = Number(legacy[key]);
      if (Number.isFinite(parsed)) out[key] = parsed;
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Printing
// ---------------------------------------------------------------------------

/** `=== Title ===` style section header. */
export function heading(text) {
  console.log(`\n${text}\n${"-".repeat(text.length)}`);
}

/** One aligned `label   value` line. Objects and arrays are summarised. */
export function show(label, value, indent = "  ") {
  const rendered = typeof value === "string" ? value : summarize(value, { depth: 1 });
  console.log(`${indent}${String(label).padEnd(18)} ${rendered}`);
}

/**
 * Compact, bounded rendering of any JSON value.
 *
 * Payload shapes differ per capability and are not frozen, so the examples print
 * what actually came back instead of asserting a field exists. This doubles as
 * the safest way to explore a new capability: run it, read the keys.
 */
export function summarize(value, options = {}) {
  const depth = options.depth ?? 2;
  const maxKeys = options.maxKeys ?? 10;
  const maxItems = options.maxItems ?? 2;
  const maxString = options.maxString ?? 72;

  if (value === null) return "null";
  if (value === undefined) return "undefined";
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (typeof value === "string") {
    return value.length > maxString ? `${JSON.stringify(value.slice(0, maxString))}…` : JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return "[] (0)";
    if (depth <= 0) return `[…] (${value.length})`;
    const head = value
      .slice(0, maxItems)
      .map((item) => summarize(item, { ...options, depth: depth - 1 }))
      .join(", ");
    const more = value.length > maxItems ? ", …" : "";
    return `[${head}${more}] (${value.length})`;
  }
  if (typeof value === "object") {
    const entries = Object.entries(value);
    if (entries.length === 0) return "{}";
    if (depth <= 0) return `{…} (${entries.length} keys)`;
    const head = entries
      .slice(0, maxKeys)
      .map(([key, item]) => `${key}: ${summarize(item, { ...options, depth: depth - 1 })}`)
      .join(", ");
    const more = entries.length > maxKeys ? ", …" : "";
    return `{${head}${more}}`;
  }
  return String(value);
}

/** The keys of an object, sorted, comma-joined — handy for exploring a payload. */
export function keysOf(value, limit = 24) {
  if (!value || typeof value !== "object") return "(not an object)";
  const keys = Object.keys(value).sort();
  const head = keys.slice(0, limit).join(", ");
  return keys.length > limit ? `${head}, … (${keys.length} keys)` : head;
}

/** Print the rate-limit budget attached to a response. */
export function showRateLimit(res, indent = "  ") {
  const rl = rateLimitFrom(res);
  const parts = [];
  if (rl.limit !== null) parts.push(`limit=${rl.limit}`);
  if (rl.remaining !== null) parts.push(`remaining=${rl.remaining}`);
  if (rl.reset !== null) parts.push(`reset=${rl.reset}s`);
  console.log(`${indent}${"rate limit".padEnd(18)} ${parts.length ? parts.join("  ") : "(no headers)"}`);
  if (rl.policy) console.log(`${indent}${"policy".padEnd(18)} ${rl.policy}`);
}

// ---------------------------------------------------------------------------
// Example scaffolding
// ---------------------------------------------------------------------------

/**
 * Gap between calls in the multi-capability examples, milliseconds.
 *
 * Raise it if you want to be gentler with your rate-limit budget — the longer
 * domain files make seven to nine sequential requests. Nothing here runs
 * concurrently on purpose: parallel calls against a per-owner budget only make
 * you wait sooner.
 */
export const PACE_MS = 400;

/**
 * Run one capability, print whatever it returned, and turn any failure into a
 * printed line instead of a stack trace. Returns a small record the caller
 * tallies at the end.
 *
 * This is the shape every `rest/*.mjs` file uses: a refused row is a normal,
 * expected outcome (that is what a plan floor is), so it must not stop the run.
 */
export async function callCapability(name, fn, options = {}) {
  console.log(`\n• ${name}${options.note ? `  — ${options.note}` : ""}`);
  try {
    const value = await withBackoff(() => fn());
    return { name, ok: true, value };
  } catch (error) {
    if (error instanceof VolstrataApiError) {
      console.log(error.describe("    "));
      return {
        name,
        ok: false,
        error,
        refused: error.isPlanRefusal || error.isAuthRequired,
        noData: error.isNoData,
      };
    }
    console.log(`    request failed: ${error?.message ?? error}`);
    return { name, ok: false, error };
  } finally {
    if (PACE_MS > 0) await sleep(PACE_MS);
  }
}

/**
 * One-line tally printed at the bottom of each domain example.
 *
 * Three of the four outcomes are normal answers, not errors: data came back, the
 * caller is below the floor, or the capability had nothing to return for this
 * symbol at this moment. Only the fourth is a real failure.
 */
export function report(results) {
  const ok = results.filter((r) => r.ok).length;
  const refused = results.filter((r) => !r.ok && r.refused).length;
  const noData = results.filter((r) => !r.ok && !r.refused && r.noData).length;
  const failed = results.length - ok - refused - noData;
  const bits = [`${ok} returned data`];
  if (refused) bits.push(`${refused} refused (auth or plan floor)`);
  if (noData) bits.push(`${noData} had nothing to return right now`);
  if (failed) bits.push(`${failed} failed`);
  console.log(`\n${results.length} capabilities called — ${bits.join(", ")}.`);
  if (refused && !hasApiKey) {
    console.log("Set VOLSTRATA_API_KEY to run the gated rows: https://volstrata.com/api-keys");
  }
}

/** Banner every example opens with, so a reader knows which mode they are in. */
export function banner(title) {
  heading(title);
  show("base url", BASE);
  show("api key", hasApiKey ? "detected in VOLSTRATA_API_KEY" : "none — running anonymously");
}

/**
 * Wrap a `main()`. Unexpected failures (a DNS error, a bug in the example)
 * exit non-zero; everything the examples expect is handled inline before it
 * reaches here.
 */
export async function runMain(main) {
  try {
    await main();
  } catch (error) {
    if (error instanceof VolstrataApiError) {
      console.error("\nUnhandled API error:");
      console.error(error.describe("  "));
    } else {
      console.error(`\nUnexpected failure: ${error?.stack ?? error}`);
    }
    process.exitCode = 1;
  }
}
