"""Copyright 2026 Volstrata.com

The `accuracy`, `gammapin`, `dealergamma`, `stats` and `status` domains: the
self-scoring half of the surface.
Docs: https://volstrata.com/docs/api-catalog
      https://volstrata.com/docs/api-rate-limits

    python rest/accuracy_and_stats.py

Nine capabilities:

    accuracy.scoreboard          GET /api/v1/accuracy/scoreboard
    accuracy.tape                GET /api/v1/accuracy/tape
    accuracy.pin_contest         GET /api/v1/accuracy/pin_contest
    accuracy.pin_leaderboard     GET /api/v1/accuracy/pin_leaderboard
    gammapin.today               GET /api/v1/gammapin/today
    dealergamma.history          GET /api/v1/dealergamma/history
    dealergamma.tickers          GET /api/v1/dealergamma/tickers
    stats.greeks.wall_migration  GET /api/v1/stats/greeks/wall_migration
    status.overview              GET /api/v1/status/overview

One shared shape runs through most of them, and it is the reason this file is
worth reading. Wherever a number is scored, the response carries a `claim`:

    {"label": "...", "measured": true, "n": <sample size>, "hits": <n>,
     "rate": <fraction>, "min_n": <floor>, "sufficient": true,
     "state": "reliable" | "no_sample" | ...,
     "baseline": <fraction>, "baseline_kind": "...", "baseline_n": <n>,
     "baseline_note": "...", "beats_baseline": true,
     "wilson_lo": <fraction>, "wilson_hi": <fraction>}

Read it as a unit. `rate` on its own is not a result: `n`, `sufficient` and the
interval bounds are what say whether it means anything, and `measured: false`
or `state: "no_sample"` means there is nothing to render yet. Show the state,
do not compute around it.

This file makes nine sequential requests. An anonymous caller has a modest
per-minute budget, so you may see one pause while the retry logic honours a
Retry-After header -- that is the backoff in volstrata_helpers working, not a
failure.
"""

import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from volstrata_helpers import (  # noqa: E402  (import after the path fix, on purpose)
    attempt,
    describe_freshness,
    get,
    heading,
    key_banner,
    row,
    run_examples,
)

TICKER = "SPX"


def _claim(prefix: str, claim) -> None:
    """Print a claim block the same way everywhere it appears."""
    if not isinstance(claim, dict):
        return
    if not claim.get("measured"):
        print("  {0}: not measured yet (state={1}, n={2}, min_n={3})".format(
            prefix, claim.get("state"), claim.get("n"), claim.get("min_n")))
        return
    print("  {0}: rate={1} n={2} sufficient={3} state={4}".format(
        prefix, claim.get("rate"), claim.get("n"),
        claim.get("sufficient"), claim.get("state")))
    if claim.get("baseline") is not None:
        print("      vs baseline {0} ({1}) -> beats_baseline={2}".format(
            claim.get("baseline"), claim.get("baseline_kind"),
            claim.get("beats_baseline")))
    if claim.get("wilson_lo") is not None:
        print("      interval [{0}, {1}]".format(
            claim.get("wilson_lo"), claim.get("wilson_hi")))


def scoreboard() -> None:
    """accuracy.scoreboard: one row per ticker/horizon/regime.

        {"ok": true, "generated_at": <unix>, "model_version": "...",
         "horizons": ["30m", ...],
         "board": [{"ticker": "...", "horizon": "30m", "regime": "...",
                    "regime_label": "...", "samples": <n>,
                    "directional_acc": <fraction>, "directional_n": <n>,
                    "level_hit_rate": <fraction>,
                    "coverage_68": <fraction>, "coverage_95": <fraction>,
                    "directional": {<claim>}}, ...],
         "overall": {...}, "model_changelog": [...]}

    `samples` and the `directional` claim block are the honest part of a row.
    Sort by them before you sort by accuracy: a high rate over a handful of
    samples is not a better row, it is a smaller one.
    """
    heading("accuracy.scoreboard")
    data = attempt("accuracy.scoreboard", get, "/accuracy/scoreboard")
    if data is None:
        return
    row("model_version", data.get("model_version"))
    row("horizons", ", ".join(data.get("horizons") or []))
    board = data.get("board") or []
    row("rows", len(board))
    for item in board[:4]:
        print("  {0:<6} {1:<5} {2:<8} samples={3:<6} directional_acc={4}".format(
            item.get("ticker", "?"), item.get("horizon", "?"),
            item.get("regime", "?"), str(item.get("samples")),
            item.get("directional_acc")))
    overall = data.get("overall") or {}
    _claim("overall.directional", overall.get("directional"))


def tape() -> None:
    """accuracy.tape scores individual signals rather than a model.

    Each row is {signal_key, label, description, fired_total, resolved,
    pending, wins, losses, timeouts, n_decided, hit_rate, claim, ...}.

    `fired_total` and `resolved` are different numbers: a signal that has fired
    a hundred times and resolved twice has a hit_rate over two events. `pending`
    is the gap. Show all three or none.
    """
    heading("accuracy.tape")
    data = attempt("accuracy.tape", get, "/accuracy/tape")
    if data is None:
        return
    row("armed", data.get("armed"))
    row("min_credible_n", data.get("min_credible_n"))
    _claim("headline", data.get("headline"))
    for item in (data.get("rows") or [])[:4]:
        print("  {0:<18} fired={1:<5} resolved={2:<4} pending={3:<4} hit_rate={4}".format(
            item.get("signal_key", "?"), str(item.get("fired_total")),
            str(item.get("resolved")), str(item.get("pending")),
            item.get("hit_rate")))


def pin_contest() -> None:
    """accuracy.pin_contest and accuracy.pin_leaderboard: a daily game, scored.

    The contest response carries a `state` block ({accepting, cutoff,
    entries_count, session_day, reference}) and a `disclaimer` written for
    display. `your_entry` and `your_stats` are null for an anonymous caller and
    populated for a credential that has played -- one response shape, two
    audiences.

    Print the `disclaimer` IN FULL if you surface any of this to a user. It is
    there so you do not have to write your own -- and a risk disclaimer cut off
    mid-sentence is worse than one you never showed, because it demonstrates
    that you knew it was there. Wrap it; never slice it.
    """
    heading("accuracy.pin_contest")
    data = attempt("accuracy.pin_contest", get, "/accuracy/pin_contest", ticker=TICKER)
    if data is not None:
        state = data.get("state") or {}
        row("session_day", state.get("session_day"))
        row("accepting", state.get("accepting"))
        row("entries_count", state.get("entries_count"))
        row("hit_band_pct", data.get("hit_band_pct"))
        row("your_entry", data.get("your_entry"))
        reference = state.get("reference") or {}
        if reference:
            row("reference keys", ", ".join(sorted(reference)))
        disclaimer = data.get("disclaimer")
        if disclaimer:
            # Wrapped for the terminal, never truncated. The whole string is the
            # disclaimer; the operative clauses are at the end of it.
            print("  disclaimer:")
            for line in textwrap.wrap(str(disclaimer), width=72):
                print("    {0}".format(line))

    heading("accuracy.pin_leaderboard")
    board = attempt("accuracy.pin_leaderboard", get, "/accuracy/pin_leaderboard",
                    ticker=TICKER)
    if board is not None:
        rows = board.get("leaderboard") or []
        row("tickers", ", ".join(board.get("tickers") or []))
        row("entries", len(rows))
        for item in rows[:5]:
            print("  {0}".format(item))


def pin_and_history() -> None:
    """gammapin.today (intraday series) and dealergamma.history (daily series).

    gammapin.today:
        {"ok": true, "day": "YYYY-MM-DD", "count": <n>,
         "current": {...}, "summary": {...},
         "series": [{"t": <unix>, "spot": <price>, "magnet": <price>,
                     "max_pain": <price>, "zero_gamma": <price>,
                     "net_gex_bn": <n>, "regime": "...",
                     "magnet_basis": "...", "zero_gamma_basis": "..."}, ...]}

    dealergamma.history:
        {"ok": true, "days": <n>, "count": <n>,
         "series": [{"day": "YYYY-MM-DD", "spot": <price>, "call_wall": <price>,
                     "put_wall": <price>, "zero_gamma": <price>,
                     "net_gex_bn": <n>, "regime": "...",
                     "is_quad_witch": false, "opex_type": null}, ...],
         "latest": {...}, "next_opex": {...}, "delivery": {...}}

    The `*_basis` fields say which definition produced the neighbouring value.
    Two rows in the same series can carry a different basis, so carry the basis
    with the number when you store it -- otherwise you are comparing two things
    that share a column name.

    dealergamma.tickers is the index of what has history at all: ask it before
    you request a symbol, rather than interpreting an empty series.
    """
    heading("gammapin.today")
    today = attempt("gammapin.today", get, "/gammapin/today", ticker=TICKER)
    if today is not None:
        row("day", today.get("day"))
        row("points", today.get("count"))
        current = today.get("current") or {}
        for field in ("spot", "magnet", "magnet_basis", "max_pain",
                      "zero_gamma", "zero_gamma_basis", "net_gex_bn", "pinned"):
            if field in current:
                row(field, current[field])

    heading("dealergamma.history")
    history = attempt("dealergamma.history", get, "/dealergamma/history",
                      ticker=TICKER, days=5)
    if history is not None:
        row("days requested", history.get("days_requested"))
        row("days returned", history.get("days"))
        row("delayed", history.get("delayed"))
        row("freshness", describe_freshness(history))
        for item in (history.get("series") or [])[:5]:
            print("  {0}  spot={1:<9} zero_gamma={2:<9} regime={3}".format(
                item.get("day"), str(item.get("spot")),
                str(item.get("zero_gamma")), item.get("regime")))
        opex = history.get("next_opex") or {}
        if opex:
            row("next_opex", "{0} ({1}, in {2} days)".format(
                opex.get("date"), opex.get("opex_type"), opex.get("days_to_expiry")))

    heading("dealergamma.tickers")
    index = attempt("dealergamma.tickers", get, "/dealergamma/tickers")
    if index is not None:
        rows = index.get("tickers") or []
        row("symbols with history", len(rows))
        for item in rows[:5]:
            print("  {0:<8} days={1:<5} last_day={2}".format(
                item.get("ticker", "?"), str(item.get("days")), item.get("last_day")))


def statistics_and_status() -> None:
    """A stats.greeks.* row, and the service's own status.

    The stats.* capabilities publish study results as data:

        {"ok": true, "capability": "stats.greeks.wall_migration",
         "label": "...", "kind": "character", "decision_instant": "...",
         "independent_sessions": <n>,
         "groups": [{"label": "...",
                     "buckets": [{"label": "...", "value": <n>, "unit": "..."}],
                     "claim": {<claim>}}, ...]}

    `decision_instant` is the field that makes a result usable: it says at what
    moment the measurement was taken. A number without that is not comparable to
    anything.

    status.overview is the operational view -- lanes, their state, and how long
    ago each was updated. Check it before you conclude a stale response is a bug
    in your code.
    """
    heading("stats.greeks.wall_migration")
    study = attempt("stats.greeks.wall_migration", get, "/stats/greeks/wall_migration")
    if study is not None:
        row("capability", study.get("capability"))
        row("label", (study.get("label") or "")[:80])
        row("kind", study.get("kind"))
        row("decision_instant", study.get("decision_instant"))
        row("independent_sessions", study.get("independent_sessions"))
        for group in (study.get("groups") or [])[:2]:
            print("  group: {0}".format(group.get("label")))
            _claim("    claim", group.get("claim"))
            for bucket in (group.get("buckets") or [])[:3]:
                print("      {0}: {1} {2}".format(
                    bucket.get("label"), bucket.get("value"), bucket.get("unit") or ""))

    heading("status.overview")
    status = attempt("status.overview", get, "/status/overview")
    if status is not None:
        row("status", "{0} -- {1}".format(status.get("status"), status.get("status_label")))
        row("incidents", len(status.get("incidents") or []))
        for lane in (status.get("lanes") or [])[:5]:
            print("  {0:<18} state={1:<8} updated {2}s ago".format(
                lane.get("name", "?"), str(lane.get("state")),
                lane.get("fresh_seconds_ago")))


def main() -> int:
    print("VolStrata: accuracy, statistics and status -- https://volstrata.com")
    key_banner()
    exit_code = run_examples((
        ("scoreboard", scoreboard),
        ("tape", tape),
        ("pin contest", pin_contest),
        ("pin and history", pin_and_history),
        ("statistics and status", statistics_and_status),
    ))
    heading("Next")
    print("  rest/gex_levels.py    the levels these results are about")
    print("  Rate limits: https://volstrata.com/docs/api-rate-limits")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
