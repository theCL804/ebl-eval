#!/usr/bin/env python3
"""Compute each current team's full transaction ledger (trades, waiver
claims, free agent moves) across all history, for the team page's
"Transactions" drill-down. See CLAUDE.md for the phantom team / departed
team handling rules this follows.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_DIR = DATA_DIR / "history"
SEASONS = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
PHANTOM_OWNER_ID = "480904402215890944"


def load(path):
    return json.loads(path.read_text())


def player_info(players, player_id):
    p = players.get(player_id)
    return {
        "player_id": player_id,
        "name": p.get("full_name") if p else f"Player {player_id}",
        "position": p.get("position") if p else None,
        "team": p.get("team") if p else None,
    }


def main():
    teams = load(DATA_DIR / "teams.json")
    players = load(DATA_DIR / "players.json")
    owner_to_name = {t["owner_id"]: t["team_name"] for t in teams}
    current_owner_ids = set(owner_to_name.keys())

    last_known_name = {}
    ledger = {o: [] for o in current_owner_ids}

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
                if t.get("status") != "complete":
                    continue
                ttype = t.get("type")
                if ttype not in ("trade", "waiver", "free_agent"):
                    continue

                roster_ids = t.get("roster_ids") or []
                owners = [roster_owner.get(rid) for rid in roster_ids]
                owners = [o for o in owners if o and o != PHANTOM_OWNER_ID]
                if not owners:
                    continue

                adds = t.get("adds") or {}
                drops = t.get("drops") or {}

                if ttype == "trade":
                    if len(set(owners)) < 2:
                        continue
                    gained_by = {}
                    lost_by = {}
                    for player_id, roster_id in adds.items():
                        owner = roster_owner.get(roster_id)
                        if owner in owners:
                            gained_by.setdefault(owner, []).append(player_info(players, player_id))
                    for dp in t.get("draft_picks") or []:
                        owner = roster_owner.get(dp["owner_id"])
                        if owner in owners:
                            gained_by.setdefault(owner, []).append(
                                {"pick": True, "season": dp["season"], "round": dp["round"]}
                            )

                    for owner in set(owners):
                        others = [o for o in set(owners) if o != owner]
                        gave = [item for other in others for item in gained_by.get(other, [])]
                        received = gained_by.get(owner, [])
                        if owner not in ledger:
                            continue
                        ledger[owner].append(
                            {
                                "type": "trade",
                                "season": season,
                                "week": week,
                                "created": t.get("created"),
                                "transaction_id": t["transaction_id"],
                                "opponents": [
                                    {"owner_id": o, "name": owner_to_name.get(o) or last_known_name.get(o) or "(departed team)"}
                                    for o in others
                                ],
                                "gave": gave,
                                "received": received,
                            }
                        )
                else:
                    # waiver claim / free agent move: one roster per transaction
                    owner = owners[0]
                    if owner not in ledger:
                        continue
                    gave = [player_info(players, pid) for pid, rid in drops.items() if roster_owner.get(rid) == owner]
                    received = [player_info(players, pid) for pid, rid in adds.items() if roster_owner.get(rid) == owner]
                    ledger[owner].append(
                        {
                            "type": ttype,
                            "season": season,
                            "week": week,
                            "created": t.get("created"),
                            "transaction_id": t["transaction_id"],
                            "opponents": [],
                            "gave": gave,
                            "received": received,
                        }
                    )

    for owner in ledger:
        ledger[owner].sort(key=lambda x: (x["created"] or 0), reverse=True)

    (DATA_DIR / "team_transactions.json").write_text(json.dumps(ledger, indent=2))
    total = sum(len(v) for v in ledger.values())
    print(f"wrote team_transactions.json: {total} transactions across {len(ledger)} teams")


if __name__ == "__main__":
    main()
