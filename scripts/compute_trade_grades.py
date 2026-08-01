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
            aged_values, aged_completes = zip(*(side_value(side, s, crosswalk) for s in horizon_snapshots))
            sides[owner_id] = {
                "hist_value": hist_value,
                "hist_complete": hist_complete,
                "aged_value": round(sum(aged_values) / len(aged_values), 1),
                "aged_complete": all(aged_completes),
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
