#!/usr/bin/env python3
"""Compute the full trade ledger (players + picks) from data/history/*.json.

Unlike compute_draft_flow.py (which only tracks pick ownership snapshots),
this reads the raw trade transactions directly so it can show which players
moved in each deal, not just draft capital. See CLAUDE.md for the phantom
team / departed team handling rules this follows.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_DIR = DATA_DIR / "history"
SEASONS = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
PHANTOM_OWNER_ID = "480904402215890944"


def load(path):
    return json.loads(path.read_text())


def main():
    teams = load(DATA_DIR / "teams.json")
    players = load(DATA_DIR / "players.json")
    owner_to_name = {t["owner_id"]: t["team_name"] for t in teams}
    current_owner_ids = set(owner_to_name.keys())

    # departed owners get their most recent historical team name, since
    # they have no current (2026) name to display under
    last_known_name = {}

    trades = []
    for season in SEASONS:
        path = HISTORY_DIR / f"{season}.json"
        if not path.exists():
            continue
        data = load(path)
        roster_owner = {r["roster_id"]: r["owner_id"] for r in data["rosters"]}
        season_name_by_owner = {
            u["user_id"]: (u.get("metadata") or {}).get("team_name") or u["display_name"]
            for u in data["users"]
        }
        for owner_id, name in season_name_by_owner.items():
            last_known_name[owner_id] = name

        for week_str, txs in data.get("transactions_by_week", {}).items():
            week = int(week_str)
            for t in txs:
                if t.get("type") != "trade" or t.get("status") != "complete":
                    continue
                roster_ids = t.get("roster_ids") or []
                owners = [roster_owner.get(rid) for rid in roster_ids]
                owners = [o for o in owners if o and o != PHANTOM_OWNER_ID]
                if len(set(owners)) < 2:
                    continue

                sides = {o: {"players": [], "picks": []} for o in set(owners)}

                adds = t.get("adds") or {}
                for player_id, roster_id in adds.items():
                    owner = roster_owner.get(roster_id)
                    if owner not in sides:
                        continue
                    p = players.get(player_id)
                    sides[owner]["players"].append(
                        {
                            "player_id": player_id,
                            "name": p.get("full_name") if p else f"Player {player_id}",
                            "position": p.get("position") if p else None,
                            "team": p.get("team") if p else None,
                        }
                    )

                for dp in t.get("draft_picks") or []:
                    owner = roster_owner.get(dp["owner_id"])
                    if owner not in sides:
                        continue
                    sides[owner]["picks"].append({"season": dp["season"], "round": dp["round"]})

                trades.append(
                    {
                        "season": season,
                        "week": week,
                        "created": t.get("created"),
                        "transaction_id": t["transaction_id"],
                        "teams": sorted(set(owners)),
                        "sides": sides,
                    }
                )

    trades.sort(key=lambda t: (t["created"] or 0), reverse=True)

    def display_name(owner_id):
        return owner_to_name.get(owner_id) or last_known_name.get(owner_id) or "(departed team)"

    for t in trades:
        t["team_names"] = {o: display_name(o) for o in t["teams"]}

    # pairwise partner breakdown (multi-team trades count toward every pair involved)
    pair_trades = {}
    for t in trades:
        owners = t["teams"]
        for i in range(len(owners)):
            for j in range(i + 1, len(owners)):
                a, b = sorted((owners[i], owners[j]))
                pair_trades.setdefault((a, b), []).append(t)

    partners = []
    for (a, b), pair_list in pair_trades.items():
        partners.append(
            {
                "a": a,
                "b": b,
                "a_name": display_name(a),
                "b_name": display_name(b),
                "count": len(pair_list),
                "both_current": a in current_owner_ids and b in current_owner_ids,
                "trades": pair_list,
            }
        )
    partners.sort(key=lambda p: -p["count"])

    result = {"trades": trades, "partners": partners}
    (DATA_DIR / "trades.json").write_text(json.dumps(result, indent=2))
    print(f"wrote trades.json: {len(trades)} trades, {len(partners)} team pairs")


if __name__ == "__main__":
    main()
