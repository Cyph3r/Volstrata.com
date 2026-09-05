# scripts

Two scripts. One writes the generated reference, the other proves it is still correct.

Neither reads, needs or sends an API key: every source they use on
[volstrata.com](https://volstrata.com) is public and unauthenticated. Neither has any
third-party dependency — Python 3.9+ and the standard library, nothing else. See
[`requirements.txt`](requirements.txt).

| Script | What it does |
|---|---|
| [`sync_catalog.py`](sync_catalog.py) | Regenerates every file in [`../docs/reference/`](../docs/reference/) from the public API. |
| [`check_drift.py`](check_drift.py) | Regenerates into a temporary directory and fails if the committed copies differ. |

## The rule

**`docs/reference/` is generated. Never hand-edit anything in it.**

Nothing in those four files hand-types an endpoint name, an MCP tool name, a parameter or
a plan floor. Every one of those facts is read from a public endpoint at generation time,
and CI diffs the committed copy against a fresh regeneration. A hand-edit to a generated
file is therefore not a fix — it is a build failure waiting for the next pull request.
If a generated file looks wrong, the source it came from is wrong;
[open an issue](https://github.com/Cyph3r/Volstrata.com/issues).

**That guarantee stops at `docs/reference/`.** The guides in `docs/` and the files under
`examples/` quote capability names, paths, plan floors and counts by hand, and no check in
this repository verifies them. When you change one, re-check it against
[`../docs/reference/REST_ENDPOINTS.md`](../docs/reference/REST_ENDPOINTS.md) yourself.

## `sync_catalog.py`

```bash
python scripts/sync_catalog.py
```

Writes four files into `docs/reference/`:

| File | How it is produced |
|---|---|
| `openapi.json` | `GET https://volstrata.com/api/openapi.json`, saved byte-for-byte verbatim. |
| `REST_ENDPOINTS.md` | Rendered from that document: one table per domain tag, every operation with its method, path and plan floor. The floor is the only gate the specification publishes per operation, so it is the only one this table states — a Free floor is not a promise of anonymous access, and `GET /api/v1/meta/access` is the runtime answer. |
| `mcp-tools.json` | The MCP tool table, projected from `GET /api/v1/meta/capabilities` (paged to the end) with each tool marked reachable-anonymously or not, from an un-credentialed `tools/list` against `POST /api/v1/mcp`. |
| `MCP_TOOLS.md` | Rendered from `mcp-tools.json`. |

Options:

```
--base <url>            Host to fetch from. Default https://volstrata.com.
--source live           Fetch the OpenAPI document from --base (default).
--source local:<path>   Read the OpenAPI document from a file you already have.
                        The capability catalog and MCP tool list still come from --base.
--out <dir>             Write somewhere other than docs/reference/.
--check                 Regenerate into a temporary directory and exit non-zero
                        if the committed docs/reference/ differs.
```

There is no default local path: `--source local:` takes an explicit argument or nothing
happens. `--base` changes only where bytes are *read from*; it never changes what is
*written*. Public URLs printed into the generated files are taken from `servers[0].url`
inside the specification itself, so pointing the fetcher at a mirror cannot leak that
location into a committed file.

### Determinism

The committed files must be reproducible, or the drift gate fires on unrelated pull
requests and the scheduled job opens a noise pull request every week. So:

- No wall-clock timestamp, hostname, username, local path or run id is ever written into
  a generated file. The only version markers are `info.version` and
  `info["x-catalog-fingerprint"]`, both read from the specification.
- Every collection the generator builds is sorted — domains by name, operations by
  `operationId`, tools by kind then name, JSON object keys alphabetically. The one
  exception is a capability's `params` list, whose source order is meaningful and is
  preserved as received.
- Generated text is written with LF line endings on every platform.
- `openapi.json` is copied verbatim: no reformatting, no re-serialisation, no key
  reordering, and no header of ours. It is served with CRLF line endings, so it must not
  be normalised on checkout or the byte comparison fails — see
  [`../docs/reference/README.md`](../docs/reference/README.md).

### Live API etiquette

These scripts run against the production API under the anonymous per-minute ceiling. A
full run makes nine requests — one for the specification, seven to page the capability
catalog, one for `tools/list` — which is most of an anonymous caller's per-minute budget.
Running `sync_catalog.py` and `check_drift.py` back to back will therefore hit a `429`
partway through the second one; that is expected and handled, and it is why a run can
pause for the better part of a minute before finishing.

Requests are spaced, `Retry-After` is honoured on `429`, retries are capped, and the
pagination loop is bounded — it raises rather than looping further if the catalog does
not finish paging. Do not wrap either script in a polling loop.

## `check_drift.py`

```bash
python scripts/check_drift.py --check
```

Regenerates into a temporary directory and byte-compares the four generated artifacts
against what is committed. It writes nothing outside that temporary directory, so it is
safe to run anywhere, with no credentials and no write access to the working tree.

For a text file it prints a truncated unified diff of the first difference. For
`openapi.json` it prints a size, version and fingerprint comparison instead of a
half-megabyte diff, and calls out a line-ending mismatch explicitly. An unreachable host
is reported as a sentence, not a traceback, and is distinguished from actual drift.

Exit codes:

| Code | Meaning |
|---|---|
| `0` | The committed reference matches a fresh regeneration. |
| `1` | Drift. Run `python scripts/sync_catalog.py` and commit the result. |
| `2` | The check could not run — unreachable host, unreadable specification, bad arguments. Nothing was verified. |

## Related

- [`../docs/reference/`](../docs/reference/) — the generated files themselves
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — what to do before opening a pull request
- [The public API catalog](https://volstrata.com/docs/api-catalog)

---

Copyright 2026 Volstrata.com - https://volstrata.com
