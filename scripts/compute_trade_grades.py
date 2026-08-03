#!/usr/bin/env python3
"""Grade every trade in data/trades.json using DynastyProcess dynasty values
(data/dynasty_values.json, from fetch_dynasty_values.py): total value each
side had as of the trade date, versus the average of that value 1/2/3 years
later (whichever of those have elapsed). Writes data/trade_grades.json,
keyed by transaction_id.

Trades from before ~May 2020 have no grade -- DynastyProcess's value data
doesn't go back that far in a usable form (see fetch_dynasty_values.py).
Trades less than a year old have no "aged" value yet either.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load(name):
    return json.loads((DATA_DIR / name).read_text())


def side_value(side, snapshot, crosswalk):
    """Returns (value, complete) -- complete is False if any asset in this
    side couldn't be valued (missing crosswalk match or missing from this
    snapshot), so callers can tell a real $0 side from an unpriceable one.
    """
    total = 0.0
    complete = True
    for p in side["players"]:
        fp_id = crosswalk.get(p["player_id"])
        v = snapshot["player_values"].get(fp_id) if fp_id else None
        if v is None:
            complete = False
        else:
            total += v
    for pk in side["picks"]:
        v = snapshot["pick_values"].get(f"{pk['season']}-{pk['round']}")
        if v is None:
            complete = False
        else:
            total += v
    return round(total, 1), complete


def side_aged_value(side, horizon_snapshots, crosswalk):
    """Aged value of a side, averaged per-asset over only the horizon
    snapshots where that asset was actually priceable, then summed.

    A draft pick only exists as a "future pick" in DynastyProcess's data for
    the current draft class plus roughly the next two years out -- once its
    season's draft has happened, it drops out of values-picks.csv entirely
    rather than being priced low. Averaging a side's *total* across horizons
    (the old approach) treated that disappearance as the pick's value
    crashing to $0 at that checkpoint, which dragged down the whole side's
    aged average even though the other horizons priced it normally. The same
    thing can happen to a player who's dropped from the league/retired and
    no longer appears in a later snapshot. Averaging per-asset over just the
    horizons where it was actually found avoids phantom zeros from either
    case. An asset that's unpriceable at every horizon still marks the side
    incomplete, same as before.
    """
    complete = True
    total = 0.0
    for p in side["players"]:
        fp_id = crosswalk.get(p["player_id"])
        vals = [v for s in horizon_snapshots if fp_id and (v := s["player_values"].get(fp_id)) is not None]
        if vals:
            total += sum(vals) / len(vals)
        else:
            complete = False
    for pk in side["picks"]:
        key = f"{pk['season']}-{pk['round']}"
        vals = [v for s in horizon_snapshots if (v := s["pick_values"].get(key)) is not None]
        if vals:
            total += sum(vals) / len(vals)
        else:
            complete = False
    return round(total, 1), complete


def main():
    trades = load("trades.json")["trades"]
    dv = load("dynasty_values.json")
    snapshots = dv["snapshots"]
    crosswalk = dv["crosswalk"]

    grades = {}
    ungraded_no_data = 0
    ungraded_too_recent = 0
    for t in trades:
        info = dv["trade_snapshot"].get(t["transaction_id"], {})
        at_trade_snapshot = snapshots.get(info.get("at_trade"))
        if not at_trade_snapshot or not at_trade_snapshot["available"]:
            ungraded_no_data += 1
            continue

        horizon_snapshots = [snapshots[sha] for sha in info.get("horizon_shas", []) if snapshots[sha]["available"]]
        if not horizon_snapshots:
            ungraded_too_recent += 1
            continue

        sides = {}
        for owner_id, side in t["sides"].items():
            hist_value, hist_complete = side_value(side, at_trade_snapshot, crosswalk)
            aged_value, aged_complete = side_aged_value(side, horizon_snapshots, crosswalk)
            sides[owner_id] = {
                "hist_value": hist_value,
                "hist_complete": hist_complete,
                "aged_value": aged_value,
                "aged_complete": aged_complete,
            }

        grades[t["transaction_id"]] = {
            "snapshot_date": at_trade_snapshot["date"][:10],
            "horizon_years": len(horizon_snapshots),
            "horizon_dates": [s["date"][:10] for s in horizon_snapshots],
            "sides": sides,
        }

    (DATA_DIR / "trade_grades.json").write_text(json.dumps(grades, indent=2))
    print(
        f"wrote trade_grades.json ({len(grades)} graded, "
        f"{ungraded_no_data} ungraded -- no DynastyProcess value data (pre-May-2020), "
        f"{ungraded_too_recent} ungraded -- not yet 1 year old)"
    )


if __name__ == "__main__":
    main()
