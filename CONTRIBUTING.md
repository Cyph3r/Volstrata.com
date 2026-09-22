# Contributing

Thanks for taking the time. This repository holds runnable examples for the VolStrata
public API at https://volstrata.com — nothing else. Pull requests that add a language,
fix a broken example or improve a guide are welcome.

## Ground rules, shortest form

1. `docs/reference/` is generated. Never hand-edit anything in it.
2. Never commit a credential, and never paste one into an issue or a pull request.
3. Every example runs with no API key set, start to finish. A capability the caller cannot
   reach prints its refusal and the run continues.
4. Every file carries `Copyright 2026 Volstrata.com` — footer line for Markdown, header
   comment for everything else. A file you wrote yourself may carry your own copyright
   line alongside it; see [Inbound contributions](#inbound-contributions).

## docs/reference/ is generated — do not hand-edit

Everything under `docs/reference/` is produced by `scripts/sync_catalog.py`, which reads
the public OpenAPI document at https://api.volstrata.com/api/openapi.json and the public
capability list at `GET https://api.volstrata.com/api/v1/meta/capabilities`. No endpoint name,
path, parameter or plan floor in those four files is typed by hand.

**The guides and the examples are different.** They do quote capability names, paths, plan
floors and counts in prose and in comments, because a worked example that cannot name the
thing it is calling is not a worked example. Nothing checks those by machine. If you change
one, re-check it against [`docs/reference/REST_ENDPOINTS.md`](docs/reference/REST_ENDPOINTS.md)
and say in the pull request that you did.

To refresh the reference:

```bash
python scripts/sync_catalog.py
```

CI runs `scripts/check_drift.py`, which regenerates into a temporary directory and diffs
against what is committed. A hand-edit to a generated file fails that check on the next
pull request, including pull requests that had nothing to do with it. If a reference file
looks wrong, the fix belongs in the generator or upstream in the API — not in the file.

## Adding an example for a new language

Existing languages are curl, Python and JavaScript. To add another:

1. Create `examples/<language>/` with a `README.md` explaining how to run it.
2. Start with a quickstart that calls a Free capability that answers with no key, so a
   reader who has just cloned the repository gets real output before configuring anything.
   `gex.levels` is the one the other three languages use. Not every Free-floor capability
   qualifies: a few ask for any valid key and answer `401 auth_required` without one.
3. Work from [`docs/reference/REST_ENDPOINTS.md`](docs/reference/REST_ENDPOINTS.md).
   That table is the authoritative surface: capability name, method, path and plan floor.
   Pick a small number of representative capabilities rather than one file per endpoint.
4. Mirror the structure the other languages use — a quickstart, an auth-and-errors
   example, and a handful of domain examples — so a reader can move between languages
   without relearning the layout.
5. Keep the dependency footprint at zero or near zero. Python examples use `requests`;
   JavaScript uses the runtime's native `fetch`. There is no VolStrata SDK package to
   install, so do not add one as a dependency or import.

Every example must:

- Set an explicit `User-Agent` header. Some default agents are refused at the CDN edge
  before the request reaches the API, and the resulting plain-text 403 is not JSON.
- Read the API key from the `VOLSTRATA_API_KEY` environment variable, and the base URL
  from `VOLSTRATA_API_BASE`, defaulting to `https://api.volstrata.com`.
- Handle failure. Refusals are RFC 9457 `application/problem+json` — parse the body and
  print `title`, `status` and `detail` rather than dumping a stack trace.
- Show the unauthenticated path explicitly. If an example calls a gated capability, it
  must degrade with a clear message naming the required plan, never crash.
- Be bounded. The anonymous rate limit is 10 requests per minute and every example runs
  against the live production API. No unbounded loops, no polling, no concurrency, and
  honour `Retry-After` when it appears.

## Inbound contributions

By opening a pull request you certify that you wrote the contribution yourself, or that you
otherwise have the right to submit it, and you licence it to the project under the MIT
licence in [`LICENSE`](LICENSE) — the same terms this repository is distributed under.

Ground rule 4 asks every file to carry `Copyright 2026 Volstrata.com`, because most files
here are project-authored and the licence names the project as the copyright holder. **If
you wrote a file yourself, add your own copyright line to it.** Both lines can sit in the
same header:

```
Copyright 2026 Volstrata.com - https://volstrata.com
Copyright 2026 <your name or organisation>
```

Nothing here asks you to assign your copyright, and nothing here asks you to put someone
else's name on work you authored.

## No secrets

- No key, token, cookie or session value in any file, ever — including in a commented-out
  line, a test fixture, or a screenshot.
- Credentials appear only as environment-variable names read at runtime.
- Placeholders are obviously fake: `YOUR_API_KEY` or `gex_key_v1_XXXXXXXX`. Never a
  string that could be mistaken for a real key.
- `.env` is git-ignored, and so is any MCP client config you fill in: `mcp.json` and
  `.mcp.json` are ignored at every level in the tree. Confirm with
  `git check-ignore -v mcp.json examples/mcp/mcp.json` before you commit.
- Three MCP templates *are* committed — `examples/mcp/mcp.json.example`,
  `examples/mcp/claude_desktop_config.json` and `examples/mcp/vscode_mcp.json`. Every one
  of them carries `YOUR_API_KEY` and never a value. The latter two are tracked under their
  real filenames, so a key pasted into one in place would be staged like any other edit:
  copy a template to `mcp.json` — which is ignored — and put your key in the copy.
- Sample responses in documentation are hand-written with synthetic values. Do not paste
  a captured live response body: those carry request ids, cookies and edge headers.

A secret scan runs on every pull request. If it fires, the fix is to rotate the exposed
credential first and rewrite the branch second — see [`SECURITY.md`](SECURITY.md).

## Running the checks locally

```bash
python scripts/sync_catalog.py     # regenerate docs/reference/ from the public API
python scripts/check_drift.py      # fail if the committed reference is stale
```

Then run the example you changed, exactly as a reader would, from a clean shell with no
`VOLSTRATA_API_KEY` set — that is the path most readers take, and the one most likely to
be broken. If your change touches a gated capability, run it a second time with a key to
confirm both branches behave.

These are the same steps the `verify` workflow runs, plus the secret scan.

## Pull requests

Keep them focused: one language or one guide per pull request. Say in the description
which commands you ran and what output you saw. If you found a discrepancy between an
example and the live API, say which endpoint — that is useful even without a fix.

---

Copyright 2026 Volstrata.com - https://volstrata.com
