#!/usr/bin/env python3
"""Compute historical + future draft pick trade flow from traded_picks data.

Historical trades (2019-2025) are read from each season's own traded_picks
snapshot, since that reflects the final pre-draft state for that draft
class. Future trades (2026-2028) reuse the already-fetched
data/traded_picks.json for the current league.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_DIR = DATA_DIR / "history"
SEASONS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]


def load(path):
    return json.loads(path.read_text())


def main():
    teams = load(DATA_DIR / "teams.json")
    owner_to_name = {t["owner_id"]: t["team_name"] for t in teams}
    current_owner_ids = set(owner_to_name.keys())

    net_capital = {o: {"team_name": owner_to_name[o], "picks_gained": 0, "picks_lost": 0} for o in current_owner_ids}

    historical_trades = []
    for season in SEASONS:
        path = HISTORY_DIR / f"{season}.json"
        if not path.exists():
            continue
        data = load(path)
        roster_owner = {r["roster_id"]: r["owner_id"] for r in data["rosters"]}
        for tp in data["traded_picks"]:
            if int(tp["season"]) > 2025:
                continue  # future-pick trades belong in future_trades, sourced from the current league
            from_owner = roster_owner.get(tp["roster_id"])
            to_owner = roster_owner.get(tp["owner_id"])
            if not from_owner or not to_owner or from_owner == to_owner:
                continue
            historical_trades.append(
                {
                    "season": tp["season"],
                    "round": tp["round"],
                    "from_owner": from_owner,
                    "from_name": owner_to_name.get(from_owner, "(departed team)"),
                    "to_owner": to_owner,
                    "to_name": owner_to_name.get(to_owner, "(departed team)"),
                }
            )
            if to_owner in net_capital:
                net_capital[to_owner]["picks_gained"] += 1
            if from_owner in net_capital:
                net_capital[from_owner]["picks_lost"] += 1

    # dedupe: the same (season, round, from_owner) pick can appear in multiple
    # later season snapshots as it changes hands again; keep only the last
    # (most recent season snapshot) resolution for each pick
    dedup = {}
    for t in historical_trades:
        key = (t["season"], t["round"], t["from_owner"])
        dedup[key] = t  # later seasons in the loop overwrite earlier resolutions
    historical_trades = sorted(dedup.values(), key=lambda t: (-int(t["season"]), t["round"]))

    # recompute net_capital cleanly from deduped trades
    net_capital = {o: {"team_name": owner_to_name[o], "picks_gained": 0, "picks_lost": 0} for o in current_owner_ids}
    for t in historical_trades:
        if t["to_owner"] in net_capital:
            net_capital[t["to_owner"]]["picks_gained"] += 1
        if t["from_owner"] in net_capital:
            net_capital[t["from_owner"]]["picks_lost"] += 1
    for o, v in net_capital.items():
        v["net"] = v["picks_gained"] - v["picks_lost"]

    # future trades (2026-2028), already fetched for the current league
    traded_picks_current = load(DATA_DIR / "traded_picks.json")
    roster_to_owner = {t["roster_id"]: t["owner_id"] for t in teams}
    future_trades = []
    for tp in traded_picks_current:
        from_owner = roster_to_owner.get(tp["roster_id"])
        to_owner = roster_to_owner.get(tp["owner_id"])
        if not from_owner or not to_owner or from_owner == to_owner:
            continue
        future_trades.append(
            {
                "season": tp["season"],
                "round": tp["round"],
                "from_owner": from_owner,
                "from_name": owner_to_name.get(from_owner),
                "to_owner": to_owner,
                "to_name": owner_to_name.get(to_owner),
            }
        )
    future_trades.sort(key=lambda t: (t["season"], t["round"]))

    for t in future_trades:
        if t["to_owner"] in net_capital:
            net_capital[t["to_owner"]]["picks_gained"] += 1
        if t["from_owner"] in net_capital:
            net_capital[t["from_owner"]]["picks_lost"] += 1
    for o, v in net_capital.items():
        v["net"] = v["picks_gained"] - v["picks_lost"]

    result = {
        "historical_trades": historical_trades,
        "future_trades": future_trades,
        "net_capital": net_capital,
    }
    (DATA_DIR / "draft_flow.json").write_text(json.dumps(result, indent=2))
    print(f"wrote draft_flow.json: {len(historical_trades)} historical trades, {len(future_trades)} future trades")


if __name__ == "__main__":
    main()
