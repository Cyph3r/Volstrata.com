# Freshness and delivery — how old is this, and which lane am I on

Two small blocks ride along inside successful responses and answer two different questions:
`freshness` says **how old the data in this body is**, and `delivery` says **whether this
body came from the realtime lane or a delayed one, and why**.
API home: <https://volstrata.com>

Both are *additive*: they appear alongside an operation's own payload without changing it,
and not every operation carries them. Read them with `.get()` / optional chaining and render
what is there.

This page describes the **fields** — their names, types and how to display them. What the
numbers in the payload around them mean is defined in the public glossary on the site; how
any of it is produced is not part of the API contract and is not described here.

---

## `freshness`

```jsonc
// Illustrative. Values are synthetic.
{
  "ok": true,
  "freshness": {
    "as_of": 1780000000000,
    "age_seconds": 12,
    "live": true,
    "stale": false,
    "stale_after_seconds": 300
  },
  "…": "…payload…"
}
```

| Field | Type | Meaning |
|---|---|---|
| `as_of` | integer \| null | The data's own timestamp, in **epoch milliseconds**. `null` when the timestamp is not known |
| `age_seconds` | integer \| null | How old the data was when the server answered, floored at 0. `null` when `as_of` is unknown |
| `live` | boolean | The data has a known timestamp *and* its age is within the threshold for this feed |
| `stale` | boolean | The mirror of `live` — `live == not stale`, always |
| `stale_after_seconds` | integer | The age threshold applied to **this** body |

Three properties worth internalising:

**An unknown timestamp is honestly stale.** When the server cannot establish `as_of`, it
reports `as_of: null`, `age_seconds: null`, `stale: true`, `live: false`. It does not
substitute the current time and call the result fresh. So `stale: true` covers two distinct
situations — *known and too old*, and *age unknown* — and you can tell them apart by whether
`as_of` is null. Neither is a good moment to present a number as current.

**`stale_after_seconds` is a value to read, not a constant to hard-code.** Different feeds
carry different thresholds, and a threshold can change without your code changing. Compare
against the number in the response you are holding.

**Prefer `age_seconds` to arithmetic of your own.** It is the server's view of the age.
Computing `now - as_of` on the client folds in your machine's clock skew, which on a laptop
that has been asleep can be minutes.

### Rendering it

The whole point of the block is that one renderer works everywhere:

```python
from datetime import datetime, timezone


def render_freshness(body):
    """-> a short human string like 'as of 14:32:10 UTC · 12s ago', or a stale notice."""
    f = body.get("freshness")
    if not f:
        return ""                                  # additive: the block may be absent

    as_of_ms = f.get("as_of")
    age = f.get("age_seconds")

    if as_of_ms is None:
        return "timestamp unknown"                 # do not invent one

    # as_of is epoch MILLISECONDS. Passing it to a seconds-based constructor
    # produces a date tens of thousands of years from now — a classic silent bug.
    stamp = datetime.fromtimestamp(as_of_ms / 1000, tz=timezone.utc)
    label = f"as of {stamp:%H:%M:%S} UTC"

    if age is not None:
        label += f" · {age}s ago"
    if f.get("stale"):
        label += " · stale"
    return label
```

```javascript
export function renderFreshness(body) {
  const f = body?.freshness;
  if (!f) return "";

  if (f.as_of == null) return "timestamp unknown";

  const stamp = new Date(f.as_of); // epoch ms — Date wants ms, so no conversion here
  let label = `as of ${stamp.toISOString().slice(11, 19)} UTC`;
  if (f.age_seconds != null) label += ` · ${f.age_seconds}s ago`;
  if (f.stale) label += " · stale";
  return label;
}
```

Guidance for a UI: show the timestamp always, show the age when you have it, and mark the
stale state visibly rather than quietly. A value that is stale and looks live is worse than
no value at all — the reader has no way to know they are looking at the past.

The `freshness` block may carry additional descriptive fields beyond the five above. Ignore
keys you do not recognise rather than failing on them; the block is designed to grow.

---

## `delivery`

```jsonc
// Illustrative. Values are synthetic.
{
  "ok": true,
  "delivery": {
    "mode": "delayed",
    "delay_seconds": 600,
    "reason": "plan_tier",
    "upgrade_tier": "pro"
  },
  "…": "…payload…"
}
```

| Field | Type | Meaning |
|---|---|---|
| `mode` | `"live"` \| `"delayed"` | Whether this body came from the realtime lane or a delayed one |
| `delay_seconds` | integer \| null | The size of the delay. **`null` means a delay of unknown magnitude — not zero** |
| `reason` | `"plan_tier"` \| `"source_delay"` \| null | Why the body is delayed. `null` when `mode` is `"live"` |
| `upgrade_tier` | string \| null | A plan **slug**, or `null` when nothing would clear the delay |

### `delay_seconds: null` is not `0`

This is the one field on this page that will bite you if you skim it.

- `0` is a **positive assertion**: there is no delay.
- `null` is an **absence of knowledge**: this body is delayed, and the server is not claiming
  to know by how much.

They are not interchangeable, and the idiom most people reach for first collapses them:

```python
delay = body["delivery"].get("delay_seconds") or 0   # WRONG: null becomes 0
```

`or 0` turns "delayed by an unknown amount" into "not delayed at all", and the interface you
build on top of it will confidently label a delayed number as realtime. Branch on `None`
explicitly:

```python
delivery = body.get("delivery") or {}
mode = delivery.get("mode")
delay = delivery.get("delay_seconds")

if mode == "live":
    label = "live"
elif delay is None:
    label = "delayed"                 # magnitude unknown — say exactly that
else:
    label = f"delayed {delay}s"
```

```javascript
const d = body?.delivery ?? {};
let label;
if (d.mode === "live") label = "live";
else if (d.delay_seconds == null) label = "delayed";   // == null catches null and undefined
else label = `delayed ${d.delay_seconds}s`;
```

### The two reasons behave differently

| `reason` | What it means | Can the caller fix it? |
|---|---|---|
| `plan_tier` | The delay comes from the calling credential's entitlement | **Yes** — a higher plan clears it |
| `source_delay` | The data arrives delayed before the API ever sees it | **No** — no plan changes it |

That difference should reach the person reading your screen, because it decides whether there
is anything for them to do:

```python
if delivery.get("reason") == "plan_tier":
    note = "Delayed on your current plan."
elif delivery.get("reason") == "source_delay":
    note = "This data is delayed at the source."
else:
    note = ""
```

Do not put an upgrade prompt behind `source_delay`. Nothing upstream of the delay is on sale,
and offering an upgrade that cannot fix the problem is the kind of detail readers remember.

`upgrade_tier` is an internal **slug** (`edge`, `pro`, …), not a customer-facing plan name —
the same slug-versus-name distinction as `x-plan-tier` / `x-plan-tier-name` in
[REST_API.md](./REST_API.md) and `required_plan` / `required_plan_name` in
[ERRORS.md](./ERRORS.md). Use it to decide *whether* to show an upgrade affordance; do not
print it. Where you need a plan name in front of a person, take it from a field that gives
you the name.

---

## The two blocks answer different questions

They are easy to conflate and should not be:

> A body can be perfectly **fresh** for its lane and still be **delayed** — the delayed lane
> is being served promptly. Freshness measures the age of what you were handed. Delivery
> tells you which lane handed it to you.

So `freshness.live: true` and `delivery.mode: "delayed"` is a coherent, common pair, not a
contradiction. Render both, and let them say different things:

```
SPX  as of 14:32:10 UTC · 12s ago        [delayed 600s — your plan]
```

A reader who sees only the first half thinks they are looking at the market right now.

---

## Using freshness to avoid a request

`age_seconds` and `stale_after_seconds` together tell you roughly how long the body you are
holding remains within its threshold. If you fetched something eight seconds ago and its
threshold is measured in minutes, fetching it again buys you nothing and costs a request out
of a per-minute budget you share with everything else you are running
([RATE_LIMITS.md](./RATE_LIMITS.md)).

```python
def is_worth_refetching(body):
    f = body.get("freshness") or {}
    age = f.get("age_seconds")
    threshold = f.get("stale_after_seconds")
    if age is None or threshold is None:
        return True                    # no basis to skip — go and ask
    return age >= threshold
```

Treat that as a hint rather than a schedule. It tells you when a body has passed its
threshold; it does not promise that a new one is waiting.

---

## Checklist for a client

- Read both blocks with `.get()` / `?.` — they are additive and may be absent.
- Never render a timestamp when `as_of` is `null`. Say the timestamp is unknown.
- Treat `stale: true` as a display state, not an error. The payload is still there.
- Never coerce `delay_seconds: null` to `0`.
- Branch on `reason` before you offer an upgrade.
- Ignore fields you do not recognise; both blocks are designed to be extended.

---

## Where to go next

- The envelopes these blocks ride in: [REST_API.md](./REST_API.md)
- Budgeting your requests: [RATE_LIMITS.md](./RATE_LIMITS.md)
- What a refusal looks like instead: [ERRORS.md](./ERRORS.md)
- Every operation and its plan floor:
  [`reference/REST_ENDPOINTS.md`](./reference/REST_ENDPOINTS.md)

---

## Related

- [API overview](https://volstrata.com/docs/api-overview) — how the API is organised, including the response contracts shared across it.

---

Copyright 2026 Volstrata.com - https://volstrata.com
