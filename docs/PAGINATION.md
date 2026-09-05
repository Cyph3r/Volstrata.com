# Pagination — one cursor model, everywhere

Operations that can return more rows than fit in one response share a single cursor
pagination model. Learn it once and it works on all of them.
API home: <https://volstrata.com>

**17 of the 180 published operations** declare a `cursor` parameter. Everything else answers
in one response. Which is which is recorded per-operation in
[`reference/REST_ENDPOINTS.md`](./reference/REST_ENDPOINTS.md) and in the OpenAPI document.

---

## The model

Two request parameters:

| Parameter | Meaning |
|---|---|
| `limit` | How many rows you want in this page |
| `cursor` | Where to resume. Omit it on the first request; on every later request, send back the `next_cursor` you were given |

The one envelope field the model depends on:

```jsonc
// Illustrative — the payload key holding the rows differs per operation.
{
  "ok": true,
  "next_cursor": "…opaque…",
  "…": "…rows…"
}
```

| Field | Meaning |
|---|---|
| `next_cursor` | Pass to the next request to get the following page. **`null` means this was the last page** — that is the whole termination condition, and the only field your loop actually needs |
| `ok` | The usual success flag |

**Counters are per-operation, not part of the shared contract.** An operation may also
report how big the page it applied was, and how many rows exist in total, but the field
names differ and some operations report neither — `meta.capabilities`, for instance,
answers with `count` and no `limit`. Read whichever counter the operation you are calling
actually returns, treat it as optional, and never terminate a loop on it.

The rows themselves live under the operation's own payload key alongside these fields, and
that key differs per operation too. Print one page before you write the loop: it shows you
the collection's name and which counters you actually have, in one request.

A first page, by hand:

```bash
curl -sS \
  -A "volstrata-examples/1.0" \
  "https://volstrata.com/api/v1/meta/capabilities?limit=50"
```

---

## The cursor is opaque

> A cursor is a token the server gives you and the server reads back. Its contents are not
> part of the contract.

Which means, concretely:

- **Do not parse it.** Not to extract an offset, an id, a timestamp, or a page number.
- **Do not construct one.** There is no arithmetic that produces "page 4"; the only way to
  reach page 4 is through pages 1, 2 and 3.
- **Do not edit one.** Pass the exact string you were given, URL-encoded when it goes into a
  query string. Your HTTP library does this for you if you pass parameters as a mapping
  rather than by concatenating a URL.
- **Do not store one for later.** Treat a cursor as valid for the walk in progress. If you
  need to resume tomorrow, start a fresh walk rather than reviving yesterday's token.

Anything a cursor's internals appear to tell you today is an implementation detail that can
change without notice, and code that reads it will break silently rather than loudly.

---

## Walk the pages — with a bound

The loop is "until `next_cursor` is null", and it always carries a page cap. Not because
`next_cursor` cannot be trusted to terminate, but because an unbounded network loop is how a
rate-limit budget disappears while you are looking at something else
([RATE_LIMITS.md](./RATE_LIMITS.md)).

```python
def iter_pages(session, url, params=None, *, limit=100, max_pages=20, timeout=30):
    """Yield each page envelope until next_cursor is null, or max_pages is reached.

    Yields whole envelopes: the caller picks out the rows, because the payload key
    holding them differs per operation.
    """
    query = dict(params or {})
    query["limit"] = limit
    cursor = None

    for _ in range(max_pages):
        if cursor:
            query["cursor"] = cursor          # pass the token back verbatim

        resp = session.get(url, params=query, timeout=timeout)
        if resp.status_code != 200:           # status first, always
            resp.raise_for_status()

        page = resp.json()
        yield page

        cursor = page.get("next_cursor")
        if not cursor:                        # null -> that was the last page
            return

    raise RuntimeError(f"stopped after {max_pages} pages: raise the cap deliberately")
```

Using it:

```python
ROWS_KEY = "..."   # the payload key holding the rows, read off a printed page

rows, total = [], None
for page in iter_pages(session, f"{base}/api/v1/meta/capabilities", limit=100):
    rows.extend(page.get(ROWS_KEY, []))
    total = page.get("total", total)

print(len(rows), "rows collected of", total)
```

JavaScript, same shape:

```javascript
export async function* iterPages(url, { headers, limit = 100, maxPages = 20 } = {}) {
  let cursor = null;

  for (let i = 0; i < maxPages; i++) {
    const u = new URL(url);
    u.searchParams.set("limit", String(limit));
    if (cursor) u.searchParams.set("cursor", cursor);   // URL-encodes for you

    const res = await fetch(u, { headers });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const page = await res.json();
    yield page;

    cursor = page.next_cursor;
    if (!cursor) return;
  }
  throw new Error(`stopped after ${maxPages} pages: raise the cap deliberately`);
}
```

Note what the cap does when it trips: it **raises**, loudly, naming itself. A cap that
silently returns a partial result is worse than no cap at all — it hands you a truncated
dataset that looks complete.

---

## Practical notes

- **Choose a sane `limit`.** Larger pages mean fewer requests against your rate-limit budget.
  The envelope's `limit` tells you what the server actually applied, which may be smaller
  than you asked for.
- **A page can be empty and still not be last.** Terminate on `next_cursor`, never on an
  empty row list.
- **Do not fetch pages in parallel.** You cannot know page N+1's cursor before page N
  arrives, and concurrency does not raise the ceiling anyway.
- **Handle a 429 mid-walk** with the retry helper from [RATE_LIMITS.md](./RATE_LIMITS.md) and
  then resume with the same cursor. A retried page is the same page.
- **Cache the walk, not the cursor.** For slow-moving listings such as the capability
  catalog, keep the assembled rows for the run and re-walk on the next run.

---

## Related

- [Writing a client](https://volstrata.com/docs/api-sdks) — where a paging helper like the one above belongs in a small hand-rolled client wrapper.

---

Copyright 2026 Volstrata.com - https://volstrata.com
