#!/usr/bin/env python3
"""Fail if ``docs/reference/`` no longer matches a fresh regeneration.

This is the CI gate behind the repo's one rule about generated files: nothing
here hand-types an endpoint name, an MCP tool name, a parameter or a plan floor,
so if the committed reference and a fresh run of ``scripts/sync_catalog.py``
disagree, the committed copy is stale (or was edited by hand) and must be
regenerated.

The script regenerates into a temporary directory and byte-compares the four
generated artifacts against the committed copies:

  * ``docs/reference/openapi.json``       compared by size, version and
                                          fingerprint rather than by printing a
                                          half-megabyte diff
  * ``docs/reference/REST_ENDPOINTS.md``  unified diff, truncated
  * ``docs/reference/mcp-tools.json``     unified diff, truncated
  * ``docs/reference/MCP_TOOLS.md``       unified diff, truncated

It reads public endpoints only. It needs no API key, writes nothing outside a
temporary directory, and reports an unreachable host as a sentence rather than
a traceback.

Usage::

    python scripts/check_drift.py --check     # the CI invocation
    python scripts/check_drift.py             # identical; --check is accepted
                                              # for symmetry with sync_catalog.py

Exit codes::

    0   the committed reference matches a fresh regeneration
    1   drift - regenerate with `python scripts/sync_catalog.py` and commit
    2   the check could not run (host unreachable, bad spec, bad arguments)

Standard library only. See ``scripts/README.md``.

Copyright 2026 Volstrata.com - https://volstrata.com
"""

from __future__ import annotations

import argparse
import difflib
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

try:
    import sync_catalog
except ImportError as exc:  # pragma: no cover - only if the file is missing
    print(
        "error: could not import sync_catalog.py from {0} ({1})".format(HERE, exc),
        file=sys.stderr,
    )
    sys.exit(2)

#: How many diff lines to print before truncating. A full re-render of a 56-domain
#: table is thousands of lines; the first screenful is what tells you what broke.
MAX_DIFF_LINES = 60


def read_text(path):
    """Read a file without letting the platform rewrite its line endings."""
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def describe_openapi(fresh_path, committed_path):
    """Compare the spec by its identity, not by dumping half a megabyte of JSON."""
    lines = []

    def facts(path):
        raw = path.read_bytes()
        info = {}
        try:
            info = json.loads(raw.decode("utf-8")).get("info", {})
        except (UnicodeDecodeError, ValueError):
            pass
        return {
            "bytes": len(raw),
            "version": info.get("version", "(unreadable)"),
            "fingerprint": info.get("x-catalog-fingerprint", "(unreadable)"),
            "crlf": b"\r\n" in raw,
        }

    fresh = facts(fresh_path)
    if not committed_path.is_file():
        lines.append("  committed copy is missing entirely")
        lines.append(
            "  live: {0} bytes, version {1}, {2}".format(
                fresh["bytes"], fresh["version"], fresh["fingerprint"]
            )
        )
        return lines

    committed = facts(committed_path)
    lines.append("  {0:<14} {1:<70} {2}".format("", "committed", "live"))
    for label, key in (
        ("bytes", "bytes"),
        ("info.version", "version"),
        ("fingerprint", "fingerprint"),
    ):
        marker = "!" if committed[key] != fresh[key] else " "
        lines.append(
            "{0} {1:<14} {2:<70} {3}".format(
                marker, label, str(committed[key]), str(fresh[key])
            )
        )
    if committed["crlf"] != fresh["crlf"]:
        lines.append(
            "  line endings differ (committed CRLF={0}, live CRLF={1}). The spec is "
            "copied byte-for-byte, so it must not be normalised on checkout - see "
            "docs/reference/README.md.".format(committed["crlf"], fresh["crlf"])
        )
    return lines


def describe_text(fresh_path, committed_path):
    """A truncated unified diff of a generated text file."""
    if not committed_path.is_file():
        return ["  committed copy is missing entirely"]
    diff = list(
        difflib.unified_diff(
            read_text(committed_path).splitlines(),
            read_text(fresh_path).splitlines(),
            fromfile="committed/" + committed_path.name,
            tofile="regenerated/" + fresh_path.name,
            lineterm="",
            n=2,
        )
    )
    if not diff:
        # Byte-different but line-identical: only the line endings can differ.
        return [
            "  contents match line-for-line but the bytes differ - this is a line-ending "
            "difference. Generated text files are written with LF."
        ]
    shown = diff[:MAX_DIFF_LINES]
    lines = ["  " + line for line in shown]
    if len(diff) > MAX_DIFF_LINES:
        lines.append(
            "  ... {0} more diff lines suppressed".format(len(diff) - MAX_DIFF_LINES)
        )
    return lines


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Verify docs/reference/* still matches a fresh regeneration from the "
            "public VolStrata API. Needs no API key."
        )
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="accepted for symmetry with sync_catalog.py; this script always checks.",
    )
    parser.add_argument(
        "--base",
        default=sync_catalog.DEFAULT_BASE,
        help="host to regenerate from (default: %(default)s).",
    )
    parser.add_argument(
        "--source",
        default="live",
        help="'live' (default) or 'local:<path>' for the OpenAPI document.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    base = args.base.rstrip("/")
    if not base.startswith("https://") and not base.startswith("http://"):
        print("error: --base must be an http(s) URL", file=sys.stderr)
        return 2

    reference_dir = sync_catalog.REFERENCE_DIR
    if not reference_dir.is_dir():
        print(
            "error: {0} does not exist. Run `{1}` first.".format(
                reference_dir.as_posix(), sync_catalog.GENERATING_COMMAND
            ),
            file=sys.stderr,
        )
        return 2

    print("regenerating docs/reference from {0} ...".format(base))
    try:
        with tempfile.TemporaryDirectory(prefix="volstrata-drift-") as tmp:
            sync_catalog.generate(base, args.source, tmp, quiet=True)
            differences = sync_catalog.compare(tmp, reference_dir)
            if not differences:
                print(
                    "clean: all {0} generated files match.".format(
                        len(sync_catalog.GENERATED_FILES)
                    )
                )
                return 0

            print("", file=sys.stderr)
            print(
                "DRIFT in {0} of {1} generated files: {2}".format(
                    len(differences),
                    len(sync_catalog.GENERATED_FILES),
                    ", ".join(differences),
                ),
                file=sys.stderr,
            )

            # Detail for the first difference only; the rest are listed above.
            first = differences[0]
            fresh_path = pathlib.Path(tmp) / first
            committed_path = reference_dir / first
            print("", file=sys.stderr)
            print("--- {0}".format(first), file=sys.stderr)
            if first == "openapi.json":
                detail = describe_openapi(fresh_path, committed_path)
            else:
                detail = describe_text(fresh_path, committed_path)
            for line in detail:
                print(line, file=sys.stderr)
            print("", file=sys.stderr)
            print(
                "Fix: run `{0}` and commit docs/reference/. Never hand-edit those "
                "files.".format(sync_catalog.GENERATING_COMMAND),
                file=sys.stderr,
            )
            return 1
    except sync_catalog.SyncError as exc:
        print("error: {0}".format(exc), file=sys.stderr)
        print(
            "The drift check could not run, so nothing was verified. This is not a "
            "drift failure.",
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:  # pragma: no cover
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
